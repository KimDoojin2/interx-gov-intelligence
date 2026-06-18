"""
BizinfoCollector  —  기업마당 (bizinfo.go.kr)
Playwright 렌더링 → 복수 파싱 전략 (table / card / 링크 fallback)
"""
from __future__ import annotations

import hashlib
import re
from typing import List, Optional
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from interx_engine.infrastructure.collectors.sites.base_collector import (
    PlaywrightBaseCollector, _extract_dates,
)
from interx_engine.core.entities.notice import Notice

_BASE    = "https://www.bizinfo.go.kr"
_LIST    = _BASE + "/web/lay1/bbs/S1T122C128/AS/74/list.do?pageIndex={page}"
_DATE_RE = re.compile(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}")

# 상세 URL 판단 패턴
_DETAIL_RE = re.compile(r"/web/.*?/view\.do", re.I)


def _normalize_date(d: str) -> str:
    d2 = re.sub(r"[./]", "-", d)
    parts = d2.split("-")
    if len(parts) == 3:
        y, m, dd = parts
        return f"{y}-{m.zfill(2)}-{dd.zfill(2)}"
    return d


def _make_notice_id(detail_url: str) -> str:
    try:
        q = parse_qs(urlparse(detail_url).query)
        pid = (q.get("pblancId") or [""])[0]
        if pid:
            return f"bizinfo-{pid}"
    except Exception:
        pass
    return "bizinfo-" + hashlib.md5(detail_url.encode()).hexdigest()[:8]


def _parse_dates_from_period(period_text: str):
    """'YYYY-MM-DD ~ YYYY-MM-DD' 형태에서 시작·마감 날짜 추출."""
    dates = [_normalize_date(d) for d in _DATE_RE.findall(period_text)]
    start   = dates[0]  if dates else ""
    end     = dates[-1] if dates else ""
    return start, end


