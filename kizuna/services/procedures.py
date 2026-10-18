"""Knowledge Library: procedure versions, structured editing, expert review,
publishing, revision history, diffs, exports and learning analytics."""
from __future__ import annotations

import json

from .. import audit
from ..auth import can
from ..db import DB, dumps, loads, new_id, now_iso
from ..domain import workflow
from ..domain.procedure_schema import (approval_blockers, needs_confirmation, normalize_content,
                                       publish_blockers)
from ..web import ApiError, bad_request, conflict, forbidden, not_found
from . import common


def _visible_version(user: dict, v: dict) -> bool:
    if can(user, "procedure.read_unpublished"):
        return True
    return v["status"] == workflow.PUBLISHED


def list_procedures(db: DB, org_id: str, user: dict) -> list[dict]:
    rows = db.all("""SELECT p.*, lv.status AS latest_status, lv.version_no AS latest_version_no, lv.updated_at AS latest_updated,
                            lv.content_json AS latest_content, pv.version_no AS published_version_no,
                            pv.content_json AS published_content, pv.published_at,
                            u.name AS owner_name, u.name_ja AS owner_name_ja
                     FROM procedures p
                     LEFT JOIN procedure_versions lv ON lv.id = p.latest_version_id
                     LEFT JOIN procedure_versions pv ON pv.id = p.published_version_id
                     LEFT JOIN users u ON u.id = p.owner_expert_id
                     WHERE p.org_id = ? ORDER BY p.code""", (org_id,))
    out = []
    unpublished_ok = can(user, "procedure.read_unpublished")
    for r in rows:
        if not unpublished_ok and not r["published_version_id"]:
            continue
        content = loads(r["published_content"] if not unpublished_ok else r["latest_content"], {}) or {}
        steps = content.get("steps", [])
        out.append({
            "id": r["id"], "code": r["code"], "title": r["title"], "owner_name": r["owner_name"],
            "owner_name_ja": r["owner_name_ja"], "owner_expert_id": r["owner_expert_id"],
            "latest_status": r["latest_status"] if unpublished_ok else workflow.PUBLISHED,
            "latest_version_no": r["latest_version_no"] if unpublished_ok else r["published_version_no"],
            "latest_version_id": r["latest_version_id"] if unpublished_ok else r["published_version_id"],
            "published_version_id": r["published_version_id"], "published_version_no": r["published_version_no"],
            "published_at": r["published_at"], "updated_at": r["latest_updated"], "skills": content.get("skills", []),
            "machine": content.get("machine", ""), "step_count": len(steps),
            "verified_steps": sum(1 for s in steps if s.get("evidence_verified")),
            "safety_critical_steps": sum(1 for s in steps if s.get("safety_critical")),
            "question_count": len(content.get("questions", [])) + len(content.get("scenarios", [])),
        })
    return out


def evidence_summary(content: dict) -> dict:
    steps = content.get("steps", [])
    counts = {k: 0 for k in ("demonstration", "transcript", "expert_note", "expert_edit", "inference")}
    for s in steps:
        counts[s.get("source_type", "inference")] = counts.get(s.get("source_type", "inference"), 0) + 1
    return {
        "by_source": counts,
        "verified": sum(1 for s in steps if s.get("evidence_verified")),
        "confirmed": sum(1 for s in steps if s.get("expert_confirmed")),
        "needs_confirmation": sum(1 for s in steps if s.get("source_type") != "expert_edit" and not s.get("expert_confirmed")),
        "needs_individual_review": sum(1 for s in steps if needs_confirmation(s) and not s.get("expert_confirmed")),
        "open_questions": sum(1 for q in content.get("open_questions", []) if not q.get("resolved")),
        "total": len(steps),
    }


