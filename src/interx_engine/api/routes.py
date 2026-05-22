"""
InterX REST API Routes — 프론트엔드 연동 엔드포인트.

주요 엔드포인트:
    GET  /api/v1/notices          — 공고 목록 (필터·정렬·페이징)
    GET  /api/v1/notices/{id}     — 공고 상세
    GET  /api/v1/stats            — 통계 (등급별·사이트별)
    GET  /api/v1/pipeline/status  — 마지막 실행 상태
    POST /api/v1/pipeline/run     — 파이프라인 수동 실행 (비동기)
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

log = logging.getLogger("interx.api")

router = APIRouter(tags=["InterX Engine"])

# ── DB 경로 ──────────────────────────────────────────────────────────────────
def _db_path() -> Path:
    import os
    p = os.getenv("INTERX_DB_PATH", "")
    if p:
        return Path(p)
    # fallback: project root 추정
    root = Path(__file__).resolve().parents[3]
    return root / "data" / "interx_pipeline.db"


def _get_conn() -> sqlite3.Connection:
    db = _db_path()
    if not db.exists():
        raise HTTPException(status_code=503, detail=f"DB 파일 없음: {db}")
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


# ── 공고 목록 ────────────────────────────────────────────────────────────────
@router.get("/notices")
async def list_notices(
    grade: Optional[str] = Query(None, description="등급 필터 (A/B/C/D)"),
    site: Optional[str] = Query(None, description="사이트 필터"),
    l3_strong: Optional[bool] = Query(None, description="L3 강공고만"),
    keyword: Optional[str] = Query(None, description="키워드 검색"),
    sort_by: str = Query("collected_at", description="정렬 기준"),
    order: str = Query("desc", description="정렬 방향 (asc/desc)"),
    page: int = Query(1, ge=1, description="페이지"),
    size: int = Query(50, ge=1, le=200, description="페이지 크기"),
):
    """공고 목록 조회 (필터·정렬·페이징)."""
    conn = _get_conn()
    try:
        where_clauses = []
        params = []

        if grade:
            where_clauses.append("grade = ?")
            params.append(grade.upper())
        if site:
            where_clauses.append("site = ?")
            params.append(site)
        if l3_strong is True:
            where_clauses.append("l3_strong = 'Y'")
        if keyword:
            where_clauses.append("(notice_name LIKE ? OR body_text LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # 정렬 (SQL injection 방지: 허용된 컬럼만)
        allowed_sort = {"collected_at", "deadline", "score", "win_probability", "grade", "notice_name", "site"}
        if sort_by not in allowed_sort:
            sort_by = "collected_at"
        order_dir = "DESC" if order.lower() == "desc" else "ASC"

        offset = (page - 1) * size

        # 카운트
        count_sql = f"SELECT COUNT(*) FROM notices{where_sql}"
        total = conn.execute(count_sql, params).fetchone()[0]

        # 데이터
        data_sql = (
            f"SELECT notice_id, notice_name, org, department, deadline, budget, "
            f"grade, score, win_probability, l3_strong, site, link, collected_at, "
            f"recurring_flag, recurring_group, manager, bd_milestone, status "
            f"FROM notices{where_sql} "
            f"ORDER BY {sort_by} {order_dir} "
            f"LIMIT ? OFFSET ?"
        )
        rows = conn.execute(data_sql, params + [size, offset]).fetchall()
        items = [dict(r) for r in rows]

        return {
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size,
            "items": items,
        }
    finally:
        conn.close()


# ── 공고 상세 ────────────────────────────────────────────────────────────────
@router.get("/notices/{notice_id}")
async def get_notice(notice_id: str):
    """공고 상세 정보 (본문·키워드·스코어 포함)."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM notices WHERE notice_id = ?", (notice_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다")
        return dict(row)
    finally:
        conn.close()


# ── 통계 ─────────────────────────────────────────────────────────────────────
@router.get("/stats")
async def get_stats():
    """대시보드용 통계 (등급별·사이트별)."""
    conn = _get_conn()
    try:
        result = {}

        # 등급별 수
        rows = conn.execute(
            "SELECT grade, COUNT(*) as cnt FROM notices GROUP BY grade ORDER BY grade"
        ).fetchall()
        result["by_grade"] = {r["grade"]: r["cnt"] for r in rows}

        # 사이트별 수
        rows = conn.execute(
            "SELECT site, COUNT(*) as cnt FROM notices GROUP BY site ORDER BY cnt DESC"
        ).fetchall()
        result["by_site"] = {r["site"]: r["cnt"] for r in rows}

        # L3 강공고 수
        l3 = conn.execute(
            "SELECT COUNT(*) FROM notices WHERE l3_strong = 'Y'"
        ).fetchone()[0]
        result["l3_strong_count"] = l3

        # 전체 수
        total = conn.execute("SELECT COUNT(*) FROM notices").fetchone()[0]
        result["total"] = total

        # 평균 점수
        avg = conn.execute("SELECT AVG(score) FROM notices WHERE score > 0").fetchone()[0]
        result["avg_score"] = round(avg, 1) if avg else 0

        return result
    finally:
        conn.close()


# ── 긴급 마감 공고 ──────────────────────────────────────────────────────────
@router.get("/notices/urgent")
async def urgent_notices(days: int = Query(7, ge=1, le=30)):
    """마감 D-day 이내 공고 목록."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT notice_id, notice_name, deadline, grade, score, win_probability, site "
            "FROM notices "
            "WHERE deadline IS NOT NULL AND deadline != '' "
            "AND date(deadline) BETWEEN date('now') AND date('now', ? || ' days') "
            "ORDER BY deadline ASC",
            (str(days),),
        ).fetchall()
        return {"count": len(rows), "items": [dict(r) for r in rows]}
    finally:
        conn.close()


# ── 파이프라인 상태 ──────────────────────────────────────────────────────────
@router.get("/pipeline/status")
async def pipeline_status():
    """최근 파이프라인 실행 상태."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return {"status": "never_run"}
        return dict(row)
    except sqlite3.OperationalError:
        return {"status": "no_pipeline_table"}
    finally:
        conn.close()


# ── 파이프라인 수동 실행 ────────────────────────────────────────────────────
_pipeline_lock = threading.Lock()
_pipeline_running = False


@router.post("/pipeline/run")
async def trigger_pipeline(
    sites: Optional[str] = Query(None, description="사이트 (쉼표 구분)"),
    dry_run: bool = Query(False, description="Mock 데이터 테스트"),
):
    """파이프라인 수동 실행 (백그라운드 스레드)."""
    global _pipeline_running

    if _pipeline_running:
        raise HTTPException(status_code=409, detail="파이프라인 이미 실행 중")

    def _run():
        global _pipeline_running
        with _pipeline_lock:
            _pipeline_running = True
            try:
                import sys
                from pathlib import Path as _P
                root = _P(__file__).resolve().parents[3]
                if str(root) not in sys.path:
                    sys.path.insert(0, str(root))
                # run_engine import
                sys.path.insert(0, str(root.parent))
                from run_engine import main as engine_main
                site_list = [s.strip() for s in sites.split(",")] if sites else None
                engine_main(
                    site_keys=site_list,
                    enable_sheets=True,
                    dry_run=dry_run,
                )
            except Exception as e:
                log.error("[API] 파이프라인 실행 실패: %s", e)
            finally:
                _pipeline_running = False

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return {
        "status": "started",
        "dry_run": dry_run,
        "sites": sites,
        "started_at": datetime.now().isoformat(),
    }
