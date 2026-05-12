"""
notice_mapper 단위 테스트
실행: pytest tests/unit/test_notice_mapper.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from interx_engine.core.entities.notice import Notice
from interx_engine.application.mappers.notice_mapper import notice_to_master_row, _calc_dday


def _notice(**kw) -> Notice:
    defaults = dict(execution_id="EX-001", site="bizinfo", notice_id="n001",
                    title="AI 스마트공장 지원사업", deadline_date="2099-12-31")
    return Notice(**{**defaults, **kw})


class TestCalcDday:
    def test_future_date(self):
        d = _calc_dday("2099-12-31")
        assert int(d) > 0

    def test_past_date(self):
        d = _calc_dday("2020-01-01")
        assert int(d) < 0

    def test_empty_string(self):
        assert _calc_dday("") == ""

    def test_invalid_string(self):
        # "마감없음"은 is_open_ended()가 True → "상시" 반환이 올바른 동작
        assert _calc_dday("마감없음") == "상시"

    def test_unparseable_date(self):
        # 날짜 패턴은 있지만 파싱 불가한 경우 → ""
        assert _calc_dday("2024-13-45") == ""


class TestNoticeToMasterRow:
    def test_required_keys_present(self):
        n   = _notice()
        row = notice_to_master_row(n)
        # sheets.yaml 01_영업기회_정보 컬럼 기준 핵심 키 확인
        for key in ["실행ID", "사이트", "공고명", "마감일", "D-day",
                    "L3강공고", "파트너후보", "상세URL"]:
            assert key in row, f"키 누락: {key}"

    def test_dday_calculated(self):
        n   = _notice(deadline_date="2099-06-01")
        row = notice_to_master_row(n)
        assert row["D-day"] != ""
        assert int(row["D-day"]) > 0

    def test_closed_flag(self):
        n   = _notice(deadline_date="2020-01-01")
        row = notice_to_master_row(n)
        assert row["마감여부"] == "Y"

    def test_with_score(self):
        from interx_engine.core.entities.score_card import ScoreCard
        sc = ScoreCard(
            execution_id="EX-001", notice_id="n001", site="bizinfo",
            fitness_score=72.5, priority_score=68.0, priority_grade="P2",
            solution_scores={"ManufacturingDT": 45.0}, industry_score=30.0,
        )
        n   = _notice()
        row = notice_to_master_row(n, sc)
        assert row["적합도점수"]  == 72.5
        assert row["우선순위등급"] == "P2"
        # 솔루션별 점수는 master row에 없음 (sheets.yaml 01_영업기회_정보 스펙)
        assert "ManufacturingDT점수" not in row
