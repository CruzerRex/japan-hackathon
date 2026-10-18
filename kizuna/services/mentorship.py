"""Global Mentorship: mentor discovery, requests, in-app scheduling, session
notes, mentor feedback and follow-up tasks."""
from __future__ import annotations

from datetime import datetime

from .. import audit
from ..auth import can
from ..db import DB, new_id, now_iso
from ..web import bad_request, conflict, forbidden, not_found
from . import common


def mentors(db: DB, org_id: str) -> list[dict]:
    rows = db.all("SELECT id, name, name_ja, role, title, department, languages, years_experience, bio FROM users "
                  "WHERE org_id = ? AND active = 1 AND role IN ('expert','trainer') ORDER BY years_experience DESC", (org_id,))
    for r in rows:
        r["skills"] = db.all("SELECT s.id, s.code, s.name, s.name_ja, e.proficiency FROM expert_skills e JOIN skills s ON s.id = e.skill_id "
                             "WHERE e.user_id = ? ORDER BY e.proficiency DESC", (r["id"],))
        r["active_mentees"] = db.scalar("SELECT COUNT(DISTINCT mentee_id) FROM mentorship_requests WHERE mentor_id = ? AND status = 'accepted'",
                                        (r["id"],))
        r["procedures"] = db.all("SELECT id, code, title FROM procedures WHERE owner_expert_id = ? AND published_version_id IS NOT NULL",
                                 (r["id"],))
    return rows


def _req(db: DB, org_id: str, request_id: str) -> dict:
    r = db.one("SELECT * FROM mentorship_requests WHERE id = ? AND org_id = ?", (request_id, org_id))
    if not r:
        raise not_found("Mentorship request")
    return r


def _participant(user: dict, r: dict) -> bool:
    return user["id"] in (r["mentor_id"], r["mentee_id"]) or can(user, "assessment.signoff")


def overview(db: DB, org_id: str, user: dict) -> dict:
    sql = """SELECT r.*, me.name AS mentee_name, me.name_ja AS mentee_name_ja, me.title AS mentee_title, me.languages AS mentee_languages,
                    mo.name AS mentor_name, mo.name_ja AS mentor_name_ja, s.code AS skill_code, s.name AS skill_name, s.id AS skill_id,
                    p.code AS procedure_code, p.title AS procedure_title
             FROM mentorship_requests r JOIN users me ON me.id = r.mentee_id JOIN users mo ON mo.id = r.mentor_id
             LEFT JOIN skills s ON s.id = r.skill_id LEFT JOIN procedures p ON p.id = r.procedure_id WHERE r.org_id = ?"""
    params: list = [org_id]
    if not can(user, "assessment.signoff") and user["role"] != "admin":
        sql += " AND (r.mentor_id = ? OR r.mentee_id = ?)"
        params += [user["id"], user["id"]]
    sql += " ORDER BY r.created_at DESC"
    reqs = db.all(sql, params)
    for r in reqs:
        r["sessions"] = db.all("SELECT * FROM mentoring_sessions WHERE request_id = ? ORDER BY scheduled_at", (r["id"],))
        for s in r["sessions"]:
            s["followups"] = db.all("SELECT f.*, u.name AS owner_name FROM followup_tasks f LEFT JOIN users u ON u.id = f.owner_id "
                                    "WHERE f.session_id = ? ORDER BY f.created_at", (s["id"],))
        r["mentee_competency"] = db.one("SELECT status, score FROM competency_records WHERE user_id = ? AND skill_id = ?",
                                        (r["mentee_id"], r["skill_id"])) if r["skill_id"] else None
    return {"requests": reqs, "mentors": mentors(db, org_id), "skills": common.skills(db, org_id)}


def create_request(db: DB, org_id: str, user: dict, data: dict) -> dict:
    mentor = common.user_in_org(db, org_id, data.get("mentor_id") or "")
    if mentor["role"] not in ("expert", "trainer"):
        raise bad_request("Mentors must be experts or trainers")
    if mentor["id"] == user["id"]:
        raise bad_request("You cannot request mentoring from yourself")
    skill_id = data.get("skill_id") or None
    if skill_id and not db.one("SELECT 1 FROM skills WHERE id = ? AND org_id = ?", (skill_id, org_id)):
        raise bad_request("Unknown skill")
    proc_id = data.get("procedure_id") or None
    if proc_id:
        common.procedure(db, org_id, proc_id)
    msg = (data.get("message") or "").strip()
    if len(msg) < 5:
        raise bad_request("Add a short message describing what you want to learn")
    if db.one("SELECT 1 FROM mentorship_requests WHERE mentee_id = ? AND mentor_id = ? AND status IN ('requested','accepted') "
              "AND COALESCE(skill_id,'') = COALESCE(?, '')", (user["id"], mentor["id"], skill_id)):
        raise conflict("You already have an open mentoring relationship with this mentor for this skill")
    row = {"id": new_id("mreq"), "org_id": org_id, "mentee_id": user["id"], "mentor_id": mentor["id"], "skill_id": skill_id,
           "procedure_id": proc_id, "message": msg[:1500], "status": "requested", "created_at": now_iso()}
    db.insert("mentorship_requests", row)
    audit.record(db, org_id, user["id"], "mentorship.requested", "mentorship", row["id"], f"{user['name']} requested mentoring from {mentor['name']}")
    return row


