from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class Partner:
    partner_id: str
    name: str
    solutions: List[str]   # ["ManufacturingDT", "QualityAI"]
    keywords: List[str]    # ["디지털트윈", "품질"]
    tier: str              # TIER1 / TIER2 / TIER3
    contact: str = ""
    note: str = ""
    match_score: float = 0.0  # 공고 매칭 시 채워짐
