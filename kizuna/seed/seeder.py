"""Reproducible demo seeding.

The demo is built through the same service functions the API uses (capture,
extraction, review transitions, training attempts, sign-off, mentorship), so
every seeded record is internally consistent: attempts reference real
published versions, competency records reference real attempts, risk scores
derive from real holder/procedure/competency rows. Timestamps are then
back-dated so the activity feed reads like a few weeks of real use.

Demo password for every simulated account: see DEMO_PASSWORD (documented in
README). The persona switcher on the sign-in page only works for simulated
organisations and can be disabled with KIZUNA_DEMO_MODE=false.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import auth
from ..ai.registry import Registry
from ..db import DB, dumps, migrate, now_iso
from ..domain import workflow
from ..services import capture, competency, mentorship, procedures, training, translations
from . import content as C

DEMO_PASSWORD = "kizuna-demo-2026"


def T(days_ago: float, hour: int = 10, minute: int = 0) -> str:
    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    t = base - timedelta(days=days_ago) + timedelta(hours=hour - 9, minutes=minute)  # JST working hours ≈ UTC+9
    return t.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Clock:
    """Back-dates audit events written by services inside a `with clock.at(...)` block."""

    def __init__(self, db: DB):
        self.db = db

    def at(self, ts: str):
        db = self.db

        class _Ctx:
            def __enter__(self_inner):
                self_inner.start = db.scalar("SELECT COALESCE(MAX(id), 0) FROM audit_events")
                return ts

            def __exit__(self_inner, *exc):
                if exc[0] is None:
                    db.execute("UPDATE audit_events SET created_at = ? WHERE id > ?", (ts, self_inner.start))
                return False
        return _Ctx()


def _user(db: DB, uid: str) -> dict:
    u = db.one("SELECT * FROM users WHERE id = ?", (uid,))
    u.pop("password_hash", None)
    return u


def _transcript_from(content: dict, speaker: str) -> str:
    lines = {}
    for coll in ("steps", "tips", "mistakes", "failure_modes", "safety"):
        for it in content.get(coll, []):
            if it.get("source_type") == "transcript" and it.get("source_timestamp"):
                lines.setdefault(it["source_timestamp"], it["evidence_quote"])
    return "\n".join(f"[{ts}] {speaker}: {q}" for ts, q in sorted(lines.items()))


def _notes_from(content: dict) -> str:
    return "\n".join(it["evidence_quote"] for coll in ("tips", "mistakes", "failure_modes")
                     for it in content.get(coll, []) if it.get("source_type") == "expert_note")


def seed(db_path: Path, upload_dir: Path | None = None, fast_hash: bool = False, settings=None) -> dict:
    db_path = Path(db_path)
    for suffix in ("", "-wal", "-shm"):
        Path(str(db_path) + suffix).unlink(missing_ok=True)
    migrate(db_path)
    db = DB(db_path)
    clock = Clock(db)
    iterations = 1000 if fast_hash else auth.PBKDF2_ITERATIONS
    created = T(60)

    # -- organisations, people, skills ---------------------------------------------------------------
    for org in (C.ORG, C.OTHER_ORG):
        db.insert("organizations", {**org, "created_at": created})
    for org_id, users in (("org_minato", C.USERS), ("org_hokuto", C.OTHER_USERS)):
        for uid, email, name, name_ja, role, title, dept, langs, years, retire, bio in users:
            db.insert("users", {"id": uid, "org_id": org_id, "email": email, "name": name, "name_ja": name_ja, "role": role,
                                "title": title, "department": dept, "languages": langs, "years_experience": years, "bio": bio,
                                "locale": "en", "retirement_date": retire,
                                "retirement_entered_by": "usr_morita" if retire else None,
                                "retirement_entered_at": T(40) if retire else None,
                                "password_hash": auth.hash_password(DEMO_PASSWORD, iterations), "created_at": created})
    skill_ids = {}
    for code, name, name_ja, cat, crit, desc in C.SKILLS:
        sid = "skl_" + code.lower().replace("sk-", "").replace("-", "_")
        skill_ids[code] = sid
        db.insert("skills", {"id": sid, "org_id": "org_minato", "code": code, "name": name, "name_ja": name_ja,
                             "category": cat, "criticality": crit, "description": desc})
    db.insert("skills", {"id": "skl_hokuto_mould", "org_id": "org_hokuto", "code": "SK-MOULD", "name": "Green-sand moulding",
                         "name_ja": "生砂造型", "category": "Casting", "criticality": 4, "description": "Tenant isolation fixture"})
    for uid, code, prof in C.HOLDERS:
        db.insert("expert_skills", {"user_id": uid, "skill_id": skill_ids[code], "proficiency": prof})
    for i, (kind, name, name_ja, detail) in enumerate(C.ASSETS, 1):
        db.insert("assets", {"id": f"ast_{i:02d}", "org_id": "org_minato", "kind": kind, "name": name, "name_ja": name_ja,
                             "detail": detail})

    morita, tanaka, kobayashi, saito, watanabe = (_user(db, u) for u in
                                                  ("usr_morita", "usr_tanaka", "usr_kobayashi", "usr_saito", "usr_watanabe"))
    yuta, nguyen, mei, ricardo = (_user(db, u) for u in ("usr_ishikawa", "usr_nguyen", "usr_takahashi", "usr_oshiro"))

    def new_capture(spec: dict, expert: dict, by: dict, cid: str, ts: str, with_transcript: bool = True) -> str:
        with clock.at(ts):
            c = capture.create_capture(db, "org_minato", by, {
                "title": spec["title"], "expert_id": expert["id"], "task_category": spec["task_category"],
                "machine": spec["machine"], "tools": spec["tools"], "materials": spec["materials"],
                "skill_ids": [skill_ids[s] for s in spec["skill_codes"]], "experience_level": spec["experience_level"],
                "transcript": spec["transcript"] if with_transcript else "",
                "transcript_source": "uploaded" if with_transcript and spec["transcript"] else "none",
                "expert_notes": spec["expert_notes"], "tips": spec["tips"], "mistakes": spec["mistakes"],
                "troubleshooting": spec["troubleshooting"], "safety_notes": spec["safety_notes"]})
            db.execute("UPDATE capture_sessions SET id = ? WHERE id = ?", (cid, c["id"]))
            db.execute("UPDATE audit_events SET entity_id = ? WHERE entity_id = ?", (cid, c["id"]))
            capture.update_capture(db, "org_minato", by, cid, {
                "consent_given": True,
                "consent_scope": f"{expert['name']} consents to internal use of this recording and notes for training "
                                 f"Minato Precision Works employees. Not to be shared outside the company."})
            for t, kind, label, note in spec.get("markers", []):
                capture.add_marker(db, "org_minato", by, cid, {"t_seconds": t, "kind": kind, "label": label, "note": note})
        db.execute("UPDATE capture_sessions SET created_at = ?, updated_at = ?, consent_at = ? WHERE id = ?", (ts, ts, ts, cid))
        return cid

    def direct_procedure(pid: str, code: str, owner: dict, cap_id: str, versions: list[tuple], approver: dict,
                         publisher: dict) -> None:
        """Insert hand-authored historical versions; last tuple is the published one."""
        first_ts = versions[0][2]
        db.insert("procedures", {"id": pid, "org_id": "org_minato", "code": code, "title": versions[-1][1]["title"],
                                 "owner_expert_id": owner["id"], "capture_id": cap_id, "created_at": first_ts, "updated_at": versions[-1][2]})
        prev = None
        for n, (vid, content, ts, summary) in enumerate(versions, 1):
            status = workflow.PUBLISHED if n == len(versions) else workflow.SUPERSEDED
            db.insert("procedure_versions", {
                "id": vid, "procedure_id": pid, "org_id": "org_minato", "version_no": n, "status": status,
                "content_json": dumps(procedures.normalize_content(content).content), "extractor": "rule_based" if n == 1 else "revision",
                "extraction_meta_json": "{}", "change_summary": summary, "based_on_version_id": prev, "created_by": watanabe["id"],
                "created_at": ts, "updated_at": ts, "approved_by": approver["id"], "approved_at": ts,
                "published_by": publisher["id"], "published_at": ts})
            for frm, to, actor, comment in ((workflow.DRAFT, workflow.AI_PROCESSED, watanabe, "Extracted from capture"),
                                            (workflow.AI_PROCESSED, workflow.EXPERT_REVIEW, watanabe, None),
                                            (workflow.EXPERT_REVIEW, workflow.APPROVED, approver, "Checked against the floor practice"),
                                            (workflow.APPROVED, workflow.PUBLISHED, publisher, None)):
                db.insert("review_events", {"id": f"rev_{vid}_{to.lower()}", "org_id": "org_minato", "version_id": vid,
                                            "actor_id": actor["id"], "from_status": frm, "to_status": to, "comment": comment,
                                            "created_at": ts})
            db.execute("""INSERT INTO audit_events (org_id, actor_id, action, entity_type, entity_id, summary, detail_json, created_at)
                          VALUES (?, ?, 'procedure.publish', 'procedure', ?, ?, '{}', ?)""",
                       ("org_minato", publisher["id"], pid, f"Publish: {code} v{n} → PUBLISHED", ts))
            prev = vid
        db.update("procedures", pid, {"latest_version_id": prev, "published_version_id": prev})
        db.update("capture_sessions", cap_id, {"status": "extracted", "procedure_id": pid})

    # -- captures & procedures -------------------------------------------------------------------------------
    lathe_cap = {"title": "LT-03 pre-shift inspection walk-through", "task_category": "Preventive maintenance",
                 "machine": "2-axis CNC turning centre LT-03", "tools": ["Chip hook", "Brush"], "materials": [],
                 "skill_codes": ["SK-LATHE-PM"], "experience_level": "Beginner", "transcript": C.LATHE_TRANSCRIPT,
                 "expert_notes": "", "tips": "", "mistakes": "Skipping the warm-up to save 10 minutes.", "troubleshooting": "",
                 "safety_notes": ""}
    new_capture(lathe_cap, saito, watanabe, "cap_lathe", T(52))
    direct_procedure("prc_lathe", "PR-001", saito, "cap_lathe",
                     [("ver_lathe_1", C.LATHE_V1, T(50), "Initial capture of Saito's pre-shift routine"),
                      ("ver_lathe_2", C.LATHE_V2, T(27), "Added spindle warm-up step after first-part size drift was traced to cold starts")],
                     saito, watanabe)

    runout_cap = {"title": "Spindle run-out check (monthly PM)", "task_category": "Preventive maintenance",
                  "machine": C.RUNOUT["machine"], "tools": ["Test bar", "Dial test indicator", "Magnetic base"], "materials": [],
                  "skill_codes": ["SK-SPDL"], "experience_level": "Intermediate", "transcript": _transcript_from(C.RUNOUT, "Saito"),
                  "expert_notes": "", "tips": "", "mistakes": _notes_from(C.RUNOUT), "troubleshooting": "", "safety_notes": ""}
    new_capture(runout_cap, saito, watanabe, "cap_runout", T(46))
    direct_procedure("prc_runout", "PR-002", saito, "cap_runout", [("ver_runout_1", C.RUNOUT, T(44), "Initial publication")],
                     saito, watanabe)

    micro_cap = {"title": "Micrometer zero check", "task_category": "Metrology", "machine": "Inspection bench",
                 "tools": ["Outside micrometer 50–75 mm", "50 mm standard"], "materials": ["Lens paper"],
                 "skill_codes": ["SK-MICRO"], "experience_level": "Beginner", "transcript": _transcript_from(C.MICRO, "Tanaka"),
                 "expert_notes": "", "tips": "", "mistakes": _notes_from(C.MICRO), "troubleshooting": "", "safety_notes": ""}
    new_capture(micro_cap, tanaka, watanabe, "cap_micro", T(41))
    direct_procedure("prc_micro", "PR-003", tanaka, "cap_micro", [("ver_micro_1", C.MICRO, T(39), "Initial publication")],
                     tanaka, watanabe)

    # PR-004 — genuinely extracted by the offline extractor and waiting for Kobayashi's review
    registry = Registry(settings) if settings else Registry(_NoSettings())
    new_capture(C.DRESSING_CAPTURE, kobayashi, watanabe, "cap_dressing", T(6))
    with clock.at(T(5, 14)):
        res = capture.extract(db, registry, "org_minato", watanabe, "cap_dressing", "rule_based")
        procedures.transition(db, "org_minato", watanabe, res["version_id"], "submit", None)
    db.execute("UPDATE procedure_versions SET created_at = ?, updated_at = ? WHERE id = ?", (T(5, 14), T(5, 14), res["version_id"]))
    db.execute("UPDATE review_events SET created_at = ? WHERE version_id = ?", (T(5, 14), res["version_id"]))

    # Signature capture: metadata, consent, notes and demonstration markers recorded; transcript not yet attached
    new_capture(C.SIGNATURE_CAPTURE, tanaka, watanabe, "cap_bore", T(2, 16), with_transcript=False)
    # Kisage: an incomplete capture draft (resume later)
    with clock.at(T(9)):
        c = capture.create_capture(db, "org_minato", watanabe, {
            "title": C.KISAGE_CAPTURE["title"], "expert_id": kobayashi["id"], "task_category": C.KISAGE_CAPTURE["task_category"],
            "machine": C.KISAGE_CAPTURE["machine"], "tools": C.KISAGE_CAPTURE["tools"],
            "skill_ids": [skill_ids["SK-KISAGE"]], "experience_level": "Advanced", "expert_notes": C.KISAGE_CAPTURE["expert_notes"]})
    db.execute("UPDATE capture_sessions SET id = 'cap_kisage', created_at = ?, updated_at = ? WHERE id = ?", (T(9), T(9), c["id"]))
    db.execute("UPDATE audit_events SET entity_id = 'cap_kisage' WHERE entity_id = ?", (c["id"],))

    # -- translations --------------------------------------------------------------------------------------------
    with clock.at(T(20)):
        translations.save(db, "org_minato", watanabe, "ver_lathe_2", "ja", {"content": C.LATHE_JA})
        translations.review(db, "org_minato", saito, "ver_lathe_2", "ja")
    with clock.at(T(15)):
        translations.save(db, "org_minato", watanabe, "ver_runout_1", "ja", {"content": C.RUNOUT_JA})

    # -- training, assessments, sign-off -----------------------------------------------------------------------
    def train(user: dict, pid: str, ts: str) -> None:
        v = db.one("SELECT published_version_id FROM procedures WHERE id = ?", (pid,))
        steps = [s["step_id"] for s in procedures.common.version(db, "org_minato", v["published_version_id"])["content"]["steps"]]
        with clock.at(ts):
            training.update_progress(db, "org_minato", user, pid, {"completed_steps": steps, "guided_completed": True})
        db.execute("UPDATE training_progress SET started_at = ?, updated_at = ?, guided_completed_at = ? WHERE user_id = ? AND procedure_id = ?",
                   (ts, ts, ts, user["id"], pid))

    def take(user: dict, pid: str, ts: str, wrong: tuple = (), hints: tuple = (), minutes: int = 14) -> str:
        att = training.start_attempt(db, "org_minato", user, pid)
        row = db.one("SELECT answers_json, version_id FROM assessment_attempts WHERE id = ?", (att["attempt_id"],))
        orders = procedures.loads(row["answers_json"])["_orders"]
        content = procedures.common.version(db, "org_minato", row["version_id"])["content"]
        from ..domain.scoring import assessment_items
        answers = {}
        for it in assessment_items(content):
            orig = it["answer_index"] if it["id"] not in wrong else (it["answer_index"] + 1) % len(it["options"])
            answers[it["id"]] = orders[it["id"]].index(orig)
        for h in hints:
            training.hint(db, "org_minato", user, att["attempt_id"], h)
        with clock.at(ts):
            training.submit_attempt(db, "org_minato", user, att["attempt_id"], {"answers": answers, "duration_s": minutes * 60})
        start = (datetime.fromisoformat(ts.replace("Z", "+00:00")) - timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")
        db.execute("UPDATE assessment_attempts SET started_at = ?, submitted_at = ? WHERE id = ?", (start, ts, att["attempt_id"]))
        db.execute("UPDATE competency_records SET updated_at = ? WHERE latest_attempt_id = ?", (ts, att["attempt_id"]))
        db.execute("UPDATE remediation_tasks SET created_at = ? WHERE attempt_id = ?", (ts, att["attempt_id"]))
        return att["attempt_id"]

    def sign(attempt_id: str, decision: str, ts: str, feedback: str = "") -> None:
        with clock.at(ts):
            competency.signoff(db, "org_minato", watanabe, attempt_id, {"decision": decision, "feedback": feedback})
        db.execute("UPDATE signoffs SET created_at = ? WHERE attempt_id = ?", (ts, attempt_id))
        db.execute("UPDATE competency_records SET validated_at = CASE WHEN validated_at IS NULL THEN NULL ELSE ? END, updated_at = ? "
                   "WHERE latest_attempt_id = ?", (ts, ts, attempt_id))

    # Yuta: lathe PM validated; micrometer: critical failure then improvement and validation
    train(yuta, "prc_lathe", T(24, 9))
    a = take(yuta, "prc_lathe", T(24, 11), minutes=12)
    sign(a, "approve", T(23, 15), "Observed on the floor on 2 shifts; checklist correct.")
    train(yuta, "prc_micro", T(21, 9))
    take(yuta, "prc_micro", T(21, 10), wrong=("q-001", "q-003"), minutes=9)
    a = take(yuta, "prc_micro", T(17, 10), hints=("q-002",), minutes=11)
    sign(a, "approve", T(16, 16), "Big improvement after remediation. Zero check observed at the bench.")
    db.execute("UPDATE remediation_tasks SET status = 'done', completed_at = ? WHERE user_id = ?", (T(18), yuta["id"]))

    # Nguyen: lathe PM validated, run-out passed and awaiting sign-off
    train(nguyen, "prc_lathe", T(22, 9))
    a = take(nguyen, "prc_lathe", T(22, 13), minutes=15)
    sign(a, "approve", T(21, 11), "Explained each check clearly in Japanese and English.")
    train(nguyen, "prc_runout", T(4, 9))
    take(nguyen, "prc_runout", T(3, 15), wrong=("q-003",), minutes=16)

    # Mei: micrometer passed, waiting for sign-off
    train(mei, "prc_micro", T(2, 9))
    take(mei, "prc_micro", T(1, 14), minutes=10)

    # Ricardo: run-out critical failure -> automatic remediation task
    train(ricardo, "prc_runout", T(8, 9))
    take(ricardo, "prc_runout", T(7, 15), wrong=("q-001", "q-003"), minutes=18)
    take(ricardo, "prc_lathe", T(12, 11), wrong=("q-003", "q-004"), minutes=13)  # plain fail (score)

    # -- continuous improvement feedback ----------------------------------------------------------------------
    with clock.at(T(7, 16)):
        procedures.add_feedback(db, "org_minato", ricardo, "prc_runout",
                                {"note": "Step 4 doesn't say where to put the magnetic base on LT-03 — I wasn't sure which surface is non-rotating.",
                                 "step_id": "step-004"})

    # -- mentorship --------------------------------------------------------------------------------------------
    with clock.at(T(10)):
        r1 = mentorship.create_request(db, "org_minato", nguyen, {
            "mentor_id": tanaka["id"], "skill_id": skill_ids["SK-BORE"],
            "message": "I will take over SH-62 bore inspection on the night shift. Could you show me how you judge when a housing is cool enough?"})
        mentorship.respond(db, "org_minato", tanaka, r1["id"], {"action": "accept", "note": "Yes. Bring the inspection sheet."})
        s1 = mentorship.schedule(db, "org_minato", tanaka, r1["id"], {
            "scheduled_at": T(-3, 14)[:16], "duration_min": 90, "mode": "onsite", "location": "Inspection room, bench 2",
            "agenda": "Thermal soak judgement; zeroing at the turning point; six-point measurement on two housings."})
    with clock.at(T(19)):
        r2 = mentorship.create_request(db, "org_minato", yuta, {
            "mentor_id": kobayashi["id"], "skill_id": skill_ids["SK-KISAGE"],
            "message": "I'd like to learn kisage before Kobayashi-san retires. Can we start with the basics on a scrap way?"})
        mentorship.respond(db, "org_minato", kobayashi, r2["id"], {"action": "accept"})
        s2 = mentorship.schedule(db, "org_minato", yuta, r2["id"], {
            "scheduled_at": T(12, 15)[:16], "duration_min": 120, "mode": "onsite", "location": "Rebuild bay",
            "agenda": "Scraper sharpening; reading the blue bearing pattern."})
    with clock.at(T(12, 17)):
        mentorship.update_session(db, "org_minato", yuta, s2["id"], {
            "status": "completed",
            "notes": "Sharpened the scraper twice. Kobayashi-san's cue: the scraper should 'bite' the high spot and leave a crescent, not skate."})
        mentorship.update_session(db, "org_minato", kobayashi, s2["id"], {
            "mentor_feedback": "Good wrist control for a first session. Strokes still too long — practise 10 mm strokes."})
        f1 = mentorship.add_followup(db, "org_minato", yuta, s2["id"], {"description": "Practise 10 mm strokes on scrap way for 30 min/day", "owner_id": yuta["id"]})
        mentorship.add_followup(db, "org_minato", kobayashi, s2["id"], {"description": "Record a kisage demonstration video for Capture Studio", "owner_id": kobayashi["id"]})
        mentorship.toggle_followup(db, "org_minato", yuta, f1["id"], True)
    with clock.at(T(1, 11)):
        mentorship.create_request(db, "org_minato", mei, {
            "mentor_id": saito["id"], "skill_id": skill_ids["SK-SPDL"],
            "message": "Could you review my run-out measurement technique before I take the assessment?"})
    for table in ("mentorship_requests",):
        db.execute(f"UPDATE {table} SET created_at = ? WHERE id = ?", (T(10), r1["id"]))
        db.execute(f"UPDATE {table} SET created_at = ? WHERE id = ?", (T(19), r2["id"]))

    # -- isolation tenant content -------------------------------------------------------------------------------
    db.insert("procedures", {"id": "prc_hokuto", "org_id": "org_hokuto", "code": "PR-001", "title": "Mould venting check (other tenant)",
                             "owner_expert_id": "usr_hokuto_admin", "created_at": created, "updated_at": created,
                             "latest_version_id": "ver_hokuto_1", "published_version_id": "ver_hokuto_1"})
    db.insert("procedure_versions", {"id": "ver_hokuto_1", "procedure_id": "prc_hokuto", "org_id": "org_hokuto", "version_no": 1,
                                     "status": "PUBLISHED", "content_json": dumps(procedures.normalize_content({
                                         "title": "Mould venting check (other tenant)", "skills": ["SK-MOULD"],
                                         "steps": [{"title": "Check vents", "instruction": "Confidential Hokuto knowledge: check vent holes.",
                                                    "source_type": "expert_edit"}],
                                         "questions": [{"prompt": "Check?", "options": ["Yes", "No"], "answer_index": 0}]}).content),
                                     "created_at": created, "updated_at": created})
    db.close()
    return {"password": DEMO_PASSWORD}


class _NoSettings:
    anthropic_enabled = False
    anthropic_key_present = False
    anthropic_model = ""
    anthropic_timeout_s = 0
