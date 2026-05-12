import sqlite3
import os
from pathlib import Path
from typing import List, Set

from core.models import Notice
from config.settings import DB_PATH

class DBClient:
    def __init__(self):
        self.db_path = Path(DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL") 
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS notices (
                    notice_key TEXT PRIMARY KEY,
                    site TEXT, notice_id TEXT, title TEXT,
                    detail_url TEXT, posted_date TEXT, deadline_date TEXT,
                    agency TEXT, status TEXT
                )
            ''')

    def get_existing_keys(self) -> Set[str]:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT notice_key FROM notices")
            return {row[0] for row in cursor.fetchall()}

    def save_notices(self, notices: List[Notice]):
        if not notices: 
            return
        
        rows = [(
            n.notice_key, n.site, n.notice_id, n.title,
            n.detail_url, n.posted_date, n.deadline_date, n.agency, "NEW"
        ) for n in notices]

        with self._get_conn() as conn:
            conn.executemany('''
                INSERT OR REPLACE INTO notices 
                (notice_key, site, notice_id, title, detail_url, posted_date, deadline_date, agency, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', rows)
        print(f"✅ [DB] {len(rows)}건 저장 완료!")
