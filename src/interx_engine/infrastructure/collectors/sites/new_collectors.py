"""
InterX 신규 사이트 수집기
  nrf    한국연구재단       https://www.nrf.re.kr
  kised  창업진흥원         https://www.k-startup.go.kr
  ketep  에너지기술평가원   https://www.ketep.re.kr
  koiia  산업지능화협회     https://www.koiia.or.kr
"""
from __future__ import annotations

import logging
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector,
    PlaywrightBaseCollector,
    _extract_dates,
    _notice_id,
)
from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.collectors")


# ── 공통 테이블 파서 헬퍼 ─────────────────────────────────────────────────────
def _parse_tbody(soup: BeautifulSoup, execution_id: str,
                 site_key: str, base_url: str,
                 ministry: str, agency: str) -> List[Notice]:
    notices = []
    tbody = soup.find("tbody")
    rows  = tbody.find_all("tr") if tbody else soup.select("table tr")

    for tr in rows:
        a = tr.find("a", href=True)
        if not a:
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 3:
            continue
        href   = a["href"]
        detail = href if href.startswith("http") else urljoin(base_url, href)
        text   = tr.get_text(" ", strip=True)
        dates  = _extract_dates(text)
        notices.append(Notice(
            execution_id  = execution_id,
            site          = site_key,
            notice_id     = _notice_id(site_key, detail),
            title         = title,
            detail_url    = detail,
            notice_link   = detail,
            deadline_date = dates[-1] if dates else "",
            posted_date   = dates[0]  if len(dates) >= 2 else "",
            ministry      = ministry,
            agency        = agency,
        ))
    return notices


# =============================================================================
# 한국연구재단 (NRF)
# =============================================================================
class NrfCollector(BaseCollector):
    site_key = "nrf"
    ministry = "과학기술정보통신부"
    agency   = "한국연구재단"
    LIST_URL = "https://www.nrf.re.kr/biz/notice/list?menu_no=378&page={page}"

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        return _parse_tbody(soup, execution_id, self.site_key,
                            "https://www.nrf.re.kr", self.ministry, self.agency)


# =============================================================================
# 창업진흥원 (KISED) → k-startup.go.kr 로 이전 (2024~)
# =============================================================================
import re as _re
_GOVIEW_RE = _re.compile(r"go_view\((\d+)\)", _re.I)

class KisedCollector(BaseCollector):
    site_key = "kised"
    ministry = "중소벤처기업부"
    agency   = "창업진흥원"
    LIST_URL = (
        "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"
        "?schM=list&page={page}"
    )
    _BASE    = "https://www.k-startup.go.kr"
    _DETAIL  = _BASE + "/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={uid}"

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices = []
        for item in soup.select("li.notice"):
            a = item.find("a", href=lambda h: h and "go_view" in str(h))
            if not a:
                continue
            m = _GOVIEW_RE.search(a.get("href", ""))
            if not m:
                continue
            detail = self._DETAIL.format(uid=m.group(1))

            # title: ann_tit, ann_title, p.tit 등 시도 → 없으면 a 전체 텍스트
            title_tag = (a.select_one(".ann_tit, .tit, p.subject, .ann_title, p")
                         or a)
            title = title_tag.get_text(" ", strip=True)
            # 공통 오염 문구 제거 (카테고리 배지, D-숫자 등)
            import re as _re2
            title = _re2.sub(r"D-\d+", "", title).strip()
            for badge in item.select(".flag"):
                title = title.replace(badge.get_text(strip=True), "").strip()
            if not title or len(title) < 3:
                continue

            text  = item.get_text(" ", strip=True)
            dates = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0]  if len(dates) >= 2 else "",
            ))
        return notices


# =============================================================================
# 한국에너지기술평가원 (KETEP)  → requests (2025~ URL 변경)
# 구 URL: /biz/rnd/announce/list.do (400 Bad Request)
# 신 URL: /businessAcment?menuId=MENU002080200000000&pageNum={page}
# =============================================================================
import re as _re_ketep

