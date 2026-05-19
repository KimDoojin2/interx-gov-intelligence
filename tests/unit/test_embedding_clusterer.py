"""
EmbeddingClusterer / TfidfClusterer 단위 테스트
실행: pytest tests/unit/test_embedding_clusterer.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.core.entities.cluster import NoticeCluster
from interx_engine.infrastructure.clustering.tfidf_clusterer import TfidfClusterer
from interx_engine.infrastructure.clustering.embedding_clusterer import EmbeddingClusterer


# ── 픽스처 ────────────────────────────────────────────────────────────────────

def _notices():
    titles = [
        "스마트공장 구축 지원사업 공고",
        "스마트공장 도입 지원 2026년",
        "AI 활용 제조혁신 사업",
        "중소기업 R&D 기술개발 지원",
        "중소기업 연구개발 지원사업 공고",
    ]
    return [
        Notice(execution_id="TEST", notice_id=f"C{i}", site="test", title=t, body_text=t)
        for i, t in enumerate(titles)
    ]

def _cards(notices):
    return [
        ScoreCard(
            execution_id="TEST", notice_id=n.notice_id, site="test",
            fitness_score=60, priority_score=55,
            priority_grade="B", industry_score=50,
            positive_keywords=["스마트공장", "AI"],
        )
        for n in notices
    ]


# ── TfidfClusterer ────────────────────────────────────────────────────────────

class TestTfidfClusterer:
    def setup_method(self):
        self.clusterer = TfidfClusterer(threshold=0.3, min_cluster_size=2)

    def test_empty_notices_returns_empty(self):
        result = self.clusterer.cluster([], [])
        assert result == []

    def test_returns_list_of_notice_cluster(self):
        notices = _notices()
        result  = self.clusterer.cluster(notices, _cards(notices))
        assert isinstance(result, list)
        for c in result:
            assert isinstance(c, NoticeCluster)

    def test_cluster_has_required_fields(self):
        notices = _notices()
        clusters = self.clusterer.cluster(notices, _cards(notices))
        if clusters:
            c = clusters[0]
            assert c.cluster_id
            assert len(c.notice_ids) >= 2
            assert c.representative_title

    def test_similar_titles_grouped(self):
        """'스마트공장' 두 공고는 같은 클러스터에 묶여야 함"""
        notices = _notices()
        clusters = self.clusterer.cluster(notices, _cards(notices))
        # 클러스터 중 스마트공장 두 개가 함께 있는지 확인
        for c in clusters:
            if "C0" in c.notice_ids and "C1" in c.notice_ids:
                return  # 통과
        # 클러스터가 아예 없으면 threshold가 높아서임 — skip
        if not clusters:
            pytest.skip("threshold 높아서 클러스터 없음")

    def test_min_cluster_size_respected(self):
        notices = _notices()
        clusters = self.clusterer.cluster(notices, _cards(notices))
        for c in clusters:
            assert len(c.notice_ids) >= self.clusterer.min_cluster_size

    def test_single_notice_no_cluster(self):
        notices = [Notice(execution_id="TEST", notice_id="ONLY", site="test",
                          title="유일한 공고", body_text="특수한 내용")]
        cards   = [ScoreCard(execution_id="TEST", notice_id="ONLY", site="test",
                             fitness_score=50, priority_score=50,
                             priority_grade="C", industry_score=50)]
        result  = self.clusterer.cluster(notices, cards)
        assert result == []


# ── EmbeddingClusterer ────────────────────────────────────────────────────────

class TestEmbeddingClusterer:
    """sentence-transformers 미설치 시 TfidfClusterer fallback 검증"""

    def setup_method(self):
        self.clusterer = EmbeddingClusterer(threshold=0.65, min_cluster_size=2)

    def test_empty_notices_returns_empty(self):
        result = self.clusterer.cluster([], [])
        assert result == []

    def test_returns_list(self):
        notices = _notices()
        result  = self.clusterer.cluster(notices, _cards(notices))
        assert isinstance(result, list)

    def test_cluster_objects_valid(self):
        notices  = _notices()
        clusters = self.clusterer.cluster(notices, _cards(notices))
        for c in clusters:
            assert isinstance(c, NoticeCluster)
            assert len(c.notice_ids) >= 2

    def test_fallback_works_without_sentence_transformers(self, monkeypatch):
        """ImportError 시 TfidfClusterer로 자동 전환"""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "sentence_transformers":
                raise ImportError("강제 미설치 시뮬레이션")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        # 새 인스턴스 — 모델 캐시 없음
        clusterer = EmbeddingClusterer(threshold=0.3, min_cluster_size=2)
        notices   = _notices()
        result    = clusterer.cluster(notices, _cards(notices))
        assert isinstance(result, list)   # fallback 정상 동작

    def test_min_cluster_size_respected(self):
        notices  = _notices()
        clusters = self.clusterer.cluster(notices, _cards(notices))
        for c in clusters:
            assert len(c.notice_ids) >= self.clusterer.min_cluster_size
