from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import yaml

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.core.rules.l3_strong_policy import L3StrongPolicy
from interx_engine.core.rules.priority_scoring_policy import PriorityScoringPolicy


class ScoreNoticesUseCase:
    def __init__(self):
        config_root = Path.cwd() / "configs"

        keyword_profile = {}
        l3_rules = {}
        scoring_conf = {}

        kp_path = config_root / "keywords_profile.yaml"
        if kp_path.exists():
            keyword_profile = yaml.safe_load(kp_path.read_text(encoding="utf-8")) or {}

        l3_path = config_root / "l3_rules.yaml"
        if l3_path.exists():
            l3_rules = yaml.safe_load(l3_path.read_text(encoding="utf-8")) or {}

        sc_path = config_root / "scoring.yaml"
        if sc_path.exists():
            scoring_conf = yaml.safe_load(sc_path.read_text(encoding="utf-8")) or {}

        high_signal = ((keyword_profile.get("policy_keywords") or {}).get("high_signal") or [])
        mapping = keyword_profile.get("solution_mapping") or {}

        thresholds = (l3_rules.get("l3_rules") or {}).get("thresholds") or {}
        gating = (l3_rules.get("l3_rules") or {}).get("gating") or {}

        l3_score_threshold = float(thresholds.get("l3_strong_score", (scoring_conf.get("scoring") or {}).get("l3_threshold", 75)))
        partner_threshold = float(thresholds.get("partner_candidate_score", (scoring_conf.get("scoring") or {}).get("partner_candidate_threshold", 55)))
        min_hits = int(gating.get("min_high_signal_hits", 2))

        self.l3_policy = L3StrongPolicy(
            high_signal_keywords=high_signal,
            l3_score_threshold=l3_score_threshold,
            min_high_signal_hits=min_hits,
        )
        self.scoring_policy = PriorityScoringPolicy(
            solution_mapping=mapping,
            weights=(scoring_conf.get("weights") or {}),
            partner_candidate_threshold=partner_threshold,
        )
        self.partner_threshold = partner_threshold

    def execute(self, notices: List[Notice]) -> Tuple[List[Notice], List[ScoreCard]]:
        score_cards = []

        for notice in notices:
            score_card = self.scoring_policy.calculate(notice)
            notice.l3_strong = "Y" if self.l3_policy.is_l3_strong(notice, score_card.fitness_score) else "N"
            notice.partner_candidate = "Y" if score_card.priority_score >= self.partner_threshold and notice.l3_strong != "Y" else "N"
            score_cards.append(score_card)

        return notices, score_cards
