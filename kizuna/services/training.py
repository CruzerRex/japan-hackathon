"""Training Academy: published modules, guided/challenge practice and the final
(simulated) assessment. Answer keys never leave the server before grading."""
from __future__ import annotations

import random

from .. import audit
from ..auth import can
from ..db import DB, dumps, loads, new_id, now_iso
from ..domain.scoring import SCORING_RULES, assessment_items, score_attempt
from ..web import bad_request, conflict, forbidden, not_found
from . import common, competency


def _public_content(c: dict) -> dict:
    """Content safe to send to a learner: no answer keys."""
    out = {k: v for k, v in c.items() if k not in ("questions", "scenarios", "open_questions")}
    out["questions"] = [{k: q[k] for k in ("id", "prompt", "options", "step_id", "critical", "skill")} for q in c.get("questions", [])]
    out["scenarios"] = [{"id": s["id"], "situation": s["situation"], "options": [o["text"] for o in s["options"]],
                         "step_id": s.get("step_id"), "critical": s.get("critical"), "skill": s.get("skill")}
                        for s in c.get("scenarios", [])]
    return out


def _progress(db: DB, org_id: str, user_id: str, version_id: str) -> dict | None:
    p = db.one("SELECT * FROM training_progress WHERE user_id = ? AND version_id = ? AND org_id = ?",
               (user_id, version_id, org_id))
    if p:
        p["completed_steps"] = loads(p["completed_steps"], [])
        p["step_checks"] = loads(p["step_checks"], {})
        p["challenge_results"] = loads(p["challenge_results"], {})
    return p


def list_modules(db: DB, org_id: str, user: dict) -> list[dict]:
    rows = db.all("""SELECT p.id, p.code, p.title, p.published_version_id, v.version_no, v.content_json, v.published_at,
                            u.name AS owner_name, u.name_ja AS owner_name_ja
                     FROM procedures p JOIN procedure_versions v ON v.id = p.published_version_id
                     LEFT JOIN users u ON u.id = p.owner_expert_id
                     WHERE p.org_id = ? ORDER BY p.code""", (org_id,))
    skills = common.skills_by_code(db, org_id)
    out = []
    for r in rows:
        c = loads(r["content_json"], {})
        prog = _progress(db, org_id, user["id"], r["published_version_id"])
        attempts = db.all("SELECT id, score, outcome, signoff_status, submitted_at FROM assessment_attempts "
                          "WHERE user_id = ? AND procedure_id = ? AND status = 'submitted' ORDER BY submitted_at DESC",
                          (user["id"], r["id"]))
        n_steps = len(c.get("steps", []))
        out.append({
            "procedure_id": r["id"], "code": r["code"], "title": r["title"], "version_no": r["version_no"],
            "version_id": r["published_version_id"], "published_at": r["published_at"], "owner_name": r["owner_name"],
            "owner_name_ja": r["owner_name_ja"], "machine": c.get("machine"), "purpose": c.get("purpose"),
            "skills": [{"code": s, "name": skills[s]["name"], "name_ja": skills[s]["name_ja"]} for s in c.get("skills", []) if s in skills],
            "step_count": n_steps, "critical_steps": sum(1 for s in c.get("steps", []) if s.get("critical_checkpoint")),
            "item_count": len(c.get("questions", [])) + len(c.get("scenarios", [])),
            "est_minutes": 5 + n_steps * 3,
            "progress": {"completed_steps": len(prog["completed_steps"]) if prog else 0,
                         "guided_completed": bool(prog and prog["guided_completed_at"]),
                         "challenge_done": len(prog["challenge_results"]) if prog else 0},
            "best_score": max((a["score"] for a in attempts), default=None),
            "last_attempt": attempts[0] if attempts else None, "attempt_count": len(attempts),
        })
    return out


