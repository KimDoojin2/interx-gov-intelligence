from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PredictionResult:
    notice_id: str
    site: str
    title: str
    win_probability: float          # 0.0 ~ 1.0
    win_grade: str                  # A / B / C / D
    feature_contributions: Dict[str, float] = field(default_factory=dict)
    # {"fitness_score": 0.35, "budget_억": 0.20, "dday_urgency": 0.15, ...}
    recommended_priority: str = ""  # "즉시투자" / "검토" / "관망" / "제외"


@dataclass
class WinPredictionReport:
    execution_id: str
    predictions: List[PredictionResult] = field(default_factory=list)
    model_version: str = "rule_v1"
    top_opportunities: List[str] = field(default_factory=list)  # notice_id 목록
