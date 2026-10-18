"""Competency Validation Engine: competency records, trainer sign-off,
remediation and the competency matrix."""
from __future__ import annotations

from .. import audit
from ..auth import can
from ..db import DB, dumps, loads, new_id, now_iso
from ..domain.scoring import OUTCOME_TO_STATUS, SCORING_RULES, SIGNOFF_TO_ATTEMPT, SIGNOFF_TO_STATUS
from ..web import bad_request, conflict, forbidden, not_found
from . import common


VERBS = {"approve": "validated", "reject": "rejected the evidence of", "remediate": "assigned remediation to",
         "reassess": "required reassessment of"}


def _skill_ids(db: DB, org_id: str, codes: list[str]) -> list[str]:
    by_code = common.skills_by_code(db, org_id)
    return [by_code[c]["id"] for c in codes if c in by_code]


def _upsert(db: DB, org_id: str, user_id: str, skill_id: str, **fields) -> None:
    now = now_iso()
    row = db.one("SELECT id FROM competency_records WHERE user_id = ? AND skill_id = ?", (user_id, skill_id))
    if row:
        db.update("competency_records", row["id"], {**fields, "updated_at": now})
    else:
        db.insert("competency_records", {"id": new_id("cmp"), "org_id": org_id, "user_id": user_id, "skill_id": skill_id,
                                         "status": fields.pop("status", "in_training"), **fields, "updated_at": now})


def mark_in_training(db: DB, org_id: str, user_id: str, skill_codes: list[str]) -> None:
    for sid in _skill_ids(db, org_id, skill_codes):
        if not db.one("SELECT 1 FROM competency_records WHERE user_id = ? AND skill_id = ?", (user_id, sid)):
            _upsert(db, org_id, user_id, sid, status="in_training")


def apply_attempt(db: DB, org_id: str, user: dict, attempt: dict, version: dict, result: dict) -> None:
    status = OUTCOME_TO_STATUS[result["outcome"]]
    for sid in _skill_ids(db, org_id, version["content"].get("skills", [])):
        current = db.one("SELECT status FROM competency_records WHERE user_id = ? AND skill_id = ?", (attempt["user_id"], sid))
        if current and current["status"] == "validated" and status != "pending_signoff":
            continue  # a later failed practice attempt does not silently revoke a trainer-validated competency
        _upsert(db, org_id, attempt["user_id"], sid, status=status, score=result["score"], latest_attempt_id=attempt["id"])
    if result["outcome"] == "critical_failure":
        steps = {s["step_id"]: s for s in version["content"]["steps"]}
        failed_steps = list(dict.fromkeys(i["step_id"] for i in result["items"]
                                          if i["critical"] and not i["is_correct"] and i.get("step_id")))
        titles = ", ".join(f"“{steps[s]['title']}”" for s in failed_steps if s in steps) or "the critical checkpoints"
        db.insert("remediation_tasks", {
            "id": new_id("rem"), "org_id": org_id, "user_id": attempt["user_id"],
            "skill_id": (_skill_ids(db, org_id, version["content"].get("skills", [])) or [None])[0],
            "procedure_id": attempt["procedure_id"], "attempt_id": attempt["id"], "step_ids": dumps(failed_steps),
            "description": f"Critical checkpoint missed. Re-study {titles} in guided mode, then retake the assessment.",
            "assigned_by": None, "status": "open", "created_at": now_iso()})


