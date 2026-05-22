"""
일일 브리핑 자동 생성 — 매일 수집 결과 요약.

"오늘 신규 A등급 3건, 마감 임박 2건, 주목할 공고: ..." 텍스트 생성.
Slack/Telegram 알림에 활용.
"""
from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Dict, List, Optional

log = logging.getLogger("interx.ai.briefing")


def _calc_dday(deadline: str) -> int:
    try:
        dl = datetime.strptime(deadline, "%Y-%m-%d").date()
        return (dl - date.today()).days
    except (ValueError, TypeError):
        return -1


def generate_briefing(
    notices: List,
    score_map: Dict,
    execution_id: str = "",
    new_count: int = 0,
    changed_count: int = 0,
) -> str:
    """
    일일 브리핑 텍스트 생성.

    LLM 사용 가능 시 Gemini로 자연어 브리핑,
    없으면 규칙 기반 요약.

    Returns:
        브리핑 텍스트 (Slack/Telegram용)
    """
    # 통계 수집
    stats = _collect_stats(notices, score_map)

    # LLM 브리핑 시도
    from interx_engine.infrastructure.ai.gemini_client import is_available
    if is_available():
        llm_briefing = _llm_briefing(stats, notices, score_map)
        if llm_briefing:
            return llm_briefing

    # fallback: 규칙 기반
    return _rule_briefing(stats, execution_id)


def _collect_stats(notices: List, score_map: Dict) -> Dict:
    """브리핑용 통계 수집."""
    today = date.today()
    stats = {
        "total": len(notices),
        "grades": {"A": [], "B": [], "C": [], "D": []},
        "urgent_7": [],     # D-7 이내
        "urgent_3": [],     # D-3 이내
        "l3_strong": [],
        "recurring": [],
        "sites": {},
        "new_count": 0,
        "changed_count": 0,
    }

    for n in notices:
        sc = score_map.get(n.notice_id)
        grade = sc.priority_grade if sc else "D"
        stats["grades"][grade].append(n)

        # D-day
        dd = _calc_dday(n.deadline_date or "")
        if 0 <= dd <= 7:
            stats["urgent_7"].append((n, dd))
        if 0 <= dd <= 3:
            stats["urgent_3"].append((n, dd))

        # L3
        if getattr(n, "l3_strong", "N") == "Y":
            stats["l3_strong"].append(n)

        # 정기공고
        if getattr(n, "recurring_flag", "N") == "Y":
            stats["recurring"].append(n)

        # 사이트별
        stats["sites"][n.site] = stats["sites"].get(n.site, 0) + 1

    return stats


def _llm_briefing(stats: Dict, notices: List, score_map: Dict) -> str:
    """Gemini로 자연어 브리핑 생성."""
    from interx_engine.infrastructure.ai.gemini_client import generate

    # A등급 공고 요약
    a_notices_text = ""
    for n in stats["grades"]["A"][:5]:
        sc = score_map.get(n.notice_id)
        score = f"{sc.priority_score:.0f}" if sc else "0"
        a_notices_text += f"- {n.title} ({n.site}, 점수:{score}, 마감:{n.deadline_date or '-'})\n"

    # 긴급 공고
    urgent_text = ""
    for n, dd in sorted(stats["urgent_3"], key=lambda x: x[1])[:5]:
        urgent_text += f"- [D-{dd}] {n.title}\n"

    prompt = f"""다음 데이터를 기반으로 InterX BD팀을 위한 일일 브리핑을 작성해주세요.

## 오늘의 수집 결과
- 전체 공고: {stats['total']}건
- A등급: {len(stats['grades']['A'])}건, B등급: {len(stats['grades']['B'])}건
- C등급: {len(stats['grades']['C'])}건, D등급: {len(stats['grades']['D'])}건
- L3 강공고: {len(stats['l3_strong'])}건
- 정기공고 탐지: {len(stats['recurring'])}건
- 마감 7일 이내: {len(stats['urgent_7'])}건
- 마감 3일 이내: {len(stats['urgent_3'])}건

## A등급 공고 (TOP 5)
{a_notices_text or '없음'}

## 긴급 마감 (D-3 이내)
{urgent_text or '없음'}

## 작성 규칙
1. 3~5줄로 핵심만 간결하게
2. 가장 중요한 공고 1~2개 구체적으로 언급
3. 액션 아이템 1~2개 포함
4. 이모지 적절히 사용
5. Slack 메시지 형식으로"""

    system = "InterX BD팀의 일일 브리핑을 작성하는 비서입니다. 간결하고 실용적으로 작성합니다."

    try:
        return generate(prompt, system_instruction=system, temperature=0.5, max_tokens=500)
    except Exception as e:
        log.error("[브리핑] LLM 생성 실패: %s", e)
        return ""


def _rule_briefing(stats: Dict, execution_id: str = "") -> str:
    """규칙 기반 브리핑 (fallback)."""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"[InterX BD 브리핑] {today}",
        f"실행: {execution_id}" if execution_id else "",
        "",
        f"전체 {stats['total']}건 수집",
        f"  A등급: {len(stats['grades']['A'])}건 | B등급: {len(stats['grades']['B'])}건 | "
        f"C등급: {len(stats['grades']['C'])}건 | D등급: {len(stats['grades']['D'])}건",
    ]

    if stats["l3_strong"]:
        lines.append(f"  L3 강공고: {len(stats['l3_strong'])}건")

    if stats["urgent_3"]:
        lines.append(f"\n긴급 마감 (D-3 이내): {len(stats['urgent_3'])}건")
        for n, dd in sorted(stats["urgent_3"], key=lambda x: x[1])[:3]:
            lines.append(f"  [D-{dd}] {n.title[:40]}")

    if stats["grades"]["A"]:
        lines.append(f"\nA등급 주목 공고:")
        for n in stats["grades"]["A"][:3]:
            lines.append(f"  - {n.title[:45]} ({n.site})")

    if stats["recurring"]:
        lines.append(f"\n정기공고 탐지: {len(stats['recurring'])}건")

    return "\n".join(l for l in lines if l is not None)
