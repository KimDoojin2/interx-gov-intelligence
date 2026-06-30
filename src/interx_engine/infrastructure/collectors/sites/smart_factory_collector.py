"""
스마트제조혁신추진단 (smart-factory.kr) 공고 수집기
  사업공고 (bsnsPbanc) + 모집공고 (rcrtPbanc) 두 게시판 통합 수집
  React/Ant Design SPA — Playwright 필수
"""
from __future__ import annotations

import logging
import re
import time
import random
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from interx_engine.infrastructure.collectors.sites.base_collector import (
    PlaywrightBaseCollector,
    _extract_dates,
    _notice_id,
)
from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.collectors")

_SF_BASE = "https://www.smart-factory.kr"

# ── 게시판 URL 목록 ─────────────────────────────────────────────────────────────
# React SPA 라우트 (2025년 이후 개편) — 페이지 파라미터 없이 SPA 내 페이징
# fallback: 구 JSP 기반 URL (정적 HTML, pageIndex 파라미터)
_SF_BOARDS = [
    {
        "label":    "사업공고",
        "list_url": _SF_BASE + "/usr/bg/ba/ma/bsnsPbanc",
        "old_url":  _SF_BASE + "/usr/bg/ba/ma/bsnsPbanc?pageIndex={page}",
    },
    {
        "label":    "모집공고",
        "list_url": _SF_BASE + "/usr/bg/ra/ma/rcrtPbanc",
        "old_url":  _SF_BASE + "/usr/bg/ra/ma/rcrtPbanc?pageIndex={page}",
    },
]

_ID_RE = re.compile(r"[?&](?:bbsId|nttId|seq|idx|no)=([A-Za-z0-9_-]+)", re.I)
_NTT_ID_RE = re.compile(r"[?&]nttId=([A-Za-z0-9_-]+)", re.I)


def _sf_notice_id(detail_url: str) -> str:
    """
    스마트공장 전용 notice_id 생성.
    URL에서 nttId 파라미터 추출 → 있으면 nttId 기반 ID (중복 방지 핵심).
    없으면 기존 URL MD5 방식 fallback.
    """
    m = _NTT_ID_RE.search(detail_url)
    if m:
        return f"smart_factory-ntt{m.group(1)}"
    # fallback: 기존 URL MD5
    from interx_engine.infrastructure.collectors.sites.base_collector import _notice_id
    return _notice_id("smart_factory", detail_url)

# 게시판별 상세 URL 접두사
_SF_DETAIL = {
    "사업공고": _SF_BASE + "/usr/bg/ba/ma/bsnsPbancDtl",
    "모집공고": _SF_BASE + "/usr/bg/ra/ma/rcrtPbancDtl",
}


