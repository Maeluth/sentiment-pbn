"""
SQLite: токен бота, главный админ, доп. админы, whitelist, журнал апдейтов.
Файл: data/settings.db (или устаревший pbn_settings.db в корне).
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

KEY_BOT_TOKEN = os.getenv("BOT_TOKEN")
KEY_CHIEF_ADMIN_ID = "2050868308"
KEY_ADMIN_IDS = "2050868308"


class RuntimeConfigStore:
    def __init__(self, db_path: Path | None = None) -> None:
        from pbn_app.paths import settings_db_path

        self.db_path = db_path or settings_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self) -> None:
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS whitelist (
                    tg_user_id INTEGER PRIMARY KEY,
                    added_by INTEGER,
                    added_at INTEGER NOT NULL,
                    note TEXT
                );
                CREATE TABLE IF NOT EXISTS interaction_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at INTEGER NOT NULL,
                    tg_user_id INTEGER,
                    username TEXT,
                    chat_id INTEGER,
                    event_type TEXT NOT NULL,
                    summary TEXT,
                    raw_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_log_time ON interaction_log(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_log_user ON interaction_log(tg_user_id);
                """
            )

    def get_kv(self, key: str, default: str | None = None) -> str | None:
        with self._conn() as c:
            row = c.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
            if not row:
                return default
            return row["value"]

    def set_kv(self, key: str, value: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO kv(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_bot_token(self) -> str | None:
        v = self.get_kv(KEY_BOT_TOKEN)
        return v.strip() if v else None

    def set_bot_token(self, token: str) -> None:
        self.set_kv(KEY_BOT_TOKEN, token.strip())

    def get_chief_admin_id(self) -> int | None:
        raw = self.get_kv(KEY_CHIEF_ADMIN_ID)
        if not raw:
            return None
        try:
            return int(raw.strip())
        except ValueError:
            return None

    def set_chief_admin_id(self, uid: int) -> None:
        self.set_kv(KEY_CHIEF_ADMIN_ID, str(int(uid)))

    def get_extra_admin_ids(self) -> set[int]:
        raw = self.get_kv(KEY_ADMIN_IDS, "[]")
        try:
            data = json.loads(raw or "[]")
            return {int(x) for x in data}
        except (json.JSONDecodeError, TypeError, ValueError):
            return set()

    def set_extra_admin_ids(self, ids: set[int]) -> None:
        self.set_kv(KEY_ADMIN_IDS, json.dumps(sorted(ids)))

    def is_privileged(self, tg_user_id: int) -> bool:
        if tg_user_id == self.get_chief_admin_id():
            return True
        return tg_user_id in self.get_extra_admin_ids()

    def is_whitelisted(self, tg_user_id: int) -> bool:
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM whitelist WHERE tg_user_id = ?", (tg_user_id,)
            ).fetchone()
            return row is not None

    def is_allowed(self, tg_user_id: int | None) -> bool:
        if tg_user_id is None:
            return False
        return self.is_privileged(tg_user_id) or self.is_whitelisted(tg_user_id)

    def whitelist_add(self, tg_user_id: int, added_by: int, note: str | None = None) -> None:
        now = int(time.time())
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO whitelist(tg_user_id, added_by, added_at, note)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(tg_user_id) DO UPDATE SET
                    added_by = excluded.added_by,
                    added_at = excluded.added_at,
                    note = excluded.note
                """,
                (tg_user_id, added_by, now, note),
            )

    def whitelist_remove(self, tg_user_id: int) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM whitelist WHERE tg_user_id = ?", (tg_user_id,))
            return cur.rowcount > 0

    def whitelist_list(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT tg_user_id, added_by, added_at, note FROM whitelist
                ORDER BY added_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def whitelist_count(self) -> int:
        with self._conn() as c:
            row = c.execute("SELECT COUNT(*) AS n FROM whitelist").fetchone()
            return int(row["n"]) if row else 0

    def log_interaction(
        self,
        *,
        tg_user_id: int | None,
        username: str | None,
        chat_id: int | None,
        event_type: str,
        summary: str,
        raw: dict[str, Any] | None = None,
    ) -> None:
        now = int(time.time())
        blob = json.dumps(raw, ensure_ascii=False) if raw else None
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO interaction_log(
                    created_at, tg_user_id, username, chat_id, event_type, summary, raw_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    tg_user_id,
                    username,
                    chat_id,
                    event_type,
                    summary[:2000] if summary else "",
                    blob,
                ),
            )

    def recent_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT * FROM interaction_log
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                if d.get("raw_json"):
                    try:
                        d["raw_json"] = json.loads(d["raw_json"])
                    except json.JSONDecodeError:
                        pass
                out.append(d)
            return out