def respond(db: DB, org_id: str, user: dict, request_id: str, data: dict) -> dict:
    r = _req(db, org_id, request_id)
    action = data.get("action")
    if action in ("accept", "decline"):
        if user["id"] != r["mentor_id"]:
            raise forbidden("Only the requested mentor can accept or decline")
        if r["status"] != "requested":
            raise conflict(f"Request is already {r['status']}")
        status = "accepted" if action == "accept" else "declined"
    elif action == "complete":
        if not _participant(user, r) or r["status"] != "accepted":
            raise conflict("Only an accepted mentorship can be completed by its participants")
        status = "completed"
    elif action == "cancel":
        if user["id"] != r["mentee_id"] or r["status"] not in ("requested", "accepted"):
            raise forbidden("Only the mentee can cancel an open request")
        status = "cancelled"
    else:
        raise bad_request("action must be accept, decline, complete or cancel")
    db.update("mentorship_requests", request_id, {"status": status, "response_note": (data.get("note") or "")[:1000] or None,
                                                   "responded_at": now_iso()})
    audit.record(db, org_id, user["id"], f"mentorship.{status}", "mentorship", request_id, f"Mentorship {status} by {user['name']}")
    return {"status": status}


def schedule(db: DB, org_id: str, user: dict, request_id: str, data: dict) -> dict:
    r = _req(db, org_id, request_id)
    if not _participant(user, r):
        raise forbidden()
    if r["status"] != "accepted":
        raise conflict("Sessions can only be scheduled for accepted mentorships")
    when = (data.get("scheduled_at") or "").strip()
    try:
        datetime.fromisoformat(when.replace("Z", "+00:00"))
    except ValueError:
        raise bad_request("scheduled_at must be an ISO date-time, e.g. 2026-11-04T14:00")
    mode = data.get("mode", "remote")
    if mode not in ("onsite", "remote"):
        raise bad_request("mode must be onsite or remote")
    try:
        duration = int(data.get("duration_min") or 60)
    except (TypeError, ValueError):
        raise bad_request("duration_min must be a number")
    if not 15 <= duration <= 480:
        raise bad_request("duration must be between 15 and 480 minutes")
    now = now_iso()
    row = {"id": new_id("mses"), "org_id": org_id, "request_id": request_id, "scheduled_at": when[:16], "duration_min": duration,
           "mode": mode, "location": (data.get("location") or "")[:200], "agenda": (data.get("agenda") or "")[:2000],
           "status": "scheduled", "created_by": user["id"], "created_at": now, "updated_at": now}
    db.insert("mentoring_sessions", row)
    audit.record(db, org_id, user["id"], "mentorship.session_scheduled", "mentorship", request_id,
                 f"Mentoring session scheduled for {row['scheduled_at'].replace('T', ' ')} ({mode})")
    return row


def update_session(db: DB, org_id: str, user: dict, session_id: str, data: dict) -> dict:
    s = db.one("SELECT * FROM mentoring_sessions WHERE id = ? AND org_id = ?", (session_id, org_id))
    if not s:
        raise not_found("Session")
    r = _req(db, org_id, s["request_id"])
    if not _participant(user, r):
        raise forbidden()
    changes = {}
    if "notes" in data:
        changes["notes"] = (data["notes"] or "")[:5000]
    if "mentor_feedback" in data:
        if user["id"] != r["mentor_id"]:
            raise forbidden("Only the mentor can write mentor feedback")
        changes["mentor_feedback"] = (data["mentor_feedback"] or "")[:3000]
    if "status" in data:
        if data["status"] not in ("scheduled", "completed", "cancelled"):
            raise bad_request("Invalid status")
        changes["status"] = data["status"]
    if not changes:
        raise bad_request("Nothing to update")
    changes["updated_at"] = now_iso()
    db.update("mentoring_sessions", session_id, changes)
    if changes.get("status") == "completed":
        audit.record(db, org_id, user["id"], "mentorship.session_completed", "mentorship", r["id"], "Mentoring session completed")
    return {**s, **changes}


def add_followup(db: DB, org_id: str, user: dict, session_id: str, data: dict) -> dict:
    s = db.one("SELECT * FROM mentoring_sessions WHERE id = ? AND org_id = ?", (session_id, org_id))
    if not s:
        raise not_found("Session")
    r = _req(db, org_id, s["request_id"])
    if not _participant(user, r):
        raise forbidden()
    desc = (data.get("description") or "").strip()
    if not desc:
        raise bad_request("Describe the follow-up task")
    owner = data.get("owner_id") or r["mentee_id"]
    if owner not in (r["mentee_id"], r["mentor_id"]):
        raise bad_request("Follow-up owner must be the mentor or mentee")
    row = {"id": new_id("fup"), "org_id": org_id, "session_id": session_id, "description": desc[:500], "owner_id": owner,
           "due_date": data.get("due_date") or None, "done": 0, "created_at": now_iso()}
    db.insert("followup_tasks", row)
    return row


def toggle_followup(db: DB, org_id: str, user: dict, task_id: str, done: bool) -> dict:
    t = db.one("SELECT f.*, s.request_id FROM followup_tasks f JOIN mentoring_sessions s ON s.id = f.session_id "
               "WHERE f.id = ? AND f.org_id = ?", (task_id, org_id))
    if not t:
        raise not_found("Follow-up task")
    if not _participant(user, _req(db, org_id, t["request_id"])):
        raise forbidden()
    db.update("followup_tasks", task_id, {"done": 1 if done else 0})
    return {"done": done}