def get_procedure(db: DB, org_id: str, user: dict, procedure_id: str, version_id: str | None = None) -> dict:
    p = common.procedure(db, org_id, procedure_id)
    unpublished_ok = can(user, "procedure.read_unpublished")
    if not unpublished_ok and not p["published_version_id"]:
        raise not_found("Procedure")
    vid = version_id or (p["latest_version_id"] if unpublished_ok else p["published_version_id"])
    v = common.version(db, org_id, vid)
    if v["procedure_id"] != procedure_id or not _visible_version(user, v):
        raise not_found("Procedure version")
    names = common.names(db, org_id)
    versions = db.all("SELECT id, version_no, status, change_summary, created_at, created_by, approved_by, approved_at, "
                      "published_at, extractor FROM procedure_versions WHERE procedure_id = ? ORDER BY version_no DESC",
                      (procedure_id,))
    if not unpublished_ok:
        versions = [x for x in versions if x["status"] in (workflow.PUBLISHED,)]
    for x in versions:
        x["created_by_name"] = names.get(x["created_by"])
        x["approved_by_name"] = names.get(x["approved_by"])
    validation = normalize_content(v["content"]).as_dict()
    actions = []
    for a in workflow.available_actions(v["status"]):
        t = workflow.TRANSITIONS[a]
        if can(user, t.permission):
            actions.append({"action": a, "needs_comment": t.needs_comment})
    events = db.all("SELECT r.*, u.name AS actor_name, u.role AS actor_role FROM review_events r "
                    "LEFT JOIN users u ON u.id = r.actor_id WHERE r.version_id IN "
                    f"({','.join('?' for _ in versions) or 'NULL'}) ORDER BY r.created_at DESC",
                    [x["id"] for x in versions]) if unpublished_ok else []
    owner = db.one("SELECT id, name, name_ja, title, years_experience FROM users WHERE id = ?", (p["owner_expert_id"],))
    capture = None
    if p["capture_id"] and can(user, "capture.read"):
        capture = db.one("SELECT id, title, transcript, consent_given, consent_scope FROM capture_sessions WHERE id = ?",
                         (p["capture_id"],))
        if capture:
            capture["video"] = db.one("SELECT id, original_name, mime FROM files WHERE capture_id = ? AND kind = 'video' "
                                      "ORDER BY created_at DESC LIMIT 1", (p["capture_id"],))
            capture["markers"] = db.all("SELECT t_seconds, kind, label FROM capture_markers WHERE capture_id = ? "
                                        "ORDER BY t_seconds", (p["capture_id"],))
    skill_map = common.skills_by_code(db, org_id)
    v["approved_by_name"] = names.get(v["approved_by"])
    v["published_by_name"] = names.get(v["published_by"])
    v["created_by_name"] = names.get(v["created_by"])
    return {
        "procedure": p, "version": v, "versions": versions, "validation": validation,
        "approval_blockers": approval_blockers(v["content"]) if v["status"] in workflow.EDITABLE else [],
        "publish_blockers": publish_blockers(v["content"]) if v["status"] == workflow.APPROVED else [],
        "actions": actions, "editable": v["status"] in workflow.EDITABLE and can(user, "procedure.edit"),
        "can_confirm": v["status"] in workflow.EDITABLE and can(user, "procedure.approve"),
        "can_revise": can(user, "procedure.edit") and v["status"] in (workflow.PUBLISHED, workflow.APPROVED, workflow.REJECTED,
                                                                         workflow.SUPERSEDED),
        "events": events, "owner": owner, "capture": capture,
        "skills": [skill_map[c] for c in v["content"].get("skills", []) if c in skill_map],
        "evidence": evidence_summary(v["content"]),
        "is_current_published": v["id"] == p["published_version_id"],
        "translations": db.all("SELECT id, locale, status, updated_at FROM translations WHERE version_id = ?", (v["id"],)),
        "feedback": db.all("SELECT f.*, u.name AS created_by_name FROM knowledge_feedback f LEFT JOIN users u ON u.id = f.created_by "
                           "WHERE f.procedure_id = ? AND f.org_id = ? ORDER BY f.created_at DESC", (procedure_id, org_id))
        if unpublished_ok else [],
    }