_KETEP_BASE       = "https://www.ketep.re.kr"
_KETEP_MENU_ID    = "MENU002080200000000"
_KETEP_LIST_URL   = (
    _KETEP_BASE
    + "/businessAcment?menuId=" + _KETEP_MENU_ID
    + "&pageNum={page}&rowCnt=10&subj_dmsy_tc=&status=진행"
)
_KETEP_DETAIL_URL = (
    _KETEP_BASE
    + "/businessAcment/view?menuId=" + _KETEP_MENU_ID
    + "&uni_ancm_id={uid}"
)
_KETEP_ID_RE = _re_ketep.compile(r"uni_ancm_id=([A-Za-z0-9]+)")


class KetepCollector(BaseCollector):
    """
    KETEP 사업공고 수집기.
    2025년 이후 URL이 /businessAcment 로 변경됨.
    진행 중인 공고만 수집 (status=진행).
    """
    site_key = "ketep"
    ministry = "산업통상자원부"
    agency   = "한국에너지기술평가원"
    LIST_URL = _KETEP_LIST_URL

    def _page_url(self, page: int) -> str:
        return self.LIST_URL.replace("{page}", str(page))

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices = []
        seen: set = set()

        # 1) table tbody tr 기반 파싱
        for tr in soup.select("table tbody tr, tbody tr"):
            tds = tr.find_all(["td", "th"])
            if len(tds) < 2:
                continue
            # 제목+링크 td 탐색
            a = None
            for td in tds:
                candidate = td.find("a", href=True)
                if candidate:
                    txt = candidate.get_text(strip=True)
                    if len(txt) >= 3:
                        a = candidate
                        break
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            href = (a.get("href") or "").strip()
            # uni_ancm_id 추출
            m = _KETEP_ID_RE.search(href)
            if m:
                uid = m.group(1)
                detail = _KETEP_DETAIL_URL.format(uid=uid)
            elif href and not href.lower().startswith("javascript"):
                detail = href if href.startswith("http") else urljoin(_KETEP_BASE, href)
            else:
                continue

            if detail in seen:
                continue
            seen.add(detail)

            row_text = tr.get_text(" ", strip=True)
            dates    = _extract_dates(row_text)
            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0]  if len(dates) >= 2 else "",
            ))

        # 2) 링크 직접 탐색 fallback (React/SPA 렌더 결과에서 href만 있는 경우)
        if not notices:
            for a in soup.select("a[href*='uni_ancm_id'], a[href*='businessAcment/view']"):
                title = a.get_text(strip=True)
                if not title or len(title) < 3:
                    continue
                href = (a.get("href") or "").strip()
                m = _KETEP_ID_RE.search(href)
                if m:
                    detail = _KETEP_DETAIL_URL.format(uid=m.group(1))
                else:
                    detail = href if href.startswith("http") else urljoin(_KETEP_BASE, href)
                if detail in seen:
                    continue
                seen.add(detail)
                row  = a.find_parent("tr") or a.find_parent("li") or a.parent
                text = row.get_text(" ", strip=True) if row else title
                dates = _extract_dates(text)
                notices.append(self._make_notice(
                    execution_id, title, detail,
                    dates[-1] if dates else "",
                    dates[0]  if len(dates) >= 2 else "",
                ))

        return notices


# =============================================================================
# 한국산업지능화협회 (KOIIA)
# =============================================================================
import urllib3 as _urllib3

