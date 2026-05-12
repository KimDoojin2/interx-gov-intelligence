from __future__ import annotations
from typing import Dict, List, Tuple
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.core.entities.recommendation import Recommendation
from interx_engine.core.rules.recommendation_rules import RecommendationRules


class RecommendNoticesUseCase:
    """
    스코어링 결과를 받아 공고별 Recommendation 을 생성한다.
    rule 기반 → 향후 LLM 기반으로 교체 가능 (rules 만 교체하면 됨).
    """

    def __init__(self):
        self.rules = RecommendationRules()

    def execute(
        self,
        notices: List[Notice],
        score_cards: List[ScoreCard],
    ) -> List[Recommendation]:
        score_map: Dict[str, ScoreCard] = {s.notice_id: s for s in score_cards}
        recommendations = []
        for notice in notices:
            score = score_map.get(notice.notice_id)
            if score is None:
                continue
            rec = self.rules.generate(notice, score)
            recommendations.append(rec)
        return recommendations
