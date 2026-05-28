"""
예산 파싱 포트 — application 계층이 budget_parser에 직접 의존하지 않도록 래핑.
"""
from __future__ import annotations

from typing import Optional


def parse_budget_eok(raw: str) -> Optional[float]:
    """예산 문자열 → 억원 float. 실패 시 None."""
    try:
        from interx_engine.infrastructure.utils.budget_parser import parse_budget_eok as _parse
        return _parse(raw)
    except ImportError:
        return None


def normalize_budget(raw: str) -> str:
    """예산 문자열 정규화. 실패 시 원본 반환."""
    try:
        from interx_engine.infrastructure.utils.budget_parser import normalize_budget as _norm
        return _norm(raw)
    except ImportError:
        return raw


def is_open_ended(deadline: str) -> bool:
    """상시모집 여부 판별. 실패 시 False."""
    try:
        from interx_engine.infrastructure.utils.budget_parser import is_open_ended as _check
        return _check(deadline)
    except ImportError:
        return False