def create_manual(db: DB, org_id: str, user: dict, data: dict) -> dict:
    content = data.get("content") or {"title": data.get("title", ""), "steps": data.get("steps", [])}
    res = normalize_content(content)
    if not res.content["title"]:
        raise bad_request("A title is required")
    now = now_iso()
    n = db.scalar("SELECT COUNT(*) FROM procedures WHERE org_id = ?", (org_id,)) + 1
    code = f"PR-{n:03d}"
    while db.scalar("SELECT 1 FROM procedures WHERE org_id = ? AND code = ?", (org_id, code)):
        n += 1
        code = f"PR-{n:03d}"
    pid, vid = new_id("prc"), new_id("ver")
    for s in res.content["steps"]:
        if s["source_type"] == "inference":
            s["source_type"] = "expert_edit"
            s["evidence_verified"] = True
    with db.tx():
        db.insert("procedures", {"id": pid, "org_id": org_id, "code": code, "title": res.content["title"],
                                 "owner_expert_id": user["id"], "latest_version_id": vid, "created_at": now, "updated_at": now})
        db.insert("procedure_versions", {"id": vid, "procedure_id": pid, "org_id": org_id, "version_no": 1,
                                         "status": workflow.DRAFT, "content_json": dumps(res.content), "extractor": "manual",
                                         "change_summary": "Authored manually", "created_by": user["id"],
                                         "created_at": now, "updated_at": now})
        audit.record(db, org_id, user["id"], "procedure.created", "procedure", pid, f"Created {code} “{res.content['title']}”")
    return {"procedure_id": pid, "version_id": vid}


def _step_text(s: dict) -> tuple:
    return (s.get("title"), s.get("instruction"), s.get("quality_check"), s.get("why"))


def save_content(db: DB, org_id: str, user: dict, version_id: str, content: dict, note: str | None = None) -> dict:
    v = common.version(db, org_id, version_id)
    if v["status"] not in workflow.EDITABLE:
        raise conflict(f"A {v['status']} version cannot be edited. Create a new revision instead.")
    res = normalize_content(content)
    old_steps = {s["step_id"]: s for s in v["content"].get("steps", [])}
    for s in res.content["steps"]:
        old = old_steps.get(s["step_id"])
        if old is None:
            if s["source_type"] == "inference" and not s.get("evidence_quote"):
                s["source_type"] = "expert_edit"
            s["expert_edited"], s["edited_by"] = True, user["name"]
        elif _step_text(old) != _step_text(s):
            s["expert_edited"], s["edited_by"] = True, user["name"]
            # Text changed: a prior confirmation no longer applies to the new wording.
            if old.get("expert_confirmed") and s.get("expert_confirmed") and s.get("confirmed_by") != user["name"]:
                s["expert_confirmed"], s["confirmed_by"] = False, None
        if s["source_type"] == "expert_edit":
            s["evidence_verified"] = True
    if res.content["title"]:
        db.update("procedures", v["procedure_id"], {"title": res.content["title"], "updated_at": now_iso()})
    with db.tx():
        db.update("procedure_versions", version_id, {"content_json": dumps(res.content), "updated_at": now_iso()})
        audit.record(db, org_id, user["id"], "procedure.edited", "procedure", v["procedure_id"],
                     f"Edited v{v['version_no']} of “{res.content['title']}”" + (f": {note}" if note else ""),
                     {"version_id": version_id, "errors": len(res.errors)})
    return {"validation": res.as_dict(), "content": res.content}


def confirm_items(db: DB, org_id: str, user: dict, version_id: str, item_ids: list[str], confirmed: bool = True) -> dict:
    v = common.version(db, org_id, version_id)
    if v["status"] not in workflow.EDITABLE:
        raise conflict("Items can only be confirmed while the version is under review")
    if not isinstance(item_ids, list) or not item_ids:
        raise bad_request("item_ids must be a non-empty list")
    c = v["content"]
    found = 0
    for coll, key_name in (("steps", "step_id"), ("safety", "id")):
        for it in c.get(coll, []):
            if it.get(key_name) in item_ids:
                it["expert_confirmed"] = confirmed
                it["confirmed_by"] = user["name"] if confirmed else None
                found += 1
    if not found:
        raise not_found("Items")
    with db.tx():
        db.update("procedure_versions", version_id, {"content_json": dumps(c), "updated_at": now_iso()})
        audit.record(db, org_id, user["id"], "procedure.confirmed" if confirmed else "procedure.unconfirmed", "procedure",
                     v["procedure_id"], f"{'Confirmed' if confirmed else 'Un-confirmed'} {found} item(s) in v{v['version_no']}",
                     {"version_id": version_id, "items": item_ids})
    return {"confirmed": found, "blockers": approval_blockers(c)}


