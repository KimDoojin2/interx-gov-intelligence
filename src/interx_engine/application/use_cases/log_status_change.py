"""
상태변경 로그 — 공고의 검토상태/BD마일스톤 변경 이력 기록.
sheets.yaml의 97_상태변경로그 시트에 기록.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.status_change")


def detect_status_changes(
    current_notices: List[Notice],
    previous_snapshot: Dict[str, Dict[str, str]],
    execution_id: str = "",
) -> tuple[List[List[str]], Dict[str, Dict[str, str]]]:
    """
    현재 공고 목록과 이전 스냅샷을 비교하여 상태 변경을 감지한다.

    Args:
        current_notices: 현재 실행의 공고 목록
        previous_snapshot: {notice_id: {"status": ..., "bd_milestone": ..., "grade": ...}}
        execution_id: 실행 ID

    Returns:
        (change_rows, new_snapshot)
        change_rows: [[변경일시, 실행ID, 공고ID, 공고명, 변경필드, 이전값, 변경값, 변경사유, 처리자], ...]
        new_snapshot: 다음 비교를 위한 현재 스냅샷
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    change_rows: List[List[str]] = []
    new_snapshot: Dict[str, Dict[str, str]] = {}

    # 추적 대상 필드
    TRACKED_FIELDS = [
        ("status", "검토상태"),
        ("bd_milestone", "BD마일스톤"),
    ]

    for notice in current_notices:
        nid = notice.notice_id
        title = (notice.title or "")[:50]

        # 현재 상태
        cur_state = {
            "status": getattr(notice, "status", "") or "",
            "bd_milestone": getattr(notice, "bd_milestone", "") or "",
        }
        new_snapshot[nid] = cur_state

        # 이전 상태와 비교
        prev_state = previous_snapshot.get(nid, {})
        if not prev_state:
            # 신규 공고 → 변경 로그 불필요
            continue

        for field_key, field_label in TRACKED_FIELDS:
            old_val = prev_state.get(field_key, "")
            new_val = cur_state.get(field_key, "")
            if old_val != new_val and (old_val or new_val):
                reason = _infer_reason(field_key, old_val, new_val)
                change_rows.append([
                    now,
                    execution_id,
                    nid,
                    title,
                    field_label,
                    old_val or "(없음)",
                    new_val or "(없음)",
                    reason,
                    "시스템",  # 자동 파이프라인
                ])

    if change_rows:
        log.info("[StatusChange] %d건 상태 변경 감지", len(change_rows))

    return change_rows, new_snapshot


def _infer_reason(field: str, old: str, new: str) -> str:
    """변경 사유 자동 추론."""
    if field == "bd_milestone":
        if not old and new:
            return f"마일스톤 배정: {new}"
        if old and new:
            return f"마일스톤 변경: {old} → {new}"
    if field == "status":
        if not old and new:
            return f"상태 설정: {new}"
        return f"상태 변경"
    return "자동 감지"


# ── 스냅샷 파일 관리 ──────────────────────────────────────────────────────────
import json
import os
import tempfile
from pathlib import Path

_PROJ_ROOT = Path(__file__).resolve().parents[4]


def _snapshot_path() -> Path:
    env = os.getenv("INTERX_STATUS_SNAPSHOT")
    if env:
        return Path(env)
    primary = _PROJ_ROOT / "data" / "status_snapshot.json"
    try:
        primary.parent.mkdir(parents=True, exist_ok=True)
        return primary
    except OSError:
        return Path(tempfile.gettempdir()) / "interx_status_snapshot.json"


def load_snapshot() -> Dict[str, Dict[str, str]]:
    """이전 상태 스냅샷 로드."""
    p = _snapshot_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("[StatusChange] 스냅샷 로드 실패: %s", e)
    return {}


def save_snapshot(snapshot: Dict[str, Dict[str, str]]) -> None:
    """현재 상태 스냅샷 저장."""
    p = _snapshot_path()
    try:
        p.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("[StatusChange] 스냅샷 저장 실패: %s", e)
