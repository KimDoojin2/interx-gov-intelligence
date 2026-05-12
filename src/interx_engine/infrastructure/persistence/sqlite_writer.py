from __future__ import annotations
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Set


class SQLitePipelineWriter:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")  # 동시 읽기·쓰기 허용
        return conn

    def _init_schema(self):
        with self._conn() as c:
            # ── pipeline_runs 테이블 ─────────────────────────────────────────
            c.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
              execution_id  TEXT PRIMARY KEY,
              created_at    TEXT,
              source_site   TEXT,
              notice_count  INTEGER,
              score_count   INTEGER,
              payload_json  TEXT
            )""")
            # 기존 DB와 스키마가 다르면 필요한 컬럼만 추가 (DROP 없이 안전 마이그레이션)
            _pr_cols = {
                row[1]
                for row in c.execute("PRAGMA table_info(pipeline_runs)").fetchall()
            }
            for col, typedef in [
                ("created_at",    "TEXT"),
                ("source_site",   "TEXT"),
                ("notice_count",  "INTEGER"),
                ("score_count",   "INTEGER"),
                ("payload_json",  "TEXT"),
            ]:
                if col not in _pr_cols:
                    try:
                        c.execute(f"ALTER TABLE pipeline_runs ADD COLUMN {col} {typedef}")
                    except Exception:
                        pass

            # ── notices 테이블 ───────────────────────────────────────────────
            # 기존 notices가 notice_key PK 방식이면 호환 불가 → 새 테이블 생성
            _notice_pk_old = any(
                row[5] == 1 and row[1] == "notice_key"
                for row in c.execute("PRAGMA table_info(notices)").fetchall()
            )
            if _notice_pk_old:
                # 기존 테이블을 백업 후 새 스키마로 교체
                try:
                    c.execute("ALTER TABLE notices RENAME TO notices_v1_bak")
                except Exception:
                    pass

            c.execute("""
            CREATE TABLE IF NOT EXISTS notices (
              execution_id      TEXT,
              notice_id         TEXT,
              site              TEXT,
              title             TEXT,
              detail_url        TEXT,
              posted_date       TEXT,
              deadline_date     TEXT,
              budget            TEXT,
              l3_strong         TEXT,
              partner_candidate TEXT,
              fitness_score     REAL,
              priority_score    REAL,
              priority_grade    TEXT,
              PRIMARY KEY (execution_id, notice_id)
            )""")
            # 새 컬럼 마이그레이션
            _nex = {
                row[1]
                for row in c.execute("PRAGMA table_info(notices)").fetchall()
            }
            for col, typedef in [
                ("budget",          "TEXT"),
                ("fitness_score",   "REAL"),
                ("priority_score",  "REAL"),
                ("priority_grade",  "TEXT"),
            ]:
                if col not in _nex:
                    try:
                        c.execute(f"ALTER TABLE notices ADD COLUMN {col} {typedef}")
                    except Exception:
                        pass
            # 빠른 단일 notice_id 조회를 위한 인덱스
            c.execute("""
            CREATE INDEX IF NOT EXISTS idx_notices_notice_id
              ON notices(notice_id)
            """)
            # attachments: seq 컬럼이 없는 구버전 테이블이면 재생성
            _att_cols = {
                row[1]
                for row in c.execute("PRAGMA table_info(attachments)").fetchall()
            }
            if _att_cols and "seq" not in _att_cols:
                try:
                    c.execute("ALTER TABLE attachments RENAME TO attachments_v1_bak")
                except Exception:
                    pass
            c.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
              execution_id    TEXT,
              notice_id       TEXT,
              seq             INTEGER,
              name            TEXT,
              url             TEXT,
              local_path      TEXT,
              download_status TEXT,
              parse_status    TEXT,
              PRIMARY KEY (execution_id, notice_id, seq)
            )""")
            # 수집 통계 테이블
            c.execute("""
            CREATE TABLE IF NOT EXISTS site_stats (
              execution_id TEXT,
              site         TEXT,
              collected    INTEGER,
              l3_count     INTEGER,
              error_count  INTEGER,
              created_at   TEXT,
              PRIMARY KEY (execution_id, site)
            )""")

    # ── 기존 notice_id 조회 (cross-run 중복 방지용) ───────────────────────────

    def existing_notice_ids(self, days: int = 30) -> Set[str]:
        """최근 N일간 수집된 notice_id 집합 반환. DB 없으면 빈 집합."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        try:
            with self._conn() as c:
                rows = c.execute(
                    """
                    SELECT DISTINCT n.notice_id
                    FROM notices n
                    JOIN pipeline_runs p USING (execution_id)
                    WHERE p.created_at >= ?
                    """,
                    (cutoff,),
                ).fetchall()
            return {r[0] for r in rows}
        except Exception:
            return set()

    # ── 저장 ─────────────────────────────────────────────────────────────────

    def save(self, execution_id: str, source_site: str, result: dict):
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notices     = result.get("notices", [])
        score_cards = {s.notice_id: s for s in result.get("score_cards", [])}

        with self._conn() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO pipeline_runs
                  (execution_id, created_at, source_site, notice_count, score_count, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    execution_id,
                    created_at,
                    source_site,
                    len(notices),
                    len(score_cards),
                    json.dumps(
                        {
                            "new_count":     result.get("new_count", 0),
                            "changed_count": result.get("changed_count", 0),
                            "dup_count":     result.get("dup_count", 0),
                            "error_count":   result.get("error_count", 0),
                            "l3_count":      len(result.get("l3_rows", [])),
                            "urgent_count":  len(result.get("urgent_rows", [])),
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

            for n in notices:
                sc = score_cards.get(n.notice_id)
                c.execute(
                    """
                    INSERT OR REPLACE INTO notices
                      (execution_id, notice_id, site, title, detail_url,
                       posted_date, deadline_date, budget,
                       l3_strong, partner_candidate,
                       fitness_score, priority_score, priority_grade)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        execution_id,
                        n.notice_id,
                        n.site,
                        n.title,
                        n.detail_url,
                        getattr(n, "posted_date",    ""),
                        getattr(n, "deadline_date",  ""),
                        getattr(n, "budget",         ""),
                        getattr(n, "l3_strong",      "N"),
                        getattr(n, "partner_candidate", "N"),
                        getattr(sc, "fitness_score",  0.0) if sc else 0.0,
                        getattr(sc, "priority_score", 0.0) if sc else 0.0,
                        getattr(sc, "priority_grade", "D") if sc else "D",
                    ),
                )

            # 첨부파일
            for n in notices:
                for i, att in enumerate(getattr(n, "attachment_items", []), start=1):
                    c.execute(
                        """
                        INSERT OR REPLACE INTO attachments
                          (execution_id, notice_id, seq, name, url,
                           local_path, download_status, parse_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            execution_id,
                            n.notice_id,
                            i,
                            att.get("name", ""),
                            att.get("url", ""),
                            att.get("local_path", ""),
                            att.get("download_status", ""),
                            att.get("parse_status", ""),
                        ),
                    )

    def save_site_stats(
        self,
        execution_id: str,
        site: str,
        collected: int,
        l3_count: int = 0,
        error_count: int = 0,
    ):
        with self._conn() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO site_stats
                  (execution_id, site, collected, l3_count, error_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    execution_id,
                    site,
                    collected,
                    l3_count,
                    error_count,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )

    # ── 조회 유틸 ─────────────────────────────────────────────────────────────

    def recent_l3_notices(self, days: int = 7) -> List[dict]:
        """최근 N일간 L3 강공고 목록 반환."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        try:
            with self._conn() as c:
                rows = c.execute(
                    """
                    SELECT n.notice_id, n.site, n.title, n.deadline_date,
                           n.fitness_score, n.detail_url
                    FROM notices n
                    JOIN pipeline_runs p USING (execution_id)
                    WHERE n.l3_strong = 'Y'
                      AND p.created_at >= ?
                    ORDER BY n.fitness_score DESC
                    LIMIT 20
                    """,
                    (cutoff,),
                ).fetchall()
            return [
                {
                    "notice_id":    r[0],
                    "site":         r[1],
                    "title":        r[2],
                    "deadline":     r[3],
                    "fitness":      r[4],
                    "url":          r[5],
                }
                for r in rows
            ]
        except Exception:
            return []
