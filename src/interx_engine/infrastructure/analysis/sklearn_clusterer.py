"""
ScikitLearnClusterer — KMeans 기반 의미론적 클러스터링
TfidfClusterer(코사인 유사도 중복제거)와 별개로,
포트폴리오 분석용 그룹화에 특화된다.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.clusterer")


class ScikitLearnClusterer:
    """
    notices → {cluster_id: [notice_id, ...]} 매핑 반환.

    tfidf_clusterer.py 와의 차이:
      - tfidf_clusterer: 코사인 유사도로 중복 제거 (cross-site dedup)
      - ScikitLearnClusterer: KMeans로 전략적 그룹화 (포트폴리오 분석용)
    """

    def __init__(self, n_clusters: int = 0, min_cluster_size: int = 2):
        self.n_clusters      = n_clusters       # 0이면 자동 결정
        self.min_cluster_size = min_cluster_size

    def fit_predict(self, notices: List[Notice]) -> Dict[str, List[str]]:
        if len(notices) < self.min_cluster_size:
            return {"0": [n.notice_id for n in notices]}

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
            from sklearn.cluster import KMeans  # type: ignore
        except ImportError:
            log.warning("[Clusterer] scikit-learn 없음")
            return {"0": [n.notice_id for n in notices]}

        k = self.n_clusters or min(max(2, len(notices) // 8), 12)
        texts = [f"{n.title} {n.summary or ''}" for n in notices]

        try:
            vec    = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3),
                                     min_df=1, max_features=5000)
            tfidf  = vec.fit_transform(texts)
            labels = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(tfidf)
        except Exception as e:
            log.warning("[Clusterer] KMeans 실패: %s", e)
            return {"0": [n.notice_id for n in notices]}

        groups: Dict[str, List[str]] = {}
        for notice, label in zip(notices, labels):
            cid = str(label)
            groups.setdefault(cid, []).append(notice.notice_id)
            notice.cluster_id = cid

        log.info("[Clusterer] %d건 → %d클러스터", len(notices), len(groups))
        return groups
