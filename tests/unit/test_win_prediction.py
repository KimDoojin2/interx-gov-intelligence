"""
WinPredictionUseCase / WinPredictionTrainer 단위 테스트
실행: pytest tests/unit/test_win_prediction.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.application.use_cases.win_prediction import (
    WinPredictionUseCase,
    _budget_score,
    _dday_score,
    _grade,
)


# ── 픽스처 ────────────────────────────────────────────────────────────────────

def _notice(notice_id="N-001", budget="5억원", deadline="2026-12-31", l3="N"):
    return Notice(
        execution_id="TEST", site="test", notice_id=notice_id,
        title=f"테스트 공고 {notice_id}",
        budget=budget, deadline_date=deadline, l3_strong=l3,
    )

def _card(notice_id="N-001", fitness=70, priority=65, industry=55, grade="B"):
    return ScoreCard(
        execution_id="TEST", notice_id=notice_id, site="test",
        fitness_score=fitness, priority_score=priority,
        priority_grade=grade, industry_score=industry,
    )


# ── _budget_score ─────────────────────────────────────────────────────────────

class TestBudgetScore:
    def test_zero_budget_returns_zero(self):
        assert _budget_score("") == 0.0

    def test_5억_returns_0_5(self):
        score = _budget_score("5억원")
        assert 0.4 <= score <= 0.6

    def test_10억_returns_1_0(self):
        score = _budget_score("10억원")
        assert score == pytest.approx(1.0)

    def test_very_large_budget_penalized(self):
        score_small = _budget_score("5억원")
        score_large = _budget_score("200억원")
        assert score_large < score_small

    def test_score_between_0_and_1(self):
        for b in ["1억", "10억", "50억", "100억", "500억"]:
            s = _budget_score(b)
            assert 0.0 <= s <= 1.0, f"{b} → {s}"


# ── _dday_score ───────────────────────────────────────────────────────────────

class TestDdayScore:
    def test_past_deadline_zero(self):
        assert _dday_score("2020-01-01") == 0.0

    def test_within_7days_is_1(self):
        from datetime import date, timedelta
        soon = (date.today() + timedelta(days=3)).isoformat()
        assert _dday_score(soon) == 1.0

    def test_within_30days_is_0_7(self):
        from datetime import date, timedelta
        mid = (date.today() + timedelta(days=20)).isoformat()
        assert _dday_score(mid) == 0.7

    def test_far_future_is_0_3(self):
        assert _dday_score("2099-12-31") == 0.3

    def test_invalid_date_returns_0_3(self):
        assert _dday_score("not-a-date") == 0.3


# ── _grade ────────────────────────────────────────────────────────────────────

class TestGrade:
    def test_0_75_is_A(self):
        assert _grade(0.75) == ("A", "즉시투자")

    def test_0_55_is_B(self):
        assert _grade(0.55) == ("B", "검토")

    def test_0_35_is_C(self):
        assert _grade(0.35) == ("C", "관망")

    def test_0_00_is_D(self):
        assert _grade(0.00) == ("D", "제외")

    def test_high_prob_A(self):
        grade, _ = _grade(0.99)
        assert grade == "A"

    def test_low_prob_D(self):
        grade, _ = _grade(0.10)
        assert grade == "D"


# ── WinPredictionUseCase (룰 기반) ────────────────────────────────────────────

class TestWinPredictionUseCase:
    def setup_method(self):
        self.uc = WinPredictionUseCase()

    def test_empty_notices_returns_empty_report(self):
        report = self.uc.execute([], [], "EXEC-000")
        assert report.predictions == []
        assert report.top_opportunities == []

    def test_returns_prediction_for_each_matched_notice(self):
        notices = [_notice(f"N-{i}") for i in range(3)]
        cards   = [_card(f"N-{i}") for i in range(3)]
        report  = self.uc.execute(notices, cards, "EXEC-001")
        assert len(report.predictions) == 3

    def test_notice_without_scorecard_skipped(self):
        notices = [_notice("N-1"), _notice("N-2")]
        cards   = [_card("N-1")]          # N-2 카드 없음
        report  = self.uc.execute(notices, cards, "EXEC-002")
        assert len(report.predictions) == 1
        assert report.predictions[0].notice_id == "N-1"

    def test_probability_between_0_and_1(self):
        notices = [_notice("N-1", budget="5억", deadline="2026-12-31", l3="Y")]
        cards   = [_card("N-1", fitness=80, priority=75, industry=60)]
        report  = self.uc.execute(notices, cards, "EXEC-003")
        p = report.predictions[0].win_probability
        assert 0.0 <= p <= 1.0

    def test_l3_y_boosts_probability(self):
        n_l3  = _notice("L3",  l3="Y")
        n_nol3 = _notice("NL3", l3="N")
        cards  = [_card("L3"), _card("NL3")]
        report = self.uc.execute([n_l3, n_nol3], cards, "EXEC-004")
        pm = {p.notice_id: p.win_probability for p in report.predictions}
        assert pm["L3"] > pm["NL3"]

    def test_sorted_by_probability_descending(self):
        notices = [_notice(f"N-{i}", budget=f"{i}억") for i in range(1, 6)]
        cards   = [_card(f"N-{i}", fitness=40+i*5) for i in range(1, 6)]
        report  = self.uc.execute(notices, cards, "EXEC-005")
        probs   = [p.win_probability for p in report.predictions]
        assert probs == sorted(probs, reverse=True)

    def test_top_opportunities_only_grade_A(self):
        notices = [_notice(f"N-{i}") for i in range(5)]
        cards   = [_card(f"N-{i}", fitness=90, priority=90, industry=90)
                   for i in range(5)]
        report  = self.uc.execute(notices, cards, "EXEC-006")
        a_ids   = {p.notice_id for p in report.predictions if p.win_grade == "A"}
        assert set(report.top_opportunities).issubset(a_ids)

    def test_top_opportunities_max_5(self):
        notices = [_notice(f"N-{i}", l3="Y") for i in range(10)]
        cards   = [_card(f"N-{i}", fitness=95, priority=95, industry=95)
                   for i in range(10)]
        report  = self.uc.execute(notices, cards, "EXEC-007")
        assert len(report.top_opportunities) <= 5

    def test_feature_contributions_keys(self):
        notices = [_notice("N-1")]
        cards   = [_card("N-1")]
        report  = self.uc.execute(notices, cards, "EXEC-008")
        expected_keys = {"fitness_score", "priority_score", "budget_억",
                         "dday_urgency", "l3_flag", "industry_score"}
        assert set(report.predictions[0].feature_contributions.keys()) == expected_keys

    def test_grade_field_valid(self):
        notices = [_notice("N-1")]
        cards   = [_card("N-1")]
        report  = self.uc.execute(notices, cards, "EXEC-009")
        assert report.predictions[0].win_grade in ("A", "B", "C", "D")

    def test_execution_id_stored(self):
        report = self.uc.execute([], [], "MY-EXEC-ID")
        assert report.execution_id == "MY-EXEC-ID"
