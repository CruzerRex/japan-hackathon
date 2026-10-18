"""People, skills, organisation settings, audit log and data portability."""
from __future__ import annotations

import csv
import io
import json
from datetime import date

from .. import audit
from ..auth import can, permissions_for
from ..db import DB, loads, now_iso
from ..web import bad_request, forbidden
from . import common


def people(db: DB, org_id: str, viewer: dict) -> list[dict]:
    rows = db.all("SELECT id, name, name_ja, email, role, title, department, locale, languages, years_experience, bio, "
                  "retirement_date, retirement_entered_at, active FROM users WHERE org_id = ? ORDER BY role, name", (org_id,))
    show_dates = can(viewer, "risk.view")
    for r in rows:
        if not show_dates:
            r.pop("retirement_date", None)
            r.pop("retirement_entered_at", None)
        r["skills"] = db.all("SELECT s.id, s.code, s.name, e.proficiency FROM expert_skills e JOIN skills s ON s.id = e.skill_id "
                             "WHERE e.user_id = ? ORDER BY e.proficiency DESC", (r["id"],))
        if not can(viewer, "people.manage"):
            r.pop("email", None)
    return rows


def set_retirement(db: DB, org_id: str, admin: dict, user_id: str, value: str | None) -> dict:
    if not can(admin, "retirement.edit"):
        raise forbidden("Only administrators may record planned retirement dates")
    u = common.user_in_org(db, org_id, user_id)
    if value:
        try:
            date.fromisoformat(value)
        except ValueError:
            raise bad_request("Date must be YYYY-MM-DD")
    db.update("users", user_id, {"retirement_date": value or None, "retirement_entered_by": admin["id"] if value else None,
                                 "retirement_entered_at": now_iso() if value else None})
    audit.record(db, org_id, admin["id"], "people.retirement", "user", user_id,
                 f"{'Recorded' if value else 'Cleared'} planned retirement date for {u['name']}")
    return {"retirement_date": value or None}


def set_skill(db: DB, org_id: str, admin: dict, user_id: str, skill_id: str, proficiency: int | None) -> dict:
    if not can(admin, "people.manage"):
        raise forbidden()
    common.user_in_org(db, org_id, user_id)
    if not db.one("SELECT 1 FROM skills WHERE id = ? AND org_id = ?", (skill_id, org_id)):
        raise bad_request("Unknown skill")
    if proficiency is None:
        db.execute("DELETE FROM expert_skills WHERE user_id = ? AND skill_id = ?", (user_id, skill_id))
    else:
        if not 1 <= int(proficiency) <= 5:
            raise bad_request("Proficiency must be 1–5")
        db.execute("INSERT INTO expert_skills (user_id, skill_id, proficiency) VALUES (?, ?, ?) "
                   "ON CONFLICT(user_id, skill_id) DO UPDATE SET proficiency = excluded.proficiency",
                   (user_id, skill_id, int(proficiency)))
    audit.record(db, org_id, admin["id"], "people.skill", "user", user_id, "Updated skill holder record")
    return {"ok": True}


def org_settings(db: DB, org_id: str, user: dict, registry) -> dict:
    from ..domain.risk import RISK_RULES
    from ..domain.scoring import SCORING_RULES
    from ..auth import PERMISSIONS
    org = db.one("SELECT * FROM organizations WHERE id = ?", (org_id,))
    counts = {t: db.scalar(f"SELECT COUNT(*) FROM {t} WHERE org_id = ?", (org_id,))
              for t in ("users", "skills", "procedures", "procedure_versions", "capture_sessions", "files",
                        "assessment_attempts", "competency_records", "audit_events")}
    storage = db.scalar("SELECT COALESCE(SUM(size_bytes), 0) FROM files WHERE org_id = ?", (org_id,))
    return {"org": org, "providers": registry.statuses(), "scoring_rules": SCORING_RULES, "risk_rules": RISK_RULES,
            "roles": {r: permissions_for(r) for r in ("admin", "expert", "trainer", "trainee")},
            "permissions": {k: sorted(v) for k, v in PERMISSIONS.items()},
            "counts": counts, "storage_bytes": storage, "my_permissions": permissions_for(user["role"])}


def audit_log(db: DB, org_id: str, user: dict, limit: int = 200) -> list[dict]:
    if not can(user, "audit.view"):
        raise forbidden()
    rows = audit.recent(db, org_id, limit)
    for r in rows:
        r["detail"] = loads(r.pop("detail_json"), {})
    return rows