def resolve_open_question(db: DB, org_id: str, user: dict, version_id: str, oq_id: str, resolution: str,
                          add_as_tip: bool = True) -> dict:
    """Tacit-knowledge elicitation loop: the expert's answer to an open question
    is stored and (by default) becomes an expert-authored tip on the step."""
    v = common.version(db, org_id, version_id)
    if v["status"] not in workflow.EDITABLE:
        raise conflict("Open questions can only be resolved while the version is editable")
    resolution = (resolution or "").strip()
    if not resolution:
        raise bad_request("Provide the expert's answer or a reason for dismissing the question")
    c = v["content"]
    oq = next((q for q in c.get("open_questions", []) if q["id"] == oq_id), None)
    if not oq:
        raise not_found("Open question")
    oq["resolved"], oq["resolution"] = True, resolution[:1500]
    if add_as_tip:
        c.setdefault("tips", []).append({
            "id": f"tip-x{len(c['tips']) + 1:03d}", "text": resolution[:1500], "step_id": oq.get("step_id"),
            "source_type": "expert_edit", "source_timestamp": None, "evidence_quote": None,
            "evidence_verified": True, "expert_confirmed": True, "confirmed_by": user["name"],
            "expert_edited": True, "edited_by": user["name"]})
    c = normalize_content(c).content
    with db.tx():
        db.update("procedure_versions", version_id, {"content_json": dumps(c), "updated_at": now_iso()})
        audit.record(db, org_id, user["id"], "procedure.tacit_resolved", "procedure", v["procedure_id"],
                     f"Answered open question: “{oq['text'][:80]}”", {"version_id": version_id})
    return {"content": c, "blockers": approval_blockers(c)}


def transition(db: DB, org_id: str, user: dict, version_id: str, action: str, comment: str | None) -> dict:
    v = common.version(db, org_id, version_id)
    try:
        t = workflow.check_transition(v["status"], action)
    except workflow.TransitionError as e:
        raise conflict(str(e))
    if not can(user, t.permission):
        raise forbidden(f"Your role ({user['role']}) cannot {action} procedures")
    comment = (comment or "").strip()
    if t.needs_comment and not comment:
        raise bad_request(f"A comment explaining the decision is required to {action.replace('_', ' ')}")
    if action == "approve":
        blockers = approval_blockers(v["content"])
        if blockers:
            raise ApiError(422, "approval_blocked", "This version cannot be approved yet", {"blockers": blockers})
    if action == "publish":
        blockers = publish_blockers(v["content"])
        if blockers:
            raise ApiError(422, "publish_blocked", "This version cannot be published yet", {"blockers": blockers})
    now = now_iso()
    changes = {"status": t.target, "updated_at": now}
    if action == "approve":
        changes.update({"approved_by": user["id"], "approved_at": now})
    if action == "publish":
        changes.update({"published_by": user["id"], "published_at": now})
    p = common.procedure(db, org_id, v["procedure_id"])
    with db.tx():
        if action == "publish":
            if p["published_version_id"]:
                db.update("procedure_versions", p["published_version_id"], {"status": workflow.SUPERSEDED, "updated_at": now})
            db.update("procedures", p["id"], {"published_version_id": version_id, "updated_at": now})
        db.update("procedure_versions", version_id, changes)
        db.insert("review_events", {"id": new_id("rev"), "org_id": org_id, "version_id": version_id, "actor_id": user["id"],
                                    "from_status": v["status"], "to_status": t.target, "comment": comment or None,
                                    "created_at": now})
        audit.record(db, org_id, user["id"], f"procedure.{action}", "procedure", p["id"],
                     f"{action.replace('_', ' ').capitalize()}: {p['code']} v{v['version_no']} → {t.target}",
                     {"version_id": version_id, "comment": comment})
    return {"status": t.target}


