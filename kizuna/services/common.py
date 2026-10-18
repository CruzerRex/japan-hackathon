"""Shared helpers for the service layer. All lookups are tenant-scoped."""
from __future__ import annotations

from ..db import DB, loads
from ..web import not_found


def skills(db: DB, org_id: str) -> list[dict]:
    return db.all("SELECT * FROM skills WHERE org_id = ? ORDER BY criticality DESC, code", (org_id,))


def skills_by_code(db: DB, org_id: str) -> dict[str, dict]:
    return {s["code"]: s for s in skills(db, org_id)}


def user_in_org(db: DB, org_id: str, user_id: str) -> dict:
    u = db.one("SELECT id, org_id, name, name_ja, role, title, department, locale, languages, years_experience, "
               "bio, retirement_date, active, email FROM users WHERE id = ? AND org_id = ?", (user_id, org_id))
    if not u:
        raise not_found("User")
    return u


def names(db: DB, org_id: str) -> dict[str, str]:
    return {r["id"]: r["name"] for r in db.all("SELECT id, name FROM users WHERE org_id = ?", (org_id,))}


def procedure(db: DB, org_id: str, procedure_id: str) -> dict:
    p = db.one("SELECT * FROM procedures WHERE id = ? AND org_id = ?", (procedure_id, org_id))
    if not p:
        raise not_found("Procedure")
    return p


def version(db: DB, org_id: str, version_id: str) -> dict:
    v = db.one("SELECT * FROM procedure_versions WHERE id = ? AND org_id = ?", (version_id, org_id))
    if not v:
        raise not_found("Procedure version")
    v["content"] = loads(v.pop("content_json"), {})
    v["extraction_meta"] = loads(v.pop("extraction_meta_json"), {})
    return v


def published_version(db: DB, org_id: str, procedure_id: str) -> dict:
    p = procedure(db, org_id, procedure_id)
    if not p["published_version_id"]:
        raise not_found("Published training module")
    return version(db, org_id, p["published_version_id"])


def procedure_skill_codes(db: DB, org_id: str) -> dict[str, dict]:
    """procedure_id -> {"published": [codes], "latest": [codes], "latest_status": str}"""
    out = {}
    rows = db.all("""SELECT p.id, p.code, p.title, p.published_version_id, p.latest_version_id,
                            pv.content_json AS pub_content, lv.content_json AS latest_content, lv.status AS latest_status
                     FROM procedures p
                     LEFT JOIN procedure_versions pv ON pv.id = p.published_version_id
                     LEFT JOIN procedure_versions lv ON lv.id = p.latest_version_id
                     WHERE p.org_id = ?""", (org_id,))
    for r in rows:
        out[r["id"]] = {
            "id": r["id"], "code": r["code"], "title": r["title"],
            "published": loads(r["pub_content"], {}).get("skills", []) if r["pub_content"] else [],
            "latest": loads(r["latest_content"], {}).get("skills", []) if r["latest_content"] else [],
            "latest_status": r["latest_status"], "published_version_id": r["published_version_id"],
        }
    return out
