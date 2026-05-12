from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ScoreCard:
    execution_id: str
    notice_id: str
    site: str
    fitness_score: float
    priority_score: float
    priority_grade: str  # A / B / C / D
    solution_scores: Dict[str, float] = field(default_factory=dict)
    positive_keywords: List[str] = field(default_factory=list)
    negative_keywords: List[str] = field(default_factory=list)
    industry_score: float = 0.0