def signoff(db: DB, org_id: str, trainer: dict, attempt_id: str, data: dict) -> dict:
    if not can(trainer, "assessment.signoff"):
        raise forbidden("Only trainers or administrators can sign off competency evidence")
    a = db.one("SELECT * FROM assessment_attempts WHERE id = ? AND org_id = ?", (attempt_id, org_id))
    if not a:
        raise not_found("Assessment attempt")
    if a["status"] != "submitted":
        raise conflict("Attempt not yet submitted")
    decision = data.get("decision")
    if decision not in SIGNOFF_TO_STATUS:
        raise bad_request("decision must be one of approve, reject, remediate, reassess")
    if decision == "approve" and a["outcome"] != "passed":
        raise conflict("Only a passed assessment can be approved as competency evidence")
    if a["signoff_status"] in ("approved", "rejected"):
        raise conflict(f"This attempt was already {a['signoff_status']}")
    if a["user_id"] == trainer["id"]:
        raise forbidden("You cannot sign off your own assessment")
    feedback = (data.get("feedback") or "").strip()[:2000]
    if decision != "approve" and not feedback:
        raise bad_request("Feedback is required when not approving")
    v = common.version(db, org_id, a["version_id"])
    now = now_iso()
    status = SIGNOFF_TO_STATUS[decision]
    learner = common.user_in_org(db, org_id, a["user_id"])
    with db.tx():
        db.insert("signoffs", {"id": new_id("sgn"), "org_id": org_id, "attempt_id": attempt_id, "trainer_id": trainer["id"],
                               "decision": decision, "feedback": feedback or None, "created_at": now})
        db.update("assessment_attempts", attempt_id, {"signoff_status": SIGNOFF_TO_ATTEMPT[decision]})
        for sid in _skill_ids(db, org_id, v["content"].get("skills", [])):
            fields = {"status": status, "feedback": feedback or None, "latest_attempt_id": attempt_id, "score": a["score"]}
            if decision == "approve":
                fields.update({"validated_by": trainer["id"], "validated_at": now})
            _upsert(db, org_id, a["user_id"], sid, **fields)
        if decision == "remediate":
            rem = data.get("remediation") or {}
            step_ids = [s for s in (rem.get("step_ids") or []) if any(st["step_id"] == s for st in v["content"]["steps"])]
            db.insert("remediation_tasks", {
                "id": new_id("rem"), "org_id": org_id, "user_id": a["user_id"],
                "skill_id": (_skill_ids(db, org_id, v["content"].get("skills", [])) or [None])[0],
                "procedure_id": a["procedure_id"], "attempt_id": attempt_id, "step_ids": dumps(step_ids),
                "description": (rem.get("description") or feedback)[:1000], "assigned_by": trainer["id"],
                "status": "open", "due_date": rem.get("due_date") or None, "created_at": now})
        p = common.procedure(db, org_id, a["procedure_id"])
        audit.record(db, org_id, trainer["id"], f"competency.{decision}", "attempt", attempt_id,
                     f"{trainer['name']} {VERBS[decision]} {learner['name']} on {p['code']}", {"feedback": feedback})
    return {"decision": decision, "competency_status": status}


def signoff_queue(db: DB, org_id: str) -> list[dict]:
    return db.all("""SELECT a.id, a.score, a.outcome, a.submitted_at, a.attempt_no, a.knowledge_accuracy, a.critical_passed,
                            a.critical_total, u.name AS learner_name, u.name_ja AS learner_name_ja, u.id AS learner_id,
                            p.code, p.title, p.id AS procedure_id
                     FROM assessment_attempts a JOIN users u ON u.id = a.user_id JOIN procedures p ON p.id = a.procedure_id
                     WHERE a.org_id = ? AND a.signoff_status = 'pending' ORDER BY a.submitted_at""", (org_id,))


def recent_attempts(db: DB, org_id: str, limit: int = 20) -> list[dict]:
    return db.all("""SELECT a.id, a.score, a.outcome, a.signoff_status, a.submitted_at, a.attempt_no, u.name AS learner_name,
                            u.id AS learner_id, p.code, p.title
                     FROM assessment_attempts a JOIN users u ON u.id = a.user_id JOIN procedures p ON p.id = a.procedure_id
                     WHERE a.org_id = ? AND a.status = 'submitted' ORDER BY a.submitted_at DESC LIMIT ?""", (org_id, limit))


