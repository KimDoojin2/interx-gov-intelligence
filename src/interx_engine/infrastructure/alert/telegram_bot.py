"""
Feature #7: Bidirectional Telegram Bot
Handles incoming commands from Telegram and sends responses.

Commands:
  /status  - Pipeline status & last run summary
  /top     - Top 5 A-grade notices
  /urgent  - D-3 urgent deadline notices
  /search <keyword> - Search notices by keyword
  /help    - Show available commands

Usage:
  # As a polling bot (standalone):
  python -m interx_engine.infrastructure.alert.telegram_bot

  # Or import and use:
  from interx_engine.infrastructure.alert.telegram_bot import TelegramBotHandler
  bot = TelegramBotHandler(token, chat_id)
  bot.start_polling()
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

log = logging.getLogger("interx.telegram_bot")

_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramBotHandler:
    """Bidirectional Telegram bot that responds to user commands."""

    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self._base = _API_BASE.format(token=self.token)
        self._offset = 0
        self._db_path = Path(__file__).resolve().parents[4] / "data" / "interx_engine.db"

    def _send(self, text: str, chat_id: str = "", parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram."""
        if not self.token:
            log.warning("[TelegramBot] No token configured")
            return False
        cid = chat_id or self.chat_id
        if not cid:
            return False
        try:
            r = requests.post(
                f"{self._base}/sendMessage",
                json={"chat_id": cid, "text": text, "parse_mode": parse_mode},
                timeout=10,
            )
            return r.status_code == 200
        except Exception as e:
            log.error("[TelegramBot] Send failed: %s", e)
            return False

    def _get_updates(self) -> List[Dict[str, Any]]:
        """Poll for new messages."""
        try:
            r = requests.get(
                f"{self._base}/getUpdates",
                params={"offset": self._offset, "timeout": 30},
                timeout=35,
            )
            if r.status_code != 200:
                return []
            data = r.json()
            results = data.get("result", [])
            if results:
                self._offset = results[-1]["update_id"] + 1
            return results
        except Exception as e:
            log.error("[TelegramBot] GetUpdates failed: %s", e)
            return []

    def _query_db(self, sql: str, params: tuple = ()) -> List[Dict]:
        """Query the SQLite database."""
        if not self._db_path.exists():
            return []
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            log.error("[TelegramBot] DB query failed: %s", e)
            return []

    def handle_status(self) -> str:
        """Return pipeline status summary."""
        rows = self._query_db(
            "SELECT COUNT(*) as cnt, MAX(collected_at) as last_run FROM notices"
        )
        if not rows or not rows[0].get("cnt"):
            return "📊 <b>파이프라인 상태</b>\n\n데이터 없음. 수집을 실행해주세요."

        total = rows[0]["cnt"]
        last = rows[0].get("last_run", "알 수 없음")

        grade_rows = self._query_db(
            "SELECT priority_grade, COUNT(*) as cnt FROM notices "
            "GROUP BY priority_grade ORDER BY priority_grade"
        )
        grade_str = " · ".join(f"{r['priority_grade']}={r['cnt']}" for r in grade_rows)

        return (
            f"📊 <b>파이프라인 상태</b>\n\n"
            f"전체 공고: <b>{total}</b>건\n"
            f"등급 분포: {grade_str}\n"
            f"마지막 수집: {last}"
        )

    def handle_top(self) -> str:
        """Return top 5 A-grade notices."""
        rows = self._query_db(
            "SELECT title, site, deadline_date, priority_score "
            "FROM notices WHERE priority_grade = 'A' "
            "ORDER BY priority_score DESC LIMIT 5"
        )
        if not rows:
            return "🏆 <b>A등급 TOP 5</b>\n\nA등급 공고가 없습니다."

        lines = []
        for i, r in enumerate(rows, 1):
            dd = ""
            try:
                dl = datetime.strptime(r["deadline_date"], "%Y-%m-%d").date()
                dd = f" (D-{(dl - date.today()).days})"
            except Exception:
                pass
            lines.append(f"{i}. <b>{r['title'][:50]}</b>\n   {r['site']} · {r['deadline_date'] or '-'}{dd} · {r.get('priority_score', 0):.0f}점")

        return f"🏆 <b>A등급 TOP 5</b>\n\n" + "\n\n".join(lines)

    def handle_urgent(self) -> str:
        """Return D-3 urgent notices."""
        today = date.today().strftime("%Y-%m-%d")
        rows = self._query_db(
            "SELECT title, site, deadline_date, priority_grade "
            "FROM notices WHERE deadline_date >= ? "
            "ORDER BY deadline_date ASC LIMIT 10",
            (today,),
        )
        urgent = []
        for r in rows:
            try:
                dl = datetime.strptime(r["deadline_date"], "%Y-%m-%d").date()
                dd = (dl - date.today()).days
                if 0 <= dd <= 3:
                    urgent.append((r, dd))
            except Exception:
                pass

        if not urgent:
            return "🚨 <b>긴급 마감 D-3</b>\n\n3일 이내 마감 공고가 없습니다."

        lines = []
        for r, dd in urgent:
            lines.append(f"🔴 D-{dd} [{r['priority_grade']}] <b>{r['title'][:45]}</b> ({r['site']})")

        return f"🚨 <b>긴급 마감 D-3 ({len(urgent)}건)</b>\n\n" + "\n".join(lines)

    def handle_search(self, keyword: str) -> str:
        """Search notices by keyword."""
        if not keyword or len(keyword) < 2:
            return "🔍 검색어를 2글자 이상 입력해주세요.\n예: /search 스마트공장"

        rows = self._query_db(
            "SELECT title, site, deadline_date, priority_grade, priority_score "
            "FROM notices WHERE title LIKE ? "
            "ORDER BY priority_score DESC LIMIT 8",
            (f"%{keyword}%",),
        )
        if not rows:
            return f"🔍 <b>'{keyword}' 검색 결과</b>\n\n일치하는 공고가 없습니다."

        lines = []
        for r in rows:
            lines.append(f"[{r['priority_grade']}] <b>{r['title'][:50]}</b>\n   {r['site']} · {r['deadline_date'] or '-'}")

        return f"🔍 <b>'{keyword}' 검색 ({len(rows)}건)</b>\n\n" + "\n\n".join(lines)

    def handle_help(self) -> str:
        """Return help message."""
        return (
            "🤖 <b>InterX Intelligence Bot</b>\n\n"
            "사용 가능한 명령어:\n"
            "/status — 파이프라인 상태 요약\n"
            "/top — A등급 TOP 5 공고\n"
            "/urgent — D-3 긴급 마감 공고\n"
            "/search &lt;키워드&gt; — 공고 검색\n"
            "/help — 도움말 표시"
        )

    def process_message(self, text: str, chat_id: str = "") -> str:
        """Process incoming message and return response."""
        text = (text or "").strip()
        if not text:
            return ""

        if text.startswith("/status"):
            return self.handle_status()
        elif text.startswith("/top"):
            return self.handle_top()
        elif text.startswith("/urgent"):
            return self.handle_urgent()
        elif text.startswith("/search"):
            keyword = text.replace("/search", "").strip()
            return self.handle_search(keyword)
        elif text.startswith("/help") or text.startswith("/start"):
            return self.handle_help()
        else:
            return self.handle_help()

    def start_polling(self, interval: float = 1.0):
        """Start polling for messages (blocking)."""
        log.info("[TelegramBot] Starting polling...")
        print("[TelegramBot] Polling started. Press Ctrl+C to stop.")
        while True:
            try:
                updates = self._get_updates()
                for update in updates:
                    msg = update.get("message", {})
                    text = msg.get("text", "")
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    if text and chat_id:
                        log.info("[TelegramBot] Received: %s from %s", text, chat_id)
                        response = self.process_message(text, chat_id)
                        if response:
                            self._send(response, chat_id)
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n[TelegramBot] Stopped.")
                break
            except Exception as e:
                log.error("[TelegramBot] Error: %s", e)
                time.sleep(5)


if __name__ == "__main__":
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token:
        print("[TelegramBot] TELEGRAM_BOT_TOKEN not set. Exiting.")
    else:
        bot = TelegramBotHandler(token, chat_id)
        bot.start_polling()
