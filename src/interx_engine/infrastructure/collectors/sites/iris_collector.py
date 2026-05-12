from __future__ import annotations

import hashlib
import json
import re
from typing import List, Optional
from urllib.parse import urljoin, parse_qs, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

from interx_engine.application.ports.notice_collector_port import NoticeCollectorPort
from interx_engine.core.entities.notice import Notice
from interx_engine.infrastructure.collectors.html_utils import safe_text

import logging
import random
import time
import urllib3

log = logging.getLogger("interx.collectors")

_UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_BASE = "https://www.iris.go.kr"

# 실제 HTML 목록 페이지 후보 (JSON API → HTML 순)
_LIST_CANDIDATES = [
    # 1순위: 실제 목록 HTML 페이지
    _BASE + "/front/pgm/prm/selectPgmPrmList.do?pageIndex={page}",
    _BASE + "/contents/retrieveBsnsAncmList.do?pageIndex={page}&recordCountPerPage=10",
    _BASE + "/main/bsnsAncm/list.do?pageIndex={page}",
    _BASE + "/bsnsAncm/list.do?page={page}",
]

# JSON API 전용 엔드포인트
_JSON_API = _BASE + "/contents/retrieveBsnsAncmList.do"

# 상세 URL 패턴
_DETAIL_PATTERNS = [
    _BASE + "/front/pgm/prm/selectPgmPrmView.do?pgmPrmId={id}",
    _BASE + "/contents/retrieveBsnsAncmDetail.do?bsnsAncmId={id}",
    _BASE + "/bsnsAncm/view.do?ancmId={id}",
]

_DATE_RE = re.compile(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}")
_ID_KEYS = ["pgmPrmId", "bsnsAncmId", "ancmId", "ntisAncmId", "bsnsAncmNo", "ancmNo", "id", "seq", "no"]


def _norm_date(d: str) -> str:
    d2 = re.sub(r"[./]", "-", d)
    parts = d2.split("-")
    if len(parts) == 3:
        y, m, dd = parts
        return f"{y}-{m.zfill(2)}-{dd.zfill(2)}"
    return d


def _extract_dates(text: str) -> List[str]:
    return [_norm_date(d) for d in _DATE_RE.findall(text)]


def _make_notice_id(url: str) -> str:
    try:
        q = parse_qs(urlparse(url).query)
        for key in _ID_KEYS:
            val = (q.get(key) or [""])[0]
            if val:
                return f"iris-{val}"[:80]
    except Exception:
        pass
    return "iris-" + hashlib.md5(url.encode()).hexdigest()[:10]


