"""
전국 테크노파크 12개 사이트 수집기 — 단일 파일 통합
각 테크노파크는 게시판 구조가 대동소이하므로 _TechnoBaseCollector 공통 클래스를 상속.

사이트별 특이사항은 _parse_page()를 오버라이드하여 처리.
"""
from __future__ import annotations

import logging
import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector,
    _extract_dates,
    _notice_id,
)
from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.collectors")

# ── 페이지네이션 / 비공고 제목 필터 패턴 ──
_PAGINATION_TITLE_RE = re.compile(
    r'^"?\d+\s*페이지"?$|'                                       # "443 페이지", 11 페이지
    r"^(처음|이전|다음|마지막|prev|next|first|last)\s*페이지?$|"
    r"^(처음|이전|다음|마지막|prev|next|first|last)$|"
    r"^[<>«»‹›]+$|^\[?\d+\]?$|^\.{2,}$",
    re.I,
)

# ── 페이지네이션 URL 패턴 (robot=Y 등) ──
_PAGINATION_URL_RE = re.compile(r"robot=Y|page=\d+$", re.I)


# ═══════════════════════════════════════════════════════════════════════════════
#  공통 파싱 로직 — 테크노파크 게시판 범용
# ═══════════════════════════════════════════════════════════════════════════════

class _TechnoBaseCollector(BaseCollector):
    """테크노파크 공통 베이스. 대부분 table/tbody 또는 li 기반 게시판."""
    BASE_URL: str = ""          # 서브클래스에서 오버라이드
    LINK_PATTERN: str = ""      # href에 포함되어야 하는 패턴 (선택)

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices: List[Notice] = []
        seen: set = set()
        base = self.BASE_URL

        # ── 1) 특정 link 패턴이 있는 경우 우선 ──
        if self.LINK_PATTERN:
            for a in soup.find_all("a", href=True):
                href = (a.get("href") or "").strip()
                if self.LINK_PATTERN not in href:
                    continue
                full = href if href.startswith("http") else urljoin(base, href)
                if full in seen:
                    continue

                title = a.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                # ── 페이지네이션 / 네비게이션 필터 ──
                # 1) 제목이 페이지네이션 텍스트 ("443 페이지", "11", "다음" 등)
                if _PAGINATION_TITLE_RE.match(title.strip()):
                    continue
                # 2) URL에 robot=Y 또는 mode=view 없이 page= 만 있는 건 페이지네이션
                if _PAGINATION_URL_RE.search(href) and "mode=view" not in href:
                    continue
                # 3) 공고 상세 URL이 아닌 네비게이션 링크 (mode=view, board_seq 없음)
                if "mode=view" not in href and "board_seq" not in href \
                        and "seq=" not in href and "idx=" not in href \
                        and "no=" not in href and "wr_id=" not in href \
                        and "nttId=" not in href:
                    # 실제 게시글 URL 식별자가 하나도 없으면 네비게이션 링크
                    continue

                seen.add(full)
                row = a.find_parent("tr") or a.find_parent("li") or a.parent
                text = row.get_text(" ", strip=True) if row else title
                dates = _extract_dates(text)
                notices.append(self._make_notice(
                    execution_id, title, full,
                    dates[-1] if dates else "",
                    dates[0] if len(dates) >= 2 else "",
                ))
            if notices:
                return notices

        # ── 2) 테이블 기반 파싱 ──
        notices = self._parse_table(soup, execution_id, base)
        if notices:
            return notices

        # ── 3) li 기반 파싱 ──
        for li in soup.select(
            "ul.board-list li, ul.notice-list li, .list-wrap li, "
            ".board_list li, .business-list li, .biz-list li, "
            ".bbsList li, .dataList li"
        ):
            a = li.find("a", href=True)
            if not a:
                continue
            title = a.get_text(" ", strip=True)
            if not title or len(title) < 3:
                continue
            href = a["href"]
            if "javascript" in href.lower():
                continue
            detail = href if href.startswith("http") else urljoin(base, href)
            if detail in seen:
                continue
            seen.add(detail)
            text = li.get_text(" ", strip=True)
            dates = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0] if len(dates) >= 2 else "",
            ))

        # ── 4) div/article fallback ──
        if not notices:
            for a in soup.select("a[href]"):
                title = a.get_text(" ", strip=True)
                if not title or len(title) < 5:
                    continue
                href = a.get("href", "")
                if not href or "javascript" in href.lower() or href == "#":
                    continue
                # 공고성 링크 필터 (board, view, detail, read 등)
                if not re.search(r"(board|view|detail|read|notice|bbs|seq|idx|no=)", href, re.I):
                    continue
                detail = href if href.startswith("http") else urljoin(base, href)
                if detail in seen:
                    continue
                seen.add(detail)
                container = a.find_parent("li") or a.find_parent("div") or a.parent
                text = container.get_text(" ", strip=True) if container else title
                dates = _extract_dates(text)
                notices.append(self._make_notice(
                    execution_id, title, detail,
                    dates[-1] if dates else "",
                    dates[0] if len(dates) >= 2 else "",
                ))

        return notices