class BizinfoCollector(PlaywrightBaseCollector):
    site_key = "bizinfo"
    ministry = ""
    agency   = "기업마당"
    LIST_URL = _LIST

    def collect(self, execution_id: str) -> List[Notice]:
        import logging, time as _t, random as _r
        log = logging.getLogger("interx.collectors")
        # 홈페이지 쿠키 선취득 → ConnectionReset 방지
        try:
            _t.sleep(_r.uniform(1.0, 2.0))
            self._session.get(
                _BASE,
                headers=self._headers(),
                timeout=self.timeout,
                verify=self.ssl_verify,
                allow_redirects=True,
            )
            _t.sleep(_r.uniform(0.5, 1.0))
        except Exception:
            pass

        # Playwright 우선 시도
        try:
            notices = self._collect_playwright(execution_id)
            if notices:
                return notices
        except Exception as e:
            log.warning("[bizinfo] playwright 실패 (%s) → requests fallback", e)

        # requests + html.parser fallback (lxml은 bizinfo href 공백 처리 못함)
        return self._collect_requests_fallback(execution_id)

    def _collect_requests_fallback(self, execution_id: str) -> List[Notice]:
        import logging, time as _t, random as _r
        log = logging.getLogger("interx.collectors")
        notices:  List[Notice] = []
        seen_ids: set          = set()

        for page in range(1, self.max_pages + 1):
            url = self._page_url(page)
            resp = self._get(url)
            if not resp:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            items = self._parse_page(soup, execution_id)
            if not items:
                break

            new = [n for n in items if n.notice_id not in seen_ids]
            if not new:
                break
            for n in new:
                seen_ids.add(n.notice_id)
            notices.extend(new)
            _t.sleep(_r.uniform(1.0, 2.0))

        if notices:
            log.info("[BIZINFO] requests fallback %d건 수집", len(notices))
            notices = self._enrich_notices(notices)
        else:
            log.warning("[bizinfo] requests fallback도 0건")
        return notices

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        # 1순위: 표준 table 파싱 (컬럼 개수 유연하게)
        notices = self._parse_table_flexible(soup, execution_id)
        if notices:
            return notices

        # 2순위: card / list 형태 div 파싱
        notices = self._parse_card_layout(soup, execution_id)
        if notices:
            return notices

        # 3순위: 상세 URL 패턴 링크 직접 수집
        return self._parse_detail_links(soup, execution_id)

    # ── 1) table 파싱 (컬럼 수 유동) ────────────────────────────────────────

    def _parse_table_flexible(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices = []

        for tr in soup.select("table tbody tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue

            # 제목 링크 탐색 — 모든 td에서 가장 긴 텍스트를 가진 링크 사용
            best_a: Optional[object] = None
            best_len = 0
            for td in tds:
                a = td.find("a")
                if not a:
                    continue
                txt_len = len(a.get_text(strip=True))
                if txt_len > best_len:
                    best_len = txt_len
                    best_a = a

            if not best_a or best_len < 3:
                continue

            href = (best_a.get("href") or "").strip()

            # javascript: href 처리
            if "javascript" in href.lower():
                # onclick 에서 URL 추출 시도
                onclick = (best_a.get("onclick") or tr.get("onclick") or "").strip()
                href = self._extract_href_from_onclick(onclick, tr)
                if not href:
                    continue

            if not href:
                continue

            # href="#" 또는 빈 앵커 처리
            if href == "#" or href.startswith("#"):
                # data 속성에서 URL 구성
                pid = tr.get("data-id") or tr.get("data-pblancid") or ""
                if pid:
                    href = f"/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pid}"
                else:
                    continue

            title  = best_a.get_text(strip=True)
            detail = href if href.startswith("http") else urljoin(_BASE, href)

            # 날짜/기관 정보 — td 순서를 유동적으로 처리
            row_text = tr.get_text(" ", strip=True)
            dates_all = [_normalize_date(d) for d in _DATE_RE.findall(row_text)]

            # 접수기간 td 탐색 (~ 구분자가 있는 td)
            period_start, period_end = "", ""
            ministry_str, agency_str, posted_str = "", "기업마당", ""

            for i, td in enumerate(tds):
                cell = td.get_text(" ", strip=True)
                if "~" in cell and _DATE_RE.search(cell):
                    period_start, period_end = _parse_dates_from_period(cell)
                elif re.match(r"^\d{4}[-./]\d{1,2}[-./]\d{1,2}$", cell.strip()):
                    posted_str = _normalize_date(cell.strip())

            # 기관/지역 — td[4] / td[5] 또는 td[-3] / td[-2] 등 유동
            if len(tds) >= 7:
                ministry_str = tds[4].get_text(strip=True)
                agency_str   = tds[5].get_text(strip=True) or "기업마당"
                posted_str   = posted_str or _normalize_date(
                    _DATE_RE.search(tds[6].get_text(strip=True)).group()
                    if _DATE_RE.search(tds[6].get_text(strip=True)) else ""
                )
            elif len(tds) >= 5:
                ministry_str = tds[-2].get_text(strip=True)
                agency_str   = tds[-1].get_text(strip=True) or "기업마당"

            posted   = posted_str   or (dates_all[0]  if dates_all else "")
            deadline = period_end   or (dates_all[-1] if dates_all else "")

            notices.append(Notice(
                execution_id         = execution_id,
                site                 = "bizinfo",
                notice_id            = _make_notice_id(detail),
                title                = title,
                detail_url           = detail,
                notice_link          = detail,
                posted_date          = posted,
                deadline_date        = deadline,
                ministry             = ministry_str,
                agency               = agency_str,
                business_type        = "정보지원사업",
                budget               = "",
                summary              = "",
                recommended_solution = "",
                recommended_action   = "검토",
                l3_strong            = "N",
                partner_candidate    = "N",
                attachments          = [],
                attachment_items     = [],
            ))

        return notices

    # ── 2) card/div 레이아웃 ─────────────────────────────────────────────────

    def _parse_card_layout(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices = []
        seen: set = set()

        # bizinfo는 .bbs_list, .list_wrap, .notice_list 등을 사용할 수 있음
        containers = soup.select(".bbs_list li, .list_wrap li, .board_list li, ul.list li")
        for li in containers:
            a = li.find("a", href=True)
            if not a:
                continue
            href  = (a.get("href") or "").strip()
            title = a.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            if not href or "javascript" in href.lower():
                continue

            full = href if href.startswith("http") else urljoin(_BASE, href)
            if full in seen:
                continue
            seen.add(full)

            text  = li.get_text(" ", strip=True)
            dates = [_normalize_date(d) for d in _DATE_RE.findall(text)]

            notices.append(Notice(
                execution_id         = execution_id,
                site                 = "bizinfo",
                notice_id            = _make_notice_id(full),
                title                = title,
                detail_url           = full,
                notice_link          = full,
                posted_date          = dates[0]  if dates else "",
                deadline_date        = dates[-1] if dates else "",
                ministry             = "",
                agency               = "기업마당",
                business_type        = "정보지원사업",
                budget               = "",
                summary              = "",
                recommended_solution = "",
                recommended_action   = "검토",
                l3_strong            = "N",
                partner_candidate    = "N",
                attachments          = [],
                attachment_items     = [],
            ))

        return notices

    # ── 3) 상세 URL 패턴 링크 직접 탐색 ─────────────────────────────────────

    def _parse_detail_links(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices = []
        seen: set = set()

        for a in soup.find_all("a", href=True):
            href  = (a.get("href") or "").strip()
            title = a.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            if not href or "javascript" in href.lower():
                continue
            # bizinfo 상세 URL 패턴 확인
            if not (_DETAIL_RE.search(href) or "pblancId" in href):
                continue

            full = href if href.startswith("http") else urljoin(_BASE, href)
            if full in seen:
                continue
            seen.add(full)

            parent = a.find_parent(["tr", "li", "div"])
            text   = parent.get_text(" ", strip=True) if parent else title
            dates  = [_normalize_date(d) for d in _DATE_RE.findall(text)]

            notices.append(Notice(
                execution_id         = execution_id,
                site                 = "bizinfo",
                notice_id            = _make_notice_id(full),
                title                = title,
                detail_url           = full,
                notice_link          = full,
                posted_date          = dates[0]  if dates else "",
                deadline_date        = dates[-1] if dates else "",
                ministry             = "",
                agency               = "기업마당",
                business_type        = "정보지원사업",
                budget               = "",
                summary              = "",
                recommended_solution = "",
                recommended_action   = "검토",
                l3_strong            = "N",
                partner_candidate    = "N",
                attachments          = [],
                attachment_items     = [],
            ))

        return notices

    # ── 유틸 ──────────────────────────────────────────────────────────────────

    def _extract_href_from_onclick(self, onclick: str, tr) -> str:
        """onclick / data 속성에서 URL 구성."""
        if not onclick:
            return ""
        # fn_GoUrl('/web/.../view.do?pblancId=XXX')
        m = re.search(r"fn_GoUrl\s*\(\s*['\"]([^'\"]+)['\"]", onclick)
        if m:
            return m.group(1)
        # location.href = '...'
        m = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", onclick)
        if m:
            return m.group(1)
        # goDetail('pblancId')
        m = re.search(r"(?:goDetail|viewDetail|fn_view)\s*\(\s*['\"]([^'\"]+)['\"]", onclick)
        if m:
            pid = m.group(1)
            return f"/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId={pid}"
        return ""