def export_org(db: DB, org_id: str, user: dict) -> str:
    """Full structured export (data portability): every procedure version with
    evidence, skills, holders, competency and training records, review
    history and audit trail. Credentials and session data are excluded."""
    if not can(user, "org.export"):
        raise forbidden()
    org = db.one("SELECT * FROM organizations WHERE id = ?", (org_id,))
    versions = db.all("SELECT * FROM procedure_versions WHERE org_id = ? ORDER BY procedure_id, version_no", (org_id,))
    for v in versions:
        v["content"] = loads(v.pop("content_json"), {})
        v["extraction_meta"] = loads(v.pop("extraction_meta_json"), {})
    attempts = db.all("SELECT id, user_id, procedure_id, version_id, attempt_no, submitted_at, duration_s, score, knowledge_accuracy, "
                      "critical_passed, critical_total, outcome, signoff_status, result_json FROM assessment_attempts "
                      "WHERE org_id = ? AND status = 'submitted'", (org_id,))
    for a in attempts:
        a["result"] = loads(a.pop("result_json"), {})
    doc = {
        "format": "kizuna-forge/org-export@1", "exported_at": now_iso(), "organization": org,
        "people": db.all("SELECT id, name, name_ja, role, title, department, languages, years_experience, retirement_date "
                         "FROM users WHERE org_id = ?", (org_id,)),
        "skills": common.skills(db, org_id),
        "skill_holders": db.all("SELECT e.* FROM expert_skills e JOIN skills s ON s.id = e.skill_id WHERE s.org_id = ?", (org_id,)),
        "procedures": db.all("SELECT * FROM procedures WHERE org_id = ?", (org_id,)),
        "procedure_versions": versions,
        "review_events": db.all("SELECT * FROM review_events WHERE org_id = ?", (org_id,)),
        "captures": db.all("SELECT id, expert_id, title, task_category, machine, transcript, expert_notes, tips, mistakes, "
                           "troubleshooting, safety_notes, consent_given, consent_scope, consent_at, created_at "
                           "FROM capture_sessions WHERE org_id = ?", (org_id,)),
        "capture_markers": db.all("SELECT m.* FROM capture_markers m JOIN capture_sessions c ON c.id = m.capture_id WHERE c.org_id = ?", (org_id,)),
        "files": db.all("SELECT id, capture_id, kind, original_name, mime, size_bytes, sha256, created_at FROM files WHERE org_id = ?", (org_id,)),
        "assessment_attempts": attempts,
        "competency_records": db.all("SELECT * FROM competency_records WHERE org_id = ?", (org_id,)),
        "signoffs": db.all("SELECT * FROM signoffs WHERE org_id = ?", (org_id,)),
        "remediation_tasks": db.all("SELECT * FROM remediation_tasks WHERE org_id = ?", (org_id,)),
        "translations": db.all("SELECT id, version_id, locale, status, content_json, reviewed_by, reviewed_at FROM translations WHERE org_id = ?", (org_id,)),
        "mentorship_requests": db.all("SELECT * FROM mentorship_requests WHERE org_id = ?", (org_id,)),
        "mentoring_sessions": db.all("SELECT * FROM mentoring_sessions WHERE org_id = ?", (org_id,)),
        "audit_events": db.all("SELECT * FROM audit_events WHERE org_id = ? ORDER BY id", (org_id,)),
    }
    audit.record(db, org_id, user["id"], "org.export", "organization", org_id, "Exported full organisation knowledge archive")
    return json.dumps(doc, ensure_ascii=False, indent=1, default=str)


def training_records_csv(db: DB, org_id: str, user: dict) -> str:
    if not can(user, "competency.view_all"):
        raise forbidden()
    rows = db.all("""SELECT u.name AS learner, p.code AS procedure, v.version_no, a.attempt_no, a.submitted_at, a.duration_s,
                            a.knowledge_accuracy, a.critical_passed, a.critical_total, a.score, a.outcome, a.signoff_status
                     FROM assessment_attempts a JOIN users u ON u.id = a.user_id JOIN procedures p ON p.id = a.procedure_id
                     JOIN procedure_versions v ON v.id = a.version_id WHERE a.org_id = ? AND a.status = 'submitted'
                     ORDER BY a.submitted_at""", (org_id,))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["learner", "procedure", "version", "attempt", "submitted_at", "duration_s", "accuracy_pct",
                "critical_passed", "critical_total", "score", "outcome", "signoff", "assessment_type"])
    for r in rows:
        w.writerow([r["learner"], r["procedure"], r["version_no"], r["attempt_no"], r["submitted_at"], r["duration_s"],
                    r["knowledge_accuracy"], r["critical_passed"], r["critical_total"], r["score"], r["outcome"],
                    r["signoff_status"], "simulated knowledge assessment (not hands-on certification)"])
    return buf.getvalue()
