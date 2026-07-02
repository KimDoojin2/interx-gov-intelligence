from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector, _extract_dates,
)
from interx_engine.core.entities.notice import Notice

# 대전테크노파크 — djtp.or.kr
# (구 ttp.kr 도메인은 TLS 인증서 오류로 더 이상 접근 불가)
_BASE = "https://www.djtp.or.kr"
_PMS  = "https://pms.dips.or.kr"

# 목록 페이지: nPage 파라미터로 페이지네이션
_LIST_URL = _BASE + "/pbanc?mid=a20101000000&nPage={page}"

# 공고 식별: pbanc_no= 파라미터 포함 링크
_PBANC_RE = re.compile(r"pbanc_no=", re.I)

# 제목 클래스 후보
_TITLE_CLS = re.compile(r"(tit|title|subject|name|ann)", re.I)


class TtpCollector(BaseCollector):
    """
    대전테크노파크 (djtp.or.kr) 공고 수집기.
    목록: https://www.djtp.or.kr/pbanc?mid=a20101000000&nPage={page}
    상세: https://pms.dips.or.kr/sso/business.jsp?gubun=pbancView&pbanc_no={id}
    """
    site_key     = "ttp"
    agency       = "대전테크노파크"
    LIST_URL     = _LIST_URL
    fetch_detail = False  # 상세 URL이 SSO(pms.dips.or.kr) JS 리다이렉트 → body 추출 불가

    def _page_url(self, page: int) -> str:
        return self.LIST_URL.format(page=page)

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices: List[Notice] = []
        seen: set = set()

        # pbanc_no= 파라미터가 있는 공고 상세 링크 수집
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not _PBANC_RE.search(href):
                continue

            full = href if href.startswith("http") else urljoin(_BASE, href)
            if full in seen:
                continue
            seen.add(full)

            # 행 컨테이너에서 제목 추출
            row = (a.find_parent("tr") or a.find_parent("li")
                   or a.find_parent("div", class_=True) or a.parent)
            title = self._extract_title(a, row)
            if not title or len(title) < 3:
                continue

            text  = row.get_text(" ", strip=True) if row else title
            dates = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, full,
                dates[-1] if dates else "",
                dates[0]  if len(dates) >= 2 else "",
            ))

        # fallback: 일반 테이블 파싱
        if not notices:
            notices = self._parse_table(soup, execution_id, _BASE)

        return notices

    # pbanc_no 형식: 2026-01-0073 (연도-월-일련번호, 마지막 숫자는 정확히 4자리)
    # \d{4,} 는 greedy 매칭으로 뒤에 붙은 연도까지 삼켜버리므로 \d{4} 로 고정
    _PBANC_NO_RE = re.compile(r"^\d{4}-\d{2}-\d{4}")

    @classmethod
    def _clean_title(cls, title: str) -> str:
        """pbanc_no 접두어(2026-01-0073)가 붙어 있으면 제거한다."""
        return cls._PBANC_NO_RE.sub("", title).strip()

    @classmethod
    def _extract_title(cls, a_tag, row) -> str:
        """행 컨테이너에서 공고 제목을 추출한다."""
        if row is None:
            return cls._clean_title(a_tag.get_text(strip=True))

        # 제목 클래스가 있는 태그 우선
        title_tag = row.find(class_=_TITLE_CLS)
        if title_tag:
            txt = cls._clean_title(title_tag.get_text(strip=True))
            if len(txt) >= 5:
                return txt

        # 가장 긴 링크 텍스트를 제목으로
        texts = [
            cls._clean_title(a2.get_text(strip=True))
            for a2 in row.find_all("a")
            if len(a2.get_text(strip=True)) >= 5
        ]
        if texts:
            return max(texts, key=len)

        return cls._clean_title(a_tag.get_text(strip=True))
