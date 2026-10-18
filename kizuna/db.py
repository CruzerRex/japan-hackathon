"""SQLite persistence: connection wrapper and migration runner.

Each HTTP request opens its own connection (SQLite connections are not shared
across threads). WAL mode allows concurrent readers while one writer commits.
The SQL used by services is portable ANSI SQL apart from `INSERT OR IGNORE`,
so moving to PostgreSQL later is a mechanical change (see ARCHITECTURE.md).
"""
from __future__ import annotations

import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def loads(value: str | None, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class DB:
    """Thin wrapper over a sqlite3 connection returning dict rows."""

    def __init__(self, path: Path | str):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, timeout=15, isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 15000")
        self._depth = 0

    def close(self) -> None:
        self.conn.close()

    # -- queries -----------------------------------------------------------
    def all(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        return [dict(r) for r in self.conn.execute(sql, tuple(params)).fetchall()]

    def one(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        row = self.conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def scalar(self, sql: str, params: Iterable[Any] = ()) -> Any:
        row = self.conn.execute(sql, tuple(params)).fetchone()
        return row[0] if row else None

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, tuple(params))

    def insert(self, table: str, row: dict) -> dict:
        cols = ", ".join(row.keys())
        marks = ", ".join("?" for _ in row)
        self.conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(row.values()))
        return row

    def update(self, table: str, row_id: str, changes: dict, id_col: str = "id") -> None:
        if not changes:
            return
        sets = ", ".join(f"{k} = ?" for k in changes)
        self.conn.execute(f"UPDATE {table} SET {sets} WHERE {id_col} = ?", (*changes.values(), row_id))

    @contextmanager
    def tx(self):
        """Nested-safe transaction (outermost level commits/rolls back)."""
        if self._depth == 0:
            self.conn.execute("BEGIN IMMEDIATE")
        self._depth += 1
        try:
            yield self
        except Exception:
            self._depth -= 1
            if self._depth == 0:
                self.conn.execute("ROLLBACK")
            raise
        else:
            self._depth -= 1
            if self._depth == 0:
                self.conn.execute("COMMIT")


def migrate(path: Path | str) -> list[str]:
    """Apply pending SQL migrations in filename order. Returns applied names."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = DB(path)
    try:
        db.conn.execute("PRAGMA journal_mode = WAL")
        db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        done = {r["version"] for r in db.all("SELECT version FROM schema_migrations")}
        applied = []
        for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if f.name in done:
                continue
            db.conn.executescript("BEGIN;\n" + f.read_text(encoding="utf-8") + "\nCOMMIT;")
            db.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (f.name, now_iso()))
            applied.append(f.name)
        return applied
    finally:
        db.close()
