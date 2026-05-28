"""
NTIS (국가과학기술지식정보서비스) 수집기
https://www.ntis.go.kr — 국가 R&D 과제 공고 수집

NTIS 목록 페이지: /rndgate/eg/announce/annEgAnncList.do
페이지네이션 파라미터: pageNumber={page}
검색 조건: 접수중/접수예정 공고만 수집
"""
from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from interx_engine.core.entities.notice import Notice
from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector, _extract_dates,
)

import logging
log = logging.getLogger("interx.collectors.ntis")


class NtisCollector(BaseCollector):
    site_key     = "ntis"
    ministry     = "과학기술정보통신부"
    agency       = "한국과학기술정보연구원(KISTI)"
    ssl_verify   = True
    fetch_detail = True

    # NTIS 공고 목록 URL
    LIST_URL = (
        "https://www.ntis.go.kr/ThSearchRndAnncList.do"
        "?pageNo={page}&pageSize=20"
    )

    # ── NTIS 목록 HTML 파싱 ──────────────────────────────────────────────────
    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices: List[Notice] = []

        # 패턴 1: 테이블 기반 목록 (일반적인 NTIS 레이아웃)
        rows = soup.select("table tbody tr")
        if rows:
            return self._parse_table_rows(rows, execution_id)

        # 패턴 2: div/ul 리스트 기반 레이아웃
        items = (
            soup.select("ul.board-list li") or
            soup.select("div.list-item") or
            soup.select(".announce-list li") or
            soup.select("article, .card")
        )
        for item in items:
            a = item.find("a", href=True)
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            href = a["href"]
            detail = self._resolve_url(href)
            text = item.get_text(" ", strip=True)
            dates = _extract_dates(text)
            budget = self._extract_budget_hint(text)

            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0] if len(dates) >= 2 else "",
                budget=budget,
            ))

        return notices

    def _parse_table_rows(
        self, rows: list, execution_id: str,
    ) -> List[Notice]:
        """테이블 행을 파싱하여 Notice 리스트 반환."""
        notices: List[Notice] = []
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            # 제목 셀 찾기 (보통 2~3번째 열에 <a> 포함)
            a = row.find("a", href=True)
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            href = a["href"]
            detail = self._resolve_url(href)

            # 날짜/예산은 셀 텍스트에서 추출
            row_text = row.get_text(" ", strip=True)
            dates = _extract_dates(row_text)
            budget = self._extract_budget_hint(row_text)

            # 주관 기관 추출 시도 (보통 특정 열에 위치)
            ministry_cell = ""
            agency_cell = ""
            for idx, cell in enumerate(cells):
                ct = cell.get_text(strip=True)
                # 부처/기관 열 (보통 "부" 또는 "원" "재단" "진흥" 포함)
                if any(kw in ct for kw in ("부", "청", "처")) and len(ct) < 30:
                    if not ministry_cell:
                        ministry_cell = ct
                elif any(kw in ct for kw in ("원", "재단", "진흥", "연구")) and len(ct) < 30:
                    if not agency_cell:
                        agency_cell = ct

            n = self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0] if len(dates) >= 2 else "",
                budget=budget,
            )
            if ministry_cell:
                n.ministry = ministry_cell
            if agency_cell:
                n.agency = agency_cell

            notices.append(n)

        return notices

    # ── 헬퍼 ─────────────────────────────────────────────────────────────────

    _BASE = "https://www.ntis.go.kr"

    def _resolve_url(self, href: str) -> str:
        """상대/절대 URL을 완전한 URL로 변환."""
        if not href:
            return ""
        if href.startswith("http"):
            return href
        # javascript:fn('id') 같은 패턴 → 공고 ID 추출 시도
        m = re.search(r"['\"]([A-Z0-9-]+)['\"]", href)
        if m and "javascript" in href.lower():
            annc_id = m.group(1)
            return (
                f"{self._BASE}/rndgate/eg/announce/annEgAnncDetail.do"
                f"?anncSeq={annc_id}"
            )
        return urljoin(self._BASE, href)

    _BUDGET_RE = re.compile(
        r"([0-9,]+)\s*(억|백만|만)\s*원"
    )

    def _extract_budget_hint(self, text: str) -> str:
        """텍스트에서 예산 힌트 추출."""
        m = self._BUDGET_RE.search(text)
        if m:
            return f"{m.group(1)}{m.group(2)}원"
        return ""