def _parse_sf_soup(soup: BeautifulSoup, execution_id: str,
                   base_url: str = _SF_BASE) -> List[Notice]:
    """Ant Design 테이블 + 구 HTML 테이블 통합 파서."""
    notices: List[Notice] = []
    seen: set = set()

    # 1) Ant Design React 테이블 (tr.ant-table-row)
    for tr in soup.select("tr.ant-table-row"):
        a = None
        for td in tr.find_all(["td", "th"]):
            candidate = td.find("a", href=True)
            if candidate:
                txt = candidate.get_text(strip=True)
                if len(txt) >= 3:
                    a = candidate
                    break
        if not a:
            a = tr.find("a", href=True)
        if not a:
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 8:   # "모집공고","사업안내" 등 메뉴 링크 필터
            continue
        href   = (a.get("href") or "").strip()
        detail = href if href.startswith("http") else urljoin(base_url, href)
        if detail in seen:
            continue
        seen.add(detail)
        row_text = tr.get_text(" ", strip=True)
        dates    = _extract_dates(row_text)
        notices.append(Notice(
            execution_id  = execution_id,
            site          = SmartFactoryCollector.site_key,
            notice_id     = _sf_notice_id(detail),
            title         = title,
            detail_url    = detail,
            notice_link   = detail,
            deadline_date = dates[-1] if dates else "",
            posted_date   = dates[0]  if len(dates) >= 2 else "",
            ministry      = SmartFactoryCollector.ministry,
            agency        = SmartFactoryCollector.agency,
        ))

    # 2) 구 JSP HTML 테이블 (tbody tr)
    if not notices:
        tbody = soup.find("tbody")
        rows  = tbody.find_all("tr") if tbody else []
        for tr in rows:
            a = tr.find("a", href=True)
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 8:   # "모집공고","사업안내" 등 메뉴 링크 필터
                continue
            href   = (a.get("href") or "").strip()
            detail = href if href.startswith("http") else urljoin(base_url, href)
            if detail in seen:
                continue
            seen.add(detail)
            row_text = tr.get_text(" ", strip=True)
            dates    = _extract_dates(row_text)
            notices.append(Notice(
                execution_id  = execution_id,
                site          = SmartFactoryCollector.site_key,
                notice_id     = _sf_notice_id(detail),
                title         = title,
                detail_url    = detail,
                notice_link   = detail,
                deadline_date = dates[-1] if dates else "",
                posted_date   = dates[0]  if len(dates) >= 2 else "",
                ministry      = SmartFactoryCollector.ministry,
                agency        = SmartFactoryCollector.agency,
            ))

    # 3) 링크 직접 탐색 fallback (SPA 렌더 결과가 비표준 구조인 경우)
    if not notices:
        for a in soup.select(
            "a[href*='bsnsPbanc'], a[href*='rcrtPbanc'], "
            "a[href*='bbsView'], a[href*='nttId'], a[href*='bbsId']"
        ):
            title = a.get_text(strip=True)
            if not title or len(title) < 8:   # "모집공고","사업안내" 등 메뉴 링크 필터
                continue
            href   = (a.get("href") or "").strip()
            detail = href if href.startswith("http") else urljoin(base_url, href)
            if detail in seen:
                continue
            seen.add(detail)
            row  = a.find_parent("tr") or a.find_parent("li") or a.parent
            text = row.get_text(" ", strip=True) if row else title
            dates = _extract_dates(text)
            notices.append(Notice(
                execution_id  = execution_id,
                site          = SmartFactoryCollector.site_key,
                notice_id     = _sf_notice_id(detail),
                title         = title,
                detail_url    = detail,
                notice_link   = detail,
                deadline_date = dates[-1] if dates else "",
                posted_date   = dates[0]  if len(dates) >= 2 else "",
                ministry      = SmartFactoryCollector.ministry,
                agency        = SmartFactoryCollector.agency,
            ))

    return notices


