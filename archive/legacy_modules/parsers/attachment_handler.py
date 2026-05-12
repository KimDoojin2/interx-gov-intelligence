import os
import aiohttp
import logging
from pathlib import Path

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

class AttachmentHandler:
    def __init__(self):
        # 다운로드 경로: data/attachments/사이트명/공고ID/파일명
        self.base_dir = Path(DATA_DIR) / "attachments"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def download_file(self, session: aiohttp.ClientSession, url: str, site: str, notice_id: str, file_name: str) -> str:
        """비동기로 개별 파일을 다운로드합니다."""
        if not url: 
            return ""
        
        # 파일명에서 특수문자 제거 (저장 오류 방지)
        safe_name = "".join([c for c in file_name if c.isalnum() or c in ' ._-()']).rstrip()
        if not safe_name: safe_name = "attachment_file"
        
        save_path = self.base_dir / site / notice_id
        save_path.mkdir(parents=True, exist_ok=True)
        file_path = save_path / safe_name
        
        # 이미 다운로드된 파일이면 통과 (속도 향상)
        if file_path.exists() and file_path.stat().st_size > 0:
            return str(file_path)

        try:
            async with session.get(url, ssl=False, timeout=15) as response:
                if response.status == 200:
                    content = await response.read()
                    # 간단하게 동기 방식으로 파일 쓰기
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    return str(file_path)
        except Exception as e:
            logger.debug(f"다운로드 실패 [{file_name}]: {e}")
            
        return ""

    async def process_notice(self, notice):
        """하나의 공고에 달린 모든 첨부파일을 다운로드"""
        if not notice.attachment_items:
            return
            
        downloaded_count = 0
        async with aiohttp.ClientSession() as session:
            for att in notice.attachment_items:
                url = att.get("url", "")
                name = att.get("name", "unknown_file")
                
                # 신청서, 양식 등 불필요한 파일 스킵 (선택사항)
                if any(kw in name for kw in ["신청서", "양식", "개인정보"]):
                    att["download_status"] = "skipped"
                    continue
                
                local_path = await self.download_file(session, url, notice.site, notice.notice_id, name)
                
                if local_path:
                    att["local_path"] = local_path
                    att["download_status"] = "downloaded"
                    downloaded_count += 1
                else:
                    att["download_status"] = "failed"
                    
        return downloaded_count
