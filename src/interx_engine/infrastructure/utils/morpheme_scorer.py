"""
형태소 기반 키워드 스코어링
kiwipiepy 설치 시 형태소 분석, 미설치 시 정규식 fallback
설치: pip install kiwipiepy
"""
from __future__ import annotations

import re
from typing import Dict, List


def extract_nouns(text: str) -> List[str]:
    """텍스트에서 명사 추출. kiwipiepy 없으면 2글자+ 한글 단어로 fallback."""
    try:
        from kiwipiepy import Kiwi  # type: ignore
        kiwi   = Kiwi()
        result = kiwi.analyze(text)
        return [
            token.form
            for token in result[0][0]
            if token.tag.startswith("N") and len(token.form) >= 2
        ]
    except ImportError:
        return re.findall(r"[가-힣]{2,}", text)
    except Exception:
        return re.findall(r"[가-힣]{2,}", text)


def morpheme_score(text: str, keyword_weights: Dict[str, float]) -> float:
    """
    형태소 분석 후 키워드 가중치 합산.
    형태소 단위 매칭(100%) + 직접 포함(80%) 두 단계로 체크.
    """
    nouns = set(extract_nouns(text.lower()))
    score = 0.0
    for kw, w in keyword_weights.items():
        kw_nouns = set(extract_nouns(kw))
        if kw_nouns and kw_nouns.issubset(nouns):
            score += w           # 형태소 완전 일치
        elif kw in text.lower():
            score += w * 0.8     # 직접 포함 (부분 가산)
    return score