def new_revision(db: DB, org_id: str, user: dict, procedure_id: str, change_summary: str | None) -> dict:
    p = common.procedure(db, org_id, procedure_id)
    open_v = db.one(f"SELECT id FROM procedure_versions WHERE procedure_id = ? AND status IN ({','.join('?' * len(workflow.EDITABLE))})",
                    (procedure_id, *workflow.EDITABLE))
    if open_v:
        raise conflict("An editable revision already exists for this procedure", {"version_id": open_v["id"]})
    base_id = p["published_version_id"] or p["latest_version_id"]
    base = common.version(db, org_id, base_id)
    content = base["content"]
    for coll in ("steps", "safety"):
        for it in content.get(coll, []):
            it["expert_confirmed"], it["confirmed_by"] = False, None  # each revision is re-confirmed
    now = now_iso()
    vid = new_id("ver")
    version_no = db.scalar("SELECT MAX(version_no) FROM procedure_versions WHERE procedure_id = ?", (procedure_id,)) + 1
    with db.tx():
        db.insert("procedure_versions", {"id": vid, "procedure_id": procedure_id, "org_id": org_id, "version_no": version_no,
                                         "status": workflow.DRAFT, "content_json": dumps(content), "extractor": "revision",
                                         "change_summary": (change_summary or f"Revision of v{base['version_no']}")[:500],
                                         "based_on_version_id": base_id, "created_by": user["id"], "created_at": now,
                                         "updated_at": now})
        db.update("procedures", procedure_id, {"latest_version_id": vid, "updated_at": now})
        audit.record(db, org_id, user["id"], "procedure.revision", "procedure", procedure_id,
                     f"Started revision v{version_no} of {p['code']}", {"based_on": base_id})
    return {"version_id": vid}


def diff_versions(db: DB, org_id: str, user: dict, a_id: str, b_id: str) -> dict:
    a, b = common.version(db, org_id, a_id), common.version(db, org_id, b_id)
    if a["procedure_id"] != b["procedure_id"]:
        raise bad_request("Versions belong to different procedures")
    if not (_visible_version(user, a) and _visible_version(user, b)):
        raise not_found("Procedure version")
    fields = ("title", "instruction", "why", "quality_check", "safety_critical", "critical_checkpoint", "source_type")
    sa = {s["step_id"]: s for s in a["content"].get("steps", [])}
    sb = {s["step_id"]: s for s in b["content"].get("steps", [])}
    steps = []
    for sid in list(dict.fromkeys([*sa.keys(), *sb.keys()])):
        if sid not in sa:
            steps.append({"step_id": sid, "change": "added", "title": sb[sid]["title"], "after": sb[sid]})
        elif sid not in sb:
            steps.append({"step_id": sid, "change": "removed", "title": sa[sid]["title"], "before": sa[sid]})
        else:
            changed = {f: {"before": sa[sid].get(f), "after": sb[sid].get(f)} for f in fields if sa[sid].get(f) != sb[sid].get(f)}
            steps.append({"step_id": sid, "change": "modified" if changed else "unchanged", "title": sb[sid]["title"],
                          "fields": changed})
    counts = {k: {"before": len(a["content"].get(k, [])), "after": len(b["content"].get(k, []))}
              for k in ("tips", "mistakes", "failure_modes", "safety", "questions", "scenarios")}
    return {"a": {"id": a["id"], "version_no": a["version_no"], "status": a["status"]},
            "b": {"id": b["id"], "version_no": b["version_no"], "status": b["status"]},
            "title": {"before": a["content"].get("title"), "after": b["content"].get("title")},
            "steps": steps, "counts": counts}


