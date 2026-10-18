"""Organisation-level insights: knowledge-risk radar, dashboard metrics and
global search. All figures are computed from persisted application data."""
from __future__ import annotations

from datetime import date

from .. import audit
from ..auth import can
from ..db import DB, loads
from ..domain.risk import RISK_RULES, assess_skill
from ..domain.workflow import EDITABLE, PUBLISHED
from . import common


def risk_radar(db: DB, org_id: str, viewer: dict, today: date | None = None) -> dict:
    today = today or date.today()
    skills = common.skills(db, org_id)
    holders_rows = db.all("""SELECT e.skill_id, u.id, u.name, u.name_ja, e.proficiency, u.retirement_date
                             FROM expert_skills e JOIN users u ON u.id = e.user_id
                             WHERE u.org_id = ? AND u.active = 1 AND e.proficiency >= ?""",
                          (org_id, RISK_RULES["holder_min_proficiency"]))
    procs = common.procedure_skill_codes(db, org_id)
    comps = db.all("""SELECT c.skill_id, c.status, u.name, u.id FROM competency_records c JOIN users u ON u.id = c.user_id
                      WHERE c.org_id = ?""", (org_id,))
    show_dates = can(viewer, "risk.view")
    results = []
    for s in skills:
        holders = [{"id": h["id"], "name": h["name"], "name_ja": h["name_ja"], "proficiency": h["proficiency"],
                    "retirement_date": h["retirement_date"]} for h in holders_rows if h["skill_id"] == s["id"]]
        holder_ids = {h["id"] for h in holders}
        covering = []
        for p in procs.values():
            if s["code"] in p["published"]:
                covering.append({"id": p["id"], "code": p["code"], "title": p["title"], "status": PUBLISHED})
            elif s["code"] in p["latest"] and p["latest_status"] not in ("REJECTED",):
                covering.append({"id": p["id"], "code": p["code"], "title": p["title"], "status": p["latest_status"]})
        status = "published" if any(c["status"] == PUBLISHED for c in covering) else ("in_progress" if covering else "none")
        covering.sort(key=lambda c: c["status"] != PUBLISHED)
        validated = [c["name"] for c in comps if c["skill_id"] == s["id"] and c["status"] == "validated" and c["id"] not in holder_ids]
        in_prog = [c["name"] for c in comps if c["skill_id"] == s["id"] and c["status"] != "validated" and c["id"] not in holder_ids]
        r = assess_skill(s, holders, {"status": status, "procedures": covering},
                         {"validated": validated, "in_progress": in_prog}, today)
        if not show_dates:
            for h in r["holders"]:
                h.pop("retirement_date", None)
        results.append(r)
    results.sort(key=lambda r: -r["score"])
    bands = {b: sum(1 for r in results if r["band"] == b) for b in ("critical", "high", "moderate", "low")}
    return {"skills": results, "bands": bands, "rules": RISK_RULES, "as_of": today.isoformat(),
            "retirement_dates_visible": show_dates}