class IrisCollector(NoticeCollectorPort):
    """
    IRIS (국가과학기술지식정보서비스) 공고 수집기.
    JSON API 우선 시도 → HTML 파싱 fallback.
    """

    def __init__(self, max_pages: int = 3, timeout: int = 30):
        self.max_pages = max_pages
        self.timeout = timeout
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        sess = requests.Session()
        retry = Retry(
            total=3, connect=3, read=3, backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"], raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        sess.mount("https://", adapter)
        sess.mount("http://", adapter)
        return sess

    def _headers(self, referer: str = "") -> dict:
        h = {
            "User-Agent": random.choice(_UA),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        if referer:
            h["Referer"] = referer
        return h

    def collect(self, execution_id: str) -> List[Notice]:
        # 1단계: JSON API 시도
        notices = self._collect_json_api(execution_id)
        if notices:
            log.info("[IRIS] JSON API: %d건 수집", len(notices))
            return notices

        # 2단계: HTML 파싱 fallback
        notices = self._collect_html(execution_id)
        if notices:
            log.info("[IRIS] HTML: %d건 수집", len(notices))
            return notices

        log.warning("⚠️  [iris] 수집 0건 — URL/구조 변경 확인 필요")
        return []

    # ── JSON API ────────────────────────────────────────────────────────────────

    def _collect_json_api(self, execution_id: str) -> List[Notice]:
        notices: List[Notice] = []
        seen: set = set()

        for page in range(1, self.max_pages + 1):
            items = self._fetch_json_page(page)
            if not items:
                break

            for item in items:
                notice = self._item_to_notice(item, execution_id)
                if notice and notice.notice_id not in seen:
                    seen.add(notice.notice_id)
                    notices.append(notice)

            time.sleep(random.uniform(0.5, 1.0))

        return notices

    def _fetch_json_page(self, page: int) -> List[dict]:
        """JSON API 엔드포인트 호출 — GET/POST 모두 시도."""
        params = {"pageIndex": page, "recordCountPerPage": 10, "currentPageNo": page}

        for method in ("GET", "POST"):
            try:
                if method == "GET":
                    resp = self.session.get(
                        _JSON_API,
                        params=params,
                        headers={**self._headers(), "Accept": "application/json, text/javascript, */*"},
                        timeout=self.timeout,
                    )
                else:
                    resp = self.session.post(
                        _JSON_API,
                        data=params,
                        headers={**self._headers(), "Accept": "application/json, text/javascript, */*",
                                 "Content-Type": "application/x-www-form-urlencoded"},
                        timeout=self.timeout,
                    )

                if resp.status_code != 200:
                    continue

                ct = resp.headers.get("Content-Type", "")
                text = resp.text.strip()

                # JSON 응답이면 파싱
                if "json" in ct or text.startswith("{") or text.startswith("["):
                    data = resp.json()
                    return self._extract_items_from_json(data)

            except Exception as e:
                log.debug("[iris] JSON API %s p%d 오류: %s", method, page, e)

        return []

    def _extract_items_from_json(self, data) -> List[dict]:
        """여러 JSON 키 패턴으로 목록 추출."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("listBsnsAncm", "resultList", "list", "data", "items", "content",
                        "bsnsAncmList", "pgmPrmList", "ancmList", "rows"):
                val = data.get(key)
                if isinstance(val, list) and val:
                    return val
            # 중첩 dict 탐색
            for v in data.values():
                if isinstance(v, list) and v:
                    return v
        return []

    def _item_to_notice(self, item: dict, execution_id: str) -> Optional[Notice]:
        """JSON 항목 → Notice 변환."""
        if not isinstance(item, dict):
            return None

        # 접수 완료 공고 제외
        if item.get("rcveStt") == "완료":
            return None

        # 제목 필드 탐색 (IRIS 실제 API: ancmTl)
        title = ""
        for k in ("ancmTl", "bsnsAncmTl", "bsnsAncmTitle", "pgmPrmNm", "ancmTitle",
                  "title", "subject", "notiTitle"):
            if item.get(k):
                title = str(item[k]).strip()
                break
        if not title:
            return None

        # ID 탐색 (IRIS 실제 API: bsnsAncmSn)
        notice_id_raw = ""
        for k in ("bsnsAncmSn", "bsnsAncmId", "pgmPrmId", "ancmId", "id", "seq", "no"):
            if item.get(k):
                notice_id_raw = str(item[k])
                break

        # 상세 URL 구성 (bsnsAncmSn + ancmId 조합 우선)
        detail_url = ""
        sn   = str(item.get("bsnsAncmSn") or "").strip()
        acid = str(item.get("ancmId") or "").strip()
        if sn:
            detail_url = _BASE + f"/contents/retrieveBsnsAncmDtl.do?bsnsAncmSn={sn}&ancmId={acid}"
        if not detail_url:
            for k in ("detailUrl", "ancmUrl", "linkUrl", "url"):
                if item.get(k):
                    u = str(item[k])
                    detail_url = u if u.startswith("http") else urljoin(_BASE, u)
                    break
        if not detail_url and notice_id_raw:
            detail_url = _BASE + f"/contents/retrieveBsnsAncmDetail.do?bsnsAncmId={notice_id_raw}"
        if not detail_url:
            return None

        notice_id = f"iris-{notice_id_raw}" if notice_id_raw else _make_notice_id(detail_url)

        # 날짜 탐색 (IRIS 실제 API: rcveStrDtMain, rcveEndDtMain)
        posted = ""
        for k in ("rcveStrDtMain", "regDt", "regDate", "postedDate", "wrtDt", "creatDt"):
            if item.get(k):
                posted = str(item[k])[:10]
                break

        deadline = ""
        for k in ("rcveEndDtMain", "rcveEndDt", "ancmEndDt", "deadlineDt", "endDt",
                  "closeDate", "rcptEndDt"):
            if item.get(k):
                deadline = str(item[k])[:10]
                break

        ministry = str(item.get("mnofNm", item.get("ministry", ""))).strip()
        agency = str(item.get("insttNm", item.get("agency", "IRIS"))).strip() or "IRIS"
        budget = str(item.get("budget", item.get("sptAmt", ""))).strip()

        return Notice(
            execution_id=execution_id,
            site="iris",
            notice_id=notice_id[:80],
            title=title,
            detail_url=detail_url,
            notice_link=detail_url,
            posted_date=posted,
            deadline_date=deadline,
            ministry=ministry,
            agency=agency,
            business_type="R&D",
            budget=budget,
            summary="",
            recommended_solution="",
            recommended_action="검토",
            l3_strong="N",
            partner_candidate="N",
            attachments=[],
            attachment_items=[],
        )

    # ── HTML fallback ────────────────────────────────────────────────────────────

    def _collect_html(self, execution_id: str) -> List[Notice]:
        notices: List[Notice] = []
        seen: set = set()

        for page in range(1, self.max_pages + 1):
            html = self._fetch_html_page(page)
            if not html:
                continue

            items = self._parse_html_list(html)
            if not items:
                continue

            for item in items:
                detail_url = item["detail_url"]
                if detail_url in seen:
                    continue
                seen.add(detail_url)

                title = item.get("title") or "IRIS 공고"
                text = item.get("row_text", "")
                dates = _extract_dates(text)
                deadline = dates[-1] if dates else ""
                posted = dates[0] if len(dates) >= 2 else ""

                notices.append(Notice(
                    execution_id=execution_id,
                    site="iris",
                    notice_id=_make_notice_id(detail_url),
                    title=title,
                    detail_url=detail_url,
                    notice_link=detail_url,
                    posted_date=posted,
                    deadline_date=deadline,
                    ministry="",
                    agency="IRIS",
                    business_type="R&D",
                    budget="",
                    summary="",
                    recommended_solution="",
                    recommended_action="검토",
                    l3_strong="N",
                    partner_candidate="N",
                    attachments=[],
                    attachment_items=[],
                ))

            time.sleep(random.uniform(0.5, 1.0))

        return notices

    def _fetch_html_page(self, page: int) -> str:
        for fmt in _LIST_CANDIDATES:
            url = fmt.format(page=page)
            try:
                resp = self.session.get(url, headers=self._headers(_BASE), timeout=self.timeout)
                if resp.status_code == 200:
                    ct = resp.headers.get("Content-Type", "")
                    if "html" in ct or "<html" in resp.text[:200].lower():
                        return resp.text
            except Exception as e:
                log.debug("[iris] HTML fetch %s p%d: %s", url, page, e)
        return ""

    def _parse_html_list(self, html: str) -> List[dict]:
        soup = BeautifulSoup(html, "lxml")
        items: List[dict] = []
        seen = set()

        # 내비게이션/메뉴성 텍스트 — 공고 목록에서 제외
        _NAV_TITLES = {
            "사업소개", "추진경과 및 내용", "기대효과", "시스템 구성", "bi 소개",
            "추진체계", "참여부처 및 기관", "사업사전안내", "공모예고(사업일정)",
            "사업공지", "카드뉴스", "iris 사용 매뉴얼", "고객센터 안내",
            "r&d 통계", "연구비통합관리시스템", "서비스 바로가기",
            "iris-기관 간 협약변경 연계", "전산업무 요청", "온라인 매뉴얼",
            "공지사항", "자료실", "faq", "메인으로", "로그인", "회원가입",
        }

        def _is_nav_title(txt: str) -> bool:
            return txt.lower().strip() in _NAV_TITLES

        def _has_id_param(url: str) -> bool:
            """URL 쿼리에 ID 역할 파라미터가 있는지 확인."""
            try:
                q = parse_qs(urlparse(url).query)
                for key in _ID_KEYS:
                    if q.get(key):
                        return True
            except Exception:
                pass
            return False

        def _add(url: str, title: str, row_text: str = "", require_id: bool = False):
            if not url or not title:
                return
            full = url if url.startswith("http") else urljoin(_BASE, url)
            if "iris.go.kr" not in full:
                return
            if full in seen:
                return
            t = safe_text(title)
            if len(t) < 8:
                return
            if _is_nav_title(t):
                return
            if require_id and not _has_id_param(full):
                return
            seen.add(full)
            items.append({"title": t, "detail_url": full, "row_text": row_text})

        # 1) table tbody tr 탐색 — ID 파라미터 필수
        for tr in soup.select("table tbody tr"):
            a = tr.find("a", href=True)
            if not a:
                continue
            href = (a.get("href") or "").strip()
            title = safe_text(a.get_text())
            if href and not href.startswith("javascript"):
                _add(href, title, tr.get_text(" ", strip=True), require_id=True)

        # 2) href 키워드 기반 탐색 — ID 파라미터 필수
        if not items:
            for a in soup.select("a[href]"):
                href = (a.get("href") or "").strip()
                txt = safe_text(a.get_text(" ", strip=True))
                if any(k in href.lower() for k in ["view", "detail", "ancm", "notice", "bbs", "prm", "prmId"]):
                    _add(href, txt, require_id=True)

        # 3) onclick 기반 탐색 — ID 파라미터 필수
        if not items:
            for node in soup.select("[onclick]"):
                oc = node.get("onclick", "") or ""
                txt = safe_text(node.get_text(" ", strip=True))
                for m in re.findall(r"['\"](/[^'\"]*(?:view|detail|ancm|notice|bbs)[^'\"]*)['\"]", oc, re.I):
                    _add(m, txt, require_id=True)

        return items[:100]
