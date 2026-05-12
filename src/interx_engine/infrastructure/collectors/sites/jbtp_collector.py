from __future__ import annotations
from typing import List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector, _extract_dates,
)
from interx_engine.core.entities.notice import Notice


class JbtpCollector(BaseCollector):
    site_key = "jbtp"
    agency   = "전북테크노파크"
    LIST_URL = (
        "https://www.jbtp.or.kr/index.jbtp"
        "?menuCd=DOM_000000102001000000&pageIndex={page}"
    )

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        BASE = "https://www.jbtp.or.kr"
        links = soup.find_all("a", href=lambda h: h and "dataSid=" in (h or ""))
        if not links:
            return self._parse_table(soup, execution_id, BASE)
        notices = []
        for a in links:
            title  = a.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            href   = a["href"]
            detail = href if href.startswith("http") else urljoin(BASE, href)
            row    = a.find_parent("tr") or a.find_parent("li") or a.parent
            text   = row.get_text(" ", strip=True) if row else title
            dates  = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0]  if len(dates) >= 2 else "",
            ))
        return notices
