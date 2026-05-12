import asyncio
import aiohttp
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from urllib.parse import parse_qs, urlparse

from core.models import Notice
from config.settings import USER_AGENT, COLLECTOR_TIMEOUT

logger = logging.getLogger(__name__)

class BaseCrawler(ABC):
    site_key: str = "base"
    base_url: str = ""
    ssl_verify: bool = True

    def __init__(self, max_pages: int = 3):
        self.max_pages = max_pages
        self.headers = {"User-Agent": USER_AGENT}

    async def fetch_html(self, session: aiohttp.ClientSession, url: str) -> str:
        for attempt in range(1, 4):
            try:
                async with session.get(url, headers=self.headers, ssl=self.ssl_verify, timeout=COLLECTOR_TIMEOUT) as response:
                    response.raise_for_status()
                    return await response.text()
            except Exception as e:
                wait_time = (1.2 ** attempt)
                logger.debug(f"[{self.site_key}] fetch retry={attempt} url={url} error={e}")
                await asyncio.sleep(wait_time)
                if attempt == 3:
                    logger.error(f"[{self.site_key}] 3회 재시도 실패: {url}")
                    raise e

    @abstractmethod
    def get_list_url(self, page: int) -> str: ...

    @abstractmethod
    def parse_list_page(self, html: str) -> List[Dict[str, str]]: ...

    @abstractmethod
    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]: ...

    def make_notice_id(self, detail_url: str) -> str:
        try:
            q = parse_qs(urlparse(detail_url).query)
            for key in ["policyNewsId", "pblancId", "biz_no", "ntcId", "id", "seq", "no", "idx"]:
                val = (q.get(key) or [""])[0]
                if val:
                    return f"{self.site_key}-{val}"[:80]
        except Exception:
            pass
        slug = detail_url.rstrip("/").split("/")[-1][:60]
        return f"{self.site_key}-{slug}"

    async def collect(self, execution_id: str) -> List[Notice]:
        notices: List[Notice] = []
        seen_urls = set()
        
        async with aiohttp.ClientSession() as session:
            for page in range(1, self.max_pages + 1):
                list_url = self.get_list_url(page)
                try:
                    html = await self.fetch_html(session, list_url)
                except Exception:
                    break 

                items = self.parse_list_page(html)
                if not items:
                    break

                tasks = []
                for item in items:
                    detail_url = item["detail_url"]
                    if detail_url not in seen_urls:
                        seen_urls.add(detail_url)
                        tasks.append(self.process_detail(session, item, execution_id))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for res in results:
                    if isinstance(res, Notice):
                        notices.append(res)
                        
        return notices

    async def process_detail(self, session: aiohttp.ClientSession, item: Dict[str, str], execution_id: str) -> Optional[Notice]:
        detail_url = item["detail_url"]
        try:
            dhtml = await self.fetch_html(session, detail_url)
            detail = self.parse_detail_page(dhtml, detail_url)
            
            notice = Notice(
                execution_id=execution_id,
                site=self.site_key,
                notice_id=self.make_notice_id(detail_url),
                title=detail.get("title") or item.get("title", ""),
                detail_url=detail_url,
                posted_date=detail.get("posted_date", ""),
                deadline_date=detail.get("deadline_date", ""),
                ministry=detail.get("ministry", ""),
                agency=detail.get("agency", self.site_key),
                summary=detail.get("summary", ""),
                body_text=detail.get("body_text", ""),
                attachment_items=detail.get("attachments", [])
            )
            return notice
        except Exception as e:
            logger.error(f"[{self.site_key}] 상세 페이지 실패 {detail_url}: {e}")
            return None
