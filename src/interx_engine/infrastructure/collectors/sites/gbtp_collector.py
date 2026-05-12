from __future__ import annotations
import re
from typing import List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector, _extract_dates,
)
from interx_engine.core.entities.notice import Notice

_ONCLICK_NTT = re.compile(r"nttNo=(\d+)", re.I)
_ONCLICK_IDX = re.compile(r"(?:fn_view|goView|viewDetail|fnView|goDetail)\s*\(\s*['\"]?(\d+)['\"]?\s*\)", re.I)


def _is_valid_href(href: str) -> bool:
    """javascript: 및 빈 href 제외."""
    return bool(href) and href.startswith(("http://", "https://", "/", "./", "../"))


class GbtpCollector(BaseCollector):
    site_key = "gbtp"
    agency   = "경북테크노파크"
    BASE     = "https://www.gbtp.or.kr"
    LIST_URL = "https://www.gbtp.or.kr/user/board.do?bbsId=BBSMSTR_000000000021&pageIndex={page}"
    DETAIL_TPL = "https://www.gbtp.or.kr/user/boardDetail.do?bbsId=BBSMSTR_000000000021&nttNo={ntt}"

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
            return self._parse_onclick(soup, execution_id)

        # 4순위: 테이블 일반 파싱
        if not links:
            return self._parse_table(soup, execution_id, self.BASE)

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
            # nttNo= 패턴 우선
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
