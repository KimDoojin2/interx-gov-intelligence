from __future__ import annotations
from datetime import date, timedelta
from typing import Dict, List, Optional
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.core.entities.recommendation import Recommendation

# ── 등급별 액션 ──────────────────────────────────────────────────────────────
_GRADE_ACTION: Dict[str, Dict] = {
    "A": {"action": "즉시 제안서 작성 착수 (48시간 내)",         "confidence": "HIGH",   "deadline_offset": 2},
    "B": {"action": "1주 내 기술 제안 여부 결정",                "confidence": "MEDIUM", "deadline_offset": 7},
    "C": {"action": "2주 내 파트너 전달 또는 패스 결정",          "confidence": "LOW",    "deadline_offset": 14},
    "D": {"action": "패스 - 자동 모니터링만 유지",               "confidence": "LOW",    "deadline_offset": 30},
}

# ── 솔루션별 이유 ─────────────────────────────────────────────────────────────
_SOLUTION_REASON: Dict[str, str] = {
    "ManufacturingDT": "스마트공장·디지털트윈 솔루션 직접 적용 가능한 사업",
    "RecipeAI":        "공정 레시피 AI 최적화 직접 수요 확인",
    "QualityAI":       "품질AI·이상탐지 솔루션 적용 기회",
    "InspectionAI":    "비전검사·머신비전 솔루션 최적 사업",
    "SafetyAI":        "중대재해·제조 안전AI 솔루션 수요 확인",
    "GenAI":           "생성형AI·LLM 솔루션 적용 기회",
    "InfraDS":         "제조 데이터 인프라·플랫폼 구축 수요",
    "PdM":             "예지보전·설비 모니터링 솔루션 수요",
}

# ── 솔루션별 파트너 타입 ────────────────────────────────────────────────────────
_SOLUTION_PARTNER: Dict[str, str] = {
    "ManufacturingDT": "MES/SI업체 + 디지털트윈 전문업체",
    "RecipeAI":        "공정 자동화업체 + 화학·소재 도메인 파트너",
    "QualityAI":       "품질관리 솔루션업체 + 제조 AI 스타트업",
    "InspectionAI":    "비전검사 전문업체 + 카메라·센서 업체",
    "SafetyAI":        "산업안전 솔루션업체 + IoT 업체",
    "GenAI":           "LLM 솔루션업체 + 클라우드 파트너",
    "InfraDS":         "데이터 플랫폼업체 + SI업체",
    "PdM":             "IIoT 플랫폼업체 + 설비 전문업체",
}


def _action_deadline(deadline_date: str, offset_days: int) -> str:
    try:
        d = date.fromisoformat(deadline_date[:10])
        action_by = min(d - timedelta(days=7), date.today() + timedelta(days=offset_days))
        return action_by.isoformat()
    except Exception:
        return (date.today() + timedelta(days=offset_days)).isoformat()


class RecommendationRules:
    """
    ScoreCard + Notice → Recommendation 생성.
    LLM 없이 순수 rule 기반. 향후 LLM 으로 교체 가능한 구조.
    """

    def generate(self, notice: Notice, score: ScoreCard) -> Recommendation:
        grade = score.priority_grade
        cfg   = _GRADE_ACTION.get(grade, _GRADE_ACTION["D"])

        # 상위 3개 솔루션
        top_solutions = sorted(
            score.solution_scores.items(), key=lambda x: x[1], reverse=True
        )
        top3 = [s for s, v in top_solutions if v > 0][:3]

        # reason: 상위 솔루션 기반
        reasons = [_SOLUTION_REASON[s] for s in top3 if s in _SOLUTION_REASON]
        if not reasons:
            reason = f"적합도점수 {score.fitness_score}점 — 추가 검토 필요"
        elif len(reasons) == 1:
            reason = reasons[0]
        else:
            reason = f"{reasons[0]} + {len(reasons)-1}개 솔루션 중복 수요"

        # partner_type: 1위 솔루션 기준
        partner_type = _SOLUTION_PARTNER.get(top3[0], "종합 SI 파트너") if top3 else "종합 SI 파트너"

        # tags
        tags = []
        if notice.l3_strong == "Y":      tags.append("L3강공고")
        if notice.partner_candidate == "Y": tags.append("파트너전달")
        if score.negative_keywords:      tags.append("감점키워드있음")
        if notice.budget:                tags.append("예산명시")

        return Recommendation(
            notice_id=notice.notice_id,
            priority_grade=grade,
            confidence=cfg["confidence"],
            reason=reason,
            action=cfg["action"],
            partner_type=partner_type,
            top_solutions=top3,
            action_deadline=_action_deadline(notice.deadline_date, cfg["deadline_offset"]),
            tags=tags,
        )
