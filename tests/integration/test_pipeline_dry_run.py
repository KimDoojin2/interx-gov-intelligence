"""
파이프라인 end-to-end 통합 테스트 (dry-run)
MockNoticeCollector + 로컬 로직만 사용 — 외부 의존성 없음
실행: pytest tests/integration/test_pipeline_dry_run.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from typing import List, Tuple

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.infrastructure.collectors.sites.mock_notice_collector import MockNoticeCollector
from interx_engine.application.use_cases.score_notices import ScoreNoticesUseCase
from interx_engine.application.use_cases.detect_changes import detect_changes
from interx_engine.application.use_cases.deduplicate_notices import deduplicate_by_tfidf
from interx_engine.application.mappers.notice_mapper import notice_to_master_row, notice_to_urgent_row
from interx_engine.application.mappers.kpi_mapper import (
    build_kpi_rows, build_exec_log_row, build_collect_log_rows,
)

EXECUTION_ID = "INTEG-TEST-001"


def _collect() -> List[Notice]:
    return MockNoticeCollector().collect(EXECUTION_ID)


def _score(notices: List[Notice]) -> Tuple[List[Notice], List[ScoreCard]]:
    use_case = ScoreNoticesUseCase()
    return use_case.execute(notices)   # (notices, score_cards)


class TestMockCollect:
    def test_returns_notices(self):
        notices = _collect()
        assert len(notices) >= 1

    def test_notice_fields_populated(self):
        notice = _collect()[0]
        assert notice.execution_id == EXECUTION_ID
        assert notice.title
        assert notice.site == "mock"


class TestScoreNotices:
    def test_score_cards_match_notices(self):
        notices = _collect()
        _, cards = _score(notices)
        assert len(cards) == len(notices)

    def test_all_cards_have_grade(self):
        notices = _collect()
        _, cards = _score(notices)
        for card in cards:
            assert card.priority_grade in ("A", "B", "C", "D")

    def test_fitness_in_range(self):
        notices = _collect()
        _, cards = _score(notices)
        for card in cards:
            assert 0.0 <= card.fitness_score <= 100.0


class TestDetectChanges:
    def test_first_run_all_new(self, tmp_path, monkeypatch):
        monkeypatch.setenv("INTERX_CACHE_PATH", str(tmp_path / "cache.json"))
        notices = _collect()
        result, new_cnt, changed_cnt = detect_changes(notices)
        assert new_cnt == len(notices)
        assert changed_cnt == 0

    def test_second_run_no_new(self, tmp_path, monkeypatch):
        monkeypatch.setenv("INTERX_CACHE_PATH", str(tmp_path / "cache.json"))
        notices = _collect()
        detect_changes(notices)
        _, new_cnt, changed_cnt = detect_changes(notices)
        assert new_cnt == 0
        assert changed_cnt == 0


class TestDeduplication:
    def test_identical_site_not_deduped(self):
        notices = _collect()
        _, cards = _score(notices)
        kept, removed = deduplicate_by_tfidf(notices, cards)
        # mock 공고는 모두 site="mock" → 같은 사이트 비교 제외
        assert removed == 0
        assert len(kept) == len(notices)

    def test_single_notice_not_deduped(self):
        notices = _collect()[:1]
        _, cards = _score(notices)
        kept, removed = deduplicate_by_tfidf(notices, cards)
        assert removed == 0


class TestMappers:
    def test_master_row_has_minimum_keys(self):
        notices = _collect()
        _, cards = _score(notices)
        sc_map  = {c.notice_id: c for c in cards}
        row = notice_to_master_row(notices[0], sc_map.get(notices[0].notice_id))
        assert len(row) >= 24   # v3 이후 추가 필드 포함

    def test_master_row_required_keys(self):
        notices = _collect()
        _, cards = _score(notices)
        sc_map  = {c.notice_id: c for c in cards}
        row = notice_to_master_row(notices[0], sc_map.get(notices[0].notice_id))
        for key in ["실행ID", "사이트", "공고명", "마감일", "D-day", "마감여부",
                    "적합도점수", "우선순위등급", "상세URL"]:
            assert key in row, f"마스터 행 키 누락: {key}"

    def test_urgent_row_11_keys(self):
        notices = _collect()
        _, cards = _score(notices)
        sc_map  = {c.notice_id: c for c in cards}
        row = notice_to_urgent_row(notices[0], sc_map.get(notices[0].notice_id))
        assert len(row) == 11

    def test_urgent_row_required_keys(self):
        notices = _collect()
        _, cards = _score(notices)
        sc_map  = {c.notice_id: c for c in cards}
        row = notice_to_urgent_row(notices[0], sc_map.get(notices[0].notice_id))
        for key in ["사이트", "공고명", "마감일", "D-day", "우선순위등급", "상세URL"]:
            assert key in row, f"긴급마감 행 키 누락: {key}"


class TestKpiMapper:
    def test_kpi_rows_nonempty(self):
        notices = _collect()
        _, cards = _score(notices)
        rows = build_kpi_rows(EXECUTION_ID, notices, cards)
        assert len(rows) > 0

    def test_kpi_rows_have_required_keys(self):
        notices = _collect()
        _, cards = _score(notices)
        rows = build_kpi_rows(EXECUTION_ID, notices, cards)
        for row in rows:
            for key in ("기준일", "구분", "지표", "값", "실행ID"):
                assert key in row

    def test_exec_log_row_keys(self):
        row = build_exec_log_row(
            EXECUTION_ID, step="collect", status="success", elapsed_sec=3.14
        )
        assert row["실행ID"] == EXECUTION_ID
        assert row["단계"] == "collect"
        assert row["상태"] == "success"
        assert row["소요초"] == 3.1

    def test_collect_log_rows(self):
        notices = _collect()
        rows = build_collect_log_rows(EXECUTION_ID, notices)
        assert len(rows) == len(notices)
        for row in rows:
            assert "사이트" in row
            assert "공고명" in row
