"""
notice_mapper 단위 테스트 (sheets.yaml 9-sheet 아키텍처 기준)
실행: pytest tests/unit/test_notice_mapper_full.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.application.mappers.notice_mapper import (
    notice_to_master_row,
    notice_to_urgent_row,
    _calc_dday,
)


def _notice(**kw) -> Notice:
    defaults = dict(
        execution_id="EX-001", site="bizinfo", notice_id="n001",
        title="AI 스마트공장 지원사업", deadline_date="2099-12-31",
        ministry="중소벤처기업부", agency="중소기업진흥공단",
        budget="3억", business_type="R&D",
    )
    return Notice(**{**defaults, **kw})


def _score(**kw) -> ScoreCard:
    defaults = dict(
        execution_id="EX-001", notice_id="n001", site="bizinfo",
        fitness_score=72.5, priority_score=68.0, priority_grade="B",
        industry_score=30.0,
        solution_scores={"ManufacturingDT": 45.0, "PdM": 20.0},
        positive_keywords=["스마트공장", "AI"],
        negative_keywords=["해외"],
    )
    return ScoreCard(**{**defaults, **kw})


# ── _calc_dday ────────────────────────────────────────────────────────────────
class TestCalcDday:
    def test_future_date_positive(self):
        d = _calc_dday("2099-12-31")
        assert int(d) > 0

    def test_past_date_negative(self):
        d = _calc_dday("2000-01-01")
        assert int(d) < 0

    def test_empty_returns_empty(self):
        assert _calc_dday("") == ""

    def test_invalid_returns_empty(self):
        # 날짜 패턴 없고 open-ended도 아닌 케이스 → ""
        assert _calc_dday("2024-13-45") == ""


# ── notice_to_urgent_row (05_긴급마감_공고: 11 컬럼) ──────────────────────────
class TestNoticeToUrgentRow:
    EXPECTED_KEYS = [
        "사이트", "공고명", "마감일", "D-day",
        "우선순위등급", "적합도점수", "추천솔루션",
        "추천액션", "예산", "담당자", "상세URL",
    ]

    def test_all_keys_present(self):
        row = notice_to_urgent_row(_notice(), _score())
        for k in self.EXPECTED_KEYS:
            assert k in row, f"긴급마감 행 키 누락: {k}"

    def test_exactly_11_keys(self):
        row = notice_to_urgent_row(_notice(), _score())
        assert len(row) == 11, f"긴급마감 행은 11개 컬럼이어야 함. 현재: {len(row)}"

    def test_score_values_filled(self):
        sc  = _score(priority_grade="A", fitness_score=88.0)
        row = notice_to_urgent_row(_notice(), sc)
        assert row["우선순위등급"] == "A"
        assert row["적합도점수"]   == 88.0

    def test_no_score_gives_empty_strings(self):
        row = notice_to_urgent_row(_notice())
        assert row["우선순위등급"] == ""
        assert row["적합도점수"]   == ""


# ── notice_to_master_row (01_영업기회_정보: 27 컬럼) ─────────────────────────
class TestNoticeToMasterRow:
    EXPECTED_KEYS = [
        "실행ID", "사이트", "공고명", "마감일", "D-day", "마감여부",
        "주무부처", "수행기관", "예산",
        "적합도점수", "우선순위등급", "추천솔루션", "추천액션", "적합키워드",
        "L3강공고", "파트너후보",
        "담당자", "검토상태", "BD마일스톤",
        "신규여부", "변경여부", "경쟁사감지", "중복의심", "메모", "상세URL",
        "정기공고여부", "정기공고그룹",
    ]

    def test_all_keys_present(self):
        row = notice_to_master_row(_notice(), _score())
        for k in self.EXPECTED_KEYS:
            assert k in row, f"마스터 행 키 누락: {k}"

    def test_exactly_25_keys(self):
        row = notice_to_master_row(_notice(), _score())
        assert len(row) == 27, f"마스터 행은 27개 컬럼이어야 함. 현재: {len(row)}"

    def test_score_fills_grade_and_fitness(self):
        sc  = _score(priority_grade="A", fitness_score=91.0)
        row = notice_to_master_row(_notice(), sc)
        assert row["우선순위등급"] == "A"
        assert row["적합도점수"]   == 91.0

    def test_no_score_gives_empty_strings(self):
        row = notice_to_master_row(_notice())
        assert row["우선순위등급"] == ""
        assert row["적합도점수"]   == ""

    def test_positive_keywords_pipe_joined(self):
        sc  = _score(positive_keywords=["A", "B", "C"])
        row = notice_to_master_row(_notice(), sc)
        assert "A" in row["적합키워드"]
        assert "|" in row["적합키워드"]

    def test_new_flag_y(self):
        n = _notice()
        n.is_new = True
        row = notice_to_master_row(n)
        assert row["신규여부"] == "Y"

    def test_changed_flag_y(self):
        n = _notice()
        n.is_changed = True
        row = notice_to_master_row(n)
        assert row["변경여부"] == "Y"

    def test_open_ended_deadline(self):
        n = _notice()
        n.open_ended = True
        row = notice_to_master_row(n)
        assert row["마감일"] == "상시모집"

    def test_competitor_flag_in_memo(self):
        n = _notice()
        n.competitor_flag = "tier1"
        row = notice_to_master_row(n)
        assert "tier1" in row["메모"] or row["경쟁사감지"] == "tier1"
