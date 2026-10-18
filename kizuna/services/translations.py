"""Linked translations. A translation belongs to one exact source version, so
it can never silently drift from the approved original. Translations that
touch safety-critical content require review by a qualified second person."""
from __future__ import annotations

from .. import audit
from ..auth import can
from ..db import DB, dumps, loads, new_id, now_iso
from ..web import bad_request, conflict, forbidden, not_found
from . import common

LOCALES = ("ja", "en", "vi", "pt")


def _safety_relevant(content: dict) -> bool:
    return bool(content.get("safety")) or any(s.get("safety_critical") for s in content.get("steps", []))


def get(db: DB, org_id: str, user: dict, version_id: str, locale: str) -> dict:
    v = common.version(db, org_id, version_id)
    if v["status"] != "PUBLISHED" and not can(user, "procedure.read_unpublished"):
        raise not_found("Procedure version")
    t = db.one("SELECT t.*, c.name AS created_by_name, r.name AS reviewed_by_name FROM translations t "
               "LEFT JOIN users c ON c.id = t.created_by LEFT JOIN users r ON r.id = t.reviewed_by "
               "WHERE t.version_id = ? AND t.locale = ?", (version_id, locale))
    if t:
        t["content"] = loads(t.pop("content_json"), {})
    c = v["content"]
    return {"source": {"title": c.get("title"), "purpose": c.get("purpose"),
                       "steps": [{"step_id": s["step_id"], "title": s["title"], "instruction": s["instruction"],
                                  "safety_critical": s.get("safety_critical")} for s in c.get("steps", [])],
                       "safety": [{"id": s["id"], "text": s["text"]} for s in c.get("safety", [])]},
            "translation": t, "version": {"id": v["id"], "version_no": v["version_no"], "status": v["status"]},
            "safety_review_required": _safety_relevant(c)}


def save(db: DB, org_id: str, user: dict, version_id: str, locale: str, data: dict) -> dict:
    if locale not in LOCALES:
        raise bad_request(f"Unsupported locale. Supported: {', '.join(LOCALES)}")
    v = common.version(db, org_id, version_id)
    c = v["content"]
    payload = data.get("content") or {}
    steps_in = payload.get("steps") or {}
    if not isinstance(steps_in, dict):
        raise bad_request("content.steps must map step_id -> {title, instruction}")
    valid = {s["step_id"] for s in c.get("steps", [])}
    steps = {sid: {"title": str(t.get("title", ""))[:200], "instruction": str(t.get("instruction", ""))[:4000]}
             for sid, t in steps_in.items() if sid in valid and isinstance(t, dict)}
    safety = {k: str(x)[:1500] for k, x in (payload.get("safety") or {}).items()
              if any(s["id"] == k for s in c.get("safety", []))}
    content = {"title": str(payload.get("title", ""))[:200], "purpose": str(payload.get("purpose", ""))[:1500],
               "steps": steps, "safety": safety}
    status = "needs_safety_review" if _safety_relevant(c) else "draft"
    now = now_iso()
    existing = db.one("SELECT id FROM translations WHERE version_id = ? AND locale = ?", (version_id, locale))
    with db.tx():
        if existing:
            db.update("translations", existing["id"], {"content_json": dumps(content), "status": status, "created_by": user["id"],
                                                       "reviewed_by": None, "reviewed_at": None, "updated_at": now})
        else:
            db.insert("translations", {"id": new_id("trn"), "org_id": org_id, "version_id": version_id, "locale": locale,
                                       "content_json": dumps(content), "status": status, "translator_kind": "manual",
                                       "created_by": user["id"], "created_at": now, "updated_at": now})
        audit.record(db, org_id, user["id"], "translation.saved", "procedure", v["procedure_id"],
                     f"Saved {locale.upper()} translation of v{v['version_no']} ({status.replace('_', ' ')})")
    return get(db, org_id, user, version_id, locale)


def review(db: DB, org_id: str, user: dict, version_id: str, locale: str) -> dict:
    if not can(user, "translation.review"):
        raise forbidden("Only experts or administrators can approve translations")
    t = db.one("SELECT * FROM translations WHERE version_id = ? AND locale = ? AND org_id = ?", (version_id, locale, org_id))
    if not t:
        raise not_found("Translation")
    if t["status"] == "reviewed":
        raise conflict("Already reviewed")
    if t["created_by"] == user["id"] and t["status"] == "needs_safety_review":
        raise forbidden("Safety-relevant translations must be reviewed by someone other than the translator")
    db.update("translations", t["id"], {"status": "reviewed", "reviewed_by": user["id"], "reviewed_at": now_iso(), "updated_at": now_iso()})
    v = common.version(db, org_id, version_id)
    audit.record(db, org_id, user["id"], "translation.reviewed", "procedure", v["procedure_id"],
                 f"Approved {locale.upper()} translation of v{v['version_no']}")
    return get(db, org_id, user, version_id, locale)