def matrix(db: DB, org_id: str, viewer: dict) -> dict:
    skills = common.skills(db, org_id)
    if can(viewer, "competency.view_all"):
        people = db.all("SELECT id, name, name_ja, role, title, department FROM users WHERE org_id = ? AND active = 1 "
                        "AND role IN ('trainee','trainer','expert') ORDER BY CASE role WHEN 'expert' THEN 0 WHEN 'trainer' THEN 1 ELSE 2 END, name",
                        (org_id,))
    else:
        people = [db.one("SELECT id, name, name_ja, role, title, department FROM users WHERE id = ?", (viewer["id"],))]
    ids = [p["id"] for p in people]
    marks = ",".join("?" * len(ids)) or "NULL"
    records = db.all(f"SELECT c.*, v.name AS validated_by_name FROM competency_records c LEFT JOIN users v ON v.id = c.validated_by "
                     f"WHERE c.org_id = ? AND c.user_id IN ({marks})", (org_id, *ids))
    holders = db.all(f"SELECT user_id, skill_id, proficiency FROM expert_skills WHERE user_id IN ({marks})", ids)
    cells: dict[str, dict] = {}
    for h in holders:
        cells[f"{h['user_id']}:{h['skill_id']}"] = {"status": "holder" if h["proficiency"] >= 4 else "practitioner",
                                                    "proficiency": h["proficiency"]}
    for r in records:
        key = f"{r['user_id']}:{r['skill_id']}"
        base = cells.get(key, {})
        cells[key] = {**base, "status": r["status"], "score": r["score"], "attempt_id": r["latest_attempt_id"],
                      "validated_by": r["validated_by_name"], "validated_at": r["validated_at"], "feedback": r["feedback"]}
    summary = {}
    for r in records:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    return {"skills": skills, "people": people, "cells": cells, "summary": summary, "rules": SCORING_RULES,
            "queue": signoff_queue(db, org_id) if can(viewer, "assessment.signoff") else [],
            "recent": recent_attempts(db, org_id) if can(viewer, "competency.view_all") else
            [a for a in recent_attempts(db, org_id, 100) if a["learner_id"] == viewer["id"]][:20]}


def remediation_for(db: DB, org_id: str, user_id: str) -> list[dict]:
    rows = db.all("""SELECT r.*, p.code, p.title, u.name AS assigned_by_name FROM remediation_tasks r
                     LEFT JOIN procedures p ON p.id = r.procedure_id LEFT JOIN users u ON u.id = r.assigned_by
                     WHERE r.org_id = ? AND r.user_id = ? ORDER BY r.status, r.created_at DESC""", (org_id, user_id))
    for r in rows:
        r["step_ids"] = loads(r["step_ids"], [])
    return rows


def complete_remediation(db: DB, org_id: str, user: dict, task_id: str) -> dict:
    t = db.one("SELECT * FROM remediation_tasks WHERE id = ? AND org_id = ?", (task_id, org_id))
    if not t:
        raise not_found("Remediation task")
    if t["user_id"] != user["id"] and not can(user, "assessment.signoff"):
        raise forbidden()
    db.update("remediation_tasks", task_id, {"status": "done", "completed_at": now_iso()})
    audit.record(db, org_id, user["id"], "remediation.done", "remediation", task_id, f"Completed remediation: {t['description'][:80]}")
    return {"status": "done"}


def person_profile(db: DB, org_id: str, viewer: dict, user_id: str) -> dict:
    if user_id != viewer["id"] and not can(viewer, "competency.view_all"):
        raise forbidden()
    u = common.user_in_org(db, org_id, user_id)
    if not can(viewer, "risk.view"):
        u.pop("retirement_date", None)
    comps = db.all("SELECT c.*, s.code, s.name, s.name_ja FROM competency_records c JOIN skills s ON s.id = c.skill_id "
                   "WHERE c.user_id = ? ORDER BY s.code", (user_id,))
    attempts = db.all("SELECT a.id, a.attempt_no, a.score, a.outcome, a.signoff_status, a.submitted_at, p.code, p.title "
                      "FROM assessment_attempts a JOIN procedures p ON p.id = a.procedure_id "
                      "WHERE a.user_id = ? AND a.status = 'submitted' ORDER BY a.submitted_at", (user_id,))
    held = db.all("SELECT s.code, s.name, s.name_ja, e.proficiency FROM expert_skills e JOIN skills s ON s.id = e.skill_id "
                  "WHERE e.user_id = ? ORDER BY e.proficiency DESC", (user_id,))
    return {"user": u, "competencies": comps, "attempts": attempts, "held_skills": held,
            "remediation": remediation_for(db, org_id, user_id)}
