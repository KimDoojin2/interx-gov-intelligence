"""파싱 검증 (validate_parsing) 단위 테스트."""
from __future__ import annotations
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.application.use_cases.validate_parsing import (
    validate_parsing, _check_grade_accuracy, FieldStat,
)


def _notice(title="테스트 공고", site="bizinfo", **kw):
    defaults = dict(execution_id="T", notice_id=f"{site}_001", detail_url="http://example.com")
    defaults.update(kw)
    return Notice(site=site, title=title, **defaults)


def _sc(notice_id="bizinfo_001", grade="B", fitness=50, **kw):
    return ScoreCard(
        execution_id="T", notice_id=notice_id, site="bizinfo",
        fitness_score=fitness, priority_score=40, priority_grade=grade, **kw,
    )


class TestFieldStat:
    def test_ratio_zero(self):
        fs = FieldStat(total=0, filled=0)
        assert fs.ratio == 0.0
        assert fs.pct == 0

    def test_ratio_full(self):
        fs = FieldStat(total=10, filled=10)
        assert fs.pct == 100


class TestGradeAccuracy:
    def test_a_grade_low_fitness(self):
        n = _notice(body_text="x" * 100, deadline_date="2026-12-31", agency="기관")
        sc = _sc(grade="A", fitness=20)
        issues = _check_grade_accuracy(n, sc)
        assert any("적합도" in i for i in issues)

    def test_a_grade_no_body(self):
        n = _notice(body_text="", deadline_date="2026-12-31", agency="기관")
        sc = _sc(grade="A", fitness=60)
        issues = _check_grade_accuracy(n, sc)
        assert any("본문" in i for i in issues)

    def test_d_grade_high_fitness(self):
        n = _notice(body_text="x" * 100, deadline_date="2026-12-31")
        sc = _sc(grade="D", fitness=55)
        issues = _check_grade_accuracy(n, sc)
        assert any("등급 산정 오류" in i for i in issues)

    def test_no_issues(self):
        n = _notice(body_text="x" * 100, deadline_date="2026-12-31", agency="기관")
        sc = _sc(grade="B", fitness=40, positive_keywords=["스마트공장"])
        issues = _check_grade_accuracy(n, sc)
        assert len(issues) == 0


class TestValidateParsing:
    def test_basic(self):
        notices = [
            _notice(body_text="긴 본문 " * 20, deadline_date="2026-12-31",
                    agency="중소벤처기업부", detail_url="http://a.com"),
        ]
        scs = [_sc()]
        vr = validate_parsing(notices, scs)
        assert vr.total_notices == 1
        assert vr.overall_completeness > 0
        assert len(vr.site_reports) == 1

    def test_missing_fields_flagged(self):
        notices = [_notice(body_text="", deadline_date="", agency="", detail_url="")]
        scs = [_sc()]
        vr = validate_parsing(notices, scs)
        assert len(vr.issues) > 0
        issue_texts = " ".join(vr.issues[0].issues)
        assert "필수 필드 누락" in issue_texts

    def test_multiple_sites(self):
        notices = [
            _notice(site="bizinfo", notice_id="b1", body_text="x" * 100,
                    deadline_date="2026-12-31", agency="A", detail_url="http://a"),
            _notice(site="kiat", notice_id="k1", body_text="x" * 100,
                    deadline_date="2026-12-31", agency="B", detail_url="http://b"),
        ]
        scs = [_sc(notice_id="b1"), _sc(notice_id="k1")]
        vr = validate_parsing(notices, scs)
        assert len(vr.site_reports) == 2

    def test_empty_input(self):
        vr = validate_parsing([], [])
        assert vr.total_notices == 0
        assert vr.overall_completeness == 0