def get_module(db: DB, org_id: str, user: dict, procedure_id: str) -> dict:
    v = common.published_version(db, org_id, procedure_id)
    p = common.procedure(db, org_id, procedure_id)
    owner = db.one("SELECT id, name, name_ja, title, years_experience FROM users WHERE id = ?", (p["owner_expert_id"],))
    prog = _progress(db, org_id, user["id"], v["id"])
    attempts = db.all("SELECT id, attempt_no, score, outcome, signoff_status, submitted_at, knowledge_accuracy "
                      "FROM assessment_attempts WHERE user_id = ? AND procedure_id = ? AND status = 'submitted' ORDER BY attempt_no DESC",
                      (user["id"], procedure_id))
    video = None
    if p["capture_id"]:
        video = db.one("SELECT id, mime FROM files WHERE capture_id = ? AND kind = 'video' ORDER BY created_at DESC LIMIT 1",
                       (p["capture_id"],))
    skills = common.skills_by_code(db, org_id)
    tr = db.one("SELECT content_json, status FROM translations WHERE version_id = ? AND locale = 'ja'", (v["id"],))
    return {
        "procedure": {"id": p["id"], "code": p["code"], "title": p["title"]},
        "version": {"id": v["id"], "version_no": v["version_no"], "status": v["status"], "published_at": v["published_at"],
                    "approved_at": v["approved_at"], "approved_by_name": common.names(db, org_id).get(v["approved_by"])},
        "content": _public_content(v["content"]), "owner": owner, "progress": prog, "attempts": attempts,
        "video": video, "rules": SCORING_RULES,
        "skills": [skills[s] for s in v["content"].get("skills", []) if s in skills],
        "translation_ja": {"status": tr["status"], "content": loads(tr["content_json"], {})} if tr else None,
    }


def update_progress(db: DB, org_id: str, user: dict, procedure_id: str, data: dict) -> dict:
    v = common.published_version(db, org_id, procedure_id)
    valid = {s["step_id"] for s in v["content"]["steps"]}
    steps = [s for s in (data.get("completed_steps") or []) if s in valid]
    now = now_iso()
    prog = _progress(db, org_id, user["id"], v["id"])
    guided_done = data.get("guided_completed") and set(steps) >= valid
    if prog:
        changes = {"completed_steps": dumps(sorted(set(prog["completed_steps"]) | set(steps))), "updated_at": now}
        if guided_done and not prog["guided_completed_at"]:
            changes["guided_completed_at"] = now
        db.update("training_progress", prog["id"], changes)
    else:
        db.insert("training_progress", {"id": new_id("tp"), "org_id": org_id, "user_id": user["id"], "procedure_id": procedure_id,
                                        "version_id": v["id"], "completed_steps": dumps(sorted(set(steps))),
                                        "guided_completed_at": now if guided_done else None, "started_at": now, "updated_at": now})
        competency.mark_in_training(db, org_id, user["id"], v["content"].get("skills", []))
    if guided_done and not (prog and prog["guided_completed_at"]):
        audit.record(db, org_id, user["id"], "training.guided_completed", "procedure", procedure_id,
                     f"{user['name']} completed guided walkthrough of {common.procedure(db, org_id, procedure_id)['code']}")
    return _progress(db, org_id, user["id"], v["id"])


def practice_check(db: DB, org_id: str, user: dict, procedure_id: str, item_id: str, choice) -> dict:
    """Immediate feedback for guided knowledge checks and challenge scenarios."""
    v = common.published_version(db, org_id, procedure_id)
    items = {i["id"]: i for i in assessment_items(v["content"])}
    it = items.get(item_id)
    if not it:
        raise not_found("Practice item")
    try:
        choice = int(choice)
    except (TypeError, ValueError):
        raise bad_request("choice must be an option index")
    if not 0 <= choice < len(it["options"]):
        raise bad_request("choice out of range")
    ok = choice == it["answer_index"]
    step = next((s for s in v["content"]["steps"] if s["step_id"] == it.get("step_id")), None)
    prog = _progress(db, org_id, user["id"], v["id"])
    now = now_iso()
    if not prog:
        update_progress(db, org_id, user, procedure_id, {"completed_steps": []})
        prog = _progress(db, org_id, user["id"], v["id"])
    key = "challenge_results" if it["kind"] == "scenario" else "step_checks"
    store = prog[key]
    store[item_id] = {"correct": ok, "at": now, "tries": store.get(item_id, {}).get("tries", 0) + 1}
    db.update("training_progress", prog["id"], {key: dumps(store), "updated_at": now})
    return {"correct": ok, "correct_index": it["answer_index"], "explanation": it["explanation"],
            "option_feedback": it.get("option_feedback", [])[choice] if it.get("option_feedback") else None,
            "step": {"step_id": step["step_id"], "title": step["title"], "source_timestamp": step.get("source_timestamp"),
                     "evidence_quote": step.get("evidence_quote")} if step else None}


