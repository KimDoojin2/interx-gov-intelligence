from __future__ import annotations
from typing import List, Protocol
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.core.entities.cluster import NoticeCluster


class ClustererPort(Protocol):
    def cluster(
        self,
        notices: List[Notice],
        score_cards: List[ScoreCard],
    ) -> List[NoticeCluster]: ...


class ClusterNoticesUseCase:
    """
    유사 공고를 그룹화한다.
    기본 구현: TF-IDF + cosine similarity (infrastructure/clustering/tfidf_clusterer.py)
    """

    def __init__(self, clusterer: ClustererPort):
        self.clusterer = clusterer

    def execute(
        self,
        notices: List[Notice],
        score_cards: List[ScoreCard],
    ) -> List[NoticeCluster]:
        if len(notices) < 2:
            return []
        return self.clusterer.cluster(notices, score_cards)
