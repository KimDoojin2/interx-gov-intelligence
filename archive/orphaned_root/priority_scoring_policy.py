from __future__ import annotations

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard


class PriorityScoringPolicy:
    def __init__(
        self,
        solution_mapping: dict[str, list[str]] | None = None,
        weights: dict[str, float] | None = None,
        partner_candidate_threshold: float = 55.0,
    ):
        self.solution_mapping = solution_mapping or {}
        self.weights = weights or {
            "manufacturing_dt": 15,
            "recipe_ai": 15,
            "quality_ai": 15,
            "inspection_ai": 15,
            "safety_ai": 10,
            "gen_ai": 10,
            "infra_ds": 10,
            "partner_fit": 10,
        }
        self.partner_candidate_threshold = partner_candidate_threshold

    def _count_hits(self, text: str, keywords: list[str]) -> int:
        text = text.lower()
        return sum(1 for kw in keywords if kw.lower() in text)

    def calculate(self, notice: Notice) -> ScoreCard:
        text = f"{notice.title} {notice.summary} {notice.business_type} {notice.recommended_solution}".lower()

        score = 0.0
        # 솔루션 카테고리별 점수
        for cat, kws in self.solution_mapping.items():
            hits = self._count_hits(text, kws)
            if hits <= 0:
                continue
            w = float(self.weights.get(cat, 10))
            score += min(w, hits * (w / 3.0))

        # 파트너 시그널 가점
        partner_hints = ["실증", "컨소시엄", "수요기업", "도입", "구축", "현장"]
        partner_hits = self._count_hits(text, partner_hints)
        if partner_hits > 0:
            score += min(float(self.weights.get("partner_fit", 10)), partner_hits * 3.0)

        fitness = round(min(100.0, score), 1)
        priority = fitness
        pipeline = round(min(100.0, fitness * 0.9), 1)

        if priority >= 80:
            priority_grade = "P1"
        elif priority >= 65:
            priority_grade = "P2"
        elif priority >= 50:
            priority_grade = "P3"
        else:
            priority_grade = "P4"

        if pipeline >= 80:
            pipeline_grade = "HIGH"
        elif pipeline >= 60:
            pipeline_grade = "MEDIUM"
        else:
            pipeline_grade = "LOW"

        return ScoreCard(
            execution_id=notice.execution_id,
            notice_id=notice.notice_id,
            title=notice.title,
            site=notice.site,
            fitness_score=fitness,
            priority_score=priority,
            priority_grade=priority_grade,
            pipeline_score=pipeline,
            pipeline_grade=pipeline_grade,
        )
