from __future__ import annotations

import logging
from pathlib import Path
from typing import Set, Tuple

from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.l3")

_DEFAULT_KEYWORDS: Set[str] = {
    "스마트공장", "스마트팩토리", "디지털트윈", "예지보전",
    "제조ai", "산업ai", "제조인공지능", "ax",
    "머신비전", "비전검사", "이상탐지", "중대재해",
    "ai팩토리", "공정최적화", "제조안전",
}
_DEFAULT_MIN_HITS = 2


def _load_l3_config() -> Tuple[Set[str], int]:
    """scoring.yaml의 l3_keywords 섹션 로드. 실패 시 기본값 반환."""
    here = Path(__file__).resolve()
    for _ in range(6):
        candidate = here / "configs" / "scoring.yaml"
        if candidate.exists():
            try:
                import yaml
                raw = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
                cfg = raw.get("l3_keywords", {})
                keywords = set(cfg.get("keywords", [])) or _DEFAULT_KEYWORDS
                min_hits = int(cfg.get("min_hits", _DEFAULT_MIN_HITS))
                return keywords, min_hits
            except Exception as e:
                log.warning("scoring.yaml l3_keywords 로드 실패: %s — fallback 사용", e)
        here = here.parent
    return _DEFAULT_KEYWORDS, _DEFAULT_MIN_HITS


class L3StrongPolicy:
    """
    키워드 기반 L3 사전 필터. scoring.yaml의 l3_keywords 섹션을 참조한다.
    제목+요약+사업유형에 핵심 키워드가 min_hits개 이상 포함되면 L3 후보로 판단.
    최종 notice.l3_strong은 PriorityScoringPolicy(fitness 기반)가 확정한다.
    """

    def __init__(self):
        self.keywords, self.min_hits = _load_l3_config()

    def is_l3_strong(self, notice: Notice) -> bool:
        text = f"{notice.title} {notice.summary} {notice.business_type}".lower()
        hits = sum(1 for kw in self.keywords if kw in text)
        return hits >= self.min_hits
