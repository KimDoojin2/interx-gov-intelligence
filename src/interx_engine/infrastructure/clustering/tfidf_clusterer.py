from __future__ import annotations
import logging
from typing import List
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.core.entities.cluster import NoticeCluster

log = logging.getLogger(__name__)


class TfidfClusterer:
    """
    제목+요약 TF-IDF → cosine similarity → threshold 기반 그룹화.

    threshold: 0.0 ~ 1.0  (높을수록 더 유사한 공고만 묶임, 기본 0.55)
    LLM 확장 포인트: cluster() 메서드를 EmbeddingClusterer로 교체 가능.
    """

    def __init__(self, threshold: float = 0.55, min_cluster_size: int = 2):
        self.threshold        = threshold
        self.min_cluster_size = min_cluster_size

    def cluster(
        self,
        notices: List[Notice],
        score_cards: List[ScoreCard],
    ) -> List[NoticeCluster]:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
        except ImportError:
            log.warning("scikit-learn 미설치 — 클러스터링 스킵 (pip install scikit-learn)")
            return []

        score_map = {s.notice_id: s for s in score_cards}
        texts = [f"{n.title} {n.summary}" for n in notices]

        try:
            vec    = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), max_features=3000)
            matrix = vec.fit_transform(texts)
            sim    = cosine_similarity(matrix)
        except Exception as e:
            log.warning("TF-IDF 계산 실패: %s", e)
            return []

        n = len(notices)
        visited = [False] * n
        clusters: List[NoticeCluster] = []

        for i in range(n):
            if visited[i]:
                continue
            group = [i]
            visited[i] = True
            for j in range(i + 1, n):
                if not visited[j] and sim[i, j] >= self.threshold:
                    group.append(j)
                    visited[j] = True

            if len(group) < self.min_cluster_size:
                continue

            # 대표 공고: fitness 점수 최고
            rep_idx = max(
                group,
                key=lambda idx: score_map.get(notices[idx].notice_id, None) and
                                score_map[notices[idx].notice_id].fitness_score or 0,
            )
            rep_notice = notices[rep_idx]
            rep_score  = score_map.get(rep_notice.notice_id)

            # 공통 키워드
            all_kw: List[List[str]] = []
            for idx in group:
                sc = score_map.get(notices[idx].notice_id)
                if sc:
                    all_kw.append(sc.positive_keywords)
            common_kw: List[str] = []
            if all_kw:
                from collections import Counter
                counter = Counter(kw for kws in all_kw for kw in kws)
                common_kw = [kw for kw, cnt in counter.most_common(5) if cnt > 1]

            # 대표 솔루션
            top_sol = ""
            if rep_score and rep_score.solution_scores:
                top_sol = max(rep_score.solution_scores, key=rep_score.solution_scores.get)

            clusters.append(NoticeCluster(
                cluster_id=f"CLU-{i:04d}",
                notice_ids=[notices[idx].notice_id for idx in group],
                representative_title=rep_notice.title,
                common_keywords=common_kw,
                top_solution=top_sol,
            ))

        log.info("클러스터링 결과: %d개 클러스터 (임계값=%.2f)", len(clusters), self.threshold)
        return clusters
