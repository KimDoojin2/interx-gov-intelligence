"""
TF-IDF 코사인 유사도 기반 중복 공고 완전 제거
같은 사업이 여러 사이트에 중복 게시된 경우 낮은 점수 공고를 리스트에서 삭제.
(플래그만 마킹하지 않고 실제 제거 — 시트에 중복 공고 자체가 올라오지 않음)
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard

log = logging.getLogger("interx.dedup")

def _sim_threshold() -> float:
    from interx_engine.application.ports.settings_port import sim_threshold
    return sim_threshold()


def deduplicate_by_tfidf(
    notices: List[Notice],
    score_cards: List[ScoreCard],
) -> Tuple[List[Notice], int]:
    """
    TF-IDF + 코사인 유사도로 cross-site 중복 공고를 완전 제거.

    - 같은 사이트 내 공고는 비교하지 않음 (이미 notice_id 중복 제거됨)
    - 유사도 >= threshold: 두 공고 중 적합도 낮은 쪽을 리스트에서 삭제
    - sklearn 없으면 스킵 (공고 손실 없음)

    Returns:
        (deduplicated_notices, removed_count)
    """
    if len(notices) < 2:
        return notices, 0

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        log.warning("[Dedup] scikit-learn 없음 — 중복 제거 스킵")
        return notices, 0

    score_map = {s.notice_id: (s.fitness_score or 0) for s in score_cards}
    titles    = [n.title for n in notices]

    try:
        vec   = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), min_df=1)
        tfidf = vec.fit_transform(titles)
        sim   = cosine_similarity(tfidf)
    except Exception as e:
        log.warning("[Dedup] TF-IDF 계산 실패: %s", e)
        return notices, 0

    remove_idx: set = set()
    n = len(notices)

    for i in range(n):
        if i in remove_idx:
            continue
        for j in range(i + 1, n):
            if j in remove_idx:
                continue
            # 같은 사이트 공고끼리는 비교 제외
            if notices[i].site == notices[j].site:
                continue
            if sim[i, j] >= _sim_threshold():
                score_i = score_map.get(notices[i].notice_id, 0)
                score_j = score_map.get(notices[j].notice_id, 0)
                # 낮은 점수 쪽을 제거 대상으로 마킹
                drop_idx = j if score_i >= score_j else i
                remove_idx.add(drop_idx)
                log.debug(
                    "[Dedup] 중복 제거 (유사도=%.2f): '%s' ↔ '%s' → '%s' 삭제",
                    sim[i, j],
                    notices[i].title[:25],
                    notices[j].title[:25],
                    notices[drop_idx].title[:25],
                )

    removed_count = len(remove_idx)
    if removed_count:
        kept = [n for idx, n in enumerate(notices) if idx not in remove_idx]
        log.info("[Dedup] 중복 공고 %d건 완전 제거 (%d → %d건)",
                 removed_count, len(notices), len(kept))
        return kept, removed_count

    return notices, 0