def start_attempt(db: DB, org_id: str, user: dict, procedure_id: str) -> dict:
    v = common.published_version(db, org_id, procedure_id)
    items = assessment_items(v["content"])
    if not items:
        raise conflict("This module has no assessment items yet")
    existing = db.one("SELECT id FROM assessment_attempts WHERE user_id = ? AND procedure_id = ? AND status = 'in_progress'",
                      (user["id"], procedure_id))
    if existing:
        db.execute("DELETE FROM assessment_attempts WHERE id = ?", (existing["id"],))  # abandon unfinished attempt
    rng = random.Random()
    orders = {}
    for it in items:
        perm = list(range(len(it["options"])))
        rng.shuffle(perm)
        orders[it["id"]] = perm
    rng.shuffle(items)
    n = (db.scalar("SELECT MAX(attempt_no) FROM assessment_attempts WHERE user_id = ? AND procedure_id = ?",
                   (user["id"], procedure_id)) or 0) + 1
    aid = new_id("att")
    db.insert("assessment_attempts", {"id": aid, "org_id": org_id, "user_id": user["id"], "procedure_id": procedure_id,
                                      "version_id": v["id"], "attempt_no": n, "status": "in_progress", "started_at": now_iso(),
                                      "answers_json": dumps({"_orders": orders, "_sequence": [i["id"] for i in items]})})
    return {"attempt_id": aid, "attempt_no": n, "rules": SCORING_RULES,
            "items": [{"id": it["id"], "kind": it["kind"], "prompt": it["prompt"], "critical": it["critical"],
                       "options": [it["options"][j] for j in orders[it["id"]]]} for it in items]}


def _attempt(db: DB, org_id: str, attempt_id: str) -> dict:
    a = db.one("SELECT * FROM assessment_attempts WHERE id = ? AND org_id = ?", (attempt_id, org_id))
    if not a:
        raise not_found("Assessment attempt")
    return a


def hint(db: DB, org_id: str, user: dict, attempt_id: str, item_id: str) -> dict:
    a = _attempt(db, org_id, attempt_id)
    if a["user_id"] != user["id"] or a["status"] != "in_progress":
        raise forbidden("Hints are only available during your own active attempt")
    v = common.version(db, org_id, a["version_id"])
    it = next((i for i in assessment_items(v["content"]) if i["id"] == item_id), None)
    if not it:
        raise not_found("Item")
    step = next((s for s in v["content"]["steps"] if s["step_id"] == it.get("step_id")), None)
    used = loads(a["hints_used"], [])
    if item_id not in used:
        used.append(item_id)
        db.update("assessment_attempts", attempt_id, {"hints_used": dumps(used)})
    return {"hint": (f"Review step “{step['title']}”: {step['instruction']}" if step else
                     "Re-read the procedure's troubleshooting and checkpoint sections."),
            "penalty_points": SCORING_RULES["hint_penalty_points"], "hints_used": len(used)}


