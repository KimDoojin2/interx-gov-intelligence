"""
AI Agent 모듈 단위 테스트.
Gemini API 없이 fallback 로직 검증.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest
from unittest.mock import patch, MagicMock


# ── gemini_client ─────────────────────────────────────────────────────────────

class TestGeminiClient:
    def test_is_available_false_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            from interx_engine.infrastructure.ai.gemini_client import is_available
            # 환경변수 없으면 False
            import os
            old = os.environ.pop("GEMINI_API_KEY", None)
            try:
                assert is_available() is False
            finally:
                if old:
                    os.environ["GEMINI_API_KEY"] = old

    def test_is_available_true_with_key(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            from interx_engine.infrastructure.ai.gemini_client import is_available
            assert is_available() is True

    def test_generate_returns_empty_on_no_key(self):
        with patch.dict("os.environ", {}, clear=True):
            import os
            old = os.environ.pop("GEMINI_API_KEY", None)
            try:
                from interx_engine.infrastructure.ai.gemini_client import generate
                # API 키 없으면 ValueError
                with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                    generate("test prompt")
            finally:
                if old:
                    os.environ["GEMINI_API_KEY"] = old


# ── notice_analyzer (fallback) ────────────────────────────────────────────────

class TestNoticeAnalyzer:
    def test_fallback_analysis_basic(self):
        from interx_engine.infrastructure.ai.notice_analyzer import _fallback_analysis
        result = _fallback_analysis(
            title="스마트공장 AI 품질검사 시스템 구축",
            matched_keywords="스마트공장, 품질검사, AI",
            grade="A",
            solution_scores={"QualityAI": 80, "InspectionAI": 60, "PdM": 0},
        )
        assert "fit_reason" in result
        assert "proposal_strategy" in result
        assert "A등급" in result["fit_reason"]
        assert len(result["fit_reason"]) > 10

    def test_fallback_analysis_empty_scores(self):
        from interx_engine.infrastructure.ai.notice_analyzer import _fallback_analysis
        result = _fallback_analysis(
            title="테스트 공고",
            matched_keywords="",
            grade="D",
        )
        assert "fit_reason" in result
        assert "AI 솔루션" in result["proposal_strategy"]

    def test_fallback_with_solutions(self):
        from interx_engine.infrastructure.ai.notice_analyzer import _fallback_analysis
        result = _fallback_analysis(
            title="디지털트윈 실증",
            matched_keywords="디지털트윈, 제조",
            grade="B",
            solution_scores={"ManufacturingDT": 90, "GenAI": 40},
        )
        assert "제조DT" in result["proposal_strategy"]

    @patch("interx_engine.infrastructure.ai.gemini_client.is_available", return_value=False)
    def test_analyze_notice_uses_fallback(self, mock_avail):
        from interx_engine.infrastructure.ai.notice_analyzer import analyze_notice
        result = analyze_notice(
            title="AI 제조혁신",
            grade="A",
            score=75,
            solution_scores={"QualityAI": 80},
        )
        assert "fit_reason" in result
        assert len(result["fit_reason"]) > 0


# ── chatbot (fallback) ────────────────────────────────────────────────────────

class TestChatbot:
    def _make_notice(self, notice_id, title, site="bizinfo", deadline="2026-06-01",
                     body_text="", l3="N", recurring="N"):
        n = MagicMock()
        n.notice_id = notice_id
        n.title = title
        n.site = site
        n.deadline_date = deadline
        n.agency = "테스트기관"
        n.ministry = "테스트부"
        n.budget = "1억"
        n.body_text = body_text
        n.l3_strong = l3
        n.recurring_flag = recurring
        return n

    def _make_score(self, notice_id, grade="B", score=50):
        sc = MagicMock()
        sc.notice_id = notice_id
        sc.priority_grade = grade
        sc.priority_score = score
        sc.positive_keywords = ["스마트공장", "AI"]
        return sc

    def test_fallback_answer_grade_filter(self):
        from interx_engine.infrastructure.ai.chatbot import _fallback_answer
        n1 = self._make_notice("n1", "스마트공장 AI 구축")
        n2 = self._make_notice("n2", "바이오 연구지원")
        sc1 = self._make_score("n1", "A", 80)
        sc2 = self._make_score("n2", "D", 10)
        sc_map = {"n1": sc1, "n2": sc2}

        answer = _fallback_answer("A등급 공고는?", [n1, n2], sc_map)
        assert "스마트공장" in answer
        assert "1건" in answer or "검색 결과" in answer

    def test_fallback_answer_keyword_filter(self):
        from interx_engine.infrastructure.ai.chatbot import _fallback_answer
        n1 = self._make_notice("n1", "스마트공장 구축 사업", body_text="스마트공장 관련 내용")
        n2 = self._make_notice("n2", "바이오 신약 개발")
        sc1 = self._make_score("n1", "B")
        sc2 = self._make_score("n2", "B")
        sc_map = {"n1": sc1, "n2": sc2}

        answer = _fallback_answer("스마트공장 관련 공고는?", [n1, n2], sc_map)
        assert "스마트공장" in answer

    def test_fallback_no_results(self):
        from interx_engine.infrastructure.ai.chatbot import _fallback_answer
        answer = _fallback_answer("존재하지않는키워드", [], {})
        assert "찾지 못했습니다" in answer or "0건" in answer


# ── briefing_generator (fallback) ─────────────────────────────────────────────

class TestBriefingGenerator:
    def _make_notice(self, notice_id, title, deadline="2026-06-01", l3="N", recurring="N"):
        n = MagicMock()
        n.notice_id = notice_id
        n.title = title
        n.site = "bizinfo"
        n.deadline_date = deadline
        n.l3_strong = l3
        n.recurring_flag = recurring
        return n

    def test_rule_briefing(self):
        from interx_engine.infrastructure.ai.briefing_generator import _rule_briefing
        a1 = self._make_notice("a1", "A등급 테스트 공고")
        a2 = self._make_notice("a2", "A등급 공고2")
        a3 = self._make_notice("a3", "A등급 공고3")
        stats = {
            "total": 50,
            "grades": {"A": [a1, a2, a3], "B": [a1, a2], "C": [a1], "D": [a1, a2, a3, a1]},
            "urgent_7": [],
            "urgent_3": [],
            "l3_strong": [],
            "recurring": [],
            "sites": {"bizinfo": 20, "kiat": 10},
        }
        briefing = _rule_briefing(stats, "EXEC-TEST")
        assert "50건" in briefing
        assert "A등급: 3건" in briefing
        assert "EXEC-TEST" in briefing

    def test_collect_stats(self):
        from interx_engine.infrastructure.ai.briefing_generator import _collect_stats
        n1 = self._make_notice("n1", "테스트1", l3="Y")
        n2 = self._make_notice("n2", "테스트2", recurring="Y")
        sc1 = MagicMock(); sc1.notice_id = "n1"; sc1.priority_grade = "A"
        sc2 = MagicMock(); sc2.notice_id = "n2"; sc2.priority_grade = "B"
        sc_map = {"n1": sc1, "n2": sc2}

        stats = _collect_stats([n1, n2], sc_map)
        assert stats["total"] == 2
        assert len(stats["grades"]["A"]) == 1
        assert len(stats["l3_strong"]) == 1
        assert len(stats["recurring"]) == 1


