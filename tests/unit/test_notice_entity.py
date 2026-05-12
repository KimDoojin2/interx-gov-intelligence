"""
Notice 엔티티 단위 테스트
실행: pytest tests/unit/test_notice_entity.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from datetime import date
import pytest
from interx_engine.core.entities.notice import Notice


def _notice(**kw) -> Notice:
    defaults = dict(execution_id="EX-001", site="test", notice_id="n001", title="테스트 공고")
    return Notice(**{**defaults, **kw})


class TestNoticeKey:
    def test_notice_key_is_hex(self):
        n = _notice()
        assert len(n.notice_key) == 32
        assert all(c in "0123456789abcdef" for c in n.notice_key)

    def test_different_ids_give_different_keys(self):
        a = _notice(notice_id="a001")
        b = _notice(notice_id="b001")
        assert a.notice_key != b.notice_key


class TestIsClosed:
    def test_past_deadline_is_closed(self):
        n = _notice(deadline_date="2020-01-01")
        assert n.is_closed() is True

    def test_future_deadline_is_open(self):
        n = _notice(deadline_date="2099-12-31")
        assert n.is_closed() is False

    def test_empty_deadline_is_not_closed(self):
        n = _notice(deadline_date="")
        assert n.is_closed() is False

    def test_invalid_date_is_not_closed(self):
        n = _notice(deadline_date="마감없음")
        assert n.is_closed() is False


class TestV44Fields:
    """v4.4에서 추가된 필드 기본값 검증"""

    def test_category_defaults_empty(self):
        n = _notice()
        assert n.category == ""

    def test_partner_candidates_default_list(self):
        n = _notice()
        assert n.partner_candidates == []

    def test_l3_strong_default_n(self):
        n = _notice()
        assert n.l3_strong == "N"

    def test_partner_candidate_default_n(self):
        n = _notice()
        assert n.partner_candidate == "N"
