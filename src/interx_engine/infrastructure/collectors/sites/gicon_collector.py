from __future__ import annotations
from typing import List
from bs4 import BeautifulSoup
from interx_engine.infrastructure.collectors.sites.base_collector import BaseCollector
from interx_engine.core.entities.notice import Notice


class GiconCollector(BaseCollector):
    site_key = "gicon"
    agency   = "광주정보문화산업진흥원"
    LIST_URL = "https://www.gicon.or.kr/board.es?mid=a10204000000&bid=0003&pageIndex={page}"

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        return self._parse_table(soup, execution_id, "https://www.gicon.or.kr")
