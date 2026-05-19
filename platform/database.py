"""
Platform Database — SQLite ORM for the BD web platform.
Reads from engine's existing DB + maintains platform-specific tables.
"""
import sqlite3
import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Optional

# Engine DB (populated by pipeline)
_ENGINE_DB = Path(__file__).resolve().parent.parent / "data" / "interx_engine.db"
# Platform DB (web-specific: status changes, user memos, etc.)
_PLATFORM_DB = Path(__file__).resolve().parent / "platform.db"


def _engine_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_ENGINE_DB))
    conn.row_factory = sqlite3.Row
    return conn


def _platform_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_PLATFORM_DB))
    conn.row_factory = sqlite3.Row
    return conn


def init_platform_db():
    """Create platform-specific tables if they don't exist."""
    conn = _platform_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS status_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notice_id TEXT NOT NULL,
            field TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            reason TEXT,
            changed_by TEXT DEFAULT '',
            changed_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS user_memos (
            notice_id TEXT PRIMARY KEY,
            memo TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS pipeline_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id TEXT NOT NULL UNIQUE,
            run_at TEXT DEFAULT (datetime('now', 'localtime')),
            notice_count INTEGER DEFAULT 0,
            l3_count INTEGER DEFAULT 0,
            a_count INTEGER DEFAULT 0,
            b_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            elapsed_sec REAL DEFAULT 0,
            payload TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS notices (
            notice_id TEXT PRIMARY KEY,
            execution_id TEXT,
            site TEXT,
            title TEXT,
            deadline TEXT,
            dday INTEGER,
            ministry TEXT,
            agency TEXT,
            budget TEXT,
            fitness_score REAL DEFAULT 0,
            priority_score REAL DEFAULT 0,
            grade TEXT DEFAULT 'D',
            win_probability REAL DEFAULT 0,
            win_grade TEXT DEFAULT 'D',
            l3_strong TEXT DEFAULT 'N',
            partner_candidate TEXT DEFAULT 'N',
            recurring_flag TEXT DEFAULT 'N',
            recurring_group TEXT DEFAULT '',
            manager TEXT DEFAULT '',
            status TEXT DEFAULT 'new',
            bd_milestone TEXT DEFAULT '',
            matched_keywords TEXT DEFAULT '',
            recommended_solutions TEXT DEFAULT '',
            recommended_action TEXT DEFAULT '',
            detail_url TEXT DEFAULT '',
            body_text TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            apply_status TEXT DEFAULT '',
            collected_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
    """)
    conn.commit()
    conn.close()


# ── Query Functions ──────────────────────────────────────────────────────────

def get_dashboard_stats() -> Dict[str, Any]:
    """Dashboard KPI cards data."""
    conn = _platform_conn()
    cur = conn.cursor()

    total = cur.execute("SELECT COUNT(*) FROM notices").fetchone()[0]
    a_count = cur.execute("SELECT COUNT(*) FROM notices WHERE grade='A'").fetchone()[0]
    b_count = cur.execute("SELECT COUNT(*) FROM notices WHERE grade='B'").fetchone()[0]
    l3_count = cur.execute("SELECT COUNT(*) FROM notices WHERE l3_strong='Y'").fetchone()[0]

    today = date.today().isoformat()
    urgent = cur.execute(
        "SELECT COUNT(*) FROM notices WHERE deadline >= ? AND dday BETWEEN 0 AND 7",
        (today,)
    ).fetchone()[0]

    recurring = cur.execute("SELECT COUNT(*) FROM notices WHERE recurring_flag='Y'").fetchone()[0]

    # Grade distribution
    grades = {}
    for row in cur.execute("SELECT grade, COUNT(*) as cnt FROM notices GROUP BY grade"):
        grades[row["grade"]] = row["cnt"]

    # Top sites
    sites = []
    for row in cur.execute(
        "SELECT site, COUNT(*) as cnt FROM notices GROUP BY site ORDER BY cnt DESC LIMIT 8"
    ):
        sites.append({"site": row["site"], "count": row["cnt"]})

    # Solution demand
    solutions = {}
    for row in cur.execute("SELECT recommended_solutions FROM notices WHERE recommended_solutions != ''"):
        for sol in row["recommended_solutions"].split(" / "):
            sol = sol.strip()
            if sol:
                solutions[sol] = solutions.get(sol, 0) + 1

    # Recent pipeline runs
    runs = []
    for row in cur.execute(
        "SELECT * FROM pipeline_results ORDER BY run_at DESC LIMIT 5"
    ):
        runs.append(dict(row))

    conn.close()
    return {
        "total": total,
        "a_count": a_count,
        "b_count": b_count,
        "l3_count": l3_count,
        "urgent": urgent,
        "recurring": recurring,
        "grades": grades,
        "sites": sites,
        "solutions": dict(sorted(solutions.items(), key=lambda x: -x[1])[:8]),
        "recent_runs": runs,
    }


def get_notices(
    grade: str = "",
    site: str = "",
    search: str = "",
    l3_only: bool = False,
    urgent_only: bool = False,
    status: str = "",
    sort_by: str = "priority_score",
    sort_dir: str = "DESC",
    page: int = 1,
    per_page: int = 30,
) -> Dict[str, Any]:
    """Paginated notice list with filters."""
    conn = _platform_conn()
    cur = conn.cursor()

    where = []
    params = []

    if grade:
        where.append("grade = ?")
        params.append(grade)
    if site:
        where.append("site = ?")
        params.append(site)
    if search:
        where.append("(title LIKE ? OR matched_keywords LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if l3_only:
        where.append("l3_strong = 'Y'")
    if urgent_only:
        today = date.today().isoformat()
        where.append(f"deadline >= '{today}' AND dday BETWEEN 0 AND 7")
    if status:
        where.append("status = ?")
        params.append(status)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    allowed_sorts = {"priority_score", "fitness_score", "win_probability", "deadline", "dday", "title", "collected_at"}
    if sort_by not in allowed_sorts:
        sort_by = "priority_score"
    if sort_dir not in ("ASC", "DESC"):
        sort_dir = "DESC"

    count = cur.execute(f"SELECT COUNT(*) FROM notices{where_sql}", params).fetchone()[0]

    offset = (page - 1) * per_page
    rows = cur.execute(
        f"SELECT * FROM notices{where_sql} ORDER BY {sort_by} {sort_dir} LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()

    conn.close()
    return {
        "notices": [dict(r) for r in rows],
        "total": count,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (count + per_page - 1) // per_page),
    }


def get_notice_detail(notice_id: str) -> Optional[Dict[str, Any]]:
    """Single notice full detail."""
    conn = _platform_conn()
    row = conn.execute("SELECT * FROM notices WHERE notice_id = ?", (notice_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_sites_list() -> List[str]:
    conn = _platform_conn()
    rows = conn.execute("SELECT DISTINCT site FROM notices ORDER BY site").fetchall()
    conn.close()
    return [r["site"] for r in rows]


def update_notice_status(notice_id: str, field: str, value: str, reason: str = "", changed_by: str = ""):
    """Update a notice field and log the change."""
    conn = _platform_conn()
    cur = conn.cursor()

    old = cur.execute(f"SELECT {field} FROM notices WHERE notice_id = ?", (notice_id,)).fetchone()
    old_val = old[0] if old else ""

    cur.execute(f"UPDATE notices SET {field} = ?, updated_at = datetime('now','localtime') WHERE notice_id = ?",
                (value, notice_id))

    cur.execute(
        "INSERT INTO status_changes (notice_id, field, old_value, new_value, reason, changed_by) VALUES (?,?,?,?,?,?)",
        (notice_id, field, old_val, value, reason, changed_by)
    )
    conn.commit()
    conn.close()


def ingest_pipeline_result(data: Dict[str, Any]) -> int:
    """Receive pipeline result from Colab and store notices."""
    conn = _platform_conn()
    cur = conn.cursor()

    exec_id = data.get("execution_id", "")
    notices = data.get("notices", [])

    # Save pipeline run metadata
    cur.execute("""
        INSERT OR REPLACE INTO pipeline_results
        (execution_id, notice_count, l3_count, a_count, b_count, error_count, elapsed_sec, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        exec_id,
        data.get("notice_count", len(notices)),
        data.get("l3_count", 0),
        data.get("a_count", 0),
        data.get("b_count", 0),
        data.get("error_count", 0),
        data.get("elapsed_sec", 0),
        json.dumps(data.get("summary", {}), ensure_ascii=False),
    ))

    # Upsert notices
    inserted = 0
    for n in notices:
        cur.execute("""
            INSERT OR REPLACE INTO notices
            (notice_id, execution_id, site, title, deadline, dday, ministry, agency,
             budget, fitness_score, priority_score, grade, win_probability, win_grade,
             l3_strong, partner_candidate, recurring_flag, recurring_group,
             manager, bd_milestone, matched_keywords, recommended_solutions,
             recommended_action, detail_url, body_text, summary, apply_status, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                    COALESCE((SELECT status FROM notices WHERE notice_id=?), 'new'))
        """, (
            n.get("notice_id", ""),
            exec_id,
            n.get("site", ""),
            n.get("title", ""),
            n.get("deadline", ""),
            n.get("dday", 0),
            n.get("ministry", ""),
            n.get("agency", ""),
            n.get("budget", ""),
            n.get("fitness_score", 0),
            n.get("priority_score", 0),
            n.get("grade", "D"),
            n.get("win_probability", 0),
            n.get("win_grade", "D"),
            n.get("l3_strong", "N"),
            n.get("partner_candidate", "N"),
            n.get("recurring_flag", "N"),
            n.get("recurring_group", ""),
            n.get("manager", ""),
            n.get("bd_milestone", ""),
            n.get("matched_keywords", ""),
            n.get("recommended_solutions", ""),
            n.get("recommended_action", ""),
            n.get("detail_url", ""),
            n.get("body_text", "")[:8000],
            n.get("summary", ""),
            n.get("apply_status", ""),
            n.get("notice_id", ""),
        ))
        inserted += 1

    conn.commit()
    conn.close()
    return inserted


# Auto-init on import
init_platform_db()
