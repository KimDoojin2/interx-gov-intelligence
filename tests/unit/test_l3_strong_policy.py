"""
L3StrongPolicy 단위 테스트
실행: pytest tests/unit/test_l3_strong_policy.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest
from interx_engine.core.entities.notice import Notice
from interx_engine.core.rules.l3_strong_policy import L3StrongPolicy


def _notice(title: str, summary: str = "", business_type: str = "") -> Notice:
    return Notice(
        execution_id="TEST-001",
        site="test",
        notice_id="t-l3-001",
        title=title,
        summary=summary,
        business_type=business_type,
    )


policy = L3StrongPolicy()


class TestIsL3Strong:
    def test_two_high_signal_keywords_true(self):
        n = _notice("스마트공장 디지털트윈 구축 지원")
        assert policy.is_l3_strong(n) is True

    def test_one_keyword_true(self):
        # scoring.yaml: min_hits=1 → 키워드 1개로 L3 충족
        n = _notice("스마트공장 도입 지원사업")
        assert policy.is_l3_strong(n) is True

    def test_zero_keywords_false(self):
        n = _notice("일반 창업 지원사업")
        assert policy.is_l3_strong(n) is False

    def test_keywords_in_summary_count(self):
        n = _notice("제조 지원사업", summary="예지보전 머신비전 이상탐지")
        assert policy.is_l3_strong(n) is True

    def test_keywords_in_business_type_count(self):
        n = _notice("지원사업", business_type="스마트팩토리 제조ai")
        assert policy.is_l3_strong(n) is True

    def test_case_insensitive(self):
        n = _notice("AX Sprint 스마트공장")
        assert policy.is_l3_strong(n) is True
