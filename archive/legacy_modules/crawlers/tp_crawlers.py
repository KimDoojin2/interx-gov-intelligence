from bs4 import BeautifulSoup
from typing import List, Dict, Any
from crawlers.base import BaseCrawler

class BoardEsCrawler(BaseCrawler):
    """board.es 기반 테크노파크 공통 수집기 (초간단 구조)"""
    bid: str = "0001"
    mid_path: str = ""
    
    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/board.es?mid={self.mid_path}&bid={self.bid}&nPage={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        items = []
        for a in soup.select("table tbody tr td a, td.title a, td.subject a"):
            href = a.get("href", "").strip()
            title = a.get_text(" ", strip=True)
            if len(title) > 3 and "board.es" in href:
                full_url = f"{self.base_url}{href}" if href.startswith("/") else href
                items.append({"title": title, "detail_url": full_url})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        body_text = soup.get_text(" ", strip=True)
        
        title_el = soup.select_one(".view-title, .title, .subject")
        title = title_el.get_text(strip=True) if title_el else ""
        
        return {
            "title": title,
            "body_text": body_text[:1500], # 속도를 위해 앞부분 요약만 추출
            "agency": self.site_key.upper()
        }

# 💡 위 공통 클래스를 상속받아 주소만 바꿔주면 끝!
class DjtpCrawler(BoardEsCrawler):
    site_key = "djtp"
    base_url = "https://www.djtp.or.kr"
    mid_path = "a10401000000"

class JntpCrawler(BoardEsCrawler):
    site_key = "jntp"
    base_url = "https://www.jntp.or.kr"
    mid_path = "a10201000000"
    ssl_verify = False # SSL 접속 거부 완벽 우회!
