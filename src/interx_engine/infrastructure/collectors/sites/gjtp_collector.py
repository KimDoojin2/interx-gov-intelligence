from __future__ import annotations
from typing import List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector, _extract_dates,
)
from interx_engine.core.entities.notice import Notice


class GjtpCollector(BaseCollector):
    site_key = "gjtp"
    agency   = "광주테크노파크"
    LIST_URL = "https://www.gjtp.or.kr/home/business.cs?m=8&pageIndex={page}"

    def _enrich_notices(self, notices: List[Notice]) -> List[Notice]:
        """
        gjtp detail URL은 bsnssId= 카테고리 필터 URL → 개별 공고 페이지가 아님.
        해당 페이지를 enrich 하면 사이드바의 제조 카테고리 키워드(스마트공장, 자율형공장 등)가
        모든 공고 summary/body_text 에 오염됨 → enrichment 를 완전히 스킵.
        제목 기준으로만 채점되므로 실제 제조AI 관련 공고는 제목에 키워드가 있어 정상 채점됨.
        """
        return notices

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices = []
        # BASE에 경로 포함 필수 — href가 "?act=view&bsnssId=..." 쿼리만 있으므로
        # urljoin("https://www.gjtp.or.kr", "?...") → 경로 없이 메인으로 감
        BASE = "https://www.gjtp.or.kr/home/business.cs"
        links = soup.find_all("a", href=lambda h: h and "bsnssId=" in (h or ""))
        if not links:
            return self._parse_table(soup, execution_id, BASE)
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
