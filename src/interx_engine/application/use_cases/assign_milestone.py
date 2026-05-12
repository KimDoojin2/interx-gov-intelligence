"""
BD 마일스톤 자동 배정 Use Case

배정 우선순위 (높음 → 낮음):
  M05  즉시 컨셉 제안   — L3강공고=Y + D-day ≤ 14 (A/B등급) 또는 D-day ≤ 7 (전등급)
  M01  공고 발굴·등록   — L3강공고=Y (기본)
  P01  파트너 후보 발굴  — 파트너후보=Y (BD 트랙과 별개로 동시 적용 가능)

notice.bd_milestone 형식:
  BD 트랙 단독:     "M01", "M05"
  파트너 트랙 단독:  "P01"
  BD + 파트너 동시:  "M01|P01",  "M05|P01"
  미해당:            "" (빈 문자열)
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.application.mappers.notice_mapper import _calc_dday

log = logging.getLogger("interx.milestone")

# ── 임계값 (필요 시 scoring.yaml 로 이전 가능) ───────────────────────────────
_URGENT_DDAY   = 7    # D-day ≤ 7 → 무조건 M05
_FAST_DDAY     = 14   # D-day ≤ 14 + A/B등급 → M05
_PARTNER_GRADE = {"A", "B", "C"}   # P01 배정 허용 등급


def _bd_code(notice: Notice, score: Optional[ScoreCard]) -> str:
    """BD 트랙 코드 결정. 해당 없으면 "" 반환."""
    if notice.l3_strong != "Y":
        return ""

    grade   = score.priority_grade if score else ""
    dday_s  = _calc_dday(notice.deadline_date)

    # 상시모집은 M01 (마감 압박 없음)
    if dday_s in ("상시", ""):
        return "M01"

    try:
        dday = int(dday_s)
    except ValueError:
        return "M01"

    if dday < 0:          # 마감 지남 — 안전망 (pipeline에서 이미 제거하지만)
        return ""
    if dday <= _URGENT_DDAY:
        return "M05"
    if dday <= _FAST_DDAY and grade in ("A", "B"):
        return "M05"
    return "M01"


def _partner_code(notice: Notice, score: Optional[ScoreCard]) -> str:
    """파트너 트랙 코드 결정. 해당 없으면 "" 반환."""
    if notice.partner_candidate != "Y":
        return ""
    grade = score.priority_grade if score else ""
    if grade not in _PARTNER_GRADE:
        return ""
    return "P01"


def assign_milestones(
    notices: List[Notice],
    score_cards: List[ScoreCard],
) -> List[Notice]:
    """
    각 Notice에 bd_milestone 코드를 배정한다.
    기존에 수동 입력된 코드(비어 있지 않은 경우)는 덮어쓰지 않는다.
    """
    score_map = {s.notice_id: s for s in score_cards}
    assigned = 0

    for notice in notices:
        if notice.bd_milestone:   # 수동 지정 값 보존
            continue

        score   = score_map.get(notice.notice_id)
        bd      = _bd_code(notice, score)
        partner = _partner_code(notice, score)

        if bd and partner:
            notice.bd_milestone = f"{bd}|{partner}"
        elif bd:
            notice.bd_milestone = bd
        elif partner:
            notice.bd_milestone = partner
        # else: "" 유지

        if notice.bd_milestone:
            assigned += 1

    log.info("[Milestone] 배정 완료: %d / %d건", assigned, len(notices))
    return notices
