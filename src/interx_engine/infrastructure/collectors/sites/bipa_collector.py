from __future__ import annotations
from typing import List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector, _extract_dates,
)
from interx_engine.core.entities.notice import Notice


class BipaCollector(BaseCollector):
    site_key = "bipa"
    agency   = "부산정보산업진흥원"
    LIST_URL = "https://bipa.kr/board/business?page={page}"

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices = []
        items = (soup.select("ul.board-list li") or
                 soup.select("table tbody tr") or
                 soup.select(".board_list li"))
        if not items:
            items = soup.select("a[href*='/board/business/view']")
        for item in items:
            a = (item.find("a", href=True)
                 if hasattr(item, "find") else item)
            if not a:
                continue
            href = a.get("href", "")
            if "/board/business/view" not in href:
                continue
            title  = a.get_text(strip=True)
            detail = href if href.startswith("http") else urljoin("https://bipa.kr", href)
            text   = item.get_text(" ", strip=True) if hasattr(item, "get_text") else title
            dates  = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0]  if len(dates) >= 2 else "",
            ))
        return notices
