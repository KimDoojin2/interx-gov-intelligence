"""
Colab → Platform Sync Module
Add to the end of your pipeline run on Colab to auto-sync results.

Usage in Colab:
    from platform.colab_sync import sync_pipeline_result
    sync_pipeline_result(result, scored_notices, score_cards, platform_url="http://YOUR_SERVER:8000")

Or standalone:
    python platform/colab_sync.py --url http://YOUR_SERVER:8000
    (reads from the latest SQLite data)
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("interx.platform_sync")


def _calc_dday(deadline: str) -> int:
    """Calculate D-day from deadline string."""
    try:
        dl = datetime.strptime(deadline, "%Y-%m-%d").date()
        return (dl - date.today()).days
    except (ValueError, TypeError):
        return -1


def build_notice_payload(notice, score_card=None) -> Dict[str, Any]:
    """Convert Notice + ScoreCard to JSON-serializable dict for platform API."""
    n = notice
    sc = score_card

    data = {
        "notice_id": getattr(n, "notice_id", ""),
        "site": getattr(n, "site", ""),
        "title": getattr(n, "title", ""),
        "deadline": getattr(n, "deadline_date", ""),
        "dday": _calc_dday(getattr(n, "deadline_date", "")),
        "ministry": getattr(n, "ministry", ""),
        "agency": getattr(n, "agency", ""),
        "budget": getattr(n, "budget", ""),
        "l3_strong": getattr(n, "l3_strong", "N"),
        "partner_candidate": getattr(n, "partner_candidate", "N"),
        "recurring_flag": getattr(n, "recurring_flag", "N"),
        "recurring_group": getattr(n, "recurring_group", ""),
        "manager": getattr(n, "manager", ""),
        "bd_milestone": getattr(n, "bd_milestone", ""),
        "detail_url": getattr(n, "detail_url", "") or getattr(n, "notice_link", ""),
        "body_text": (getattr(n, "body_text", "") or "")[:8000],
        "summary": getattr(n, "summary", ""),
        "apply_status": getattr(n, "__dict__", {}).get("apply_status", ""),
    }

    if sc:
        data.update({
            "fitness_score": getattr(sc, "fitness", 0),
            "priority_score": getattr(sc, "priority", 0),
            "grade": getattr(sc, "grade", "D"),
            "win_probability": getattr(sc, "win_probability", 0),
            "win_grade": getattr(sc, "win_grade", "D"),
            "matched_keywords": " | ".join(getattr(sc, "matched_keywords", [])),
            "recommended_solutions": " / ".join(
                s for s, v in getattr(sc, "solution_scores", {}).items() if v > 0
            ),
            "recommended_action": getattr(sc, "recommended_action", ""),
        })

    return data


def sync_pipeline_result(
    result: Dict[str, Any],
    notices: list,
    score_cards: Optional[dict] = None,
    platform_url: str = "http://localhost:8000",
) -> bool:
    """
    Send pipeline results to the BD Platform.

    Args:
        result: Pipeline final result dict
        notices: List of Notice objects
        score_cards: Dict of {notice_id: ScoreCard} (optional)
        platform_url: Platform API base URL

    Returns:
        True if sync succeeded
    """
    import requests

    score_cards = score_cards or {}

    notices_data = []
    for n in notices:
        sc = score_cards.get(getattr(n, "notice_id", ""))
        notices_data.append(build_notice_payload(n, sc))

    payload = {
        "execution_id": result.get("execution_id", ""),
        "notice_count": len(notices_data),
        "l3_count": sum(1 for d in notices_data if d.get("l3_strong") == "Y"),
        "a_count": sum(1 for d in notices_data if d.get("grade") == "A"),
        "b_count": sum(1 for d in notices_data if d.get("grade") == "B"),
        "error_count": result.get("error_count", 0),
        "elapsed_sec": result.get("elapsed_sec", 0),
        "notices": notices_data,
        "summary": {
            "total": len(notices_data),
            "sites": list(set(d["site"] for d in notices_data)),
        },
    }

    try:
        resp = requests.post(
            f"{platform_url}/api/pipeline/sync",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        log.info("[PlatformSync] OK: ingested %d notices (exec=%s)",
                 data.get("ingested", 0), payload["execution_id"])
        print(f"[Platform Sync] Success: {data.get('ingested', 0)} notices synced")
        return True
    except Exception as e:
        log.warning("[PlatformSync] Failed: %s", e)
        print(f"[Platform Sync] Failed: {e}")
        return False


def sync_from_sqlite(platform_url: str = "http://localhost:8000"):
    """
    Read latest data from engine's SQLite DB and sync to platform.
    Useful for initial data migration or manual sync.
    """
    import sqlite3
    db_path = Path(__file__).resolve().parent.parent / "data" / "interx_engine.db"
    if not db_path.exists():
        print(f"[Sync] DB not found: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Engine DB schema: notices table has flat columns (no separate score_cards table)
    rows = conn.execute("""
        SELECT * FROM notices ORDER BY priority_score DESC LIMIT 500
    """).fetchall()

    notices_data = []
    for r in rows:
        d = dict(r)
        notices_data.append({
            "notice_id": d.get("notice_id", ""),
            "site": d.get("site", ""),
            "title": d.get("title", ""),
            "deadline": d.get("deadline_date", ""),
            "dday": _calc_dday(d.get("deadline_date", "")),
            "ministry": d.get("ministry", ""),
            "agency": d.get("agency", ""),
            "budget": d.get("budget", ""),
            "fitness_score": d.get("fitness_score", 0) or 0,
            "priority_score": d.get("priority_score", 0) or 0,
            "grade": d.get("priority_grade", "D") or "D",
            "win_probability": d.get("win_probability", 0) or 0,
            "win_grade": d.get("win_grade", "D") or "D",
            "l3_strong": d.get("l3_strong", "N") or "N",
            "partner_candidate": d.get("partner_candidate", "N") or "N",
            "recurring_flag": d.get("recurring_flag", "N") or "N",
            "recurring_group": d.get("recurring_group", "") or "",
            "manager": d.get("manager", "") or "",
            "bd_milestone": d.get("bd_milestone", "") or "",
            "matched_keywords": d.get("matched_keywords", "") or "",
            "recommended_solutions": d.get("recommended_solutions", "") or "",
            "recommended_action": d.get("recommended_action", "") or "",
            "detail_url": d.get("detail_url", "") or "",
            "body_text": (d.get("body_text", "") or "")[:8000],
            "summary": d.get("summary", "") or "",
        })

    conn.close()

    if not notices_data:
        print("[Sync] No data in SQLite DB")
        return

    import requests
    payload = {
        "execution_id": f"SYNC-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "notice_count": len(notices_data),
        "l3_count": sum(1 for d in notices_data if d.get("l3_strong") == "Y"),
        "a_count": sum(1 for d in notices_data if d.get("grade") == "A"),
        "b_count": sum(1 for d in notices_data if d.get("grade") == "B"),
        "notices": notices_data,
    }

    try:
        resp = requests.post(f"{platform_url}/api/pipeline/sync", json=payload, timeout=30)
        print(f"[Sync] Result: {resp.json()}")
    except Exception as e:
        print(f"[Sync] Error: {e}")


if __name__ == "__main__":
    url = "http://localhost:8000"
    if len(sys.argv) > 2 and sys.argv[1] == "--url":
        url = sys.argv[2]
    sync_from_sqlite(url)