def dashboard(db: DB, org_id: str, user: dict) -> dict:
    org = db.one("SELECT * FROM organizations WHERE id = ?", (org_id,))
    procs = db.all("SELECT p.id, p.code, p.title, p.published_version_id, v.status, v.content_json FROM procedures p "
                   "LEFT JOIN procedure_versions v ON v.id = p.latest_version_id WHERE p.org_id = ?", (org_id,))
    published = sum(1 for p in procs if p["published_version_id"])
    records = {"steps": 0, "tips": 0, "mistakes": 0, "failure_modes": 0, "safety": 0}
    verified_steps = total_steps = 0
    for p in procs:
        if p["status"] == "REJECTED":
            continue
        c = loads(p["content_json"], {}) or {}
        for k in records:
            records[k] += len(c.get(k, []))
        total_steps += len(c.get("steps", []))
        verified_steps += sum(1 for s in c.get("steps", []) if s.get("evidence_verified"))
    captures = db.scalar("SELECT COUNT(*) FROM capture_sessions WHERE org_id = ? AND status != 'archived'", (org_id,))
    modules_completed = db.scalar("SELECT COUNT(*) FROM training_progress WHERE org_id = ? AND guided_completed_at IS NOT NULL", (org_id,))
    attempts = db.scalar("SELECT COUNT(*) FROM assessment_attempts WHERE org_id = ? AND status = 'submitted'", (org_id,))
    validated_workers = db.scalar("SELECT COUNT(DISTINCT user_id) FROM competency_records WHERE org_id = ? AND status = 'validated'", (org_id,))
    review_versions = db.all(f"""SELECT v.id, v.status, v.version_no, v.updated_at, p.id AS procedure_id, p.code, p.title
                                FROM procedure_versions v JOIN procedures p ON p.id = v.procedure_id
                                WHERE v.org_id = ? AND v.status IN ({','.join('?' * len(EDITABLE | {'APPROVED'}))})
                                ORDER BY v.updated_at DESC""", (org_id, *sorted(EDITABLE | {"APPROVED"})))
    pending_signoff = db.scalar("SELECT COUNT(*) FROM assessment_attempts WHERE org_id = ? AND signoff_status = 'pending'", (org_id,))
    radar = risk_radar(db, org_id, user)
    at_risk = [r for r in radar["skills"] if r["band"] in ("critical", "high")]

    # Coverage by skill category
    coverage: dict[str, dict] = {}
    for r in radar["skills"]:
        cat = coverage.setdefault(r["category"] or "Other", {"category": r["category"] or "Other", "published": 0,
                                                             "in_progress": 0, "none": 0})
        cat[r["documentation"]["status"]] += 1
    # Competency progress by skill
    comp_rows = db.all("""SELECT s.code, s.name, c.status, COUNT(*) AS n FROM competency_records c JOIN skills s ON s.id = c.skill_id
                          WHERE c.org_id = ? GROUP BY s.code, s.name, c.status""", (org_id,))
    progress: dict[str, dict] = {}
    for r in comp_rows:
        progress.setdefault(r["code"], {"code": r["code"], "name": r["name"]})[r["status"]] = r["n"]
    my = None
    if user["role"] == "trainee":
        my = {
            "competencies": db.all("SELECT c.status, c.score, s.code, s.name FROM competency_records c JOIN skills s ON s.id = c.skill_id "
                                   "WHERE c.user_id = ?", (user["id"],)),
            "remediation_open": db.scalar("SELECT COUNT(*) FROM remediation_tasks WHERE user_id = ? AND status = 'open'", (user["id"],)),
        }
    feed = audit.recent(db, org_id, 14)
    if user["role"] == "trainee":
        feed = [e for e in feed if e["entity_type"] in ("attempt", "procedure") and (e["action"] in ("procedure.publish",) or e["actor_id"] == user["id"])]
    return {
        "org": org,
        "metrics": {
            "procedures_published": published, "procedures_total": len(procs),
            "knowledge_records": sum(records.values()), "records_breakdown": records, "captures": captures,
            "evidence_verified_pct": round(verified_steps / total_steps * 100) if total_steps else 0,
            "modules_completed": modules_completed, "assessments": attempts,
            "validated_workers": validated_workers, "skills_at_risk": len(at_risk), "skills_total": len(radar["skills"]),
            "review_queue": len(review_versions), "pending_signoff": pending_signoff,
        },
        "at_risk": at_risk[:6] if can(user, "risk.view") else [],
        "risk_bands": radar["bands"],
        "coverage": sorted(coverage.values(), key=lambda c: c["category"]),
        "competency_progress": list(progress.values()),
        "review_queue": review_versions[:8] if can(user, "procedure.read_unpublished") else [],
        "activity": feed,
        "mine": my,
    }


