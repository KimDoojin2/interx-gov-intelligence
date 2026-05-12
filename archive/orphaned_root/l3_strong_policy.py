from __future__ import annotations

from interx_engine.core.entities.notice import Notice


class L3StrongPolicy:
    def __init__(
        self,
        high_signal_keywords: list[str] | None = None,
        l3_score_threshold: float = 75.0,
        min_high_signal_hits: int = 2,
    ):
        self.high_signal_keywords = [k.lower() for k in (high_signal_keywords or [])]
        self.l3_score_threshold = l3_score_threshold
        self.min_high_signal_hits = min_high_signal_hits

    def count_high_signals(self, notice: Notice) -> int:
        text = f"{notice.title} {notice.summary} {notice.business_type} {notice.recommended_solution}".lower()
        return sum(1 for kw in self.high_signal_keywords if kw in text)

    def is_l3_strong(self, notice: Notice, fitness_score: float = 0.0) -> bool:
        hits = self.count_high_signals(notice)
        return hits >= self.min_high_signal_hits and fitness_score >= self.l3_score_threshold
