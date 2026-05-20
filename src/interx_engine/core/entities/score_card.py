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
    # ── v3 고도화 필드 ──────────────────────────────────────────────────────
    keyword_density: float = 0.0        # 키워드 밀도 (0~1)
    budget_score: float = 0.0           # 예산 구간 점수 (0~10)
    notice_type: str = ""               # 공고 유형 (실증/R&D/바우처/인력/기타)
    type_multiplier: float = 1.0        # 유형별 보정 배율
    tfidf_similarity: float = 0.0       # InterX 프로필 코사인 유사도 (0~1)
    urgency_boost: float = 0.0          # 긴급도 × 등급 교차 부스트
    combo_keywords: List[str] = field(default_factory=list)  # 히트한 콤보 키워드 쌍
