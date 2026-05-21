"""
InterX 컬렉터 공통 베이스
모든 사이트 컬렉터가 이 모듈을 import한다.
"""
from __future__ import annotations

import hashlib
import logging
import random
import re
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from interx_engine.application.ports.notice_collector_port import NoticeCollectorPort
from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.collectors")

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_DATE_RE = re.compile(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}")

# ── 예산 추출 패턴 (우선순위 순) ─────────────────────────────────────────────
_BUDGET_PATTERNS = [
    re.compile(r"지원\s*(?:금액|규모)\s*[:：]\s*([0-9,]+)\s*(억|백만|만)?\s*원"),
    re.compile(r"총\s*(?:지원|사업|연구)\s*(?:금액|규모|비)\s*[:：]\s*([0-9,]+)\s*(억|백만|만)?\s*원"),
    re.compile(r"과제당\s*[:：]?\s*([0-9,]+)\s*(억|백만|만)\s*원"),
    re.compile(r"최대\s*([0-9,]+)\s*(억|백만|만)\s*원"),
    re.compile(r"([0-9,]+)\s*(억|백만|만)\s*원\s*(?:이내|내외|규모|지원)"),
    re.compile(r"지원금\s*[:：]\s*([0-9,]+)\s*(억|백만|만)?\s*원"),
]

# ── 구조화 섹션 키워드 ────────────────────────────────────────────────────────
_SECTION_MAP: Dict[str, List[str]] = {
    "사업목적":  ["사업목적", "추진목적", "목적", "추진배경"],
    "지원내용":  ["지원내용", "지원항목", "지원사항", "사업내용", "주요내용"],
    "지원대상":  ["지원대상", "신청자격", "지원 대상", "참여 자격", "모집대상"],
    "지원금액":  ["지원금액", "지원규모", "지원 금액", "지원 규모", "과제 규모", "사업비"],
    "신청방법":  ["신청방법", "접수방법", "신청 방법", "접수절차"],
    "추진일정":  ["추진일정", "사업일정", "추진 일정", "접수기간"],
}

# ── 첨부파일 확장자 ───────────────────────────────────────────────────────────
_FILE_EXT_RE = re.compile(
    r"\.(pdf|hwp|hwpx|docx|doc|xlsx|xls|zip|pptx|ppt|png|jpg|jpeg|gif)$",
    re.I,
)
_DOWNLOAD_KWORDS = re.compile(
    r"(download|fileDown|atchFile|downFile|attFile|fileView|getFile|dwnld|attach)",
    re.I,
)


def _extract_dates(text: str) -> List[str]:
    raw = _DATE_RE.findall(text)
    normalized = []
    for d in raw:
        d2 = re.sub(r"[./]", "-", d)
        parts = d2.split("-")
        if len(parts) == 3:
            y, m, dd = parts
            normalized.append(f"{y}-{m.zfill(2)}-{dd.zfill(2)}")
    return normalized


# ── 접수상태 자동 분류 (P4: bizinfo_datalist.py 대비 보강) ────────────────────────
_APPLY_PERIOD_RE = re.compile(
    r"(?:접수|신청|모집)\s*(?:기간|일정)\s*[:：]?\s*"
    r"(\d{4}[-./]\d{1,2}[-./]\d{1,2})\s*[-~]\s*(\d{4}[-./]\d{1,2}[-./]\d{1,2})"
)


