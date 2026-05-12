"""
DiciaCollector  —  KMEDI hub (kmedihub.re.kr)
구 dgmif.re.kr → www.kmedihub.re.kr 로 도메인 변경됨 (2024~)
onclick="fn_icms_navi_common('view', nttId)" 패턴 사용
"""
from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from interx_engine.infrastructure.collectors.sites.base_collector import (
    PlaywrightBaseCollector, _extract_dates,
)
from interx_engine.core.entities.notice import Notice

_BASE = "https://www.kmedihub.re.kr"

# 공고 게시판 (사업공고, 사업공지 등 복수 게시판 수집)
_BOARDS = [
    {"menu_id": "00000063", "bbs_id": "BBS_00001", "label": "사업공고"},
    {"menu_id": "00000064", "bbs_id": "BBS_00002", "label": "사업공지"},
]

# 목록 URL 템플릿
_LIST_TPL  = _BASE + "/index.do?menu_id={menu_id}&pageIndex={page}"
# 상세 URL 템플릿 (GET 버전 — 실제 내부는 POST이지만 식별 목적)
_DETAIL_TPL = (
    _BASE + "/index.do?menu_link=/icms/bbs/selectBoardArticle.do"
    "&nttId={ntt_id}&bbsId={bbs_id}&menu_id={menu_id}"
)

# fn_icms_navi_common('view', 'nttId') 패턴
_NTT_RE = re.compile(
    r"fn_icms_navi_common\s*\(\s*['\"]view['\"].*?['\"](\d+)['\"]",
    re.I,
)


class DiciaCollector(PlaywrightBaseCollector):
    """
    KMEDI hub (한국첨단의료산업진흥재단) 공고 수집기.
    구 dgmif.re.kr 에서 kmedihub.re.kr 로 변경.
    """
    site_key   = "dicia"
    ssl_verify = True
    agency     = "한국첨단의료산업진흥재단"
    LIST_URL   = _LIST_TPL.replace("{menu_id}", _BOARDS[0]["menu_id"])

    def _page_url(self, page: int) -> str:
        return self.LIST_URL.replace("{page}", str(page))

    def collect(self, execution_id: str) -> List[Notice]:
        """여러 게시판을 순차 수집."""
        all_notices: List[Notice] = []
        seen: set = set()

        for board in _BOARDS:
            self.LIST_URL = _LIST_TPL.replace("{menu_id}", board["menu_id"])
            self._current_board = board

            notices = super().collect(execution_id)
            for n in notices:
                if n.notice_id not in seen:
                    seen.add(n.notice_id)
                    all_notices.append(n)

        return all_notices

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        board = getattr(self, "_current_board", _BOARDS[0])
        notices = []

        for tr in soup.select("table tbody tr"):
            tds = tr.find_all(["td", "th"])
            if len(tds) < 2:
                continue

            # 제목 td 탐색 — onclick이 있는 a 태그 우선
            title_a = None
            for td in tds:
                a = td.find("a")
                if not a:
                    continue
                onclick = (a.get("onclick") or "").strip()
                if _NTT_RE.search(onclick):
                    title_a = a
                    break

            if not title_a:
                continue

            title = title_a.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            onclick = title_a.get("onclick") or ""
            m = _NTT_RE.search(onclick)
            if not m:
                continue
            ntt_id = m.group(1)

            detail_url = _DETAIL_TPL.format(
                ntt_id=ntt_id,
                bbs_id=board["bbs_id"],
                menu_id=board["menu_id"],
            )

            row_text = tr.get_text(" ", strip=True)
            dates    = _extract_dates(row_text)
            posted   = dates[0]  if dates else ""
            deadline = dates[-1] if len(dates) >= 2 else (dates[0] if dates else "")

            notices.append(Notice(
                execution_id         = execution_id,
                site                 = "dicia",
                notice_id            = f"dicia-{ntt_id}",
                title                = title,
                detail_url           = detail_url,
                notice_link          = detail_url,
                posted_date          = posted,
                deadline_date        = deadline,
                ministry             = "",
                agency               = self.agency,
                business_type        = "지원사업",
                budget               = "",
                summary              = "",
                recommended_solution = "",
                recommended_action   = "검토",
                l3_strong            = "N",
                partner_candidate    = "N",
                attachments          = [],
                attachment_items     = [],
            ))

        return notices