# ═══════════════════════════════════════════════════════════════════════════════
#  개별 테크노파크 수집기 (12개)
# ═══════════════════════════════════════════════════════════════════════════════

class SeoultpCollector(_TechnoBaseCollector):
    """서울테크노파크 — seoultp.or.kr (javascript:goBoardView → POST 기반, 정적 URL 불가)"""
    site_key      = "seoultp"
    agency        = "서울테크노파크"
    ministry      = "서울특별시"
    fetch_detail  = False  # 상세 URL이 javascript: → HTTP URL 변환 불가
    BASE_URL = "https://seoultp.or.kr"
    LIST_URL = "https://seoultp.or.kr/user/nd19746.do?page={page}"

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        """javascript:goBoardView 호출에서 공고 ID 추출 → 목록URL로 대체"""
        notices: List[Notice] = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "goBoardView" not in href:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            # 목록 페이지 URL을 detail_url로 사용 (POST 기반이라 직접 링크 불가)
            detail = self.LIST_URL.format(page=1)
            row = a.find_parent("tr") or a.find_parent("li") or a.parent
            text = row.get_text(" ", strip=True) if row else title
            dates = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0] if len(dates) >= 2 else "",
            ))
        if not notices:
            return super()._parse_page(soup, execution_id)
        return notices


class GtpCollector(_TechnoBaseCollector):
    """경기테크노파크 — gtp.or.kr"""
    site_key = "gtp"
    agency   = "경기테크노파크"
    ministry = "경기도"
    BASE_URL = "https://www.gtp.or.kr"
    LIST_URL = "https://www.gtp.or.kr/front/user/archBoardList.do?ARCH_ID=business&page={page}"
    LINK_PATTERN = "archBoardView"


class GdtpCollector(_TechnoBaseCollector):
    """경기대진테크노파크 — gdtp.or.kr"""
    site_key = "gdtp"
    agency   = "경기대진테크노파크"
    ministry = "경기도"
    BASE_URL = "https://www.gdtp.or.kr"
    LIST_URL = "https://www.gdtp.or.kr/board/announcement?page={page}"


class ItpCollector(_TechnoBaseCollector):
    """인천테크노파크 — itp.or.kr"""
    site_key = "itp"
    agency   = "인천테크노파크"
    ministry = "인천광역시"
    BASE_URL = "https://www.itp.or.kr"
    LIST_URL = "https://www.itp.or.kr/intro.jsp?mid=IT010101&page={page}"
    LINK_PATTERN = "mid=IT010101"


