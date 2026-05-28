"""
Gemini AI 포트 — application 계층이 gemini_client에 직접 의존하지 않도록 래핑.
"""
from __future__ import annotations

from typing import Optional


def is_available() -> bool:
    """Gemini API 사용 가능 여부."""
    try:
        from interx_engine.infrastructure.ai.gemini_client import is_available as _check
        return _check()
    except ImportError:
        return False


def generate(prompt: str, max_tokens: int = 4096) -> Optional[str]:
    """Gemini 텍스트 생성. 실패 시 None."""
    try:
        from interx_engine.infrastructure.ai.gemini_client import generate as _gen
        return _gen(prompt, max_tokens=max_tokens)
    except ImportError:
        return None
