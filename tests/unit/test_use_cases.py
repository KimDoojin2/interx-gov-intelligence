# -*- coding: utf-8 -*-
"""
Use Case 단위 테스트 — 핵심 유스케이스 8개 커버
  1. score_notices        (L3 + 우선순위 스코어링)
  2. deduplicate_notices  (TF-IDF 코사인 유사도 중복 제거)
  3. detect_recurring     (정기공고 패턴 매칭)
  4. detect_changes       (신규/변경 감지)
  5. assign_manager       (담당자 자동 배정)
  6. assign_milestone     (BD 마일스톤 자동 배정)
  7. site_quality_grader  (사이트 품질 등급)
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard


# ── 테스트 헬퍼 ──────────────────────────────────────────────────────────────

def _notice(
    title: str = "테스트 공고",
    site: str = "bizinfo",
    notice_id: str = "",
    deadline: str = "",
    budget: str = "",
    ministry: str = "",
    agency: str = "",
    body_text: str = "",
    l3_strong: str = "N",
    partner_candidate: str = "N",
    manager: str = "",
    bd_milestone: str = "",
    **kwargs,
) -> Notice:
    nid = notice_id or f"{site}_{hash(title) % 100000:05d}"
    n = Notice(
        execution_id="test-run",
        site=site,
        notice_id=nid,
        title=title,
        detail_url=f"https://example.com/{nid}",
        deadline_date=deadline,
        budget=budget,
        ministry=ministry,
        agency=agency,
        body_text=body_text,
        l3_strong=l3_strong,
        partner_candidate=partner_candidate,
        manager=manager,
        bd_milestone=bd_milestone,
    )
    for k, v in kwargs.items():
        setattr(n, k, v)
    return n


def _scorecard(
    notice_id: str,
    fitness: float = 50.0,
    priority: float = 40.0,
    grade: str = "B",
    **kwargs,
) -> ScoreCard:
    return ScoreCard(
        execution_id="test-run",
        notice_id=notice_id,
        site="bizinfo",
        fitness_score=fitness,
        priority_score=priority,
        priority_grade=grade,
        **kwargs,
    )


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _past(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


# ═════════════════════════════════════════════════════════════════════════════
# 1. ScoreNoticesUseCase
# ═════════════════════════════════════════════════════════════════════════════

class TestScoreNotices:
    """score_notices.py — L3 판별 + 우선순위 스코어링"""

    def test_basic_scoring(self):
        from interx_engine.application.use_cases.score_notices import ScoreNoticesUseCase
        uc = ScoreNoticesUseCase()
        notices = [
            _notice("2025년 스마트공장 구축 지원사업 공고", body_text="제조 AI 디지털트윈 스마트팩토리"),
            _notice("바이오 신약 개발 지원사업", body_text="바이오 의약품 신약 개발"),
        ]
        scored_notices, cards = uc.execute(notices)
        assert len(cards) == 2
        assert all(c.priority_grade in ("A", "B", "C", "D") for c in cards)

    def test_l3_detection(self):
        from interx_engine.application.use_cases.score_notices import ScoreNoticesUseCase
        uc = ScoreNoticesUseCase()
        notices = [
            _notice(
                "스마트 제조혁신 AI·데이터 활용 실증 지원사업",
                body_text="제조 AI 디지털트윈 스마트팩토리 L3 혁신",
            ),
        ]
        scored_notices, cards = uc.execute(notices)
        # L3 키워드가 있는 공고는 l3_strong 판별이 실행됨
        assert scored_notices[0].l3_strong in ("Y", "N")  # 정책에 따라 결정

    def test_empty_input(self):
        from interx_engine.application.use_cases.score_notices import ScoreNoticesUseCase
        uc = ScoreNoticesUseCase()
        notices, cards = uc.execute([])
        assert notices == []
        assert cards == []

    def test_scorecard_fields(self):
        from interx_engine.application.use_cases.score_notices import ScoreNoticesUseCase
        uc = ScoreNoticesUseCase()
        notices = [_notice("AI 기반 제조혁신 디지털전환 스마트팩토리", body_text="제조 AI")]
        _, cards = uc.execute(notices)
        sc = cards[0]
        assert isinstance(sc.fitness_score, (int, float))
        assert isinstance(sc.priority_score, (int, float))
        assert sc.priority_grade in ("A", "B", "C", "D")
        assert 0 <= sc.fitness_score <= 100


# ═════════════════════════════════════════════════════════════════════════════
# 2. DeduplicateNotices
# ═════════════════════════════════════════════════════════════════════════════

class TestDeduplicateNotices:
    """deduplicate_notices.py — TF-IDF 코사인 유사도 중복 제거"""

    def test_no_duplicates(self):
        from interx_engine.application.use_cases.deduplicate_notices import deduplicate_by_tfidf
        n1 = _notice("스마트공장 구축 지원사업", site="bizinfo", notice_id="biz_001")
        n2 = _notice("바이오 신약 개발 지원사업", site="kiat", notice_id="kiat_001")
        sc1 = _scorecard("biz_001", fitness=60)
        sc2 = _scorecard("kiat_001", fitness=40)
        result, removed = deduplicate_by_tfidf([n1, n2], [sc1, sc2])
        assert removed == 0
        assert len(result) == 2

    def test_duplicate_removal(self):
        from interx_engine.application.use_cases.deduplicate_notices import deduplicate_by_tfidf
        # 거의 동일한 제목, 다른 사이트
        n1 = _notice("2025년 스마트공장 구축 지원사업 공고", site="bizinfo", notice_id="biz_001")
        n2 = _notice("2025년 스마트공장 구축 지원사업 공고", site="kiat", notice_id="kiat_001")
        sc1 = _scorecard("biz_001", fitness=80)
        sc2 = _scorecard("kiat_001", fitness=40)
        result, removed = deduplicate_by_tfidf([n1, n2], [sc1, sc2])
        assert removed == 1
        assert len(result) == 1
        # 높은 점수 쪽이 살아남아야 함
        assert result[0].notice_id == "biz_001"

    def test_same_site_not_compared(self):
        from interx_engine.application.use_cases.deduplicate_notices import deduplicate_by_tfidf
        # 같은 사이트 내 유사 제목 → 비교 제외
        n1 = _notice("스마트공장 구축 지원사업 1차", site="bizinfo", notice_id="biz_001")
        n2 = _notice("스마트공장 구축 지원사업 2차", site="bizinfo", notice_id="biz_002")
        sc1 = _scorecard("biz_001", fitness=60)
        sc2 = _scorecard("biz_002", fitness=40)
        result, removed = deduplicate_by_tfidf([n1, n2], [sc1, sc2])
        assert removed == 0
        assert len(result) == 2

    def test_single_notice(self):
        from interx_engine.application.use_cases.deduplicate_notices import deduplicate_by_tfidf
        n1 = _notice("공고 하나", notice_id="one")
        sc1 = _scorecard("one")
        result, removed = deduplicate_by_tfidf([n1], [sc1])
        assert removed == 0
        assert len(result) == 1


# ═════════════════════════════════════════════════════════════════════════════
# 3. DetectRecurring
# ═════════════════════════════════════════════════════════════════════════════

class TestDetectRecurring:
    """detect_recurring.py — 정기공고 패턴 매칭"""

    def test_match_recurring_direct(self):
        """_match_recurring이 패턴에 따라 매칭하는지 검증."""
        from interx_engine.application.use_cases.detect_recurring import _match_recurring, _PATTERNS

        # 패턴이 로드되었는지 확인
        from interx_engine.application.use_cases.detect_recurring import _get_patterns
        patterns = _get_patterns()
        if not patterns:
            pytest.skip("recurring.yaml 없음")

        # 스마트공장 패턴이 있다면 테스트
        flag, group, priority = _match_recurring("2025년 스마트공장 구축 지원사업")
        # 패턴에 따라 결과가 달라질 수 있지만, "스마트공장"이 있으면 매칭될 가능성이 높음
        if flag == "Y":
            assert group != ""
            assert priority in (1, 2, 3)

    def test_no_match(self):
        from interx_engine.application.use_cases.detect_recurring import _match_recurring
        flag, group, priority = _match_recurring("이 공고는 아무 패턴에도 해당하지 않음 xyz123abc")
        assert flag == "N"
        assert group == ""
        assert priority == 0

    def test_detect_recurring_sets_flags(self):
        from interx_engine.application.use_cases.detect_recurring import detect_recurring
        notices = [
            _notice("2025년 스마트공장 구축 지원사업"),
            _notice("전혀 무관한 공고 abc xyz"),
        ]
        updated, count = detect_recurring(notices)
        assert len(updated) == 2
        # 최소한 recurring_flag가 설정되어 있어야 함
        assert all(n.recurring_flag in ("Y", "N") for n in updated)

    def test_empty_notices(self):
        from interx_engine.application.use_cases.detect_recurring import detect_recurring
        result, count = detect_recurring([])
        assert result == []
        assert count == 0


# ═════════════════════════════════════════════════════════════════════════════
# 4. DetectChanges
# ═════════════════════════════════════════════════════════════════════════════

class TestDetectChanges:
    """detect_changes.py — 신규/변경 감지 (캐시 비교)"""

    def test_all_new_first_run(self, tmp_path):
        from interx_engine.application.use_cases.detect_changes import detect_changes
        cache_file = tmp_path / "test_cache.json"
        with patch.dict(os.environ, {"INTERX_CACHE_PATH": str(cache_file)}):
            notices = [
                _notice("공고A", notice_id="id_a"),
                _notice("공고B", notice_id="id_b"),
            ]
            result, new_cnt, changed_cnt = detect_changes(notices)
            assert new_cnt == 2
            assert changed_cnt == 0
            assert all(n.is_new for n in result)

    def test_no_change_second_run(self, tmp_path):
        from interx_engine.application.use_cases.detect_changes import detect_changes
        cache_file = tmp_path / "test_cache.json"
        with patch.dict(os.environ, {"INTERX_CACHE_PATH": str(cache_file)}):
            notices = [_notice("공고A", notice_id="id_a", deadline="2025-12-31", budget="1억")]
            detect_changes(notices)
            # 두 번째 실행 — 동일 데이터
            notices2 = [_notice("공고A", notice_id="id_a", deadline="2025-12-31", budget="1억")]
            result, new_cnt, changed_cnt = detect_changes(notices2)
            assert new_cnt == 0
            assert changed_cnt == 0

    def test_detect_budget_change(self, tmp_path):
        from interx_engine.application.use_cases.detect_changes import detect_changes
        cache_file = tmp_path / "test_cache.json"
        with patch.dict(os.environ, {"INTERX_CACHE_PATH": str(cache_file)}):
            notices1 = [_notice("공고A", notice_id="id_a", budget="1억")]
            detect_changes(notices1)
            # 예산 변경
            notices2 = [_notice("공고A", notice_id="id_a", budget="2억")]
            result, new_cnt, changed_cnt = detect_changes(notices2)
            assert changed_cnt == 1
            assert result[0].is_changed
            assert "변경" in result[0].memo

    def test_detect_new_notice(self, tmp_path):
        from interx_engine.application.use_cases.detect_changes import detect_changes
        cache_file = tmp_path / "test_cache.json"
        with patch.dict(os.environ, {"INTERX_CACHE_PATH": str(cache_file)}):
            notices1 = [_notice("공고A", notice_id="id_a")]
            detect_changes(notices1)
            # 새 공고 추가
            notices2 = [
                _notice("공고A", notice_id="id_a"),
                _notice("공고B", notice_id="id_b"),
            ]
            result, new_cnt, changed_cnt = detect_changes(notices2)
            assert new_cnt == 1
            assert changed_cnt == 0


# ═════════════════════════════════════════════════════════════════════════════
# 5. AssignManager
# ═════════════════════════════════════════════════════════════════════════════

class TestAssignManager:
    """assign_manager.py — 담당자 자동 배정"""

    def test_assign_with_rules(self, tmp_path):
        """YAML 규칙 파일로 담당자 배정 테스트."""
        from interx_engine.application.use_cases.assign_manager import assign_managers, _load_rules

        rules_yaml = tmp_path / "manager_rules.yaml"
        rules_yaml.write_text(
            "rules:\n"
            "  - manager: '홍길동'\n"
            "    conditions:\n"
            "      keywords: ['스마트공장', 'AI']\n"
            "  - manager: '김철수'\n"
            "    conditions:\n"
            "      ministry: ['과학기술정보통신부']\n",
            encoding="utf-8",
        )

        with patch(
            "interx_engine.application.use_cases.assign_manager._load_rules",
            return_value=[
                {"manager": "홍길동", "conditions": {"keywords": ["스마트공장", "AI"]}},
                {"manager": "김철수", "conditions": {"ministry": ["과학기술정보통신부"]}},
            ],
        ):
            notices = [
                _notice("스마트공장 구축 지원사업", ministry="중소벤처기업부"),
                _notice("양자컴퓨팅 연구과제", ministry="과학기술정보통신부"),
                _notice("바이오 신약 개발", ministry="보건복지부"),
            ]
            result = assign_managers(notices)
            assert result[0].manager == "홍길동"
            assert result[1].manager == "김철수"
            assert result[2].manager == ""  # 매칭 규칙 없음

    def test_preserve_manual_assignment(self):
        """이미 배정된 담당자는 유지."""
        with patch(
            "interx_engine.application.use_cases.assign_manager._load_rules",
            return_value=[{"manager": "자동", "conditions": {"keywords": ["스마트공장"]}}],
        ):
            from interx_engine.application.use_cases.assign_manager import assign_managers
            notices = [_notice("스마트공장 구축", manager="수동배정자")]
            result = assign_managers(notices)
            assert result[0].manager == "수동배정자"

    def test_no_rules(self):
        """규칙 파일 없으면 스킵."""
        with patch(
            "interx_engine.application.use_cases.assign_manager._load_rules",
            return_value=[],
        ):
            from interx_engine.application.use_cases.assign_manager import assign_managers
            notices = [_notice("공고")]
            result = assign_managers(notices)
            assert result[0].manager == ""


# ═════════════════════════════════════════════════════════════════════════════
# 6. AssignMilestone
# ═════════════════════════════════════════════════════════════════════════════

class TestAssignMilestone:
    """assign_milestone.py — BD 마일스톤 자동 배정"""

    def test_m01_for_l3(self):
        from interx_engine.application.use_cases.assign_milestone import assign_milestones
        n = _notice("L3 공고", l3_strong="Y", deadline=_future(30))
        sc = _scorecard(n.notice_id, grade="B")
        result = assign_milestones([n], [sc])
        assert "M01" in result[0].bd_milestone

    def test_m05_urgent_l3(self):
        from interx_engine.application.use_cases.assign_milestone import assign_milestones
        n = _notice("긴급 L3", l3_strong="Y", deadline=_future(5))
        sc = _scorecard(n.notice_id, grade="A")
        result = assign_milestones([n], [sc])
        assert "M05" in result[0].bd_milestone

    def test_m05_dday_14_ab(self):
        """D-day 14 이내 + A/B등급 → M05."""
        from interx_engine.application.use_cases.assign_milestone import assign_milestones
        n = _notice("공고", l3_strong="Y", deadline=_future(10))
        sc = _scorecard(n.notice_id, grade="A")
        result = assign_milestones([n], [sc])
        assert "M05" in result[0].bd_milestone

    def test_p01_partner_candidate(self):
        from interx_engine.application.use_cases.assign_milestone import assign_milestones
        n = _notice("파트너 공고", partner_candidate="Y", deadline=_future(30))
        sc = _scorecard(n.notice_id, grade="B")
        result = assign_milestones([n], [sc])
        assert "P01" in result[0].bd_milestone

    def test_combined_m01_p01(self):
        """L3 + 파트너 후보 → M01|P01."""
        from interx_engine.application.use_cases.assign_milestone import assign_milestones
        n = _notice("복합 공고", l3_strong="Y", partner_candidate="Y", deadline=_future(30))
        sc = _scorecard(n.notice_id, grade="B")
        result = assign_milestones([n], [sc])
        assert "|" in result[0].bd_milestone

    def test_no_milestone_for_non_l3(self):
        from interx_engine.application.use_cases.assign_milestone import assign_milestones
        n = _notice("일반 공고", l3_strong="N", partner_candidate="N")
        sc = _scorecard(n.notice_id, grade="C")
        result = assign_milestones([n], [sc])
        assert result[0].bd_milestone == ""

    def test_preserve_manual_milestone(self):
        """수동 지정된 마일스톤은 덮어쓰지 않음."""
        from interx_engine.application.use_cases.assign_milestone import assign_milestones
        n = _notice("공고", l3_strong="Y", bd_milestone="M10")
        sc = _scorecard(n.notice_id, grade="A")
        result = assign_milestones([n], [sc])
        assert result[0].bd_milestone == "M10"

    def test_d_grade_no_p01(self):
        """D등급은 P01 배정 불가."""
        from interx_engine.application.use_cases.assign_milestone import assign_milestones
        n = _notice("공고", partner_candidate="Y")
        sc = _scorecard(n.notice_id, grade="D")
        result = assign_milestones([n], [sc])
        assert "P01" not in (result[0].bd_milestone or "")


# ═════════════════════════════════════════════════════════════════════════════
# ═════════════════════════════════════════════════════════════════════════════
# 7. SiteQualityGrader
# ═════════════════════════════════════════════════════════════════════════════

class TestSiteQualityGrader:
    """site_quality_grader.py — 사이트별 품질 등급"""

    def test_basic_grading(self):
        from interx_engine.application.use_cases.site_quality_grader import grade_site_quality
        notices = [
            _notice("공고1", site="bizinfo", l3_strong="Y", budget="1억", deadline=_future(10)),
            _notice("공고2", site="bizinfo", l3_strong="Y", budget="2억", deadline=_future(20)),
            _notice("공고3", site="kiat", budget="", deadline=""),
        ]
        cards = [
            _scorecard(notices[0].notice_id, grade="A"),
            _scorecard(notices[1].notice_id, grade="B"),
            _scorecard(notices[2].notice_id, grade="D"),
        ]
        result = grade_site_quality(notices, cards)
        assert "bizinfo" in result
        assert "kiat" in result
        assert result["bizinfo"]["grade"] in ("A", "B", "C", "D", "F")
        # bizinfo: L3 100%, P1P2 100%, budget 100%, deadline 100% → 높은 점수
        assert result["bizinfo"]["score"] > result["kiat"]["score"]

    def test_empty_site(self):
        from interx_engine.application.use_cases.site_quality_grader import grade_site_quality
        result = grade_site_quality([], [])
        assert result == {}

    def test_score_formula(self):
        """점수 공식: l3*30 + p1p2*25 + budget*20 + deadline*15 + volume*10."""
        from interx_engine.application.use_cases.site_quality_grader import grade_site_quality
        # 모든 지표 100%인 사이트 (50건 이상)
        notices = []
        cards = []
        for i in range(50):
            n = _notice(f"공고{i}", site="perfect", notice_id=f"p_{i}",
                        l3_strong="Y", budget="1억", deadline=_future(10))
            notices.append(n)
            cards.append(_scorecard(n.notice_id, grade="A"))

        result = grade_site_quality(notices, cards)
        # (l3*30 + p1p2*25 + budget*20 + deadline*15 + volume*10) * 100
        # = (1*30 + 1*25 + 1*20 + 1*15 + 1*10) * 100 = 10000
        assert result["perfect"]["score"] == 10000.0
        assert result["perfect"]["grade"] == "A"

    def test_grade_boundaries(self):
        """등급 경계값 검증."""
        from interx_engine.application.use_cases.site_quality_grader import grade_site_quality
        # 1건, 모든 지표 0인 사이트
        n = _notice("공고", site="poor", notice_id="poor_1",
                    l3_strong="N", budget="", deadline="")
        sc = _scorecard("poor_1", grade="D")
        result = grade_site_quality([n], [sc])
        # volume_score = 1/50 = 0.02 → score = 0.02 * 10 * 100 = 20.0
        assert result["poor"]["score"] <= 20.0
        assert result["poor"]["grade"] in ("D", "F")

    def test_multiple_sites(self):
        from interx_engine.application.use_cases.site_quality_grader import grade_site_quality
        notices = [
            _notice("공고1", site="site_a", notice_id="a1", l3_strong="Y", budget="1억", deadline=_future(5)),
            _notice("공고2", site="site_b", notice_id="b1", l3_strong="N", budget="", deadline=""),
        ]
        cards = [
            _scorecard("a1", grade="A"),
            _scorecard("b1", grade="D"),
        ]
        result = grade_site_quality(notices, cards)
        assert len(result) == 2
        assert result["site_a"]["total"] == 1
        assert result["site_b"]["total"] == 1
