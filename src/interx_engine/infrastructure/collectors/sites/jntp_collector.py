from __future__ import annotations
from typing import List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector, _extract_dates,
)
from interx_engine.core.entities.notice import Notice

_BASE = "https://www.jntp.or.kr"

# 목록 URL — 공지사항 게시판 (boardManagementNo=16, menuNo=60)
# 실제 확인: http://www.jntp.or.kr/home/menu/16.do → 새 플랫폼으로 이전
_LIST_URL = (
    _BASE + "/base/board/list"
    "?boardManagementNo=16&menuLevel=2&menuNo=60&page={page}"
)


class JntpCollector(BaseCollector):
    """
    전남테크노파크 공고 수집기.
    URL: https://www.jntp.or.kr/base/board/list?boardManagementNo=16&...
    상세: /base/board/read?boardManagementNo=16&boardNo={id}&...
    """
    site_key = "jntp"
    agency   = "전남테크노파크"
    LIST_URL = _LIST_URL

    def _page_url(self, page: int) -> str:
        return self.LIST_URL.format(page=page)

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices: List[Notice] = []
        seen: set = set()

        # 1순위: boardNo= 파라미터가 있는 상세 링크
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if "boardNo=" not in href:
                continue

            title = a.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            full = href if href.startswith("http") else urljoin(_BASE, href)
            # 포트 443은 기본값이므로 제거 (URL 정규화)
            full = full.replace(":443/", "/")
            if full in seen:
                continue
            seen.add(full)

            row  = a.find_parent(["tr", "li"]) or a.parent
            text = row.get_text(" ", strip=True) if row else title
            dates = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, full,
                dates[-1] if dates else "",
                dates[0]  if len(dates) >= 2 else "",
            ))

        # 2순위: 일반 테이블 파싱 (fallback)
        if not notices:
            notices = self._parse_table(soup, execution_id, _BASE)

        return notices
