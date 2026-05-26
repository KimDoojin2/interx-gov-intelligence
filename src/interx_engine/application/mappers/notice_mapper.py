"""
Notice 엔티티 → 시트 row 변환 매퍼
sheets.yaml 9-sheet 아키텍처와 1:1 대응
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.infrastructure.utils.budget_parser import (
    is_open_ended, normalize_budget,
)


def _calc_dday(deadline: str) -> str:
    if not deadline:
        return ""
    if is_open_ended(deadline):
        return "상시"
    try:
        delta = (date.fromisoformat(deadline[:10]) - date.today()).days
        return str(delta)
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# 01_영업기회_정보 / 02_L3강공고  (공통 row, 21 컬럼)
# ─────────────────────────────────────────────────────────────────────────────
def notice_to_master_row(notice: Notice, score: Optional[ScoreCard] = None) -> dict:
    budget_norm  = normalize_budget(notice.budget) if notice.budget else ""
    dup_flag     = getattr(notice, "duplicate_flag",  "N")
    comp_flag    = getattr(notice, "competitor_flag", "")
    is_new       = getattr(notice, "is_new",          False)
    is_changed   = getattr(notice, "is_changed",      False)

    # 자동 메모: 변경감지·중복의심·경쟁사 뱃지 조합
    memo_parts = []
    if is_new:          memo_parts.append("🆕신규")
    if is_changed:      memo_parts.append("🔄변경감지")
    if dup_flag == "Y": memo_parts.append("⚠️중복의심")
    if comp_flag:       memo_parts.append(f"🏢경쟁사({comp_flag})")
    # notice.memo에 이미 붙어 있는 경우 중복 방지
    base_memo = getattr(notice, "memo", "") or ""
    auto_memo = " ".join(memo_parts)
    memo = f"{auto_memo} {base_memo}".strip()

    return {
        "실행ID":       notice.execution_id,
        "사이트":       notice.site,
        "공고명":       notice.title,
        "마감일":       notice.deadline_date if not getattr(notice, "open_ended", False) else "상시모집",
        "D-day":       _calc_dday(notice.deadline_date),
        "마감여부":      "상시" if getattr(notice, "open_ended", False) else ("Y" if notice.is_closed() else "N"),
        "주무부처":      notice.ministry,
        "수행기관":      notice.agency,
        "예산":         budget_norm,
        "적합도점수":    score.fitness_score  if score else "",
        "우선순위등급":   score.priority_grade if score else "",
        "추천솔루션":    notice.recommended_solution or "-",
        "추천액션":      notice.recommended_action   or "검토",
        "적합키워드":    " | ".join(score.positive_keywords[:5]) if score else "",
        "L3강공고":      notice.l3_strong,
        "파트너후보":    notice.partner_candidate,
        "담당자":       notice.manager or "",
        "검토상태":      notice.status  or "",
        "BD마일스톤":    getattr(notice, "bd_milestone", ""),
        "신규여부":      "Y" if is_new else "N",
        "변경여부":      "Y" if is_changed else "N",
        "경쟁사감지":    comp_flag or "",
        "중복의심":      dup_flag,
        "메모":         memo,
        "상세URL":      notice.detail_url,
        "정기공고여부":  getattr(notice, "recurring_flag",  "N"),
        "정기공고그룹":  getattr(notice, "recurring_group", ""),
        "접수상태":     notice.apply_status or "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 05_긴급마감_공고  (D-7 이내, 11 컬럼)
# ─────────────────────────────────────────────────────────────────────────────
def notice_to_urgent_row(notice: Notice, score: Optional[ScoreCard] = None) -> dict:
    return {
        "사이트":      notice.site,
        "공고명":      notice.title,
        "마감일":      notice.deadline_date,
        "D-day":      _calc_dday(notice.deadline_date),
        "우선순위등급": score.priority_grade  if score else "",
        "적합도점수":   score.fitness_score   if score else "",
        "추천솔루션":   notice.recommended_solution or "-",
        "추천액션":     notice.recommended_action   or "검토",
        "예산":        notice.budget,
        "담당자":       notice.manager or "",
        "상세URL":     notice.detail_url,
    }
