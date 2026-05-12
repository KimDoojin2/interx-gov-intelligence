"""
제주테크노파크 (JEJUTP) 사업공고 수집기
URL: https://www.jejutp.or.kr/board/business
pageNumber=0-based, size=30
"""
from __future__ import annotations

import logging
import re
from typing import List
from urllib.parse import urljoin

log = logging.getLogger("interx.collectors")

from bs4 import BeautifulSoup

from interx_engine.infrastructure.collectors.sites.base_collector import (
    BaseCollector,
    _extract_dates,
    _notice_id,
)
from interx_engine.core.entities.notice import Notice

_BASE = "https://www.jejutp.or.kr"
_DETAIL_ID_RE = re.compile(r"/board/business/(\d+)", re.I)


class JejtpCollector(BaseCollector):
    site_key = "jejutp"
    ministry = "제주특별자치도"
    agency   = "제주테크노파크"
    # pageNumber는 0-based → _page_url에서 page-1 적용
    LIST_URL = (
        "https://www.jejutp.or.kr/board/business"
        "?keyword=&pageNumber={page}&size=30&cate="
    )

    _JSON_API   = "https://www.jejutp.or.kr/board/business/list"
    _DETAIL_TPL = "https://www.jejutp.or.kr/board/business/detail/{anno_id}"

    def _page_url(self, page: int) -> str:
        return self.LIST_URL.format(page=page - 1)

    def collect(self, execution_id: str) -> List[Notice]:
        """JSON REST API 우선, 실패 시 HTML fallback."""
        import time
        import random

        notices: List[Notice] = []
        seen: set = set()

        for page in range(self.max_pages):          # 0-based
            try:
                resp = self._session.get(
                    self._JSON_API,
                    params={"pageNumber": page, "size": 30},
                    headers={
                        **self._headers(),
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/plain, */*",
                    },
                    timeout=self.timeout,
                    verify=self.ssl_verify,
                )
                if resp.status_code != 200:
                    log.warning("[jejutp] JSON API p%d → HTTP %d", page, resp.status_code)
                    break

                data = resp.json()
                items = (
                    data if isinstance(data, list)
                    else (data.get("content") or data.get("list") or data.get("data") or [])
                )
                if not items:
                    log.debug("[jejutp] p%d 공고 없음 → 마지막 페이지", page)
                    break

                for item in items:
                    anno_id = str(item.get("annoId") or item.get("id") or "").strip()
                    title   = (item.get("annoName") or item.get("title") or "").strip()
                    if not anno_id or not title:
                        continue
                    detail = self._DETAIL_TPL.format(anno_id=anno_id)
                    if detail in seen:
                        continue
                    seen.add(detail)
                    deadline = str(item.get("receiptEDate") or "")[:10]
                    posted   = str(item.get("createdDate") or "")[:10]
                    notices.append(self._make_notice(
                        execution_id, title, detail, deadline, posted,
                    ))

                time.sleep(random.uniform(0.3, 0.7))

            except Exception as e:
                log.warning("[jejutp] JSON API 오류 p%d: %s", page, e)
                break

        if notices:
            log.info("[JEJUTP] JSON API %d건 수집", len(notices))
            return self._enrich_notices(notices)

        # JSON API 실패 → HTML fallback
        log.warning("[jejutp] JSON API 0건 → HTML fallback")
        return super().collect(execution_id)

    def _parse_page(self, soup: BeautifulSoup, execution_id: str) -> List[Notice]:
        notices: List[Notice] = []

        # ── 카드/리스트 형태: .board-list li, .list-wrap, ul.notice-list ──────
        items = (
            soup.select("ul.board-list li, ul.notice-list li, "
                        ".list-wrap li, .board_list li, "
                        ".business-list li, .biz-list li")
        )
        if items:
            for li in items:
                a = li.find("a", href=True)
                if not a:
                    continue
                title = a.get_text(" ", strip=True)
                if not title or len(title) < 3:
                    continue
                href   = a["href"]
                if "javascript" in href.lower():
                    continue
                detail = href if href.startswith("http") else urljoin(_BASE, href)
                text   = li.get_text(" ", strip=True)
                dates  = _extract_dates(text)
                notices.append(self._make_notice(
                    execution_id, title, detail,
                    dates[-1] if dates else "",
                    dates[0]  if len(dates) >= 2 else "",
                ))
            return notices

        # ── 테이블 형태 ──────────────────────────────────────────────────────
        tbody = soup.find("tbody")
        rows  = tbody.find_all("tr") if tbody else soup.select("table tr")
        for tr in rows:
            a = tr.find("a", href=True)
            if not a:
                continue
            title = a.get_text(" ", strip=True)
            if not title or len(title) < 3:
                continue
            href   = a["href"]
            if "javascript" in href.lower():
                # onclick이나 data-id 에서 idx 추출 시도
                onclick = a.get("onclick", "") or tr.get("onclick", "")
                m = re.search(r"(\d+)", onclick)
                if m:
                    detail = f"{_BASE}/board/business/{m.group(1)}"
                else:
                    continue
            else:
                detail = href if href.startswith("http") else urljoin(_BASE, href)
            text   = tr.get_text(" ", strip=True)
            dates  = _extract_dates(text)
            notices.append(self._make_notice(
                execution_id, title, detail,
                dates[-1] if dates else "",
                dates[0]  if len(dates) >= 2 else "",
            ))

        # ── div/article 기반 레이아웃 ─────────────────────────────────────
        if not notices:
            for a in soup.select(
                "a[href*='/board/business/'], "
                "a[href*='business?'], "
                ".post-item a, article a, .card a"
            ):
                title = a.get_text(" ", strip=True)
                if not title or len(title) < 3:
                    continue
                href = a.get("href", "")
                if not href or "javascript" in href.lower():
                    continue
                detail = href if href.startswith("http") else urljoin(_BASE, href)
                container = (
                    a.find_parent("article")
                    or a.find_parent("li")
                    or a.find_parent("div")
                    or a.parent
                )
                text  = container.get_text(" ", strip=True) if container else title
                dates = _extract_dates(text)
                notices.append(Notice(
                    execution_id  = execution_id,
                    site          = self.site_key,
                    notice_id     = _notice_id(self.site_key, detail),
                    title         = title,
                    detail_url    = detail,
                    notice_link   = detail,
                    deadline_date = dates[-1] if dates else "",
                    posted_date   = dates[0]  if len(dates) >= 2 else "",
                    ministry      = self.ministry,
                    agency        = self.agency,
                ))

        return notices
