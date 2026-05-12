"""
사이트별 수집 품질 자동 등급화 (A~F)
평가 기준: 수집건수·L3전환율·예산정보율·P1P2비율
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard

log = logging.getLogger("interx.quality")


def grade_site_quality(
    notices: List[Notice],
    score_cards: List[ScoreCard],
) -> Dict[str, Dict]:
    """
    사이트별 품질 등급 계산.

    Returns:
        {site: {"grade": "A", "score": 72.5, "total": 30, ...}}
    """
    score_map = {s.notice_id: s for s in score_cards}
    buckets   = defaultdict(lambda: {
        "total": 0, "l3": 0, "p1p2": 0,
        "has_budget": 0, "has_deadline": 0,
    })

    for n in notices:
        site = n.site or "unknown"
        b    = buckets[site]
        b["total"] += 1
        if n.l3_strong == "Y":
            b["l3"] += 1
        if n.budget and n.budget not in ("-", ""):
            b["has_budget"] += 1
        if n.deadline_date:
            b["has_deadline"] += 1
        sc = score_map.get(n.notice_id)
        if sc and sc.priority_grade in ("A", "B"):
            b["p1p2"] += 1

    results = {}
    for site, b in buckets.items():
        total = b["total"]
        if total == 0:
            results[site] = {"grade": "F", "score": 0, "total": 0}
            continue

        l3_rate       = b["l3"]          / total
        p1p2_rate     = b["p1p2"]        / total
        budget_rate   = b["has_budget"]  / total
        deadline_rate = b["has_deadline"] / total
        volume_score  = min(total, 50) / 50   # 최대 50건 기준

        # 가중 합산 (100점 만점)
        score = (
            l3_rate       * 30 +
            p1p2_rate     * 25 +
            budget_rate   * 20 +
            deadline_rate * 15 +
            volume_score  * 10
        ) * 100

        if   score >= 70: grade = "A"
        elif score >= 50: grade = "B"
        elif score >= 30: grade = "C"
        elif score >= 10: grade = "D"
        else:             grade = "F"

        results[site] = {
            "grade":        grade,
            "score":        round(score, 1),
            "total":        total,
            "l3_rate":      round(l3_rate * 100, 1),
            "p1p2_rate":    round(p1p2_rate * 100, 1),
            "budget_rate":  round(budget_rate * 100, 1),
        }
        log.debug("[Quality] %-12s → %s (%.1f점, %d건, L3=%.0f%%)",
                  site, grade, score, total, l3_rate * 100)

    return results
