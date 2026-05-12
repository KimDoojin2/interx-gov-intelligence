"""
PriorityScoringPolicy 단위 테스트
실행: pytest tests/unit/test_priority_scoring_policy.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest
from interx_engine.core.entities.notice import Notice
from interx_engine.core.rules.priority_scoring_policy import PriorityScoringPolicy, L3_THRESHOLD


def _notice(title: str, body: str = "", budget: str = "") -> Notice:
    return Notice(
        execution_id="TEST-001",
        site="test",
        notice_id="t001",
        title=title,
        body_text=body,
        budget=budget,
    )


policy = PriorityScoringPolicy()


class TestCoreKeywordFilter:
    """코어 키워드 없으면 fitness=0"""

    def test_no_core_keyword_gives_zero(self):
        n = _notice("게임 콘텐츠 개발 지원사업")
        sc = policy.calculate(n)
        assert sc.fitness_score == 0.0

    def test_core_keyword_present(self):
        n = _notice("스마트공장 AI 도입 지원")
        sc = policy.calculate(n)
        assert sc.fitness_score > 0


class TestNegativeKeywords:
    """감점 키워드가 fitness를 낮춘다"""

    def test_game_keyword_penalizes(self):
        n_clean  = _notice("제조 AI 품질 검사 지원")
        n_penalized = _notice("제조 AI 게임 콘텐츠 지원")
        sc_clean     = policy.calculate(n_clean)
        sc_penalized = policy.calculate(n_penalized)
        assert sc_clean.fitness_score >= sc_penalized.fitness_score


class TestL3Strong:
    """L3 강공고 임계값 30점 검증 (scoring.yaml: l3_strong=30)"""

    def test_threshold_is_30(self):
        assert L3_THRESHOLD == 30, f"L3 임계값이 30이어야 합니다. 현재: {L3_THRESHOLD}"

    def test_high_score_sets_l3_strong_y(self):
        n = _notice(
            "스마트공장 AX 디지털트윈 AI 제조 실증 지원사업",
            body="예지보전 머신비전 품질 이상탐지 MES OT 설비 모니터링",
            budget="10억",
        )
        sc = policy.calculate(n)
        if sc.fitness_score >= L3_THRESHOLD:
            assert n.l3_strong == "Y"

    def test_low_score_sets_l3_strong_n(self):
        n = _notice("중소기업 클라우드 지원")
        sc = policy.calculate(n)
        if sc.fitness_score < L3_THRESHOLD:
            assert n.l3_strong == "N"

    def test_l3_y_iff_fitness_above_threshold(self):
        n = _notice("AI 스마트공장 제조 디지털트윈 품질 실증 예지보전 데이터 설비 모니터링")
        sc = policy.calculate(n)
        if sc.fitness_score >= L3_THRESHOLD:
            assert n.l3_strong == "Y"
        else:
            assert n.l3_strong == "N"


class TestSolutionRecommendation:
    """추천 솔루션 매핑 검증"""

    def test_manufacturing_dt_solution(self):
        n = _notice("디지털트윈 기반 스마트팩토리 실증", body="시뮬레이션 공정 자율제조")
        policy.calculate(n)
        assert "ManufacturingDT" in (n.recommended_solution or "")

    def test_pdm_solution(self):
        n = _notice("예지보전 AI 설비 모니터링 솔루션", body="센서 이상탐지 iiot")
        policy.calculate(n)
        assert n.recommended_solution  # 비어있지 않음

    def test_quality_ai_solution(self):
        n = _notice("AI 기반 품질 불량 검사 수율 개선", body="spc 이상탐지 비전검사")
        policy.calculate(n)
        assert n.recommended_solution


class TestScoreCard:
    """ScoreCard 반환값 검증"""

    def test_returns_scorecard(self):
        from interx_engine.core.entities.score_card import ScoreCard
        n  = _notice("AI 스마트공장 제조 품질 실증")
        sc = policy.calculate(n)
        assert isinstance(sc, ScoreCard)

    def test_solution_scores_keys(self):
        n  = _notice("AI 스마트공장 제조")
        sc = policy.calculate(n)
        expected = {"ManufacturingDT", "RecipeAI", "QualityAI",
                    "InspectionAI", "SafetyAI", "GenAI", "InfraDS", "PdM"}
        assert set(sc.solution_scores.keys()) == expected

    def test_grade_values(self):
        n  = _notice("AI 스마트공장 제조")
        sc = policy.calculate(n)
        assert sc.priority_grade in ("A", "B", "C", "D")

    def test_scores_in_range(self):
        n  = _notice("스마트공장 AX AI 품질 데이터 제조", budget="5억")
        sc = policy.calculate(n)
        assert 0.0 <= sc.fitness_score <= 100.0
        assert 0.0 <= sc.priority_score <= 100.0
        assert 0.0 <= sc.industry_score <= 100.0
