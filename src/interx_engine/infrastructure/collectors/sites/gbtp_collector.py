from __future__ import annotations

import logging
import re
import time
import random
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from interx_engine.infrastructure.collectors.sites.base_collector import (
    PlaywrightBaseCollector, _extract_dates,
)
from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.collectors")

_ONCLICK_NTT = re.compile(r"nttNo=(\d+)", re.I)
_ONCLICK_IDX = re.compile(
    r"(?:fn_view|goView|viewDetail|fnView|goDetail)\s*\(\s*['\"]?(\d+)['\"]?\s*\)", re.I
)


def _is_valid_href(href: str) -> bool:
    """javascript: 및 빈 href 제외."""
    return bool(href) and href.startswith(("http://", "https://", "/", "./", "../"))


class GbtpCollector(PlaywrightBaseCollector):
    site_key   = "gbtp"
    ministry   = "중소벤처기업부"
    agency     = "경북테크노파크"
    BASE       = "https://www.gbtp.or.kr"
    LIST_URL   = "https://www.gbtp.or.kr/user/board.do?bbsId=BBSMSTR_000000000021&pageIndex={page}"
    DETAIL_TPL = "https://www.gbtp.or.kr/user/boardDetail.do?bbsId=BBSMSTR_000000000021&nttNo={ntt}"

    def _page_url(self, page: int) -> str:
        return self.LIST_URL.format(page=page)

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices = []

        # 1순위: boardDetail.do 링크 직접 탐색
        links = [a for a in soup.find_all("a", href=True)
                 if "boardDetail.do" in a["href"] and _is_valid_href(a["href"])]

        # 2순위: nttNo= 파라미터가 있는 유효한 href
        if not links:
            links = [a for a in soup.find_all("a", href=True)
                     if "nttNo=" in a["href"] and _is_valid_href(a["href"])]

        # 3순위: onclick에서 nttNo 또는 idx 추출
        if not links:
            onclick_notices = self._parse_onclick(soup, execution_id)
            if onclick_notices:
                return onclick_notices

        # 4순위: tbody tr 일반 파싱
        if not links:
            return self._parse_table_rows(soup, execution_id)

        for a in links:
            title = a.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            href   = a["href"]
            detail = href if href.startswith("http") else urljoin(self.BASE, href)
            row    = a.find_parent("tr") or a.find_parent("li") or a.parent
            text   = row.get_text(" ", strip=True) if row else title
            dates  = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0]  if len(dates) >= 2 else "",
            ))
        return notices

    def _parse_onclick(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        """onclick 속성에서 nttNo 또는 idx 추출해 상세 URL 조합."""
        notices = []
        rows = soup.select("table tbody tr") or soup.select("ul li")
        for row in rows:
            a = row.find("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            onclick = a.get("onclick", "") or row.get("onclick", "")
            m = _ONCLICK_NTT.search(onclick)
            if m:
                detail = self.DETAIL_TPL.format(ntt=m.group(1))
            else:
                m = _ONCLICK_IDX.search(onclick)
                if m:
                    detail = self.DETAIL_TPL.format(ntt=m.group(1))
                else:
                    continue

            text  = row.get_text(" ", strip=True)
            dates = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0]  if len(dates) >= 2 else "",
            ))
        return notices

    def _parse_table_rows(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        """일반 tbody tr 파싱 fallback."""
        notices = []
        for tr in soup.select("table tbody tr"):
            a = tr.find("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            href = (a.get("href") or "").strip()
            if not href or href.lower().startswith("javascript"):
                continue
            detail = href if href.startswith("http") else urljoin(self.BASE, href)
            text  = tr.get_text(" ", strip=True)
            dates = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0]  if len(dates) >= 2 else "",
            ))
        return notices

    def collect(self, execution_id: str) -> List[Notice]:
        """Playwright 수집 → requests fallback."""
        try:
            return self._collect_playwright(execution_id)
        except ImportError:
            log.warning("[gbtp] playwright 미설치 → requests fallback")
            return self._collect_requests_fallback(execution_id)
        except Exception as e:
            log.warning("[gbtp] playwright 실패 (%s) → requests fallback", e)
            return self._collect_requests_fallback(execution_id)

    def _collect_playwright(self, execution_id: str) -> List[Notice]:
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

            for pg in range(1, self.max_pages + 1):
                url = self._page_url(pg)
                try:
                    page.goto(url, wait_until="networkidle", timeout=30_000)
                    page.wait_for_timeout(2_000)
                    html  = page.content()
                    soup  = BeautifulSoup(html, "lxml")
                    items = self._parse_page(soup, execution_id)
                except Exception as e:
                    log.error("[gbtp] playwright p%d 오류: %s", pg, e)
                    break

                if not items:
                    log.debug("[gbtp] p%d 공고 없음 → 마지막 페이지", pg)
                    break

                new = [n for n in items if n.notice_id not in seen_ids]
                if not new:
                    break
                for n in new:
                    seen_ids.add(n.notice_id)
                all_notices.extend(new)
                log.debug("[gbtp] p%d: %d건 (신규 %d건)", pg, len(items), len(new))
                time.sleep(random.uniform(1.0, 2.0))

            browser.close()

        if not all_notices:
            log.warning("⚠️  [gbtp] playwright 수집 0건 — URL 확인 필요")
        else:
            log.info("[GBTP] playwright %d건 수집 완료", len(all_notices))
            all_notices = self._enrich_notices(all_notices)

        return all_notices

    def _collect_requests_fallback(self, execution_id: str) -> List[Notice]:
        """requests fallback."""
        all_notices: List[Notice] = []
        seen_ids: set = set()

        for pg in range(1, self.max_pages + 1):
            url  = self._page_url(pg)
            resp = self._get(url)
            if not resp:
                break
            soup  = BeautifulSoup(resp.text, "lxml")
            items = self._parse_page(soup, execution_id)
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
            log.info("[GBTP] requests fallback %d건 수집", len(all_notices))
            all_notices = self._enrich_notices(all_notices)
        return all_notices
