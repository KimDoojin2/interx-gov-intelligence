from __future__ import annotations
import re
from typing import List
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector, _extract_dates,
)
from interx_engine.core.entities.notice import Notice

# UIPA 상세 URL에 포함되어야 할 공고 식별 파라미터
_DETAIL_PARAMS = re.compile(r"(idx|seq|nttNo|no|ntcnId|bbsNo|artcl|id|sn)=\d+", re.I)
# 페이지네이션·카테고리용 파라미터 (이게 있으면 상세 URL 아님)
_PAGING_ONLY   = re.compile(r"[?&]page(?:Index)?=\d+$", re.I)

# onclick="fn_view('123')" 또는 onclick="goView(123)" 패턴
_ONCLICK_IDX   = re.compile(r"(?:fn_view|goView|viewDetail|fnView)\s*\(\s*['\"]?(\d+)['\"]?\s*\)", re.I)


class UipaCollector(BaseCollector):
    site_key   = "uipa"
    ssl_verify = False
    agency     = "울산정보산업진흥원"
    BASE       = "https://www.uipa.or.kr"
    LIST_URL   = "https://www.uipa.or.kr/webuser/business/list.html?page={page}"
    # 상세 URL 템플릿: idx 값 추출 후 조합
    DETAIL_TPL = "https://www.uipa.or.kr/webuser/business/detail.html?idx={idx}"

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices = []

        rows = (soup.select("table.board_list tbody tr") or
                soup.select("table tbody tr") or
                soup.select("ul.board-list li") or
                soup.select("div.list_wrap li"))

        for item in rows:
            a = item.find("a", href=True)
            if not a:
                # onclick 기반 링크 탐색
                a = item.find("a", onclick=True)
            if not a:
                continue

            title = a.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            detail = self._resolve_detail_url(a, item)
            if not detail:
                continue

            text  = item.get_text(" ", strip=True)
            dates = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0]  if len(dates) >= 2 else "",
            ))
        return notices

    def _resolve_detail_url(self, a_tag, row) -> str:
        """
        <a> 태그에서 상세 URL을 추출한다.
        0) bd_id= 파라미터 명시 처리 (UIPA 고유 패턴: view.html?bd_id=XXX&page=Y)
        1) href에 공고 식별 파라미터가 있으면 그대로 사용
        2) onclick에서 idx 추출 후 DETAIL_TPL로 조합
        3) href가 detail/view 경로면 사용
        4) 실패 시 빈 문자열
        """
        href    = (a_tag.get("href") or "").strip()
        onclick = (a_tag.get("onclick") or "").strip()

        # Case 0: bd_id= 파라미터 (UIPA 전용: view.html?bd_id=23902&page=1)
        # _PAGING_ONLY 검사보다 우선 — page 파라미터가 같이 있어도 허용
        # urljoin base는 목록 디렉토리(/webuser/business/)를 포함해야
        # ./view.html 이 루트가 아닌 올바른 경로로 해석된다.
        _BUSINESS_DIR = self.BASE + "/webuser/business/"
        if href and "bd_id=" in href:
            full = href if href.startswith("http") else urljoin(_BUSINESS_DIR, href)
            return full

        # Case 1: href에 공고 식별자 파라미터 포함
        if href and href.startswith("http") and _DETAIL_PARAMS.search(href):
            if not _PAGING_ONLY.search(href):
                return href
        if href and not href.startswith("http") and _DETAIL_PARAMS.search(href):
            full = urljoin(self.BASE, href)
            if not _PAGING_ONLY.search(full):
                return full

        # Case 2: onclick에서 idx 추출
        m = _ONCLICK_IDX.search(onclick)
        if not m:
            # 행(row) 전체의 onclick도 탐색
            for el in (row.find_all(onclick=True) if row else []):
                m = _ONCLICK_IDX.search(el.get("onclick", ""))
                if m:
                    break
        if m:
            return self.DETAIL_TPL.format(idx=m.group(1))

        # Case 3: href 경로가 detail 또는 view 패턴
        if href and ("detail" in href or "view" in href):
            if href.startswith("http"):
                return href
            full = urljoin(self.BASE, href)
            # 페이지네이션 파라미터만 있는 경우 제외
            if not _PAGING_ONLY.search(full):
                return full

        return ""