def step_insights(db: DB, org_id: str, procedure_id: str) -> dict:
    """Continuous improvement: aggregate assessment errors per step to surface
    documentation gaps (steps learners repeatedly get wrong)."""
    rows = db.all("SELECT result_json FROM assessment_attempts WHERE procedure_id = ? AND org_id = ? AND status = 'submitted'",
                  (procedure_id, org_id))
    stats: dict[str, dict] = {}
    for r in rows:
        res = loads(r["result_json"], {}) or {}
        for it in res.get("items", []):
            sid = it.get("step_id")
            if not sid:
                continue
            s = stats.setdefault(sid, {"step_id": sid, "answers": 0, "wrong": 0, "critical_wrong": 0})
            s["answers"] += 1
            if not it.get("is_correct"):
                s["wrong"] += 1
                if it.get("critical"):
                    s["critical_wrong"] += 1
    out = []
    for s in stats.values():
        s["error_rate"] = round(s["wrong"] / s["answers"], 2) if s["answers"] else 0
        s["flagged"] = s["answers"] >= 2 and (s["error_rate"] >= 0.4 or s["critical_wrong"] >= 2)
        out.append(s)
    out.sort(key=lambda s: -s["error_rate"])
    return {"attempts": len(rows), "steps": out, "rule": "Flag a step when ≥2 answers and (error rate ≥ 40% or ≥2 critical errors)"}


def add_feedback(db: DB, org_id: str, user: dict, procedure_id: str, data: dict) -> dict:
    p = common.procedure(db, org_id, procedure_id)
    note = (data.get("note") or "").strip()
    if not note:
        raise bad_request("Feedback note is required")
    source = data.get("source") or ("learner" if user["role"] == "trainee" else user["role"] if user["role"] in ("trainer", "expert") else "trainer")
    if source not in ("assessment", "trainer", "learner", "expert"):
        source = "learner"
    vid = p["published_version_id"] or p["latest_version_id"]
    row = {"id": new_id("fb"), "org_id": org_id, "procedure_id": procedure_id, "version_id": vid,
           "step_id": (data.get("step_id") or None), "source": source, "note": note[:1500], "status": "open",
           "created_by": user["id"], "created_at": now_iso()}
    db.insert("knowledge_feedback", row)
    audit.record(db, org_id, user["id"], "feedback.created", "procedure", procedure_id,
                 f"Improvement note on {p['code']}" + (f" ({row['step_id']})" if row["step_id"] else ""))
    return row


def resolve_feedback(db: DB, org_id: str, user: dict, feedback_id: str, status: str) -> dict:
    if status not in ("addressed", "dismissed", "open"):
        raise bad_request("Invalid status")
    fb = db.one("SELECT * FROM knowledge_feedback WHERE id = ? AND org_id = ?", (feedback_id, org_id))
    if not fb:
        raise not_found("Feedback")
    db.update("knowledge_feedback", feedback_id, {"status": status, "resolved_by": user["id"], "resolved_at": now_iso()})
    return {"status": status}


# -- exports --------------------------------------------------------------------------------------
SOURCE_LABEL = {"demonstration": "Demonstrated", "transcript": "Said (transcript)", "expert_note": "Written by expert",
                "expert_edit": "Expert-authored", "inference": "AI-inferred (unverified)"}