def submit_attempt(db: DB, org_id: str, user: dict, attempt_id: str, data: dict) -> dict:
    a = _attempt(db, org_id, attempt_id)
    if a["user_id"] != user["id"]:
        raise forbidden("You can only submit your own assessment")
    if a["status"] != "in_progress":
        raise conflict("This attempt has already been submitted")
    meta = loads(a["answers_json"], {})
    orders = meta.get("_orders", {})
    raw = data.get("answers") or {}
    if not isinstance(raw, dict):
        raise bad_request("answers must be an object of item_id -> option index")
    answers = {}
    for item_id, shown_idx in raw.items():
        perm = orders.get(item_id)
        try:
            shown_idx = int(shown_idx)
        except (TypeError, ValueError):
            continue
        if perm and 0 <= shown_idx < len(perm):
            answers[item_id] = perm[shown_idx]
    v = common.version(db, org_id, a["version_id"])
    hints = loads(a["hints_used"], [])
    skills = v["content"].get("skills", [])
    result = score_attempt(v["content"], answers, hints, default_skill=skills[0] if skills else None)
    try:
        duration = max(0, min(int(data.get("duration_s") or 0), 6 * 3600))
    except (TypeError, ValueError):
        duration = 0
    now = now_iso()
    with db.tx():
        db.update("assessment_attempts", attempt_id, {
            "status": "submitted", "submitted_at": now, "duration_s": duration,
            "answers_json": dumps({**meta, "answers": answers}), "result_json": dumps(result),
            "knowledge_accuracy": result["accuracy"], "critical_total": result["critical_total"],
            "critical_passed": result["critical_passed"], "score": result["score"], "outcome": result["outcome"],
            "signoff_status": "pending" if result["outcome"] == "passed" else "not_applicable"})
        competency.apply_attempt(db, org_id, user, a, v, result)
        p = common.procedure(db, org_id, a["procedure_id"])
        audit.record(db, org_id, user["id"], "assessment.submitted", "attempt", attempt_id,
                     f"{user['name']} scored {result['score']} on {p['code']} ({result['outcome'].replace('_', ' ')})",
                     {"procedure_id": p["id"], "score": result["score"], "outcome": result["outcome"]})
    return get_attempt(db, org_id, user, attempt_id)


def get_attempt(db: DB, org_id: str, user: dict, attempt_id: str) -> dict:
    a = _attempt(db, org_id, attempt_id)
    if a["user_id"] != user["id"] and not can(user, "competency.view_all"):
        raise forbidden("You can only view your own assessment results")
    if a["status"] != "submitted":
        raise conflict("Attempt not yet submitted")
    p = common.procedure(db, org_id, a["procedure_id"])
    v = common.version(db, org_id, a["version_id"])
    learner = db.one("SELECT id, name, name_ja, title FROM users WHERE id = ?", (a["user_id"],))
    history = db.all("SELECT id, attempt_no, score, outcome, knowledge_accuracy, critical_passed, critical_total, submitted_at "
                     "FROM assessment_attempts WHERE user_id = ? AND procedure_id = ? AND status = 'submitted' ORDER BY attempt_no",
                     (a["user_id"], a["procedure_id"]))
    signoffs = db.all("SELECT s.*, u.name AS trainer_name FROM signoffs s JOIN users u ON u.id = s.trainer_id "
                      "WHERE s.attempt_id = ? ORDER BY s.created_at DESC", (attempt_id,))
    remediation = db.all("SELECT * FROM remediation_tasks WHERE attempt_id = ? ORDER BY created_at DESC", (attempt_id,))
    steps = {s["step_id"]: s for s in v["content"]["steps"]}
    result = loads(a["result_json"], {})
    review = [{"step_id": sid, "title": steps[sid]["title"], "source_timestamp": steps[sid].get("source_timestamp")}
              for sid in result.get("review_steps", []) if sid in steps]
    a.pop("answers_json", None)
    return {"attempt": a, "result": result, "procedure": {"id": p["id"], "code": p["code"], "title": p["title"]},
            "version_no": v["version_no"], "learner": learner, "history": history, "signoffs": signoffs,
            "remediation": remediation, "review_steps": review, "rules": SCORING_RULES,
            "competency": db.all("SELECT c.status, c.score, s.code, s.name FROM competency_records c JOIN skills s ON s.id = c.skill_id "
                                 "WHERE c.user_id = ? AND s.code IN (" + ",".join("?" * len(v["content"].get("skills", []))) + ")",
                                 (a["user_id"], *v["content"].get("skills", []))) if v["content"].get("skills") else []}
