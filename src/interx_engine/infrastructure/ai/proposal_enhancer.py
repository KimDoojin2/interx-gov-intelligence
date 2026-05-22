"""
제안서 초안 LLM 강화 — 기존 템플릿 기반 → 실제 문장 생성.

공고 요구사항 분석 → InterX 솔루션 매핑 → 제안 전략 + 차별화 포인트 자동 작성.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

log = logging.getLogger("interx.ai.proposal")


def enhance_proposal_strategy(
    title: str,
    body_text: str = "",
    structured: Optional[Dict] = None,
    matched_keywords: str = "",
    solution_scores: Optional[Dict] = None,
    budget: str = "",
) -> Dict[str, str]:
    """
    제안서 전략 섹션을 LLM으로 생성.

    Returns:
        {
            "executive_summary": "사업 참여 근거 요약 (3~4문장)",
            "approach": "기술 접근 전략 (솔루션별 역할)",
            "differentiators": "InterX 차별화 포인트 3개",
            "consortium_strategy": "컨소시엄 구성 제안",
            "risk_mitigation": "리스크 완화 방안",
        }
    """
    from interx_engine.infrastructure.ai.gemini_client import generate, is_available
    from interx_engine.infrastructure.ai.notice_analyzer import INTERX_PROFILE

    if not is_available():
        return _fallback_strategy(matched_keywords, solution_scores)

    struct_text = ""
    if structured:
        for k, v in structured.items():
            if v:
                struct_text += f"- {k}: {v[:200]}\n"

    sol_names = {
        "ManufacturingDT": "제조DT", "RecipeAI": "레시피AI",
        "QualityAI": "품질AI", "InspectionAI": "비전검사",
        "SafetyAI": "안전AI", "GenAI": "GenAI",
        "InfraDS": "데이터인프라", "PdM": "예지보전",
    }
    sol_text = ""
    if solution_scores:
        active = sorted(
            [(sol_names.get(k, k), v) for k, v in solution_scores.items() if v > 0],
            key=lambda x: -x[1]
        )[:4]
        sol_text = ", ".join(f"{n}({s:.0f}점)" for n, s in active)

    prompt = f"""다음 정부지원사업 공고에 대한 InterX의 제안서 전략을 작성해주세요.

## 공고
제목: {title}
예산: {budget or '미공개'}
매칭 키워드: {matched_keywords or '없음'}
솔루션 매칭: {sol_text or '없음'}

{f'## 공고 구조화 정보' + chr(10) + struct_text if struct_text else ''}

## 공고 본문 (발췌)
{body_text[:1200] if body_text else '없음'}

## 출력 형식 (JSON, 한국어)
{{
  "executive_summary": "사업 참여 근거 요약 3~4문장. 왜 InterX가 이 사업에 적합한지.",
  "approach": "기술 접근 전략. 어떤 솔루션을 어떻게 조합하여 사업 목표를 달성할지.",
  "differentiators": "InterX 차별화 포인트 3개 (불릿 형식)",
  "consortium_strategy": "컨소시엄 구성 제안 (필요 시 어떤 파트너가 필요한지)",
  "risk_mitigation": "주요 리스크와 완화 방안 2개"
}}"""

    system = f"""당신은 InterX의 수석 제안 전략가입니다.
정부지원사업 제안서의 핵심 전략을 작성합니다.
구체적이고 실무적으로 작성하세요. JSON 형식으로만 응답하세요.

{INTERX_PROFILE}"""

    try:
        import json
        response = generate(prompt, system_instruction=system, temperature=0.5, max_tokens=1500)
        if not response:
            return _fallback_strategy(matched_keywords, solution_scores)

        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]

        result = json.loads(text.strip())
        log.info("[제안서AI] %s 전략 생성 완료", title[:30])
        return result

    except Exception as e:
        log.error("[제안서AI] 생성 실패: %s", e)
        return _fallback_strategy(matched_keywords, solution_scores)


def _fallback_strategy(
    matched_keywords: str = "",
    solution_scores: Optional[Dict] = None,
) -> Dict[str, str]:
    """규칙 기반 전략 (fallback)."""
    sol_names = {
        "ManufacturingDT": "제조DT", "RecipeAI": "레시피AI",
        "QualityAI": "품질AI", "InspectionAI": "비전검사",
        "SafetyAI": "안전AI", "GenAI": "GenAI",
        "InfraDS": "데이터인프라", "PdM": "예지보전",
    }
    top_sols = []
    if solution_scores:
        top_sols = sorted(
            [(sol_names.get(k, k), v) for k, v in solution_scores.items() if v > 0],
            key=lambda x: -x[1]
        )[:3]

    sol_str = " + ".join(s[0] for s in top_sols) if top_sols else "AI 솔루션"

    return {
        "executive_summary": f"InterX의 {sol_str} 역량을 활용하여 본 사업의 목표를 달성할 수 있습니다. [GEMINI_API_KEY 설정 시 상세 분석 가능]",
        "approach": f"{sol_str} 패키지 접근",
        "differentiators": "- 제조AI 전문 역량\n- 다수 프로젝트 수행 실적\n- 실시간 데이터 처리 기술",
        "consortium_strategy": "필요 시 도메인 전문 파트너 구성 검토",
        "risk_mitigation": "- 기술 리스크: 검증된 기술 스택 활용\n- 일정 리스크: 단계별 마일스톤 관리",
    }