def export(db: DB, org_id: str, user: dict, procedure_id: str, version_id: str | None, fmt: str) -> tuple[str, str, str]:
    data = get_procedure(db, org_id, user, procedure_id, version_id)
    p, v, c = data["procedure"], data["version"], data["version"]["content"]
    base = f"{p['code']}_v{v['version_no']}"
    if fmt == "json":
        doc = {"format": "kizuna-forge/procedure@1", "exported_at": now_iso(),
               "procedure": {"id": p["id"], "code": p["code"], "title": p["title"]},
               "version": {"id": v["id"], "version_no": v["version_no"], "status": v["status"],
                           "approved_by": v.get("approved_by_name"), "approved_at": v["approved_at"],
                           "published_at": v["published_at"], "extractor": v["extractor"]},
               "owner_expert": data["owner"]["name"] if data["owner"] else None,
               "review_history": [{k: e[k] for k in ("from_status", "to_status", "actor_name", "comment", "created_at")}
                                  for e in data["events"]],
               "content": c}
        return json.dumps(doc, ensure_ascii=False, indent=2), "application/json; charset=utf-8", base + ".json"
    lines = [f"# {p['code']} — {c['title']}", ""]
    status_line = f"**Version {v['version_no']} · {v['status']}**"
    if v["status"] != "PUBLISHED":
        status_line += " — ⚠️ NOT APPROVED TRAINING MATERIAL"
    lines += [status_line, ""]
    if v.get("approved_by_name"):
        lines.append(f"Approved by {v['approved_by_name']} on {v['approved_at'][:10]}.")
    if data["owner"]:
        lines.append(f"Source expert: {data['owner']['name']}.")
    lines += ["", "> Evidence classes: Demonstrated · Said (transcript) · Written by expert · Expert-authored · AI-inferred (unverified).",
              "> Tolerances and values must always be checked against the current drawing/specification.", ""]
    if c.get("purpose"):
        lines += ["## Purpose", c["purpose"], ""]
    if c.get("prerequisites"):
        lines += ["## Prerequisites"] + [f"- {x}" for x in c["prerequisites"]] + [""]
    if c.get("equipment"):
        lines += ["## Equipment"] + [f"- {e['name']} ({e['kind']})" for e in c["equipment"]] + [""]
    if c.get("safety"):
        lines += ["## Safety"] + [f"- ⚠️ {s['text']}" for s in c["safety"]] + [""]
    lines.append("## Procedure")
    tips_by = {}
    for t in c.get("tips", []):
        tips_by.setdefault(t.get("step_id"), []).append(t)
    mis_by = {}
    for m in c.get("mistakes", []):
        mis_by.setdefault(m.get("step_id"), []).append(m)
    for n, s in enumerate(c["steps"], 1):
        flags = (" 🛑 SAFETY-CRITICAL" if s["safety_critical"] else "") + (" ✅ CHECKPOINT" if s["critical_checkpoint"] else "")
        lines += ["", f"### {n}. {s['title']}{flags}", s["instruction"]]
        if s.get("why"):
            lines.append(f"\n*Why:* {s['why']}")
        if s.get("quality_check"):
            lines.append(f"\n*Check:* {s['quality_check']}")
        if s.get("tolerance"):
            lines.append(f"\n*Stated requirement:* {s['tolerance']['text']}")
        ev = SOURCE_LABEL.get(s["source_type"], s["source_type"])
        ev_line = f"\n<sub>Evidence: {ev}" + (f" @ {s['source_timestamp']}" if s.get("source_timestamp") else "")
        if s.get("evidence_quote"):
            ev_line += f" — “{s['evidence_quote'][:240]}”"
        lines.append(ev_line + (" · verified" if s.get("evidence_verified") else " · unverified") + "</sub>")
        for t in tips_by.get(s["step_id"], []):
            lines.append(f"- 💡 Expert tip: {t['text']}")
        for m in mis_by.get(s["step_id"], []):
            lines.append(f"- ⚠️ Common mistake: {m['text']}")
    if c.get("failure_modes"):
        lines += ["", "## Troubleshooting", "| Symptom | Action | Source |", "|---|---|---|"]
        for f in c["failure_modes"]:
            lines.append(f"| {f['symptom']} | {f['action']} | {SOURCE_LABEL.get(f['source_type'])} {f.get('source_timestamp') or ''} |")
    unresolved = [q for q in c.get("open_questions", []) if not q.get("resolved")]
    if unresolved:
        lines += ["", "## Open questions requiring expert verification"] + [f"- {q['text']}" for q in unresolved]
    lines += ["", "---", f"Exported from Kizuna Forge on {now_iso()[:10]}. Structured JSON export available for portability."]
    md = "\n".join(lines)
    return md, "text/markdown; charset=utf-8", base + ".md"