def classify_apply_status(text: str, deadline: str = "") -> str:
    """
    본문/메타에서 접수 기간을 파싱하여 접수상태 분류.
    Returns: "접수중" | "접수예정" | "마감" | ""(판별불가)
    """
    from datetime import date, datetime

    today = date.today()

    # 1) 접수기간 패턴 매칭 (본문에서 시작~종료 날짜 추출)
    m = _APPLY_PERIOD_RE.search(text)
    if m:
        try:
            start_str = re.sub(r"[./]", "-", m.group(1))
            end_str   = re.sub(r"[./]", "-", m.group(2))
            start = datetime.strptime(start_str, "%Y-%m-%d").date()
            end   = datetime.strptime(end_str,   "%Y-%m-%d").date()
            if today < start:
                return "접수예정"
            elif today <= end:
                return "접수중"
            else:
                return "마감"
        except (ValueError, IndexError):
            pass

    # 2) deadline 기반 판별 (접수기간 못 찾았을 때)
    if deadline:
        try:
            dl = re.sub(r"[./]", "-", deadline)
            dl_date = datetime.strptime(dl, "%Y-%m-%d").date()
            if today > dl_date:
                return "마감"
            else:
                return "접수중"  # 마감 전이면 접수중으로 추정
        except (ValueError, IndexError):
            pass

    return ""


def _notice_id(site_key: str, raw: str) -> str:
    return f"{site_key}-{hashlib.md5(raw.encode()).hexdigest()[:8]}"


def _extract_budget_from_text(text: str) -> str:
    """본문 텍스트에서 예산 정보 추출. 실패 시 빈 문자열 반환."""
    for pat in _BUDGET_PATTERNS:
        m = pat.search(text)
        if m:
            amount = m.group(1).replace(",", "")
            unit = m.group(2) if m.lastindex >= 2 and m.group(2) else "원"
            return f"{amount}{unit}"
    return ""


