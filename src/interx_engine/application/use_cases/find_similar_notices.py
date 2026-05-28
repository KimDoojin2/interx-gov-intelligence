"""
유사 공고 추천 — TF-IDF 코사인 유사도 기반으로 현재 공고와 비슷한 과거/현재 공고를 찾는다.

사용:
    from interx_engine.application.use_cases.find_similar_notices import find_similar
    similar = find_similar(target_notice, all_notices, top_k=3)
    # → [{"notice": Notice, "similarity": 0.87}, ...]
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.similar")


def find_similar(
    target: Notice,
    candidates: List[Notice],
    top_k: int = 5,
    min_similarity: float = 0.25,
) -> List[Dict]:
    """
    target 공고와 유사한 공고를 candidates에서 찾아 top_k개 반환.

    Returns:
        [{"notice": Notice, "similarity": float, "shared_keywords": list}, ...]
    """
    if not candidates or len(candidates) < 2:
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        log.warning("[Similar] scikit-learn 미설치 — 유사 공고 검색 불가")
        return []

    # target + candidates 전체의 텍스트를 벡터화
    filtered = [c for c in candidates if c.notice_id != target.notice_id]
    if not filtered:
        return []

    def _text(n: Notice) -> str:
        parts = [n.title or ""]
        if n.summary:
            parts.append(n.summary)
        for key in ("사업목적", "지원내용", "지원대상"):
            v = (n.structured or {}).get(key, "")
            if v:
                parts.append(v)
        if n.recommended_solution:
            parts.append(n.recommended_solution)
        return " ".join(parts)

    target_text = _text(target)
    all_texts = [target_text] + [_text(c) for c in filtered]

    try:
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1, max_features=5000)
        tfidf = vec.fit_transform(all_texts)
        sims = cosine_similarity(tfidf[0:1], tfidf[1:])[0]
    except Exception as e:
        log.warning("[Similar] TF-IDF 계산 실패: %s", e)
        return []

    # 유사도 순 정렬
    scored = []
    for idx, sim in enumerate(sims):
        if sim >= min_similarity:
            scored.append((filtered[idx], float(sim)))
    scored.sort(key=lambda x: -x[1])

    results = []
    for notice, sim in scored[:top_k]:
        # 공통 키워드 추출
        target_words = set(target.title.split()) if target.title else set()
        notice_words = set(notice.title.split()) if notice.title else set()
        shared = sorted(target_words & notice_words - {"공고", "사업", "지원", "및", "의", "등"})

        results.append({
            "notice": notice,
            "similarity": round(sim, 3),
            "shared_keywords": shared[:5],
        })

    return results


def find_similar_from_db(
    target: Notice,
    db_path: str = "",
    top_k: int = 5,
) -> List[Dict]:
    """
    SQLite DB에서 과거 공고를 로드하여 유사도 비교.
    DB가 없으면 빈 리스트 반환.
    """
    from pathlib import Path

    if not db_path:
        from interx_engine.application.ports.settings_port import project_root
        db_path = str(Path(project_root()) / "data" / "interx_engine.db")

    db_file = Path(db_path)
    if not db_file.exists():
        return []

    try:
        import sqlite3
        conn = sqlite3.connect(str(db_file))
        rows = conn.execute(
            "SELECT notice_id, site, title, deadline_date, budget, detail_url "
            "FROM notices ORDER BY rowid DESC LIMIT 500"
        ).fetchall()
        conn.close()
    except Exception as e:
        log.warning("[Similar] DB 로드 실패: %s", e)
        return []

    candidates = []
    for r in rows:
        n = Notice(
            execution_id="db",
            site=r[1] or "",
            notice_id=r[0],
            title=r[2] or "",
            deadline_date=r[3] or "",
            budget=r[4] or "",
            detail_url=r[5] or "",
        )
        candidates.append(n)

    return find_similar(target, candidates, top_k=top_k)