class SmartFactoryCollector(PlaywrightBaseCollector):
    """
    스마트제조혁신추진단 공고 수집기.
    사업공고(bsnsPbanc) + 모집공고(rcrtPbanc) 두 게시판 수집.
    React/Ant Design SPA — Playwright 렌더링 필수.
    """
    site_key = "smart_factory"
    ministry = "중소벤처기업부"
    agency   = "스마트제조혁신추진단"
    LIST_URL = _SF_BASE + "/usr/bg/ba/ma/bsnsPbanc"   # 기본 (단일 게시판 쿼리용)

    def _page_url(self, page: int) -> str:
        """단순 호출 시 사업공고 첫 페이지 반환 (collect() 오버라이드로 미사용)."""
        return self.LIST_URL

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        return _parse_sf_soup(soup, execution_id)

    def collect(self, execution_id: str) -> List[Notice]:
        """두 게시판을 순서대로 수집 후 합산."""
        try:
            return self._collect_all_boards_playwright(execution_id)
        except ImportError:
            log.warning("[smart_factory] playwright 미설치 → requests fallback")
            return self._collect_all_boards_requests(execution_id)
        except Exception as e:
            log.warning("[smart_factory] playwright 실패 (%s) → requests fallback", e)
            return self._collect_all_boards_requests(execution_id)

    def _collect_all_boards_playwright(self, execution_id: str) -> List[Notice]:
        from playwright.sync_api import sync_playwright  # type: ignore

        all_notices: List[Notice] = []
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

            # SPA 셸 먼저 로드 (직접 SPA 라우트 접근 시 404)
            page.goto(_SF_BASE + "/", wait_until="networkidle", timeout=30_000)
            page.wait_for_timeout(2_000)

            for board in _SF_BOARDS:
                log.info("[smart_factory] 게시판 수집 시작: %s (%s)",
                         board["label"], board["list_url"])

                for pg in range(1, self.max_pages + 1):
                    try:
                        if pg == 1:
                            # SPA 내부 라우트 이동 (pushState)
                            spa_path = board["list_url"].replace(_SF_BASE, "")
                            page.evaluate(f"window.location.hash = ''; window.history.pushState({{}}, '', '{spa_path}'); window.dispatchEvent(new PopStateEvent('popstate'))")
                            page.wait_for_timeout(1_500)
                            # popstate 미반영 시 직접 goto 시도
                            try:
                                page.wait_for_selector(
                                    "tr.ant-table-row, tbody tr",
                                    timeout=5_000,
                                )
                            except Exception:
                                page.goto(board["list_url"],
                                          wait_until="networkidle", timeout=30_000)
                        else:
                            # Ant Design pagination: 페이지 번호 버튼 클릭
                            try:
                                sel = f"li.ant-pagination-item-{pg} a, button[aria-label='Page {pg}']"
                                page.click(sel, timeout=5_000)
                                page.wait_for_load_state("networkidle", timeout=15_000)
                            except Exception:
                                # SPA 페이지 클릭 실패 → 구 URL로 직접 접근
                                old_url = board["old_url"].format(page=pg)
                                page.goto(old_url, wait_until="networkidle", timeout=30_000)

                        page.wait_for_timeout(2_000)

                        # Ant Design 테이블: data-row-key + a.href(DOM property) 추출
                        # BeautifulSoup은 href 어트리뷰트만 보므로 nttId가 없을 수 있음
                        # → JS evaluation으로 실제 DOM href(full URL) 또는 data-row-key 확보
                        row_meta: list = []
                        try:
                            row_meta = page.evaluate("""
                                () => Array.from(
                                    document.querySelectorAll('tr.ant-table-row')
                                ).map(tr => {
                                    const a = tr.querySelector('a');
                                    return {
                                        rowKey: tr.getAttribute('data-row-key') || '',
                                        href:   a ? a.href : '',
                                        text:   a ? a.textContent.trim() : ''
                                    };
                                })
                            """)
                        except Exception:
                            row_meta = []

                        html  = page.content()
                        soup  = BeautifulSoup(html, "lxml")
                        items = _parse_sf_soup(soup, execution_id)

                        # detail_url 보정: JS에서 추출한 href 또는 nttId 적용
                        if row_meta and items:
                            # title → (href, rowKey) 매핑
                            meta_map = {m["text"]: m for m in row_meta if m.get("text")}
                            detail_base = _SF_DETAIL.get(board["label"], "")
                            for notice in items:
                                meta = meta_map.get(notice.title)
                                if not meta:
                                    continue
                                # 1) DOM href에 nttId가 있으면 그대로 사용
                                dom_href = meta.get("href", "")
                                if dom_href and "nttId" in dom_href:
                                    notice.detail_url  = dom_href
                                    notice.notice_link = dom_href
                                # 2) data-row-key가 숫자면 nttId로 사용
                                elif meta.get("rowKey", "").isdigit() and detail_base:
                                    proper = f"{detail_base}?nttId={meta['rowKey']}"
                                    notice.detail_url  = proper
                                    notice.notice_link = proper
                                # notice_id 재계산 (URL이 바뀌었을 수 있음) — nttId 기반
                                notice.notice_id = _sf_notice_id(notice.detail_url)

                    except Exception as e:
                        log.error("[smart_factory] %s p%d 오류: %s",
                                  board["label"], pg, e)
                        break

                    if not items:
                        log.debug("[smart_factory] %s p%d 공고 없음 → 마지막 페이지",
                                  board["label"], pg)
                        break

                    new = [n for n in items if n.notice_id not in seen_ids]
                    if not new:
                        break

                    for n in new:
                        seen_ids.add(n.notice_id)
                    all_notices.extend(new)
                    log.debug("[smart_factory] %s p%d: %d건 (신규 %d건)",
                              board["label"], pg, len(items), len(new))
                    time.sleep(random.uniform(1.0, 2.0))

            browser.close()

        if not all_notices:
            log.warning("⚠️  [smart_factory] playwright 수집 0건 — URL 확인 필요")
        else:
            log.info("[SMART_FACTORY] playwright %d건 수집 완료", len(all_notices))
            all_notices = self._enrich_notices(all_notices)

        return all_notices

    def _collect_all_boards_requests(self, execution_id: str) -> List[Notice]:
        """requests fallback — 구 JSP 정적 URL 사용."""
        import requests
        from bs4 import BeautifulSoup

        all_notices: List[Notice] = []
        seen_ids: set = set()

        for board in _SF_BOARDS:
            for pg in range(1, self.max_pages + 1):
                url  = board["old_url"].format(page=pg)
                resp = self._get(url)
                if not resp:
                    break
                soup  = BeautifulSoup(resp.text, "lxml")
                items = _parse_sf_soup(soup, execution_id)
                if not items:
                    break
                new = [n for n in items if n.notice_id not in seen_ids]
                if not new:
                    break
                for n in new:
                    seen_ids.add(n.notice_id)
                all_notices.extend(new)
                time.sleep(random.uniform(0.5, 1.0))

        if all_notices:
            log.info("[SMART_FACTORY] requests fallback %d건 수집", len(all_notices))
            all_notices = self._enrich_notices(all_notices)
        return all_notices
