from __future__ import annotations
import random
import time
from typing import List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector, _extract_dates,
)
from interx_engine.core.entities.notice import Notice

_SMBA_BASE = "https://www.mss.go.kr"
_SMBA_HOME = _SMBA_BASE + "/site/smba/main.do"


class SmbaCollector(BaseCollector):
    site_key = "smba"
    ministry = "중소벤처기업부"
    LIST_URL = _SMBA_BASE + "/site/smba/ex/bbs/List.do?cbIdx=310&pageIndex={page}"

    def collect(self, execution_id: str) -> List[Notice]:
        # 홈페이지 쿠키 선취득 → ConnectionReset 방지
        try:
            time.sleep(random.uniform(2.0, 4.0))
            self._session.get(
                _SMBA_HOME,
                headers=self._headers(),
                timeout=self.timeout,
                verify=self.ssl_verify,
                allow_redirects=True,
            )
            time.sleep(random.uniform(1.0, 2.0))
        except Exception:
            pass
        return super().collect(execution_id)

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices = []
        rows = (soup.select("table.bbs_list tbody tr") or
                soup.select("table tbody tr") or
                soup.select("ul.bbs-list li"))
        for row in rows:
            a = row.find("a", href=True)
            if not a:
                continue
            title  = a.get_text(strip=True)
            href   = a["href"]
            detail = href if href.startswith("http") else urljoin(_SMBA_BASE, href)
            text   = row.get_text(" ", strip=True)
            dates  = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0]  if len(dates) >= 2 else "",
            ))
        return notices
