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

def _load_patterns() -> List[Tuple[str, List[str], int]]:
    """
    recurring.yaml 을 로드해 (name, [aliases], priority) 리스트 반환.
    priority: 1=최우선(핵심공고), 2=중간, 3=참고. 미지정 시 2.
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
            name     = item.get("name", "").strip()
            aliases  = [a.strip() for a in item.get("aliases", []) if a.strip()]
            priority = item.get("priority", 2)
            if name and aliases:
                patterns.append((name, aliases, priority))
        # priority 낮을수록 우선 매칭 (1=최우선)
        patterns.sort(key=lambda x: x[2])
        log.debug("[recurring] %d개 패턴 로드 완료 (priority 순 정렬)", len(patterns))
        return patterns
    except Exception as e:
        log.warning("[recurring] recurring.yaml 로드 실패: %s", e)
        return []


_PATTERNS: List[Tuple[str, List[str], int]] = []

def _get_patterns() -> List[Tuple[str, List[str], int]]:
    global _PATTERNS
    if not _PATTERNS:
        _PATTERNS = _load_patterns()
    return _PATTERNS


# ── 감지 함수 ─────────────────────────────────────────────────────────────────

def _match_recurring(title: str) -> Tuple[str, str, int]:
    """
    공고명에서 정기공고 패턴 매칭.
    Returns: (recurring_flag, recurring_group, priority)
             — ("Y", "스마트공장구축", 1) or ("N", "", 0)
    """
    title_lower = title.lower()
    for name, aliases, priority in _get_patterns():
        for alias in aliases:
            if alias.lower() in title_lower:
                return "Y", name, priority
    return "N", "", 0


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
        flag, group, priority = _match_recurring(notice.title)
        notice.recurring_flag  = flag
        notice.recurring_group = group
        # recurring_priority: 1=핵심, 2=중간, 3=참고 (향후 시트/플랫폼에서 활용)
        if hasattr(notice, '__dict__'):
            notice.__dict__['recurring_priority'] = priority
        if flag == "Y":
            count += 1
            log.debug("[recurring] 정기공고 감지: %s → %s (P%d)", notice.title[:40], group, priority)

    log.info("[recurring] 정기공고 감지 완료: %d/%d건", count, len(notices))
    return notices, count