def _extract_attachment_items(soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
    """상세 페이지에서 첨부파일 링크를 추출한다."""
    items: List[Dict[str, str]] = []
    seen: set = set()

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        name = a.get_text(strip=True) or href.split("/")[-1]

        is_file = (
            _FILE_EXT_RE.search(href)
            or _DOWNLOAD_KWORDS.search(href)
            or _FILE_EXT_RE.search(name)
        )
        if not is_file:
            continue

        full_url = href if href.startswith("http") else urljoin(base_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        items.append({"name": name[:200], "url": full_url})

    return items


def _extract_structured_sections(text: str) -> Dict[str, str]:
    """
    본문 텍스트에서 '사업목적', '지원내용' 등 주요 섹션을 추출한다.
    섹션 헤더 → 다음 섹션까지의 텍스트를 최대 300자로 저장.
    """
    structured: Dict[str, str] = {}
    lines = [l.strip() for l in re.split(r"[\n\r]", text) if l.strip()]

    current_section: Optional[str] = None
    current_buf: List[str] = []

    def _flush():
        if current_section and current_buf:
            structured[current_section] = " ".join(current_buf)[:300]

    for line in lines:
        matched = False
        if len(line) <= 25:  # 섹션 헤더는 짧음
            for sec_name, kws in _SECTION_MAP.items():
                if any(kw in line for kw in kws):
                    _flush()
                    current_section = sec_name
                    current_buf = []
                    matched = True
                    break
        if not matched and current_section:
            current_buf.append(line)
            if len(" ".join(current_buf)) > 300:
                _flush()
                current_section = None
                current_buf = []

    _flush()
    return structured


class BaseCollector(NoticeCollectorPort, ABC):
    """
    공통 베이스 — 모든 사이트 수집기가 상속.

    서브클래스 필수 구현:
      site_key : str          사이트 식별자
      LIST_URL : str          {page} 플레이스홀더 포함 목록 URL
      _parse_page(soup, execution_id) -> List[Notice]

    선택 오버라이드:
      ssl_verify   : bool = True
      ministry     : str  = ""
      agency       : str  = ""
      fetch_detail : bool = True   — False이면 상세 페이지 방문 생략
      detail_workers: int = 3      — 상세 페이지 병렬 워커 수
    """

    site_key:       str  = "base"
    LIST_URL:       str  = ""
    ssl_verify:     bool = True
    ministry:       str  = ""
    agency:         str  = ""
    fetch_detail:   bool = True   # 상세 페이지 방문 여부
    detail_workers: int  = 3      # 상세 페이지 병렬 워커 수

    def __init__(self, max_pages: int = 5, timeout: int = 20):
        self.max_pages = max_pages
        self.timeout   = timeout
        self._session  = self._build_session()

    def _build_session(self) -> requests.Session:
        try:
            from interx_engine.infrastructure.config.settings_loader import settings
            _total    = settings.retry_total()
            _backoff  = settings.retry_backoff()
            _statuses = settings.retry_status_codes()
        except Exception:
            _total, _backoff, _statuses = 3, 1.0, [429, 500, 502, 503, 504]

        sess = requests.Session()
        retry = Retry(
            total=_total,
            connect=_total,
            read=_total,
            backoff_factor=_backoff,
            status_forcelist=_statuses,
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=10,
            pool_maxsize=10,
        )
        sess.mount("https://", adapter)
        sess.mount("http://",  adapter)
        if not self.ssl_verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return sess

    def _headers(self, referer: str = "") -> dict:
        h = {
            "User-Agent":                random.choice(_USER_AGENTS),
            "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language":           "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding":           "gzip, deflate, br",
            "Connection":                "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control":             "max-age=0",
            "sec-fetch-dest":            "document",
            "sec-fetch-mode":            "navigate",
            "sec-fetch-site":            "none",
            "sec-fetch-user":            "?1",
        }
        if referer:
            h["Referer"]        = referer
            h["sec-fetch-site"] = "same-origin"
        return h

    def _get(self, url: str, **kwargs) -> Optional[requests.Response]:
        t0 = time.monotonic()
        try:
            resp = self._session.get(
                url,
                headers=self._headers(),
                timeout=self.timeout,
                verify=self.ssl_verify,
                **kwargs,
            )
            elapsed = round(time.monotonic() - t0, 2)
            if resp.status_code == 200:
                log.debug("[%s] GET %s → %d (%.2fs)", self.site_key, url, resp.status_code, elapsed)
            else:
                log.warning("[%s] GET %s → %d (%.2fs)", self.site_key, url, resp.status_code, elapsed)
            resp.raise_for_status()
            return resp
        except requests.exceptions.SSLError as e:
            log.error("[%s] SSL 오류 %s: %s", self.site_key, url, e)
        except requests.exceptions.ConnectionError as e:
            log.error("[%s] 연결 실패 %s: %s", self.site_key, url, e)
        except requests.exceptions.Timeout:
            log.error("[%s] 타임아웃 %s", self.site_key, url)
        except requests.exceptions.HTTPError as e:
            log.warning("[%s] HTTP 오류 %s: %s", self.site_key, url, e)
        except Exception as e:
            log.error("[%s] 요청 실패 %s: %s", self.site_key, url, e)
        return None

    def _page_url(self, page: int) -> str:
        return self.LIST_URL.format(page=page)

    # ── 상세 페이지 파싱 (Generic) ────────────────────────────────────────────

    # 본문 영역 선택자 (우선순위순 — 한국 정부/기관 게시판 공통 패턴)
    _CONTENT_SELECTORS = [
        ".board_view", ".board-view", ".view_content", ".view-content",
        ".board_content", ".boardView", ".board-detail", ".view_area",
        ".bbs_view", ".bbsView", ".bbs-view", ".bbsContent",
        ".detail_content", ".detail-content", ".detailView",
        ".content_view", ".contentView", ".post-content",
        "#board_content", "#boardContent", "#viewContent",
        "article", ".article", "main .content", ".entry-content",
        ".sub_content", ".subContent", "#contents",
    ]
    # 본문에서 제거할 잡음 패턴 (메뉴, 네비, 푸터 텍스트)
    _JUNK_RE = re.compile(
        r"(로그인|회원가입|사이트맵|개인정보.?처리방침|이용약관|저작권|copyright|"
        r"찾아오시는\s*길|주소\s*:|전화번호|팩스|fax|대표전화|"
        r"주메뉴바로가기|본문바로가기|하위메뉴|skip\s*navigation|"
        r"MAIN\s*TOPIC|GNB|LNB|SNB|top|TOP|처음으로|홈\s*>|"
        r"이전\s*글|다음\s*글|목록\s*보기|목록으로|글\s*목록|"
        r"트위터|페이스북|카카오|공유하기|스크랩|인쇄|프린트)",
        re.I,
    )

    def _parse_detail_page(self, soup: BeautifulSoup, detail_url: str) -> Dict[str, Any]:
        """
        범용 상세 페이지 파서 — 본문 영역 정밀 추출.
        1) script/style/nav 등 불필요 태그 제거
        2) 본문 컨테이너 탐색 (board_view, view_content 등)
        3) 컨테이너 내 텍스트만 body_text로 사용 (메뉴/사이드바 오염 방지)
        """
        # ── 1) 불필요한 태그 완전 제거 ──
        for tag in soup(["script", "style", "nav", "header", "footer",
                         "noscript", "iframe", "aside", "form"]):
            tag.decompose()
        for div in soup.find_all("div", class_=re.compile(
                r"\b(gnb|lnb|snb|tnb|nav|menu|sidebar|side-bar|header|footer|"
                r"top-bar|topbar|breadcrumb|page-nav|skip|util|banner)\b", re.I)):
            div.decompose()
        for div in soup.find_all("div", id=re.compile(
                r"\b(gnb|lnb|snb|nav|menu|sidebar|header|footer|topArea|skip)\b", re.I)):
            div.decompose()

        # ── 2) 본문 컨테이너 탐색 (우선순위순) ──
        content_el = None
        for sel in self._CONTENT_SELECTORS:
            content_el = soup.select_one(sel)
            if content_el and len(content_el.get_text(strip=True)) > 50:
                break
            content_el = None

        # 컨테이너를 못 찾으면 가장 긴 텍스트 블록을 가진 div 사용
        if not content_el:
            best_div, best_len = None, 0
            for div in soup.find_all(["div", "td", "section"]):
                t = div.get_text(strip=True)
                if len(t) > best_len and len(t) > 100:
                    best_div, best_len = div, len(t)
            content_el = best_div

        target = content_el if content_el else soup

        # ── 3) 텍스트 추출 + 잡음 제거 ──
        raw_text = target.get_text(" ", strip=True)
        # 줄 단위로 잡음 필터링
        lines = raw_text.split(" ")
        clean_lines = []
        for line in lines:
            line = line.strip()
            if not line or len(line) < 3:
                continue
            if self._JUNK_RE.search(line):
                continue
            clean_lines.append(line)
        text = " ".join(clean_lines)
        text = re.sub(r"\s{2,}", " ", text).strip()

        # ── 4) 전체 페이지에서 예산/첨부 추출 (본문 영역 밖에 있을 수 있음) ──
        full_text = soup.get_text(" ", strip=True)
        budget = _extract_budget_from_text(text) or _extract_budget_from_text(full_text)
        attachment_items = _extract_attachment_items(soup, detail_url)

        # ── 5) 구조화 섹션 추출 ──
        structured = _extract_structured_sections(text)

        # ── 6) 핵심 요약 생성 — 의미 있는 문장만 추출 ──
        summary = self._extract_smart_summary(text, structured)

        return {
            "body_text":        text[:8000],
            "budget":           budget,
            "summary":          summary,
            "structured":       structured,
            "attachment_items": attachment_items,
        }

    @staticmethod
    def _extract_smart_summary(text: str, structured: Dict[str, str]) -> str:
        """
        본문에서 핵심 내용만 추출한 요약 생성.
        우선순위: 구조화 섹션(사업목적/지원내용) > 핵심 키워드 문장 > 첫 유의미 문장
        """
        # 1) 구조화 섹션이 있으면 그걸 요약으로
        for key in ["사업목적", "지원내용", "지원대상"]:
            v = structured.get(key, "")
            if v and len(v) > 20:
                return v[:300]

        # 2) 핵심 키워드 포함 문장 우선 추출
        _IMPORTANT_RE = re.compile(
            r"(지원\s*대상|지원\s*내용|지원\s*규모|지원\s*금액|신청\s*자격|"
            r"접수\s*기간|신청\s*기간|모집\s*기간|사업\s*목적|사업\s*개요|"
            r"사업\s*내용|추진\s*배경|총\s*사업비|과제당|수행\s*기간|"
            r"선정\s*규모|지원\s*분야|참여\s*자격|공모\s*분야)",
        )
        sentences = [s.strip() for s in re.split(r'(?<=[.다요됨함!\n])\s+', text) if len(s.strip()) > 20]
        important = [s for s in sentences if _IMPORTANT_RE.search(s)]
        if important:
            return " ".join(important[:3])[:400]

        # 3) 첫 유의미 문장 (30자 이상)
        for sent in sentences:
            if len(sent) >= 30:
                return sent[:300]

        return text[:300] if text else ""

    def _enrich_notices(self, notices: List[Notice]) -> List[Notice]:
        """
        수집된 공고 목록에 대해 상세 페이지를 방문해 본문·예산·첨부파일을 보강.
        fetch_detail=False 이거나 settings에서 비활성화 시 원본 반환.
        """
        if not notices:
            return notices

        # settings에서 fetch_detail 전역 설정 확인
        try:
            from interx_engine.infrastructure.config.settings_loader import settings
            if not settings.fetch_detail():
                return notices
        except Exception:
            pass

        if not self.fetch_detail:
            return notices

        def _fetch_one(notice: Notice) -> Notice:
            if not notice.detail_url:
                return notice
            # javascript: 및 비-HTTP URL 건너뜀
            if not notice.detail_url.startswith(("http://", "https://")):
                return notice
            try:
                resp = self._get(notice.detail_url)
                if not resp:
                    return notice
                soup = BeautifulSoup(resp.text, "lxml")
                data = self._parse_detail_page(soup, notice.detail_url)

                if data.get("body_text"):
                    notice.body_text = data["body_text"]
                if data.get("budget") and not notice.budget:
                    notice.budget = data["budget"]
                if data.get("summary") and not notice.summary:
                    notice.summary = data["summary"]
                if data.get("structured"):
                    notice.structured.update(data["structured"])
                if data.get("attachment_items"):
                    notice.attachment_items = data["attachment_items"]

                # P4: 접수상태 자동 분류
                source_text = data.get("body_text", "") or notice.body_text or ""
                apply_status = classify_apply_status(source_text, notice.deadline_date)
                if apply_status and hasattr(notice, '__dict__'):
                    notice.__dict__['apply_status'] = apply_status

                time.sleep(random.uniform(0.3, 0.8))
            except Exception as e:
                log.debug("[%s] detail 파싱 실패 %s: %s",
                          self.site_key, notice.detail_url, e)
            return notice

        workers = min(self.detail_workers, len(notices), 5)
        enriched: List[Notice] = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_fetch_one, n): n for n in notices}
            for fut in as_completed(futures):
                try:
                    enriched.append(fut.result())
                except Exception:
                    enriched.append(futures[fut])

        filled = sum(1 for n in enriched if n.body_text)
        log.info("[%s] detail 보강 완료: %d/%d건 body_text 획득",
                 self.site_key.upper(), filled, len(enriched))
        return enriched

    # ── 목록 수집 ─────────────────────────────────────────────────────────────

    def collect(self, execution_id: str) -> List[Notice]:
        notices:  List[Notice] = []
        seen_ids: set          = set()

        for page in range(1, self.max_pages + 1):
            url  = self._page_url(page)
            resp = self._get(url)
            if not resp:
                log.warning("[%s] p%d 응답 없음 → 수집 중단", self.site_key, page)
                break

            soup = BeautifulSoup(resp.text, "lxml")
            try:
                page_notices = self._parse_page(soup, execution_id)
            except Exception as e:
                log.error("[%s] p%d 파싱 오류: %s", self.site_key, page, e)
                break

            if not page_notices:
                log.debug("[%s] p%d 공고 없음 → 마지막 페이지", self.site_key, page)
                break

            new = [n for n in page_notices if n.notice_id not in seen_ids]
            if not new:
                log.debug("[%s] p%d 전체 중복 → 마지막 페이지로 판단", self.site_key, page)
                break

            for n in new:
                seen_ids.add(n.notice_id)
            notices.extend(new)
            log.debug("[%s] p%d: %d건 (신규 %d건)", self.site_key, page, len(page_notices), len(new))

            if page < self.max_pages:
                time.sleep(random.uniform(0.5, 1.2))

        if not notices:
            log.warning("⚠️  [%s] 수집 0건 — URL/HTML구조 확인: %s", self.site_key, self._page_url(1))
        else:
            log.info("[%s] 총 %d건 수집 완료", self.site_key.upper(), len(notices))
            # 상세 페이지 방문해 본문·예산·첨부파일 보강
            notices = self._enrich_notices(notices)

        return notices

    @abstractmethod
    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        ...

    def _make_notice(self, execution_id: str, title: str, detail: str,
                     deadline: str = "", posted: str = "",
                     budget: str = "", ministry: str = "", agency: str = "") -> Notice:
        return Notice(
            execution_id  = execution_id,
            site          = self.site_key,
            notice_id     = _notice_id(self.site_key, detail),
            title         = title.strip(),
            detail_url    = detail,
            notice_link   = detail,
            deadline_date = deadline,
            posted_date   = posted,
            budget        = budget,
            ministry      = ministry or self.ministry,
            agency        = agency   or self.agency,
        )

    def _parse_table(self, soup: BeautifulSoup, execution_id: str,
                     base_url: str, row_sel: str = "table tbody tr") -> List[Notice]:
        notices = []
        for tr in soup.select(row_sel):
            a = tr.find("a", href=True)
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title:
                continue
            href   = a["href"]
            if "javascript" in href.lower():
                continue  # javascript: 링크는 유효한 detail URL 아님
            detail = href if href.startswith("http") else urljoin(base_url, href)
            text   = tr.get_text(" ", strip=True)
            dates  = _extract_dates(text)
            deadline = dates[-1] if dates else ""
            posted   = dates[0]  if len(dates) >= 2 else ""
            notices.append(self._make_notice(execution_id, title, detail, deadline, posted))
        return notices


