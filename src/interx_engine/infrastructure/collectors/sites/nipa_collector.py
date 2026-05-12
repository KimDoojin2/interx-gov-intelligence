from __future__ import annotations
from typing import List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector, _extract_dates,
)
from interx_engine.core.entities.notice import Notice


class NipaCollector(BaseCollector):
    site_key = "nipa"
    ministry = "과학기술정보통신부"
    agency   = "정보통신산업진흥원"
    LIST_URL = "https://www.nipa.kr/home/2-2?curPage={page}&tab=2"

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices = []
        items = (soup.select("ul.notice-list li") or
                 soup.select(".board-list li") or
                 soup.select("table tbody tr") or
                 soup.select("article, .card"))
        for item in items:
            a = item.find("a", href=True)
            if not a:
                continue
            title  = a.get_text(strip=True)
            href   = a["href"]
            detail = href if href.startswith("http") else urljoin("https://www.nipa.kr", href)
            text   = item.get_text(" ", strip=True)
            dates  = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0]  if len(dates) >= 2 else "",
            ))
        return notices
