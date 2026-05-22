"""
질의응답 챗봇 — 수집된 공고 데이터 기반 RAG.

"이번 주 A등급 공고 중 스마트공장 관련은?" 같은 자연어 질문 처리.
공고 데이터를 컨텍스트로 주입하여 Gemini가 답변.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

log = logging.getLogger("interx.ai.chatbot")


def _build_context(notices: List, score_map: Dict, max_notices: int = 30) -> str:
    """공고 리스트를 텍스트 컨텍스트로 변환 (토큰 절약)."""
    lines = []
    for i, n in enumerate(notices[:max_notices]):
        sc = score_map.get(n.notice_id)
        grade = sc.priority_grade if sc else "D"
        score = f"{sc.priority_score:.0f}" if sc else "0"
        kws = ", ".join(sc.positive_keywords[:5]) if sc and sc.positive_keywords else ""
        l3 = "Y" if getattr(n, "l3_strong", "N") == "Y" else ""
        rec = getattr(n, "recurring_flag", "N")

        lines.append(
            f"{i+1}. [{grade}] {n.title} | "
            f"사이트:{n.site} | 기관:{n.agency or n.ministry or '-'} | "
            f"마감:{n.deadline_date or '-'} | 예산:{n.budget or '-'} | "
            f"점수:{score} | 키워드:{kws} | L3:{l3} | 정기:{rec}"
        )
    return "\n".join(lines)


def answer_question(
    question: str,
    notices: List,
    score_map: Dict,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    자연어 질문에 수집된 공고 데이터 기반으로 답변.

    Args:
        question: 사용자 질문
        notices: 전체 공고 리스트
        score_map: {notice_id: ScoreCard}
        chat_history: 이전 대화 히스토리 [{"role": "user"|"assistant", "content": "..."}]

    Returns:
        답변 텍스트
    """
    from interx_engine.infrastructure.ai.gemini_client import generate, is_available

    if not is_available():
        return _fallback_answer(question, notices, score_map)

    # 컨텍스트 구축
    context = _build_context(notices, score_map, max_notices=40)

    # 통계 요약
    total = len(notices)
    grade_counts = {}
    for n in notices:
        sc = score_map.get(n.notice_id)
        g = sc.priority_grade if sc else "D"
        grade_counts[g] = grade_counts.get(g, 0) + 1

    today = datetime.now().strftime("%Y-%m-%d")
    stats = (
        f"오늘: {today}\n"
        f"전체 공고: {total}건\n"
        f"등급별: A={grade_counts.get('A',0)}, B={grade_counts.get('B',0)}, "
        f"C={grade_counts.get('C',0)}, D={grade_counts.get('D',0)}\n"
    )

    # 히스토리 포맷
    history_text = ""
    if chat_history:
        for msg in chat_history[-6:]:  # 최근 6턴만
            role = "사용자" if msg["role"] == "user" else "AI"
            history_text += f"{role}: {msg['content']}\n"

    prompt = f"""## 현재 수집된 공고 데이터
{stats}

## 공고 목록 (최근 수집)
{context}

{f'## 이전 대화' + chr(10) + history_text if history_text else ''}

## 사용자 질문
{question}

위 공고 데이터를 기반으로 질문에 답해주세요.
- 구체적인 공고명과 등급을 포함하여 답하세요
- 수치(건수, 점수)를 포함하세요
- 한국어로 답하세요
- 데이터에 없는 내용은 "데이터에서 확인할 수 없습니다"라고 답하세요"""

    system = """당신은 InterX의 BD(사업개발) 어시스턴트입니다.
수집된 정부지원사업 공고 데이터를 기반으로 질문에 정확히 답합니다.
간결하고 실용적으로 답하세요. 불필요한 인사말이나 서론은 생략합니다."""

    try:
        response = generate(prompt, system_instruction=system, temperature=0.3, max_tokens=1500)
        if response:
            return response
        return _fallback_answer(question, notices, score_map)
    except Exception as e:
        log.error("[챗봇] 답변 실패: %s", e)
        return _fallback_answer(question, notices, score_map)


def _fallback_answer(question: str, notices: List, score_map: Dict) -> str:
    """API 없을 때 규칙 기반 답변."""
    q = question.lower()
    results = []

    # 등급 필터
    target_grade = None
    for g in ["a", "b", "c", "d"]:
        if f"{g}등급" in q or f"{g} 등급" in q:
            target_grade = g.upper()
            break

    # 키워드 필터
    search_kw = None
    for kw in ["스마트공장", "디지털트윈", "ai", "품질", "안전", "예지보전",
                "로봇", "자동화", "manuai", "genai", "데이터"]:
        if kw in q:
            search_kw = kw
            break

    for n in notices:
        sc = score_map.get(n.notice_id)
        grade = sc.priority_grade if sc else "D"

        # 등급 필터
        if target_grade and grade != target_grade:
            continue

        # 키워드 필터
        if search_kw:
            text = f"{n.title} {getattr(n, 'body_text', '') or ''}"
            if search_kw not in text.lower():
                continue

        results.append((n, sc, grade))

    if not results:
        return f"조건에 맞는 공고를 찾지 못했습니다. (전체 {len(notices)}건 검색)\n\n💡 GEMINI_API_KEY를 설정하면 자연어 질문이 가능합니다."

    lines = [f"검색 결과: {len(results)}건\n"]
    for n, sc, grade in results[:10]:
        score = f"{sc.priority_score:.0f}" if sc else "0"
        lines.append(f"- [{grade}] {n.title} (점수:{score}, 마감:{n.deadline_date or '-'})")

    if len(results) > 10:
        lines.append(f"\n... 외 {len(results)-10}건")

    lines.append("\n💡 GEMINI_API_KEY를 설정하면 더 정확한 AI 답변을 받을 수 있습니다.")
    return "\n".join(lines)
