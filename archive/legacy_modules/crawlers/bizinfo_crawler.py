from bs4 import BeautifulSoup
import re
from typing import List, Dict, Any

from crawlers.base import BaseCrawler

class BizinfoCrawler(BaseCrawler):
    site_key = "bizinfo"
    base_url = "https://www.bizinfo.go.kr"

    def get_list_url(self, page: int) -> str:
        return f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/list.do?pageIndex={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        
        for a in soup.select("a[href]"):
            href = (a.get("href") or "").strip()
            title = a.get_text(" ", strip=True)
            
            if "list.do" in href or "pageIndex" in href:
                continue
            if "selectBIZA200Detail.do" in href or "policyNewsId=" in href:
                full_url = f"{self.base_url}{href}" if href.startswith("/") else href
                items.append({"title": title, "detail_url": full_url})
                
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        body_text = soup.get_text(" ", strip=True)
        
        title_el = soup.select_one(".view-title, h3.title, .tit")
        title = title_el.get_text(strip=True) if title_el else ""
        
        return {
            "title": title,
            "body_text": body_text,
            "agency": "기업마당",
        }
