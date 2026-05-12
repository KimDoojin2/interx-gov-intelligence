from __future__ import annotations

import logging
from typing import List, Tuple

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.core.rules.l3_strong_policy import L3StrongPolicy
from interx_engine.core.rules.priority_scoring_policy import PriorityScoringPolicy

log = logging.getLogger("interx.score")


class ScoreNoticesUseCase:
    """
    1단계: L3StrongPolicy — 키워드 기반 사전 필터 (빠른 후보 선별)
    2단계: PriorityScoringPolicy — fitness/priority 전체 계산 + notice.l3_strong 확정
    """

    def __init__(self):
        self.l3_policy = L3StrongPolicy()
        self.scoring_policy = PriorityScoringPolicy()

    def execute(self, notices: List[Notice]) -> Tuple[List[Notice], List[ScoreCard]]:
        for notice in notices:
            if self.l3_policy.is_l3_strong(notice):
                notice.l3_strong = "Y"

        score_cards = [self.scoring_policy.calculate(n) for n in notices]
        return notices, score_cards
