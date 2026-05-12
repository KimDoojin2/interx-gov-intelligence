"""
예산 문자열 정규화 유틸리티
지원 형식:
  3억, 3.5억원, 35억, 350,000천원, 3,000백만원, 5천만원,
  3000000000원, 30억원, 상시/미정 등 비정형
"""
from __future__ import annotations

import re
from typing import Optional

# 상시모집/비정형 마감 패턴
_OPEN_ENDED = [
    "상시", "예산소진", "별도공지", "추후공지", "미정", "협의",
    "해당없음", "마감없음", "해당 없음", "수시", "상시접수",
]


def is_open_ended(deadline_str: str) -> bool:
    """마감일 문자열이 상시/비정형인지 판단."""
    if not deadline_str:
        return False
    s = deadline_str.strip()
    for p in _OPEN_ENDED:
        if p in s:
            return True
    # 날짜 패턴이 없으면서 텍스트가 있는 경우
    has_date = bool(
        re.search(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", s)
        or re.search(r"\d{8}", s)
        or re.search(r"\d{4}년\s*\d{1,2}월", s)
    )
    if not has_date and len(s) >= 2 and not s.isdigit():
        return True
    return False


def parse_budget_eok(raw: str) -> Optional[float]:
    """예산 문자열 → 억원 단위 float. 파싱 실패 시 None."""
    if not raw:
        return None
    s = str(raw).strip().replace(",", "").replace(" ", "").replace("\xa0", "")

    # 조 단위
    m = re.search(r"([0-9.]+)조", s)
    if m:
        return round(float(m.group(1)) * 10000, 2)

    # 억 + 천만원 (예: 3억5천만원)
    m = re.search(r"([0-9.]+)억([0-9.]+)천만", s)
    if m:
        return round(float(m.group(1)) + float(m.group(2)) * 0.1, 2)

    # 억 단위 단독
    m = re.search(r"([0-9.]+)억", s)
    if m:
        return round(float(m.group(1)), 2)

    # 천만원 단위
    m = re.search(r"([0-9.]+)천만", s)
    if m:
        return round(float(m.group(1)) * 0.1, 2)

    # 백만원 단위 (예: 3000백만원 → 30억)
    m = re.search(r"([0-9.]+)백만", s)
    if m:
        return round(float(m.group(1)) / 100, 2)

    # 천원 단위 (예: 350000천원 → 35억)
    m = re.search(r"([0-9.]+)천원", s)
    if m:
        return round(float(m.group(1)) / 100000, 2)

    # 만원 단위
    m = re.search(r"([0-9.]+)만원?", s)
    if m:
        return round(float(m.group(1)) / 10000, 2)

    # 순수 원 단위 (숫자만 또는 숫자+원)
    m = re.match(r"^([0-9.]+)원?$", s)
    if m:
        won = float(m.group(1))
        return round(won / 100_000_000, 2)

    return None


def normalize_budget(raw: str) -> str:
    """예산 문자열을 '3.5억' 형태로 정규화. 파싱 실패 시 원본 반환."""
    val = parse_budget_eok(raw)
    if val is None or val <= 0:
        return raw
    if val >= 1:
        # 소수점이 없으면 정수로
        return f"{int(val)}억" if val == int(val) else f"{val:.1f}억"
    else:
        man = round(val * 10000)
        return f"{man}만원"
