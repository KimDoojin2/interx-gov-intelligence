from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class NoticeCluster:
    cluster_id: str
    notice_ids: List[str]
    representative_title: str   # 가장 높은 fitness 공고 제목
    common_keywords: List[str]  # 공통 positive_keywords
    top_solution: str           # 클러스터 대표 솔루션
    size: int = 0

    def __post_init__(self):
        self.size = len(self.notice_ids)