class GwtpCollector(_TechnoBaseCollector):
    """강원테크노파크 — gwtp.or.kr (HTTP only — detail 페이지 404 반환하므로 enrich 비활성)"""
    site_key = "gwtp"
    agency   = "강원테크노파크"
    ministry = "강원특별자치도"
    fetch_detail = False   # 상세 페이지 URL 전부 404 반환 (2025-05 확인)
    BASE_URL = "http://www.gwtp.or.kr"
    LIST_URL = "http://www.gwtp.or.kr/gwtp/bbsNew_list.php?code=sub01b&keyvalue=sub01&startPage={page}"
    LINK_PATTERN = "bbsNew_view"

    def _page_url(self, page: int) -> str:
        """강원TP는 startPage=0,30,60 방식 페이지네이션 (page 1→0, 2→30, 3→60)"""
        return self.LIST_URL.format(page=(page - 1) * 30)

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        """gwtp detail URL에 || 접미사가 붙어 URL 인코딩 시 404 → 제거"""
        notices = super()._parse_page(soup, execution_id)
        for n in notices:
            if n.detail_url:
                # Base64 bbs_data에 || 붙는 문제 제거
                cleaned = re.sub(r'\|+$', '', n.detail_url)
                n.detail_url = cleaned
                n.notice_link = cleaned
        return notices


class SjtpCollector(_TechnoBaseCollector):
    """세종테크노파크 — sjtp.or.kr (그누보드 기반)"""
    site_key = "sjtp"
    agency   = "세종테크노파크"
    ministry = "세종특별자치시"
    BASE_URL = "https://sjtp.or.kr"
    LIST_URL = "https://sjtp.or.kr/bbs/board.php?bo_table=business01&page={page}"
    LINK_PATTERN = "wr_id="  # 그누보드: 개별 게시글만 매칭 (pagination 제외)


class CbtpCollector(_TechnoBaseCollector):
    """충북테크노파크 — cbtp.or.kr (HTTP→HTTPS 리다이렉트, SSL DH_KEY_TOO_SMALL)
    WeakSSLAdapter로 @SECLEVEL=1 설정하여 약한 DH 키 허용.
    응답이 EUC-KR 인코딩이므로 디코딩 보정 필요.
    """
    site_key    = "cbtp"
    agency      = "충북테크노파크"
    ministry    = "충청북도"
    ssl_verify  = False
    BASE_URL    = "https://www.cbtp.or.kr"
    LIST_URL    = "https://www.cbtp.or.kr/index.php?control=bbs&board_id=saup_notice&lm_uid=387&page={page}"
    LINK_PATTERN = "board_id=saup_notice"

    def _build_session(self):
        """SSL @SECLEVEL=1 어댑터로 DH_KEY_TOO_SMALL 우회."""
        import ssl
        from requests.adapters import HTTPAdapter
        from urllib3.util.ssl_ import create_urllib3_context

        class _WeakSSLAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                ctx = create_urllib3_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
                kwargs['ssl_context'] = ctx
                return super().init_poolmanager(*args, **kwargs)

        session = super()._build_session()
        session.mount('https://', _WeakSSLAdapter())
        return session

    def _get(self, url: str, **kwargs):
        """EUC-KR 인코딩 보정 + 약한 SSL 사용."""
        resp = self._session.get(
            url,
            headers=self._headers(),
            timeout=self.timeout,
            verify=False,
            **kwargs,
        )
        resp.raise_for_status()
        # CBTP는 EUC-KR 인코딩 사용 — 인코딩 보정
        ct = resp.headers.get('content-type', '').lower()
        if 'euc-kr' in ct or 'cp949' in ct:
            resp.encoding = 'euc-kr'
        elif resp.encoding is None or resp.encoding == 'ISO-8859-1':
            resp.encoding = 'euc-kr'
        return resp


class CtpCollector(_TechnoBaseCollector):
    """충남테크노파크 — ctp.or.kr"""
    site_key = "ctp"
    agency   = "충남테크노파크"
    ministry = "충청남도"
    BASE_URL = "https://www.ctp.or.kr"
    LIST_URL = "https://www.ctp.or.kr/business/data.do?page={page}"


