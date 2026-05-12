"""
L3 강공고 Claude API 자동 요약
ANTHROPIC_API_KEY 환경변수가 있을 때만 동작. 없으면 조용히 스킵.

요약 결과는 notice.summary 에 저장되며,
notice.structured["claude_summary"] 에도 전문이 기록된다.
"""
from __future__ import annotations

import logging
import os
import re
from typing import List

from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.summarize_l3")

_SYSTEM_PROMPT = """\
당신은 정부지원사업 공고를 분석하는 전문가입니다.
InterX는 제조 AI(스마트팩토리·디지털트윈·품질AI·예지보전·생성형AI) 전문 기업입니다.
아래 공고 본문을 읽고 다음 형식으로 한국어 요약을 작성하세요.

[형식]
• 사업목적: (1~2문장)
• 지원대상: (핵심 자격 조건)
• 지원규모: (금액/기간)
• InterX 적합 이유: (구체적인 솔루션 연관성, 없으면 "낮음"으로 표기)
• 제안 포인트: (수주 전략 1~2문장)

300자 이내로 간결하게 작성하세요.\
"""


def _call_claude(text: str, title: str) -> str:
    """Claude API 호출. 실패 시 빈 문자열 반환."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""

    try:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=api_key)

        # 본문 길이 제한 (토큰 절약)
        body_excerpt = text[:3000] if text else "(본문 없음)"

        user_content = f"공고명: {title}\n\n본문:\n{body_excerpt}"

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",   # 빠르고 저렴한 모델 사용
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text.strip()
    except ImportError:
        log.debug("[Summarize] anthropic 패키지 미설치 — pip install anthropic")
    except Exception as e:
        log.warning("[Summarize] Claude API 호출 실패: %s", e)
    return ""


def summarize_l3_notices(notices: List[Notice]) -> int:
    """
    L3 강공고 목록에 대해 Claude API 요약을 생성한다.
    요약이 없는 공고 또는 summary가 짧은 공고만 처리.

    Returns:
        성공적으로 요약된 공고 수
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        log.debug("[Summarize] ANTHROPIC_API_KEY 미설정 — L3 요약 스킵")
        return 0

    success = 0
    for notice in notices:
        # 이미 충분한 요약이 있으면 스킵
        if notice.summary and len(notice.summary) >= 100:
            continue

        body = notice.body_text or ""
        if not body and notice.structured:
            # structured 데이터에서 본문 조합
            body = " ".join(
                str(v) for k, v in notice.structured.items()
                if k in ("사업목적", "지원내용", "지원대상", "지원금액") and v
            )

        if not body and not notice.title:
            continue

        summary = _call_claude(body, notice.title)
        if summary:
            notice.summary = summary[:400]
            notice.structured["claude_summary"] = summary
            success += 1
            log.debug("[Summarize] %s 요약 완료", notice.notice_id)

    if success:
        log.info("[Summarize] Claude 요약 완료: %d/%d건", success, len(notices))
    return success
