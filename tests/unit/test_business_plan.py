"""
사업계획서 AI 생성기 단위 테스트
실행: pytest tests/unit/test_business_plan.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard


def _notice(title="테스트 공고", summary="", body="", category=""):
    return Notice(
        execution_id="TEST", site="test", notice_id="BP-001",
        title=title, agency="중소벤처기업부",
        summary=summary, body_text=body, category=category,
    )


def _card(notice_id="BP-001", fitness=70, priority=65, industry=55, grade="B"):
    return ScoreCard(
        execution_id="TEST", notice_id=notice_id, site="test",
        fitness_score=fitness, priority_score=priority,
        priority_grade=grade, industry_score=industry,
    )


# ── 모듈 임포트 테스트 ───────────────────────────────────────────────────────

class TestImport:
    def test_import_module(self):
        from interx_engine.application.use_cases.generate_business_plan import (
            generate_business_plan,
            extract_sections_from_notice,
            extract_sections_from_template,
            parse_uploaded_file,
            INTERX_CAPABILITIES,
        )
        assert callable(generate_business_plan)
        assert callable(extract_sections_from_notice)
        assert callable(parse_uploaded_file)
        assert len(INTERX_CAPABILITIES) >= 7


# ── 유형 판별 테스트 ─────────────────────────────────────────────────────────

class TestDefaultSectionsByType:
    """_default_sections가 공고 제목에 따라 다른 구조를 반환하는지 확인."""

    def test_smart_factory_has_construct_section(self):
        from interx_engine.application.use_cases.generate_business_plan import _default_sections
        n = _notice(title="2025년 제조AI특화 스마트공장 구축지원사업")
        sections = _default_sections(n)
        titles = " ".join(s["title"] for s in sections)
        assert "구축" in titles

    def test_rnd_has_necessity_section(self):
        from interx_engine.application.use_cases.generate_business_plan import _default_sections
        n = _notice(title="산업AI에이전트 기술개발 R&D 과제")
        sections = _default_sections(n)
        titles = " ".join(s["title"] for s in sections)
        assert "필요성" in titles

    def test_general_has_overview(self):
        from interx_engine.application.use_cases.generate_business_plan import _default_sections
        n = _notice(title="일반 지원사업 공고")
        sections = _default_sections(n)
        titles = " ".join(s["title"] for s in sections)
        assert "사업 개요" in titles

    def test_different_structures(self):
        """스마트공장 vs R&D vs 일반이 서로 다른 구조를 반환."""
        from interx_engine.application.use_cases.generate_business_plan import _default_sections
        sf = _default_sections(_notice(title="스마트공장 구축"))
        rd = _default_sections(_notice(title="연구개발 기술개발"))
        gn = _default_sections(_notice(title="일반 사업"))
        sf_titles = [s["title"] for s in sf]
        rd_titles = [s["title"] for s in rd]
        gn_titles = [s["title"] for s in gn]
        assert sf_titles != rd_titles
        assert sf_titles != gn_titles


# ── 솔루션 매칭 테스트 ───────────────────────────────────────────────────────

class TestSolutionDetection:
    def test_with_scorecard(self):
        from interx_engine.application.use_cases.generate_business_plan import _detect_relevant_solutions
        n = _notice(title="테스트")
        sc = _card()
        sc.solution_scores = {"QualityAI": 80, "PdM": 60, "InspectionAI": 40}
        result = _detect_relevant_solutions(n, sc)
        assert result[0] == "QualityAI"
        assert len(result) <= 3

    def test_keyword_fallback(self):
        from interx_engine.application.use_cases.generate_business_plan import _detect_relevant_solutions
        n = _notice(title="예지보전 AI 기반 설비진단 시스템")
        result = _detect_relevant_solutions(n, None)
        assert "PdM" in result

    def test_default_when_no_match(self):
        from interx_engine.application.use_cases.generate_business_plan import _detect_relevant_solutions
        n = _notice(title="xxx yyy zzz 없는 키워드")
        result = _detect_relevant_solutions(n, None)
        assert len(result) >= 2  # 기본값 반환


# ── 기본 섹션 구조 테스트 ────────────────────────────────────────────────────

class TestDefaultSections:
    def test_smart_factory_sections(self):
        from interx_engine.application.use_cases.generate_business_plan import _default_sections
        n = _notice(title="스마트공장 구축 사업")
        sections = _default_sections(n)
        assert len(sections) >= 4
        assert any("구축" in s["title"] for s in sections)

    def test_rnd_sections(self):
        from interx_engine.application.use_cases.generate_business_plan import _default_sections
        n = _notice(title="연구개발 기술개발 과제")
        sections = _default_sections(n)
        assert any("필요성" in s["title"] or "목표" in s["title"] for s in sections)

    def test_general_sections(self):
        from interx_engine.application.use_cases.generate_business_plan import _default_sections
        n = _notice(title="일반 사업")
        sections = _default_sections(n)
        assert len(sections) >= 4

    def test_subsections_exist(self):
        from interx_engine.application.use_cases.generate_business_plan import _default_sections
        n = _notice(title="스마트공장 구축")
        sections = _default_sections(n)
        for sec in sections:
            assert "subsections" in sec
            assert isinstance(sec["subsections"], list)


# ── JSON 파싱 테스트 ─────────────────────────────────────────────────────────

class TestParseJson:
    def test_valid_json(self):
        from interx_engine.application.use_cases.generate_business_plan import _parse_sections_json
        raw = '[{"title":"1. 개요","subsections":["1.1 목적"],"guidance":"사업 목적 기술"}]'
        result = _parse_sections_json(raw)
        assert len(result) == 1
        assert result[0]["title"] == "1. 개요"

    def test_json_in_codeblock(self):
        from interx_engine.application.use_cases.generate_business_plan import _parse_sections_json
        raw = '```json\n[{"title":"1. 개요","subsections":[],"guidance":""}]\n```'
        result = _parse_sections_json(raw)
        assert len(result) == 1

    def test_invalid_json(self):
        from interx_engine.application.use_cases.generate_business_plan import _parse_sections_json
        result = _parse_sections_json("이것은 JSON이 아닙니다")
        assert result == []


# ── 정규식 파싱 테스트 ───────────────────────────────────────────────────────

class TestParseRegex:
    def test_numbered_sections(self):
        from interx_engine.application.use_cases.generate_business_plan import _parse_sections_regex
        text = "1. 사업 개요\n2. 기업 현황\n3. 기술 내용\n4. 추진 일정\n5. 기대효과"
        result = _parse_sections_regex(text)
        assert len(result) == 5

    def test_excludes_budget_sections(self):
        from interx_engine.application.use_cases.generate_business_plan import _parse_sections_regex
        text = "1. 사업 개요\n2. 사업비 계획\n3. 기술 내용"
        result = _parse_sections_regex(text)
        assert len(result) == 2  # 사업비 제외


# ── Fallback 콘텐츠 테스트 ───────────────────────────────────────────────────

class TestFallbackContent:
    def test_overview_fallback(self):
        from interx_engine.application.use_cases.generate_business_plan import _fallback_content
        sec = {"title": "1. 사업 개요", "subsections": [], "guidance": ""}
        n = _notice(title="테스트 사업")
        content = _fallback_content(sec, n, ["QualityAI"], "(주)인터엑스")
        assert "인터엑스" in content
        assert "테스트 사업" in content

    def test_tech_fallback(self):
        from interx_engine.application.use_cases.generate_business_plan import _fallback_content
        sec = {"title": "3. 기술 개발 내용", "subsections": [], "guidance": ""}
        n = _notice(title="테스트")
        content = _fallback_content(sec, n, ["PdM", "QualityAI"], "(주)인터엑스")
        assert "예지보전" in content or "품질" in content

    def test_unknown_section(self):
        from interx_engine.application.use_cases.generate_business_plan import _fallback_content
        sec = {"title": "99. 알 수 없는 섹션", "subsections": [], "guidance": ""}
        n = _notice(title="테스트")
        content = _fallback_content(sec, n, [], "(주)인터엑스")
        # v3: fallback도 지식베이스 기반 실제 콘텐츠 생성
        assert "인터엑스" in content
        assert len(content) > 30


# ── 파일 파싱 테스트 ─────────────────────────────────────────────────────────

class TestFileParsing:
    def test_txt_file(self):
        from interx_engine.application.use_cases.generate_business_plan import parse_uploaded_file
        text = "테스트 사업계획서 내용입니다."
        result = parse_uploaded_file(text.encode("utf-8"), "test.txt")
        assert "테스트" in result

    def test_unsupported_format(self):
        from interx_engine.application.use_cases.generate_business_plan import parse_uploaded_file
        result = parse_uploaded_file(b"data", "test.xyz")
        assert result == ""


# ── DOCX 빌드 테스트 (python-docx 필요) ─────────────────────────────────────

class TestBuildDocx:
    def test_build_basic(self):
        try:
            from docx import Document
        except ImportError:
            pytest.skip("python-docx 미설치")

        from interx_engine.application.use_cases.generate_business_plan import build_docx
        n = _notice(title="테스트 스마트공장 구축 사업")
        sections = [
            {"title": "1. 사업 개요", "subsections": ["1.1 목적"], "guidance": ""},
            {"title": "2. 기업 현황", "subsections": [], "guidance": ""},
        ]
        contents = {
            "1. 사업 개요": "본 사업은 스마트공장 구축을 목표로 합니다.",
            "2. 기업 현황": "(주)인터엑스는 제조 AI 전문기업입니다.",
        }
        path = build_docx(n, sections, contents)
        assert path is not None
        assert Path(path).exists()
        assert path.endswith(".docx")
        # 정리
        Path(path).unlink(missing_ok=True)

    def test_build_with_scorecard(self):
        try:
            from docx import Document
        except ImportError:
            pytest.skip("python-docx 미설치")

        from interx_engine.application.use_cases.generate_business_plan import build_docx
        n = _notice(title="R&D 기술개발 과제")
        sc = _card(grade="A", fitness=85, priority=80)
        sections = [{"title": "1. 필요성", "subsections": [], "guidance": ""}]
        contents = {"1. 필요성": "본 기술개발의 필요성은 다음과 같습니다."}
        path = build_docx(n, sections, contents, score_card=sc)
        assert path is not None
        Path(path).unlink(missing_ok=True)
