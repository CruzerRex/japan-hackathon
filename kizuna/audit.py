"""Append-only audit trail for important changes."""
from __future__ import annotations

from .db import DB, dumps, now_iso


def record(db: DB, org_id: str, actor_id: str | None, action: str, entity_type: str,
           entity_id: str | None, summary: str, detail: dict | None = None) -> None:
    db.execute(
        """INSERT INTO audit_events (org_id, actor_id, action, entity_type, entity_id, summary, detail_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (org_id, actor_id, action, entity_type, entity_id, summary, dumps(detail or {}), now_iso()),
    )


def recent(db: DB, org_id: str, limit: int = 50, entity_type: str | None = None) -> list[dict]:
    sql = """SELECT a.*, u.name AS actor_name, u.role AS actor_role FROM audit_events a
             LEFT JOIN users u ON u.id = a.actor_id WHERE a.org_id = ?"""
    params: list = [org_id]
    if entity_type:
        sql += " AND a.entity_type = ?"
        params.append(entity_type)
    sql += " ORDER BY a.id DESC LIMIT ?"
    params.append(limit)
    return db.all(sql, params)