def notifications(db: DB, org_id: str, user: dict) -> list[dict]:
    out = []
    if can(user, "procedure.approve"):
        for v in db.all("SELECT v.id, v.version_no, v.status, p.id AS pid, p.code, p.title FROM procedure_versions v "
                        "JOIN procedures p ON p.id = v.procedure_id WHERE v.org_id = ? AND v.status IN ('EXPERT_REVIEW','AI_PROCESSED')",
                        (org_id,)):
            out.append({"kind": "review", "title": f"{v['code']} v{v['version_no']} awaits review",
                        "detail": v["title"], "status": v["status"], "route": f"#/procedures/{v['pid']}"})
    if can(user, "procedure.publish"):
        for v in db.all("SELECT v.version_no, p.id AS pid, p.code, p.title FROM procedure_versions v JOIN procedures p ON p.id = v.procedure_id "
                        "WHERE v.org_id = ? AND v.status = 'APPROVED'", (org_id,)):
            out.append({"kind": "publish", "title": f"{v['code']} v{v['version_no']} approved — ready to publish",
                        "detail": v["title"], "route": f"#/procedures/{v['pid']}"})
    if can(user, "assessment.signoff"):
        for a in db.all("SELECT a.id, u.name, p.code FROM assessment_attempts a JOIN users u ON u.id = a.user_id "
                        "JOIN procedures p ON p.id = a.procedure_id WHERE a.org_id = ? AND a.signoff_status = 'pending'", (org_id,)):
            out.append({"kind": "signoff", "title": f"Sign-off needed: {a['name']} · {a['code']}", "detail": "Passed simulated assessment",
                        "route": f"#/attempts/{a['id']}"})
    for r in db.all("SELECT r.id, u.name, s.name AS skill FROM mentorship_requests r JOIN users u ON u.id = r.mentee_id "
                    "LEFT JOIN skills s ON s.id = r.skill_id WHERE r.mentor_id = ? AND r.status = 'requested'", (user["id"],)):
        out.append({"kind": "mentoring", "title": f"Mentoring request from {r['name']}", "detail": r["skill"] or "",
                    "route": "#/mentorship"})
    for t in db.all("SELECT r.id, r.description, p.id AS pid FROM remediation_tasks r LEFT JOIN procedures p ON p.id = r.procedure_id "
                    "WHERE r.user_id = ? AND r.status = 'open'", (user["id"],)):
        out.append({"kind": "remediation", "title": "Remediation assigned", "detail": t["description"][:90],
                    "route": f"#/academy/{t['pid']}" if t["pid"] else "#/academy"})
    return out


def search(db: DB, org_id: str, user: dict, q: str) -> list[dict]:
    q = (q or "").strip()
    if len(q) < 2:
        return []
    like = f"%{q.lower()}%"
    out = []
    unpublished_ok = can(user, "procedure.read_unpublished")
    for p in db.all("SELECT p.id, p.code, p.title, p.published_version_id, p.latest_version_id FROM procedures p WHERE p.org_id = ?", (org_id,)):
        if not unpublished_ok and not p["published_version_id"]:
            continue
        vid = p["latest_version_id"] if unpublished_ok else p["published_version_id"]
        c = loads(db.scalar("SELECT content_json FROM procedure_versions WHERE id = ?", (vid,)), {}) or {}
        if q.lower() in (p["title"] + " " + p["code"]).lower():
            out.append({"type": "procedure", "label": f"{p['code']} · {p['title']}", "route": f"#/procedures/{p['id']}"})
        for s in c.get("steps", []):
            if q.lower() in (s["title"] + " " + s["instruction"]).lower():
                out.append({"type": "step", "label": f"{s['title']}", "sub": p["code"],
                            "route": f"#/procedures/{p['id']}?step={s['step_id']}"})
    for s in db.all("SELECT code, name, name_ja FROM skills WHERE org_id = ? AND (lower(name) LIKE ? OR lower(code) LIKE ? OR name_ja LIKE ?)",
                    (org_id, like, like, like)):
        out.append({"type": "skill", "label": f"{s['name']}", "sub": s["code"], "route": f"#/graph?focus=skill:{s['code']}"})
    for u in db.all("SELECT id, name, name_ja, role, title FROM users WHERE org_id = ? AND active = 1 AND (lower(name) LIKE ? OR name_ja LIKE ?)",
                    (org_id, like, like)):
        out.append({"type": "person", "label": u["name"], "sub": u["title"] or u["role"], "route": f"#/people/{u['id']}"})
    return out[:25]