class PlaywrightBaseCollector(BaseCollector):
    """Playwright headless 브라우저로 JS 렌더링 후 파싱. 미설치 시 requests fallback."""

    def collect(self, execution_id: str) -> List[Notice]:
        try:
            return self._collect_playwright(execution_id)
        except ImportError:
            log.warning("[%s] playwright 미설치 → requests fallback", self.site_key)
            return super().collect(execution_id)
        except Exception as e:
            log.warning("[%s] playwright 실패 (%s) → requests fallback", self.site_key, e)
            return super().collect(execution_id)

    def _collect_playwright(self, execution_id: str) -> List[Notice]:
        from playwright.sync_api import sync_playwright  # type: ignore

        notices:  List[Notice] = []
        seen_ids: set          = set()

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx     = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="ko-KR",
                ignore_https_errors=not self.ssl_verify,
            )
            page = ctx.new_page()

            for pg in range(1, self.max_pages + 1):
                url = self._page_url(pg)
                try:
                    page.goto(url, wait_until="networkidle", timeout=30_000)
                    page.wait_for_timeout(2_000)
                    html  = page.content()
                    soup  = BeautifulSoup(html, "lxml")
                    items = self._parse_page(soup, execution_id)
                except Exception as e:
                    log.error("[%s] playwright p%d 오류: %s", self.site_key, pg, e)
                    break

                if not items:
                    break

                new = [n for n in items if n.notice_id not in seen_ids]
                if not new:
                    break

                for n in new:
                    seen_ids.add(n.notice_id)
                notices.extend(new)
                time.sleep(random.uniform(1.0, 2.0))

            browser.close()

        if not notices:
            log.warning("⚠️  [%s] playwright 수집 0건", self.site_key)
        else:
            log.info("[%s] playwright %d건 수집 완료", self.site_key.upper(), len(notices))
            # 상세 페이지는 requests로 보강 (playwright보다 빠름)
            notices = self._enrich_notices(notices)

        return notices
