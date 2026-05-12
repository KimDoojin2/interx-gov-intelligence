"""
EmbeddingClusterer — sentence-transformers 기반 시맨틱 클러스터링
TfidfClusterer와 동일 인터페이스 (drop-in replacement).

모델: paraphrase-multilingual-MiniLM-L12-v2
  - 무료 / 로컬 / 한국어 지원 / 약 420MB (첫 실행 시 자동 다운로드)
  - 설치: pip install sentence-transformers

미설치 시 TfidfClusterer로 자동 fallback.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import List, Optional

from interx_engine.core.entities.cluster import NoticeCluster
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard

log = logging.getLogger("interx.embedding_clusterer")

_DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingClusterer:
    """
    sentence-transformers 기반 시맨틱 클러스터링.

    TF-IDF는 글자 n-gram 유사도만 보지만,
    Embedding은 의미(semantic) 유사도를 계산하므로
    표현이 달라도 같은 주제의 공고를 더 정확하게 묶는다.

    Parameters
    ----------
    threshold : float
        cosine similarity 기준값. 높을수록 더 유사한 것만 묶음.
        권장: 0.65 ~ 0.75 (TF-IDF 0.55 대비 약간 높게 설정)
    min_cluster_size : int
        최소 클러스터 크기. 이 값 미만이면 클러스터로 인정 안 함.
    model_name : str
        sentence-transformers 모델명. 기본: paraphrase-multilingual-MiniLM-L12-v2
    batch_size : int
        인코딩 배치 크기. GPU 없는 경우 32~64 권장.
    """

    def __init__(
        self,
        threshold: float = 0.70,
        min_cluster_size: int = 2,
        model_name: str = _DEFAULT_MODEL,
        batch_size: int = 64,
    ):
        self.threshold        = threshold
        self.min_cluster_size = min_cluster_size
        self.model_name       = model_name
        self.batch_size       = batch_size
        self._model           = None  # lazy load

    def _get_model(self):
        """모델 lazy load — 첫 호출 시 다운로드 (약 420MB)."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore
            log.info("[EmbeddingClusterer] 모델 로딩: %s (첫 실행 시 다운로드)", self.model_name)
            self._model = SentenceTransformer(self.model_name)
            log.info("[EmbeddingClusterer] 모델 로딩 완료")
        return self._model

    # ── 공개 메서드 (TfidfClusterer와 동일 인터페이스) ──────────────────────

    def cluster(
        self,
        notices: List[Notice],
        score_cards: List[ScoreCard],
    ) -> List[NoticeCluster]:
        """
        공고 목록을 시맨틱 임베딩으로 클러스터링.
        sentence-transformers 미설치 시 TfidfClusterer로 자동 fallback.
        """
        if not notices:
            return []
        try:
            return self._cluster_with_embeddings(notices, score_cards)
        except ImportError:
            log.warning(
                "[EmbeddingClusterer] sentence-transformers 미설치 → "
                "TfidfClusterer fallback (pip install sentence-transformers)"
            )
            return self._tfidf_fallback(notices, score_cards)
        except Exception as exc:
            log.error("[EmbeddingClusterer] 오류: %s → TfidfClusterer fallback", exc)
            return self._tfidf_fallback(notices, score_cards)

    # ── 내부 구현 ───────────────────────────────────────────────────────────

    def _cluster_with_embeddings(
        self,
        notices: List[Notice],
        score_cards: List[ScoreCard],
    ) -> List[NoticeCluster]:
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore

        model     = self._get_model()
        score_map = {s.notice_id: s for s in score_cards}

        # 텍스트 구성: 제목 + 요약 (요약 없으면 본문 앞 200자)
        texts = [
            f"{n.title} {n.summary or n.body_text[:200]}"
            for n in notices
        ]

        log.info("[EmbeddingClusterer] 임베딩 계산: %d건", len(texts))
        embeddings = model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,  # cosine similarity = dot product
        )

        # cosine similarity matrix (normalize=True → dot product 충분)
        sim = embeddings @ embeddings.T

        n       = len(notices)
        visited = [False] * n
        clusters: List[NoticeCluster] = []

        for i in range(n):
            if visited[i]:
                continue
            group    = [i]
            visited[i] = True

            for j in range(i + 1, n):
                if not visited[j] and sim[i, j] >= self.threshold:
                    group.append(j)
                    visited[j] = True

            if len(group) < self.min_cluster_size:
                continue

            clusters.append(
                self._build_cluster(f"EMB-{i:04d}", group, notices, score_map)
            )

        log.info(
            "[EmbeddingClusterer] %d개 클러스터 생성 (threshold=%.2f, 모델=%s)",
            len(clusters), self.threshold, self.model_name,
        )
        return clusters

    def _build_cluster(
        self,
        cluster_id: str,
        group: List[int],
        notices: List[Notice],
        score_map: dict,
    ) -> NoticeCluster:
        """그룹 인덱스 목록으로 NoticeCluster 엔티티 생성."""
        # 대표 공고: fitness_score 최고
        rep_idx = max(
            group,
            key=lambda idx: (
                score_map.get(notices[idx].notice_id) and
                score_map[notices[idx].notice_id].fitness_score or 0.0
            ),
        )
        rep_notice = notices[rep_idx]
        rep_score  = score_map.get(rep_notice.notice_id)

        # 공통 키워드 집계
        all_kw: List[List[str]] = [
            score_map[notices[idx].notice_id].positive_keywords
            for idx in group
            if notices[idx].notice_id in score_map
        ]
        common_kw: List[str] = []
        if all_kw:
            counter   = Counter(kw for kws in all_kw for kw in kws)
            common_kw = [kw for kw, cnt in counter.most_common(5) if cnt > 1]

        # 대표 솔루션
        top_sol = ""
        if rep_score and rep_score.solution_scores:
            top_sol = max(rep_score.solution_scores, key=rep_score.solution_scores.get)

        return NoticeCluster(
            cluster_id           = cluster_id,
            notice_ids           = [notices[idx].notice_id for idx in group],
            representative_title = rep_notice.title,
            common_keywords      = common_kw,
            top_solution         = top_sol,
        )

    def _tfidf_fallback(
        self,
        notices: List[Notice],
        score_cards: List[ScoreCard],
    ) -> List[NoticeCluster]:
        from interx_engine.infrastructure.clustering.tfidf_clusterer import TfidfClusterer
        return TfidfClusterer(
            threshold=self.threshold,
            min_cluster_size=self.min_cluster_size,
        ).cluster(notices, score_cards)
