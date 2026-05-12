"""
정기공고 감지 유스케이스
— configs/recurring.yaml 의 패턴과 매칭하여
  Notice.recurring_flag / Notice.recurring_group 필드를 채운다.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Dict, Tuple

from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.recurring")

# ── 패턴 로드 ─────────────────────────────────────────────────────────────────

def _load_patterns() -> List[Tuple[str, List[str]]]:
    """
    recurring.yaml 을 로드해 (name, [aliases]) 리스트 반환.
    실패 시 빈 리스트 (패턴 없으면 전체 non-recurring).
    """
    here = Path(__file__).resolve()
    candidates: List[Path] = []
    for _ in range(8):
        candidate = here / "configs" / "recurring.yaml"
        if candidate.exists():
            candidates.append(candidate)
        here = here.parent
    if not candidates:
        log.warning("[recurring] recurring.yaml 파일을 찾지 못함")
        return []
    try:
        import yaml
        raw = yaml.safe_load(candidates[0].read_text(encoding="utf-8")) or {}
        patterns = []
        for item in raw.get("patterns", []):
            name    = item.get("name", "").strip()
            aliases = [a.strip() for a in item.get("aliases", []) if a.strip()]
            if name and aliases:
                patterns.append((name, aliases))
        log.debug("[recurring] %d개 패턴 로드 완료", len(patterns))
        return patterns
    except Exception as e:
        log.warning("[recurring] recurring.yaml 로드 실패: %s", e)
        return []


_PATTERNS: List[Tuple[str, List[str]]] = []

def _get_patterns() -> List[Tuple[str, List[str]]]:
    global _PATTERNS
    if not _PATTERNS:
        _PATTERNS = _load_patterns()
    return _PATTERNS


# ── 감지 함수 ─────────────────────────────────────────────────────────────────

def _match_recurring(title: str) -> Tuple[str, str]:
    """
    공고명에서 정기공고 패턴 매칭.
    Returns: (recurring_flag, recurring_group) — ("Y", "스마트공장구축") or ("N", "")
    """
    title_lower = title.lower()
    for name, aliases in _get_patterns():
        for alias in aliases:
            if alias.lower() in title_lower:
                return "Y", name
    return "N", ""


def detect_recurring(notices: List[Notice]) -> Tuple[List[Notice], int]:
    """
    공고 목록에서 정기공고 패턴을 감지하여 recurring_flag / recurring_group 설정.
    Returns: (updated_notices, recurring_count)
    """
    if not notices:
        return notices, 0

    patterns = _get_patterns()
    if not patterns:
        log.debug("[recurring] 패턴 없음 — 전체 non-recurring")
        return notices, 0

    count = 0
    for notice in notices:
        flag, group = _match_recurring(notice.title)
        notice.recurring_flag  = flag
        notice.recurring_group = group
        if flag == "Y":
            count += 1
            log.debug("[recurring] 정기공고 감지: %s → %s", notice.title[:40], group)

    log.info("[recurring] 정기공고 감지 완료: %d/%d건", count, len(notices))
    return notices, count
