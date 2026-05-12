"""
공고 변경 감지 — 이전 실행과 비교해 신규/변경 공고 플래그
변경 감지 항목: 공고명, 마감일, 예산
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.changes")

_PROJ_ROOT = Path(__file__).resolve().parents[4]  # src/interx_engine/application/use_cases/


def _cache_path() -> Path:
    env = os.getenv("INTERX_CACHE_PATH")
    if env:
        p = Path(env)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    primary = _PROJ_ROOT / "data" / "notice_cache.json"
    try:
        primary.parent.mkdir(parents=True, exist_ok=True)
        return primary
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "interx_notice_cache.json"
        log.warning("[Changes] data/ 디렉토리 생성 불가 → %s 사용", fallback)
        return fallback


def _hash(notice: Notice) -> str:
    key = f"{notice.title}|{notice.deadline_date}|{notice.budget}"
    return hashlib.md5(key.encode()).hexdigest()


def detect_changes(
    notices: List[Notice],
) -> Tuple[List[Notice], int, int]:
    """
    이전 실행 캐시와 비교.
    - 신규 공고: notice.is_new = True
    - 변경 공고: notice.is_changed = True, 메모에 🔄변경감지 추가

    Returns: (notices, new_count, changed_count)
    """
    cache_file = _cache_path()

    # 이전 캐시 로드
    prev: Dict[str, str] = {}
    if cache_file.exists():
        try:
            prev = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("[Changes] 캐시 파일 손상, 신규 시작: %s", e)
            prev = {}

    new_count     = 0
    changed_count = 0
    current: Dict[str, str] = {}

    for notice in notices:
        h = _hash(notice)
        current[notice.notice_id] = h

        if notice.notice_id not in prev:
            notice.is_new = True
            new_count += 1
        elif prev[notice.notice_id] != h:
            notice.is_changed = True
            changed_count += 1
            notice.memo = ((notice.memo or "") + " 🔄변경감지").strip()

    # 캐시 저장
    try:
        cache_file.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("[Changes] 캐시 저장 실패: %s", e)

    if new_count or changed_count:
        log.info("[Changes] 신규: %d건 | 변경: %d건", new_count, changed_count)

    return notices, new_count, changed_count
