from __future__ import annotations
from typing import List
from bs4 import BeautifulSoup
from interx_engine.infrastructure.collectors.sites.base_collector import BaseCollector
from interx_engine.core.entities.notice import Notice


class InnopolisCollector(BaseCollector):
    site_key = "innopolis"
    agency   = "연구개발특구진흥재단"
    LIST_URL = "https://www.innopolis.or.kr/board?menuId=MENU00319&pageNum={page}"

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        return self._parse_table(soup, execution_id, "https://www.innopolis.or.kr")
