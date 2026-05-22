"""
공고 분석 에이전트 — 1번 핵심 기능.

기능:
1. "이 공고가 InterX에 왜 맞는지" 1문장 요약
2. "제안 전략: MES+AI 품질검사 패키지로 접근" 자동 생성
3. 핵심 요구사항 → InterX 솔루션 매핑
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Optional

log = logging.getLogger("interx.ai.analyzer")

# ── InterX 솔루션 프로필 (프롬프트에 주입) ──────────────────────────────────
INTERX_PROFILE = """
InterX는 제조 AI 전문기업으로 다음 8개 솔루션을 보유하고 있습니다:

1. ManufacturingDT (제조 디지털트윈): 3D 공정 시뮬레이션, OPC-UA/MQTT 실시간 동기화
2. RecipeAI (레시피 AI): 공정 조건 최적화, 배합 예측 AI, 파라미터 자동 튜닝
3. QualityAI (품질 AI): 불량 자동 검출 99%+, SPC 자동화, 품질 이상 조기 경보
4. InspectionAI (비전 검사 AI): 멀티 카메라 비전검사, 미세결함 탐지, 100ms 판정
5. SafetyAI (안전 AI): 중대재해예방, CCTV 위험행동 탐지, IoT 안전 모니터링
6. GenAI (제조 GenAI): 제조 특화 LLM/RAG, 설비 매뉴얼 QA봇, 자동 보고서
7. InfraDS (데이터 인프라): Catena-X/AAS 데이터스페이스, 클라우드-엣지 하이브리드
8. PdM (예지보전): 진동/온도/전류 고장예측, RUL 예측 90%+, 정비비 30% 절감

핵심 역량: 스마트팩토리, 디지털트윈, AI+X 제조혁신, MES 연동, 에이전틱AI, 자율공정
수행 실적: 제조AI 고도화, 스마트공장 구축, 품질검사 AI, 공정최적화, 데이터 인프라
"""


def analyze_notice(
    title: str,
    body_text: str = "",
    summary: str = "",
    structured: Optional[Dict] = None,
    matched_keywords: str = "",
    grade: str = "",
    score: float = 0,
    budget: str = "",
    solution_scores: Optional[Dict] = None,
) -> Dict[str, str]:
    """
    공고 1건을 분석하여 fit_reason + proposal_strategy 반환.

    Returns:
        {
            "fit_reason": "이 공고가 InterX에 맞는 이유 1문장",
            "proposal_strategy": "제안 전략 1~2문장",
            "key_requirements": "핵심 요구사항 요약",
            "solution_mapping": "추천 솔루션 매핑",
            "risk_factors": "주의할 리스크",
        }
    """
    from interx_engine.infrastructure.ai.gemini_client import generate, is_available

    if not is_available():
        return _fallback_analysis(title, matched_keywords, grade, solution_scores)

    # 구조화 정보 조합
    struct_text = ""
    if structured:
        for k, v in structured.items():
            if v:
                struct_text += f"- {k}: {v}\n"

    # 솔루션 점수 텍스트
    sol_text = ""
    if solution_scores:
        active = {k: v for k, v in solution_scores.items() if v > 0}
        if active:
            sol_text = ", ".join(f"{k}={v:.0f}" for k, v in sorted(active.items(), key=lambda x: -x[1]))

    prompt = f"""다음 정부지원사업 공고를 분석하여 InterX가 이 공고에 참여해야 하는 이유와 제안 전략을 작성해주세요.

## 공고 정보
- 제목: {title}
- 등급: {grade} (A가 최고)
- 적합도 점수: {score:.0f}/100
- 예산: {budget or '미공개'}
- 매칭 키워드: {matched_keywords or '없음'}
- 솔루션 매칭: {sol_text or '없음'}

{f'## 구조화 정보' + chr(10) + struct_text if struct_text else ''}

## 공고 요약
{summary[:500] if summary else '없음'}

## 공고 본문 (발췌)
{body_text[:1500] if body_text else '없음'}

## 출력 형식 (JSON)
아래 형식으로만 답하세요. 한국어로 작성.
{{
  "fit_reason": "이 공고가 InterX에 맞는 이유 1문장 (50자 이내)",
  "proposal_strategy": "제안 전략 1~2문장 (구체적 솔루션명 포함, 80자 이내)",
  "key_requirements": "공고의 핵심 요구사항 3개 불릿 (각 30자 이내)",
  "solution_mapping": "InterX 솔루션 → 공고 요구사항 매핑 (2~3개)",
  "risk_factors": "주의할 리스크 1~2개 (30자 이내)"
}}"""

    system = f"""당신은 InterX의 BD(사업개발) 전문가입니다.
정부지원사업 공고를 분석하여 InterX의 강점과 매칭하는 역할입니다.
반드시 JSON 형식으로만 응답하세요. 마크다운 코드블록(```)은 사용하지 마세요.

{INTERX_PROFILE}"""

    try:
        response = generate(prompt, system_instruction=system, temperature=0.4, max_tokens=1024)
        if not response:
            return _fallback_analysis(title, matched_keywords, grade, solution_scores)

        # JSON 파싱 (```json ... ``` 래핑 제거)
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        result = json.loads(text)
        log.info("[AI분석] %s → %s", title[:30], result.get("fit_reason", "")[:50])
        return result

    except json.JSONDecodeError:
        log.warning("[AI분석] JSON 파싱 실패, 원문 사용")
        return {
            "fit_reason": response[:100] if response else "",
            "proposal_strategy": "",
            "key_requirements": "",
            "solution_mapping": "",
            "risk_factors": "",
        }
    except Exception as e:
        log.error("[AI분석] 분석 실패: %s", e)
        return _fallback_analysis(title, matched_keywords, grade, solution_scores)


def _fallback_analysis(
    title: str,
    matched_keywords: str = "",
    grade: str = "",
    solution_scores: Optional[Dict] = None,
) -> Dict[str, str]:
    """Gemini API 없을 때 규칙 기반 분석 (fallback)."""
    # 솔루션 매핑
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
    kw_list = [k.strip() for k in (matched_keywords or "").split(",") if k.strip()][:5]

    fit = f"{grade}등급 공고로, {', '.join(kw_list[:3]) if kw_list else '제조AI'} 관련 InterX 핵심 역량 매칭"
    strategy = f"{sol_str} 패키지로 접근, InterX 수행 실적 기반 차별화"

    return {
        "fit_reason": fit,
        "proposal_strategy": strategy,
        "key_requirements": "- " + "\n- ".join(kw_list[:3]) if kw_list else "- 키워드 분석 필요",
        "solution_mapping": " → ".join(s[0] for s in top_sols) if top_sols else "수동 매핑 필요",
        "risk_factors": "API 키 미설정 — 상세 분석은 GEMINI_API_KEY 설정 후 사용",
    }
