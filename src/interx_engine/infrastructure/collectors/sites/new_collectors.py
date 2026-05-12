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
    + "&pageNum={page}&rowCnt=10"
)
_KETEP_DETAIL_URL = (
    _KETEP_BASE
    + "/businessAcment/view?menuId=" + _KETEP_MENU_ID
    + "&uni_ancm_id={uid}"
)
_KETEP_ID_RE = _re_ketep.compile(r"uni_ancm_id=([A-Za-z0-9]+)")


class KetepCollector(PlaywrightBaseCollector):
    """
    KETEP 사업공고 수집기.
    2025년 이후 URL이 /businessAcment 로 변경됨.
    Playwright로 렌더링 (React SPA 대응).
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
# IITP 정보통신기획평가원
# =============================================================================
import re as _re_iitp

_IITP_BASE       = "https://www.iitp.kr"
_IITP_LIST_URL   = _IITP_BASE + "/kr/1/business/pbancList.it?pageIndex={page}"
_IITP_DETAIL_TPL = _IITP_BASE + "/kr/1/business/pbancView.it?articleSeq={seq}"
_IITP_SEQ_RE     = _re_iitp.compile(r"articleSeq[=,'\"](\d+)", _re_iitp.I)


class IitpCollector(PlaywrightBaseCollector):
    """
    정보통신기획평가원 (IITP) 사업공고 수집기.
    Vue.js SPA — Playwright 렌더링 필수.
    AI·반도체·6G·양자·사이버보안 R&D 과제 공고.
    """
    site_key = "iitp"
    ministry = "과학기술정보통신부"
    agency   = "정보통신기획평가원"
    LIST_URL = _IITP_LIST_URL

    def _page_url(self, page: int) -> str:
        return self.LIST_URL.replace("{page}", str(page))

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices = []
        seen: set = set()

        # 1) tbody tr 기반 (서버사이드 렌더링 가능한 경우)
        for tr in soup.select("table tbody tr, tbody tr"):
            tds = tr.find_all(["td", "th"])
            if len(tds) < 2:
                continue
            a = None
            for td in tds:
                cand = td.find("a", href=True)
                if cand and len(cand.get_text(strip=True)) >= 3:
                    a = cand
                    break
            if not a:
                a = tr.find("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            href = (a.get("href") or "").strip()
            # articleSeq 추출
            m = _IITP_SEQ_RE.search(href)
            if m:
                detail = _IITP_DETAIL_TPL.format(seq=m.group(1))
            elif href and not href.lower().startswith("javascript"):
                detail = href if href.startswith("http") else urljoin(_IITP_BASE, href)
            else:
                # onclick 탐색
                onclick = (a.get("onclick") or tr.get("onclick") or "").strip()
                m2 = _IITP_SEQ_RE.search(onclick)
                if m2:
                    detail = _IITP_DETAIL_TPL.format(seq=m2.group(1))
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

        # 2) Vue.js 렌더링 후 카드/리스트 형태
        if not notices:
            for a in soup.select(
                "a[href*='pbancView'], a[href*='articleSeq'], "
                "a[href*='business/view'], .biz-list a, .notice-list a"
            ):
                title = a.get_text(strip=True)
                if not title or len(title) < 3:
                    continue
                href = (a.get("href") or "").strip()
                m = _IITP_SEQ_RE.search(href)
                if m:
                    detail = _IITP_DETAIL_TPL.format(seq=m.group(1))
                else:
                    detail = href if href.startswith("http") else urljoin(_IITP_BASE, href)
                if detail in seen:
                    continue
                seen.add(detail)
                row  = a.find_parent("tr") or a.find_parent("li") or a.find_parent("div") or a.parent
                text = row.get_text(" ", strip=True) if row else title
                dates = _extract_dates(text)
                notices.append(self._make_notice(
                    execution_id, title, detail,
                    dates[-1] if dates else "",
                    dates[0]  if len(dates) >= 2 else "",
                ))

        return notices

    def _collect_playwright(self, execution_id: str) -> List[Notice]:
        """Vue.js SPA: 렌더링 후 JS evaluate로 공고 데이터 직접 추출."""
        import time, random
        from playwright.sync_api import sync_playwright  # type: ignore

        notices: List[Notice] = []
        seen_ids: set = set()

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="ko-KR",
            )
            page = ctx.new_page()

            for pg in range(1, self.max_pages + 1):
                url = self._page_url(pg)
                try:
                    page.goto(url, wait_until="networkidle", timeout=30_000)
                    page.wait_for_timeout(3_000)  # Vue.js 렌더링 대기

                    # JS evaluate: Vue.js 렌더링 후 실제 DOM에서 공고 데이터 추출
                    rows_data: list = []
                    try:
                        rows_data = page.evaluate("""
                            () => {
                                const rows = [];
                                // 테이블 행
                                document.querySelectorAll('table tbody tr').forEach(tr => {
                                    const a = tr.querySelector('a[href]');
                                    if (a && a.textContent.trim().length >= 3) {
                                        rows.push({
                                            title:   a.textContent.trim(),
                                            href:    a.href,
                                            rowText: tr.textContent.trim().slice(0, 300)
                                        });
                                    }
                                });
                                // 리스트/카드 형태
                                if (rows.length === 0) {
                                    document.querySelectorAll('li a, .list-item a, .card a').forEach(a => {
                                        if (a.href.includes('articleSeq') || a.href.includes('pbancView')) {
                                            rows.push({
                                                title:   a.textContent.trim(),
                                                href:    a.href,
                                                rowText: (a.closest('li') || a.closest('div') || a).textContent.trim().slice(0, 300)
                                            });
                                        }
                                    });
                                }
                                return rows;
                            }
                        """)
                    except Exception:
                        rows_data = []

                    # JS 추출 성공 시 직접 공고 생성
                    items = []
                    if rows_data:
                        seen_urls: set = set()
                        for row in rows_data:
                            title = row.get("title", "").strip()
                            href  = row.get("href", "").strip()
                            if not title or len(title) < 3 or not href:
                                continue
                            detail = href if href.startswith("http") else urljoin(_IITP_BASE, href)
                            if detail in seen_urls:
                                continue
                            seen_urls.add(detail)
                            dates = _extract_dates(row.get("rowText", ""))
                            items.append(self._make_notice(
                                execution_id, title, detail,
                                dates[-1] if dates else "",
                                dates[0]  if len(dates) >= 2 else "",
                            ))

                    # JS 실패 시 BeautifulSoup fallback
                    if not items:
                        html  = page.content()
                        soup  = BeautifulSoup(html, "lxml")
                        items = self._parse_page(soup, execution_id)

                except Exception as e:
                    log.error("[iitp] playwright p%d 오류: %s", pg, e)
                    break

                if not items:
                    log.debug("[iitp] p%d 공고 없음 → 마지막 페이지", pg)
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
            log.warning("⚠️  [iitp] playwright 수집 0건 — IITP URL/구조 확인 필요")
        else:
            log.info("[IITP] playwright %d건 수집 완료", len(notices))
            notices = self._enrich_notices(notices)
        return notices


# =============================================================================
# 레지스트리
# =============================================================================
from interx_engine.infrastructure.collectors.sites.jejutp_collector import JejtpCollector
from interx_engine.infrastructure.collectors.sites.smart_factory_collector import SmartFactoryCollector
from interx_engine.infrastructure.collectors.sites.gbtp_collector import GbtpCollector

NEW_COLLECTOR_CLASSES: dict = {
    "nrf":           NrfCollector,
    "kised":         KisedCollector,
    "ketep":         KetepCollector,
    "koiia":         KoiiaCollector,
    "jejutp":        JejtpCollector,
    "smart_factory": SmartFactoryCollector,
    "gbtp":          GbtpCollector,
    "iitp":          IitpCollector,
}
