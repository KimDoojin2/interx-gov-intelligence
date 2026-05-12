from __future__ import annotations
from typing import List
from interx_engine.application.ports.notice_collector_port import NoticeCollectorPort
from interx_engine.core.entities.notice import Notice

class NtisCollector(NoticeCollectorPort):
    def __init__(self, max_pages: int = 1, timeout: int = 12):
        self.max_pages = max_pages
        self.timeout = timeout

    def collect(self, execution_id: str) -> List[Notice]:
        # 스캐폴드: Colab 환경 이슈로 NTIS 실수집은 별도 런타임에서 진행
        return []
