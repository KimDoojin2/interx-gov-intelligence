from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class Recommendation:
    notice_id: str
    priority_grade: str        # P1 / P2 / P3 / P4
    confidence: str            # HIGH / MEDIUM / LOW
    reason: str                # 왜 이 공고인가
    action: str                # 무엇을 해야 하는가
    partner_type: str          # 어떤 파트너가 필요한가
    top_solutions: List[str]   # 점수 상위 솔루션 목록
    action_deadline: str       # 마감일 - N일
    tags: List[str] = field(default_factory=list)
