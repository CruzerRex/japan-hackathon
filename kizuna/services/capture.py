"""Knowledge Capture Studio: drafts, consent, source material, markers and extraction."""
from __future__ import annotations

from .. import audit
from ..ai.base import CaptureInput, ExtractionError
from ..db import DB, dumps, loads, new_id, now_iso
from ..domain import workflow
from ..domain.procedure_schema import parse_timestamp
from ..web import ApiError, bad_request, conflict, not_found
from . import common

TEXT_FIELDS = ("title", "task_category", "machine", "experience_level", "transcript", "expert_notes", "tips",
               "mistakes", "troubleshooting", "safety_notes", "transcript_source")
LIST_FIELDS = ("tools", "materials")
MARKER_KINDS = ("step", "tip", "mistake", "checkpoint", "safety")
LIMITS = {"title": 200, "transcript": 200_000, "expert_notes": 20_000, "tips": 20_000, "mistakes": 20_000,
          "troubleshooting": 20_000, "safety_notes": 20_000}


def _row(db: DB, org_id: str, capture_id: str) -> dict:
    c = db.one("SELECT * FROM capture_sessions WHERE id = ? AND org_id = ?", (capture_id, org_id))
    if not c:
        raise not_found("Capture session")
    return c


def _shape(db: DB, c: dict, full: bool = True) -> dict:
    out = dict(c)
    out["tools"] = loads(out.pop("tools_json"), [])
    out["materials"] = loads(out.pop("materials_json"), [])
    out["skill_ids"] = loads(out.pop("skill_ids_json"), [])
    expert = db.one("SELECT id, name, name_ja, title FROM users WHERE id = ?", (c["expert_id"],))
    out["expert"] = expert
    if full:
        out["markers"] = db.all("SELECT * FROM capture_markers WHERE capture_id = ? ORDER BY t_seconds", (c["id"],))
        out["files"] = db.all("SELECT id, kind, original_name, mime, size_bytes, sha256, created_at FROM files "
                              "WHERE capture_id = ? ORDER BY created_at", (c["id"],))
        if c["procedure_id"]:
            out["procedure"] = db.one("SELECT p.id, p.code, p.title, v.status, v.version_no FROM procedures p "
                                      "JOIN procedure_versions v ON v.id = p.latest_version_id WHERE p.id = ?",
                                      (c["procedure_id"],))
    else:
        out.pop("transcript", None)
        out["marker_count"] = db.scalar("SELECT COUNT(*) FROM capture_markers WHERE capture_id = ?", (c["id"],))
        out["file_count"] = db.scalar("SELECT COUNT(*) FROM files WHERE capture_id = ?", (c["id"],))
        out["has_video"] = bool(db.scalar("SELECT 1 FROM files WHERE capture_id = ? AND kind = 'video'", (c["id"],)))
    out["completeness"] = completeness({**out, "transcript": c["transcript"]})
    return out


def completeness(c: dict) -> dict:
    checks = {
        "metadata": bool(c.get("title") and c.get("machine") and c.get("skill_ids")),
        "consent": bool(c.get("consent_given")),
        "source": bool((c.get("transcript") or "").strip())
        or any(f["kind"] == "video" for f in c.get("files") or [])
        or bool(c.get("has_video")),
        "tacit_notes": bool((c.get("tips") or "").strip() or (c.get("mistakes") or "").strip()
                            or (c.get("troubleshooting") or "").strip()),
    }
    return {"checks": checks, "pct": round(sum(checks.values()) / len(checks) * 100)}


def list_captures(db: DB, org_id: str) -> list[dict]:
    rows = db.all("SELECT * FROM capture_sessions WHERE org_id = ? AND status != 'archived' ORDER BY updated_at DESC",
                  (org_id,))
    return [_shape(db, r, full=False) for r in rows]


def get_capture(db: DB, org_id: str, capture_id: str) -> dict:
    return _shape(db, _row(db, org_id, capture_id))


def _validate_expert(db: DB, org_id: str, expert_id: str) -> None:
    u = db.one("SELECT role FROM users WHERE id = ? AND org_id = ? AND active = 1", (expert_id, org_id))
    if not u or u["role"] not in ("expert", "trainer", "admin"):
        raise bad_request("The selected expert must be an active expert, trainer or admin in your organisation")


def _validate_skills(db: DB, org_id: str, skill_ids: list) -> list[str]:
    if not isinstance(skill_ids, list):
        raise bad_request("skill_ids must be a list")
    valid = {r["id"] for r in db.all("SELECT id FROM skills WHERE org_id = ?", (org_id,))}
    bad = [s for s in skill_ids if s not in valid]
    if bad:
        raise bad_request("Unknown skill(s)", {"skill_ids": bad})
    return list(dict.fromkeys(skill_ids))