class KoiiaCollector(BaseCollector):
    site_key   = "koiia"
    ministry   = "산업통상자원부"
    agency     = "한국산업지능화협회"
    ssl_verify = False
    LIST_URL   = "https://www.koiia.or.kr/board/list.do?boardId=notice&pageIndex={page}"

    _JSON_API   = "https://www.koiia.or.kr/api/v1/board"
    _DETAIL_TPL = "https://www.koiia.or.kr/board/read.php?M2_IDX=21992&B_IDX={pk}"
    _AUTH       = "Basic 3g9nq9xeiihd1qpqb8ee34hkitsuepb9"

    def collect(self, execution_id: str) -> List[Notice]:
        """JSON REST API 우선, 실패 시 HTML fallback."""
        import time
        import random

        _urllib3.disable_warnings(_urllib3.exceptions.InsecureRequestWarning)

        notices: List[Notice] = []
        seen: set = set()

        for page in range(1, self.max_pages + 1):
            try:
                resp = self._session.get(
                    self._JSON_API,
                    params={"menu2_id": 21992, "page": page, "pa": 4},
                    headers={
                        **self._headers(),
                        "Authorization": self._AUTH,
                        "Accept": "application/json, text/plain, */*",
                    },
                    timeout=self.timeout,
                    verify=False,
                )
                if resp.status_code != 200:
                    log.warning("[koiia] JSON API p%d → HTTP %d", page, resp.status_code)
                    break

                data = resp.json()
                items = (
                    data if isinstance(data, list)
                    else (
                        data.get("data") or data.get("list") or data.get("results")
                        or data.get("rows") or data.get("items") or data.get("content")
                        or data.get("board") or data.get("notice") or []
                    )
                )
                # 여전히 없으면 dict 값 중 list인 것 탐색
                if not items and isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, list) and v:
                            items = v
                            break
                if not items:
                    log.warning("[koiia] p%d 공고 없음 → 마지막 페이지", page)
                    break

                for item in items:
                    pk    = str(item.get("pk") or item.get("id") or "").strip()
                    title = (item.get("title") or "").strip()
                    if not pk or not title:
                        continue
                    detail = self._DETAIL_TPL.format(pk=pk)
                    if detail in seen:
                        continue
                    seen.add(detail)
                    posted   = str(item.get("date") or item.get("date2") or "")[:10]
                    deadline = str(item.get("due_date") or item.get("end_date") or "")[:10]
                    notices.append(self._make_notice(
                        execution_id, title, detail, deadline, posted,
                    ))

                time.sleep(random.uniform(0.3, 0.7))

            except Exception as e:
                log.warning("[koiia] JSON API 오류 p%d: %s", page, e)
                break

        if notices:
            log.info("[KOIIA] JSON API %d건 수집", len(notices))
            return self._enrich_notices(notices)

        # JSON API 실패 → HTML fallback
        log.warning("[koiia] JSON API 0건 → HTML fallback")
        return super().collect(execution_id)

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        BASE = "https://www.koiia.or.kr"
        notices = _parse_tbody(soup, execution_id, self.site_key, BASE, self.ministry, self.agency)
        if not notices:
            # div/ul 기반 레이아웃 시도
            for a in soup.select("ul.board-list li a, .board_list a, .list_wrap a, article a"):
                title = a.get_text(strip=True)
                if not title or len(title) < 3:
                    continue
                href = a.get("href", "")
                if not href or "javascript" in href.lower():
                    continue
                detail = href if href.startswith("http") else urljoin(BASE, href)
                row  = a.find_parent("li") or a.find_parent("div") or a.parent
                text = row.get_text(" ", strip=True) if row else title
                dates = _extract_dates(text)
                notices.append(Notice(
                    execution_id  = execution_id,
                    site          = self.site_key,
                    notice_id     = _notice_id(self.site_key, detail),
                    title         = title,
                    detail_url    = detail,
                    notice_link   = detail,
                    deadline_date = dates[-1] if dates else "",
                    posted_date   = dates[0]  if len(dates) >= 2 else "",
                    ministry      = self.ministry,
                    agency        = self.agency,
                ))
        return notices


# =============================================================================
# 레지스트리
# =============================================================================
from interx_engine.infrastructure.collectors.sites.jejutp_collector import JejtpCollector

NEW_COLLECTOR_CLASSES: dict = {
    "nrf":    NrfCollector,
    "kised":  KisedCollector,
    "ketep":  KetepCollector,
    "koiia":  KoiiaCollector,
    "jejutp": JejtpCollector,
}