class BtpCollector(_TechnoBaseCollector):
    """부산테크노파크 — btp.or.kr"""
    site_key = "btp"
    agency   = "부산테크노파크"
    ministry = "부산광역시"
    BASE_URL = "https://www.btp.or.kr/kor/CMS/Board/Board.do"
    LIST_URL = "https://www.btp.or.kr/kor/CMS/Board/Board.do?mCode=MN013&page={page}"
    LINK_PATTERN = "mCode=MN013"

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        """BTP 커스텀 파싱: mode=view 링크만, 제목 중복(titleHover+subjectWr) 제거."""
        notices: List[Notice] = []
        seen: set = set()

        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if "mode=view" not in href or "board_seq" not in href:
                continue

            full = href if href.startswith("http") else urljoin(self.BASE_URL, href)
            if full in seen:
                continue
            seen.add(full)

            # 제목: span.subjectWr 또는 첫 번째 span (중복 방지)
            span = a.select_one("span.subjectWr") or a.select_one("span")
            title = span.get_text(strip=True) if span else a.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            row = a.find_parent("tr") or a.find_parent("li") or a.parent
            text = row.get_text(" ", strip=True) if row else title
            dates = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, full,
                dates[-1] if dates else "",
                dates[0] if len(dates) >= 2 else "",
            ))

        return notices


class UtpCollector(_TechnoBaseCollector):
    """울산테크노파크 — utp.or.kr (공지사항 게시판 = 사업공고 포함, 2843건+)"""
    site_key = "utp"
    agency   = "울산테크노파크"
    ministry = "울산광역시"
    BASE_URL = "https://www.utp.or.kr"
    LIST_URL = "https://www.utp.or.kr/board/board.php?bo_table=sub0501&menu_group=4&sno=0401&page={page}"
    LINK_PATTERN = "wr_id="  # 그누보드: 개별 게시글만 매칭 (pagination/메뉴 제외)


class GntpCollector(_TechnoBaseCollector):
    """경남테크노파크 — gntp.or.kr (SPA 기반 — JS 렌더링 후 공고 로드)
    HTML fallback: applyInfo 또는 테이블/리스트 기반 파싱
    """
    site_key = "gntp"
    agency   = "경남테크노파크"
    ministry = "경상남도"
    BASE_URL = "https://www.gntp.or.kr"
    LIST_URL = "https://www.gntp.or.kr/biz/apply?page={page}"
    LINK_PATTERN = ""  # SPA → LINK_PATTERN 비활성, 범용 파서로 처리

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        """GNTP SPA: applyInfo 링크 또는 범용 링크 탐색"""
        notices: List[Notice] = []
        seen: set = set()

        # 1) applyInfo 링크 우선
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if "applyInfo" in href or "bizView" in href or "apply/" in href:
                full = href if href.startswith("http") else urljoin(self.BASE_URL, href)
                if full in seen:
                    continue
                title = a.get_text(strip=True)
                if not title or len(title) < 3:
                    continue
                if _PAGINATION_TITLE_RE.match(title.strip()):
                    continue
                seen.add(full)
                row = a.find_parent("tr") or a.find_parent("li") or a.find_parent("div") or a.parent
                text = row.get_text(" ", strip=True) if row else title
                dates = _extract_dates(text)
                notices.append(self._make_notice(
                    execution_id, title, full,
                    dates[-1] if dates else "",
                    dates[0] if len(dates) >= 2 else "",
                ))

        if notices:
            return notices

        # 2) 범용 파서 fallback
        return super()._parse_page(soup, execution_id)


class PtpCollector(_TechnoBaseCollector):
    """포항테크노파크 — ptp.or.kr (javascript:void(0) → JS렌더링, 정적 URL 불가)"""
    site_key      = "ptp"
    agency        = "포항테크노파크"
    ministry      = "경상북도"
    fetch_detail  = False  # 상세 URL이 javascript:void(0) → HTTP URL 변환 불가
    BASE_URL = "https://www.ptp.or.kr"
    LIST_URL = "https://www.ptp.or.kr/main/board/index.do?menu_idx=116&manage_idx=15&page={page}"