def _apply_fields(db: DB, org_id: str, data: dict, changes: dict) -> None:
    for f in TEXT_FIELDS:
        if f in data:
            v = data[f]
            if v is not None and not isinstance(v, str):
                raise bad_request(f"'{f}' must be text")
            v = (v or "").strip() if f != "transcript" else (v or "")
            if len(v) > LIMITS.get(f, 500):
                raise bad_request(f"'{f}' is too long (max {LIMITS.get(f, 500)} characters)")
            changes[f] = v
    if "transcript_source" in changes and changes["transcript_source"] not in ("none", "typed", "uploaded", "sample"):
        raise bad_request("Invalid transcript_source")
    for f in LIST_FIELDS:
        if f in data:
            vals = data[f]
            if isinstance(vals, str):
                vals = [x.strip() for x in vals.split(",")]
            if not isinstance(vals, list):
                raise bad_request(f"'{f}' must be a list")
            changes[f + "_json"] = dumps([str(x).strip()[:120] for x in vals if str(x).strip()][:40])
    if "skill_ids" in data:
        changes["skill_ids_json"] = dumps(_validate_skills(db, org_id, data["skill_ids"]))
    if "expert_id" in data:
        _validate_expert(db, org_id, data["expert_id"])
        changes["expert_id"] = data["expert_id"]


def create_capture(db: DB, org_id: str, user: dict, data: dict) -> dict:
    if not (data.get("title") or "").strip():
        raise bad_request("A title is required", {"field": "title"})
    expert_id = data.get("expert_id") or user["id"]
    _validate_expert(db, org_id, expert_id)
    now = now_iso()
    row = {"id": new_id("cap"), "org_id": org_id, "expert_id": expert_id, "created_by": user["id"],
           "title": "", "created_at": now, "updated_at": now}
    changes: dict = {}
    _apply_fields(db, org_id, {**data, "expert_id": expert_id}, changes)
    row.update(changes)
    with db.tx():
        db.insert("capture_sessions", row)
        audit.record(db, org_id, user["id"], "capture.created", "capture", row["id"], f"Started capture “{row['title']}”")
    return get_capture(db, org_id, row["id"])


def update_capture(db: DB, org_id: str, user: dict, capture_id: str, data: dict) -> dict:
    c = _row(db, org_id, capture_id)
    if c["status"] == "archived":
        raise conflict("Archived captures cannot be edited")
    changes: dict = {}
    _apply_fields(db, org_id, data, changes)
    if "title" in changes and not changes["title"]:
        raise bad_request("A title is required", {"field": "title"})
    if "consent_given" in data:
        given = bool(data["consent_given"])
        scope = (data.get("consent_scope") or c["consent_scope"] or "").strip()
        if given and not scope:
            raise bad_request("Describe the consent scope (who may view the recording and for what purpose)")
        changes.update({"consent_given": 1 if given else 0, "consent_scope": scope[:500] if given else None,
                        "consent_recorded_by": user["id"] if given else None, "consent_at": now_iso() if given else None})
    if not changes:
        return get_capture(db, org_id, capture_id)
    changes["updated_at"] = now_iso()
    with db.tx():
        db.update("capture_sessions", capture_id, changes)
        if "consent_given" in changes:
            audit.record(db, org_id, user["id"], "capture.consent", "capture", capture_id,
                         ("Recorded expert consent" if changes["consent_given"] else "Withdrew consent") + f" for “{c['title']}”",
                         {"scope": changes.get("consent_scope")})
    return get_capture(db, org_id, capture_id)


def add_marker(db: DB, org_id: str, user: dict, capture_id: str, data: dict) -> dict:
    _row(db, org_id, capture_id)
    t = data.get("t_seconds")
    if isinstance(t, str):
        t = parse_timestamp(t)
    try:
        t = float(t)
    except (TypeError, ValueError):
        raise bad_request("t_seconds must be a time in seconds or HH:MM:SS")
    if t < 0 or t > 24 * 3600:
        raise bad_request("Timestamp out of range")
    kind = data.get("kind", "step")
    if kind not in MARKER_KINDS:
        raise bad_request(f"kind must be one of {', '.join(MARKER_KINDS)}")
    label = (data.get("label") or "").strip()
    if not label:
        raise bad_request("A marker label is required")
    row = {"id": new_id("mrk"), "capture_id": capture_id, "t_seconds": round(t, 1), "kind": kind,
           "label": label[:200], "note": (data.get("note") or "").strip()[:1000], "created_by": user["id"],
           "created_at": now_iso()}
    db.insert("capture_markers", row)
    db.update("capture_sessions", capture_id, {"updated_at": now_iso()})
    return row


def delete_marker(db: DB, org_id: str, capture_id: str, marker_id: str) -> None:
    _row(db, org_id, capture_id)
    cur = db.execute("DELETE FROM capture_markers WHERE id = ? AND capture_id = ?", (marker_id, capture_id))
    if cur.rowcount == 0:
        raise not_found("Marker")


