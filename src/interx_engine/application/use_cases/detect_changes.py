"""
공고 변경 감지 v2 — 이전 실행과 비교해 신규/변경 공고 플래그
변경 감지 항목: 공고명, 마감일, 예산, 접수상태, 첨부파일 수
변경 사유를 change_reasons 리스트로 기록.
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


def _detail_snapshot(notice: Notice) -> dict:
    """변경 감지용 상세 스냅샷. 필드별로 저장해 변경 사유를 특정할 수 있게."""
    return {
        "hash": _hash(notice),
        "deadline": notice.deadline_date or "",
        "budget": notice.budget or "",
        "apply_status": getattr(notice, "apply_status", "") or "",
        "att_count": len(getattr(notice, "attachment_items", []) or []),
    }


def _diff_reasons(prev_snap: dict, curr_snap: dict) -> List[str]:
    """이전/현재 스냅샷 비교 → 변경 사유 리스트."""
    reasons = []
    if prev_snap.get("deadline") != curr_snap.get("deadline"):
        reasons.append(f"마감일({prev_snap.get('deadline', '?')}→{curr_snap.get('deadline', '?')})")
    if prev_snap.get("budget") != curr_snap.get("budget"):
        reasons.append(f"예산({prev_snap.get('budget', '?')}→{curr_snap.get('budget', '?')})")
    if prev_snap.get("apply_status") != curr_snap.get("apply_status"):
        old_s = prev_snap.get("apply_status") or "미확인"
        new_s = curr_snap.get("apply_status") or "미확인"
        reasons.append(f"접수상태({old_s}→{new_s})")
    p_att = prev_snap.get("att_count", 0)
    c_att = curr_snap.get("att_count", 0)
    if p_att != c_att:
        reasons.append(f"첨부파일({p_att}→{c_att}건)")
    if not reasons and prev_snap.get("hash") != curr_snap.get("hash"):
        reasons.append("제목/기타 변경")
    return reasons


def detect_changes(
    notices: List[Notice],
) -> Tuple[List[Notice], int, int]:
    """
    이전 실행 캐시와 비교.
    - 신규 공고: notice.is_new = True
    - 변경 공고: notice.is_changed = True, 메모에 변경 사유 추가

    Returns: (notices, new_count, changed_count)
    """
    cache_file = _cache_path()

    # 이전 캐시 로드 (v2: dict of snapshots, v1 호환: string hash)
    prev_raw: Dict = {}
    if cache_file.exists():
        try:
            prev_raw = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("[Changes] 캐시 파일 손상, 신규 시작: %s", e)
            prev_raw = {}

    new_count     = 0
    changed_count = 0
    current: Dict[str, dict] = {}

    for notice in notices:
        snap = _detail_snapshot(notice)
        current[notice.notice_id] = snap

        prev_entry = prev_raw.get(notice.notice_id)
        if prev_entry is None:
            notice.is_new = True
            new_count += 1
            continue

        # v1 호환: 이전 캐시가 문자열(hash)이면 hash 비교만
        if isinstance(prev_entry, str):
            if prev_entry != snap["hash"]:
                notice.is_changed = True
                changed_count += 1
                notice.memo = ((notice.memo or "") + " 🔄변경감지").strip()
            continue

        # v2: 상세 비교
        reasons = _diff_reasons(prev_entry, snap)
        if reasons:
            notice.is_changed = True
            changed_count += 1
            reason_str = ", ".join(reasons)
            notice.memo = ((notice.memo or "") + f" 🔄변경({reason_str})").strip()
            if hasattr(notice, '__dict__'):
                notice.__dict__['change_reasons'] = reasons
            log.debug("[Changes] 변경 감지: %s → %s", notice.title[:30], reason_str)

    # 캐시 저장 (v2 포맷)
    try:
        cache_file.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("[Changes] 캐시 저장 실패: %s", e)

    if new_count or changed_count:
        log.info("[Changes] 신규: %d건 | 변경: %d건", new_count, changed_count)

    return notices, new_count, changed_count
