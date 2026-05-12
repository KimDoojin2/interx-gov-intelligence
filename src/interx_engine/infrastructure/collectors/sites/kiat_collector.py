from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from interx_engine.infrastructure.collectors.sites.base_collector import (
    PlaywrightBaseCollector, _extract_dates,
)
from interx_engine.core.entities.notice import Notice

_BASE   = "https://www.kiat.or.kr"
_BOARD  = 90
_MENU   = "b159c9dac684471b87256f1e25404f5e"

# 상세 URL 템플릿
_DETAIL_TPL = (
    _BASE + "/front/board/boardContentsViewPage.do"
    "?contents_id={uid}&board_id={board}&MenuId={menu}"
)

# onclick 패턴 — 한국 정부 사이트에서 흔히 쓰이는 JS 함수명들을 모두 포함
_JS_CALL_RE = re.compile(
    r"(?:contentsView|fn_view|fnView|goView|viewContents|boardView|fn_detail|goDetail|goPagePost)"
    r"\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
    re.I,
)
# goPagePost 3번째 인자(detailUrl)에서 직접 URL 추출
_GO_PAGE_POST_RE = re.compile(
    r"goPagePost\s*\(\s*['\"][^'\"]+['\"].*?['\"]([^'\"]*boardContentsViewPage[^'\"]*)['\"]",
    re.I,
)
# 일반 JS 호출 fallback: 첫 번째 문자열 인자 추출
_JS_ANY_RE = re.compile(r"\(\s*['\"]([^'\"]{3,})['\"]", re.I)

# 쿼리 파라미터에서 ID 추출용 키
_ID_PARAM_KEYS = ["contents_id", "contentsId", "seq", "brdSn", "nttSn", "ancmId", "id"]


def _extract_uid_from_url(url: str) -> str:
    """URL 쿼리스트링에서 글 ID 추출."""
    try:
        q = parse_qs(urlparse(url).query)
        for key in _ID_PARAM_KEYS:
            val = (q.get(key) or [""])[0]
            if val:
                return val
    except Exception:
        pass
    return ""


def _build_detail_url(href: str, onclick: str, base: str = _BASE) -> str:
    """href/onclick 으로부터 상세 URL 생성."""
    # 1) 직접 href (javascript: 아님)
    if href and not href.lower().startswith("javascript"):
        full = href if href.startswith("http") else urljoin(base, href)
        return full

    # 2) javascript:contentsView('UUID') 형태 href에서 UID 추출
    for source in (href, onclick):
        if not source:
            continue
        # goPagePost 3번째 인자에서 직접 URL 추출
        mp = _GO_PAGE_POST_RE.search(source)
        if mp:
            path = mp.group(1)
            return path if path.startswith("http") else urljoin(base, path)
        # 알려진 함수 패턴
        m = _JS_CALL_RE.search(source)
        if m:
            uid = m.group(1).strip()
            return _DETAIL_TPL.format(uid=uid, board=_BOARD, menu=_MENU)
        # 일반 JS 호출 첫 인자 fallback
        m2 = _JS_ANY_RE.search(source)
        if m2:
            uid = m2.group(1).strip()
            if re.match(r'^[a-zA-Z0-9\-_]{8,}$', uid):
                return _DETAIL_TPL.format(uid=uid, board=_BOARD, menu=_MENU)

    return ""


class KiatCollector(PlaywrightBaseCollector):
    site_key = "kiat"
    ministry = "산업통상자원부"
    agency   = "한국산업기술진흥원"
    LIST_URL = (
        _BASE + "/front/board/boardContentsListPage.do"
        "?board_id={board}&MenuId={menu}&pageIndex={{page}}".format(board=_BOARD, menu=_MENU)
    )

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices = []

        # 1) tbody tr 기반 파싱
        for tr in soup.select("table tbody tr, .board-list tbody tr, tbody tr"):
            tds = tr.find_all(["td", "th"])
            if len(tds) < 2:
                continue

            # 링크 요소 탐색 — td 순서 불문하고 첫 번째 유효 링크 사용
            a = None
            for td in tds:
                candidate = td.find("a")
                if candidate:
                    # 너무 짧은 텍스트(번호, 날짜 등)는 스킵
                    txt = candidate.get_text(strip=True)
                    if len(txt) >= 3:
                        a = candidate
                        break

            if not a:
                a = tr.find("a")
            if not a:
                continue

            title = a.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            href    = (a.get("href") or "").strip()
            onclick = (a.get("onclick") or tr.get("onclick") or "").strip()

            detail = _build_detail_url(href, onclick)
            if not detail:
                continue

            row_text = tr.get_text(" ", strip=True)
            dates    = _extract_dates(row_text)
            # dates[0]=가장 이른 날짜(등록일), dates[-1]=가장 늦은 날짜(마감일)
            posted   = dates[0]  if dates else ""
            deadline = dates[-1] if len(dates) >= 2 else (dates[0] if dates else "")

            notices.append(self._make_notice(
                execution_id, title, detail, deadline, posted,
            ))

        # 2) href 직접 탐색 fallback (table 구조가 없는 경우)
        if not notices:
            notices = self._fallback_link_parse(soup, execution_id)

        return notices

    def _fallback_link_parse(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        """table 구조 없을 때 — 상세 URL 패턴 링크 직접 수집."""
        notices = []
        seen: set = set()

        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href or href.lower().startswith("javascript"):
                continue
            # KIAT 상세 URL 패턴 확인
            if "boardContentsViewPage" not in href and "contents_id" not in href:
                continue
            full = href if href.startswith("http") else urljoin(_BASE, href)
            if full in seen:
                continue
            seen.add(full)

            title = a.get_text(strip=True)
            if not title or len(title) < 3:
                # 부모 요소에서 제목 추출 시도
                parent = a.find_parent(["li", "tr", "div"])
                if parent:
                    title = parent.get_text(" ", strip=True)[:100].strip()
            if not title:
                continue

            row_text = a.find_parent(["tr", "li", "div"]) or a
            text = row_text.get_text(" ", strip=True) if hasattr(row_text, "get_text") else ""
            dates = _extract_dates(text)

            notices.append(self._make_notice(
                execution_id, title, full,
                dates[-1] if len(dates) >= 2 else (dates[0] if dates else ""),
                dates[0]  if dates else "",
            ))

        return notices