def build_input(db: DB, org_id: str, c: dict) -> tuple[CaptureInput, list[dict]]:
    shaped = _shape(db, c)
    skill_rows = db.all("SELECT id, code, name FROM skills WHERE org_id = ?", (org_id,))
    by_id = {s["id"]: s for s in skill_rows}
    skills = [{"code": by_id[s]["code"], "name": by_id[s]["name"]} for s in shaped["skill_ids"] if s in by_id]
    markers = shaped["markers"]
    cap = CaptureInput(
        title=c["title"], expert_name=shaped["expert"]["name"] if shaped["expert"] else "", task_category=c["task_category"] or "",
        machine=c["machine"] or "", tools=shaped["tools"], materials=shaped["materials"], skills=skills,
        experience_level=c["experience_level"] or "", transcript=c["transcript"] or "", expert_notes=c["expert_notes"],
        tips=c["tips"], mistakes=c["mistakes"], troubleshooting=c["troubleshooting"], safety_notes=c["safety_notes"],
        markers=markers, has_video=any(f["kind"] == "video" for f in shaped["files"]))
    return cap, markers


def extract(db: DB, registry, org_id: str, user: dict, capture_id: str, provider: str) -> dict:
    c = _row(db, org_id, capture_id)
    if not c["consent_given"]:
        raise ApiError(422, "consent_required", "Record the expert's consent before processing their recording")
    cap, markers = build_input(db, org_id, c)
    try:
        result = registry.run_extraction(provider, cap, markers)
    except ExtractionError as e:
        status = {"not_configured": 503, "unavailable": 503, "rate_limited": 429, "timeout": 504,
                  "invalid_input": 422, "auth": 502, "refused": 422, "truncated": 422, "malformed": 502}.get(e.code, 502)
        audit.record(db, org_id, user["id"], "extraction.failed", "capture", capture_id,
                     f"Extraction with {provider} failed: {e.code}")
        raise ApiError(status, f"extraction_{e.code}", e.message, {"retryable": e.retryable, "provider": provider})
    content, meta = result["content"], result["meta"]
    now = now_iso()
    with db.tx():
        if c["procedure_id"]:
            proc = common.procedure(db, org_id, c["procedure_id"])
            open_v = db.one("SELECT id, status FROM procedure_versions WHERE procedure_id = ? AND status IN (?,?,?,?)",
                            (proc["id"], *workflow.EDITABLE))
            if open_v:
                raise conflict("This capture already has an unreviewed extracted version. Review or reject it first.",
                               {"version_id": open_v["id"]})
            version_no = db.scalar("SELECT MAX(version_no) FROM procedure_versions WHERE procedure_id = ?", (proc["id"],)) + 1
            proc_id = proc["id"]
        else:
            n = db.scalar("SELECT COUNT(*) FROM procedures WHERE org_id = ?", (org_id,)) + 1
            code = f"PR-{n:03d}"
            while db.scalar("SELECT 1 FROM procedures WHERE org_id = ? AND code = ?", (org_id, code)):
                n += 1
                code = f"PR-{n:03d}"
            proc_id = new_id("prc")
            db.insert("procedures", {"id": proc_id, "org_id": org_id, "code": code, "title": content["title"],
                                     "owner_expert_id": c["expert_id"], "capture_id": capture_id,
                                     "created_at": now, "updated_at": now})
            version_no = 1
        vid = new_id("ver")
        db.insert("procedure_versions", {
            "id": vid, "procedure_id": proc_id, "org_id": org_id, "version_no": version_no,
            "status": workflow.AI_PROCESSED, "content_json": dumps(content), "extractor": meta["provider"],
            "extraction_meta_json": dumps(meta), "change_summary": f"Extracted from capture “{c['title']}” by {meta['provider_label']}",
            "created_by": user["id"], "created_at": now, "updated_at": now})
        db.update("procedures", proc_id, {"latest_version_id": vid, "updated_at": now})
        db.update("capture_sessions", capture_id, {"status": "extracted", "procedure_id": proc_id, "updated_at": now})
        db.insert("review_events", {"id": new_id("rev"), "org_id": org_id, "version_id": vid, "actor_id": user["id"],
                                    "from_status": workflow.DRAFT, "to_status": workflow.AI_PROCESSED,
                                    "comment": f"{meta['provider_label']}: {meta['stats']['steps']} steps, "
                                               f"{meta['stats']['steps_verified']} evidence-verified",
                                    "created_at": now})
        audit.record(db, org_id, user["id"], "extraction.completed", "procedure", proc_id,
                     f"Extracted “{content['title']}” ({meta['stats']['steps']} steps) with {meta['provider_label']}",
                     {"version_id": vid, "stats": meta["stats"]})
    return {"procedure_id": proc_id, "version_id": vid, "meta": meta}
