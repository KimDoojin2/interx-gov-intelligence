"""
kpi_mapper 단위 테스트
실행: pytest tests/unit/test_kpi_mapper.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.application.mappers.kpi_mapper import (
    build_kpi_rows,
    build_exec_log_row,
    build_collect_log_rows,
    build_error_log_rows,
)


def _notice(notice_id="n001", l3="N", partner="N", budget="3억") -> Notice:
    return Notice(
        execution_id="EX-001", site="bizinfo",
        notice_id=notice_id, title="테스트 공고",
        l3_strong=l3, partner_candidate=partner,
        budget=budget, deadline_date="2099-12-31",
    )


def _score(notice_id="n001", grade="B") -> ScoreCard:
    return ScoreCard(
        execution_id="EX-001", notice_id=notice_id, site="bizinfo",
        fitness_score=60.0, priority_score=55.0,
        priority_grade=grade, industry_score=25.0,
    )


class TestBuildKpiRows:
    REQUIRED_COLS = {"기준일", "구분", "지표", "값", "실행ID"}

    def test_all_rows_have_required_columns(self):
        notices = [_notice("n1", l3="Y"), _notice("n2"), _notice("n3", partner="Y")]
        scores  = [_score("n1", "A"), _score("n2", "B"), _score("n3", "C")]
        rows = build_kpi_rows("EX-001", notices, scores)
        assert len(rows) > 0
        for row in rows:
            assert self.REQUIRED_COLS == set(row.keys()), f"컬럼 불일치: {row}"

    def test_categories_present(self):
        notices = [_notice()]
        scores  = [_score()]
        rows = build_kpi_rows("EX-001", notices, scores)
        categories = {r["구분"] for r in rows}
        assert "수집현황" in categories
        assert "등급현황" in categories

    def test_l3_count_correct(self):
        notices = [_notice("n1", l3="Y"), _notice("n2", l3="Y"), _notice("n3")]
        scores  = [_score("n1"), _score("n2"), _score("n3")]
        rows = build_kpi_rows("EX-001", notices, scores)
        l3_row = next(r for r in rows if r["지표"] == "L3강공고수")
        assert l3_row["값"] == "2"

    def test_execution_id_filled(self):
        rows = build_kpi_rows("EX-TEST", [_notice()], [_score()])
        assert all(r["실행ID"] == "EX-TEST" for r in rows)

    def test_empty_notices(self):
        rows = build_kpi_rows("EX-001", [], [])
        assert len(rows) > 0   # 헤더 지표들은 0 값으로 포함됨
        total_row = next(r for r in rows if r["지표"] == "전체공고수")
        assert total_row["값"] == "0"


class TestBuildExecLogRow:
    def test_required_keys(self):
        row = build_exec_log_row("EX-001", "test_step", "OK", 12.5, "완료")
        assert set(row.keys()) == {"실행ID", "실행시각", "단계", "상태", "소요초", "메시지"}

    def test_elapsed_rounded(self):
        row = build_exec_log_row("EX-001", "step", "OK", 12.567)
        assert row["소요초"] == 12.6

    def test_default_elapsed_zero(self):
        row = build_exec_log_row("EX-001", "step", "OK")
        assert row["소요초"] == 0.0


class TestBuildCollectLogRows:
    def test_row_count_matches_notices(self):
        notices = [_notice("n1"), _notice("n2"), _notice("n3")]
        rows = build_collect_log_rows("EX-001", notices)
        assert len(rows) == 3

    def test_required_keys(self):
        rows = build_collect_log_rows("EX-001", [_notice()])
        assert set(rows[0].keys()) == {
            "실행ID", "사이트", "공고ID", "공고명", "등록일", "마감일", "첨부수", "수집시각"
        }


class TestBuildErrorLogRows:
    def test_empty_errors(self):
        assert build_error_log_rows("EX-001", []) == []

    def test_required_keys(self):
        errs = [{"site": "bizinfo", "notice_id": "n1",
                 "error_type": "HTTP", "error_message": "404"}]
        rows = build_error_log_rows("EX-001", errs)
        assert len(rows) == 1
        assert set(rows[0].keys()) == {
            "실행ID", "사이트", "공고ID", "에러유형", "에러메시지", "실행시각"
        }
