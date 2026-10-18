"""HTTP API routes. Each handler: authorise → validate → call a service."""
from __future__ import annotations

import threading
import time

from . import auth
from .auth import can, require
from .db import DB, new_id, now_iso
from .services import (admin, assistant, capture, common, competency, graph, insights, mentorship, procedures,
                       training, translations)
from . import storage, audit
from .web import ApiError, Response, Router, bad_request, forbidden, not_found


def build_router(registry) -> Router:
    r = Router()
    failures: dict[str, list[float]] = {}
    lock = threading.Lock()

    def org(req) -> str:
        return req.user["org_id"]

    # -- auth ------------------------------------------------------------------------------------
    @r.route("GET", "/api/health", auth=False)
    def health(req):
        req.db.scalar("SELECT 1")
        return {"status": "ok", "time": now_iso()}

    @r.route("POST", "/api/auth/login", auth=False)
    def login(req):
        data = req.json()
        email = (data.get("email") or "").strip().lower()
        key = f"{req.handler.client_address[0]}:{email}"
        with lock:
            recent = [t for t in failures.get(key, []) if t > time.time() - 900]
            failures[key] = recent
            if len(recent) >= 8:
                raise ApiError(429, "too_many_attempts", "Too many failed sign-in attempts. Try again in 15 minutes.")
        u = req.db.one("SELECT * FROM users WHERE lower(email) = ? AND active = 1", (email,))
        if not u or not auth.verify_password(data.get("password") or "", u["password_hash"]):
            with lock:
                failures.setdefault(key, []).append(time.time())
            raise ApiError(401, "invalid_credentials", "Email or password is incorrect")
        auth.create_session(req, u["id"])
        audit.record(req.db, u["org_id"], u["id"], "auth.login", "user", u["id"], f"{u['name']} signed in")
        return {"ok": True}

    @r.route("GET", "/api/auth/demo-accounts", auth=False)
    def demo_accounts(req):
        if not req.app.settings.demo_mode:
            return {"enabled": False, "accounts": []}
        rows = req.db.all("""SELECT u.id, u.name, u.name_ja, u.role, u.title, o.name AS org_name FROM users u
                             JOIN organizations o ON o.id = u.org_id WHERE o.is_simulated = 1 AND u.active = 1
                             ORDER BY o.created_at, CASE u.role WHEN 'admin' THEN 0 WHEN 'expert' THEN 1 WHEN 'trainer' THEN 2 ELSE 3 END, u.name""")
        return {"enabled": True, "accounts": rows}

    @r.route("POST", "/api/auth/demo-login", auth=False)
    def demo_login(req):
        """Persona switcher for the simulated demo organisation only. Disabled
        when KIZUNA_DEMO_MODE=false. Real organisations always use passwords."""
        if not req.app.settings.demo_mode:
            raise forbidden("Demo sign-in is disabled")
        uid = req.json().get("user_id") or ""
        u = req.db.one("SELECT u.* FROM users u JOIN organizations o ON o.id = u.org_id "
                       "WHERE u.id = ? AND o.is_simulated = 1 AND u.active = 1", (uid,))
        if not u:
            raise not_found("Demo account")
        auth.destroy_session(req)
        req.set_cookies.clear()
        auth.create_session(req, u["id"])
        audit.record(req.db, u["org_id"], u["id"], "auth.demo_login", "user", u["id"], f"Switched to demo persona {u['name']}")
        return {"ok": True}

    @r.route("POST", "/api/auth/logout")
    def logout(req):
        auth.destroy_session(req)
        return {"ok": True}

    @r.route("GET", "/api/me")
    def me(req):
        o = req.db.one("SELECT id, name, name_ja, industry, location, employee_count, plan_tier, is_simulated, recording_policy, "
                       "retention_days FROM organizations WHERE id = ?", (org(req),))
        return {"user": auth.public_user(req.user), "permissions": auth.permissions_for(req.user["role"]), "org": o,
                "demo_mode": req.app.settings.demo_mode}

    @r.route("PATCH", "/api/me")
    def update_me(req):
        loc = req.json().get("locale")
        if loc not in ("en", "ja"):
            raise bad_request("locale must be en or ja")
        req.db.update("users", req.user["id"], {"locale": loc})
        return {"locale": loc}

    # -- overview / search ------------------------------------------------------------------------------
    @r.route("GET", "/api/dashboard")
    def dash(req):
        return insights.dashboard(req.db, org(req), req.user)

    @r.route("GET", "/api/notifications")
    def notes(req):
        return {"items": insights.notifications(req.db, org(req), req.user)}

    @r.route("GET", "/api/search")
    def search(req):
        return {"results": insights.search(req.db, org(req), req.user, req.query.get("q", ""))}

    @r.route("GET", "/api/providers")
    def providers(req):
        return registry.statuses()

    # -- people & skills ----------------------------------------------------------------------------------
    @r.route("GET", "/api/skills")
    def skills(req):
        return {"skills": common.skills(req.db, org(req))}

    @r.route("GET", "/api/people")
    def people(req):
        return {"people": admin.people(req.db, org(req), req.user)}

    @r.route("GET", "/api/people/{uid}")
    def person(req):
        return competency.person_profile(req.db, org(req), req.user, req.params["uid"])

    @r.route("PUT", "/api/people/{uid}/retirement")
    def retirement(req):
        return admin.set_retirement(req.db, org(req), req.user, req.params["uid"], req.json().get("retirement_date"))

    @r.route("PUT", "/api/people/{uid}/skills/{sid}")
    def person_skill(req):
        return admin.set_skill(req.db, org(req), req.user, req.params["uid"], req.params["sid"], req.json().get("proficiency"))

    # -- capture studio -----------------------------------------------------------------------------------
    @r.route("GET", "/api/captures")
    def captures(req):
        require(req, "capture.read")
        return {"captures": capture.list_captures(req.db, org(req))}

    @r.route("POST", "/api/captures")
    def capture_create(req):
        require(req, "capture.write")
        return capture.create_capture(req.db, org(req), req.user, req.json())

    @r.route("GET", "/api/captures/{cid}")
    def capture_get(req):
        require(req, "capture.read")
        return capture.get_capture(req.db, org(req), req.params["cid"])

    @r.route("PATCH", "/api/captures/{cid}")
    def capture_update(req):
        require(req, "capture.write")
        return capture.update_capture(req.db, org(req), req.user, req.params["cid"], req.json())

    @r.route("POST", "/api/captures/{cid}/markers")
    def marker_add(req):
        require(req, "capture.write")
        return capture.add_marker(req.db, org(req), req.user, req.params["cid"], req.json())

    @r.route("DELETE", "/api/captures/{cid}/markers/{mid}")
    def marker_del(req):
        require(req, "capture.write")
        capture.delete_marker(req.db, org(req), req.params["cid"], req.params["mid"])
        return {"ok": True}

    @r.route("PUT", "/api/captures/{cid}/files")
    def upload(req):
        require(req, "capture.write")
        c = req.db.one("SELECT id, title FROM capture_sessions WHERE id = ? AND org_id = ?", (req.params["cid"], org(req)))
        if not c:
            raise not_found("Capture session")
        kind, name = req.query.get("kind", ""), storage.safe_name(req.query.get("name", ""))
        try:
            ext, mime = storage.validate_meta(kind, name)
            limit = storage.limit_bytes(kind, req.app.settings.max_upload_mb)
            stored, size, sha, path = storage.store(req.app.settings.upload_dir, org(req), ext,
                                                    lambda fh: req.stream_to(fh, limit))
        except storage.UploadError as e:
            raise ApiError(415, "unsupported_file", str(e))
        fid = new_id("fil")
        req.db.insert("files", {"id": fid, "org_id": org(req), "capture_id": c["id"], "kind": kind, "original_name": name,
                                "stored_name": stored, "mime": mime, "size_bytes": size, "sha256": sha,
                                "uploaded_by": req.user["id"], "created_at": now_iso()})
        if kind == "transcript":
            text = path.read_text(encoding="utf-8", errors="replace")
            req.db.update("capture_sessions", c["id"], {"transcript": text[:200_000], "transcript_source": "uploaded",
                                                        "updated_at": now_iso()})
        audit.record(req.db, org(req), req.user["id"], "capture.file", "capture", c["id"],
                     f"Uploaded {kind} “{name}” ({round(size / 1024)} KB) to “{c['title']}”", {"sha256": sha})
        return {"id": fid, "kind": kind, "original_name": name, "mime": mime, "size_bytes": size, "sha256": sha}

    @r.route("GET", "/api/files/{fid}")
    def file_get(req):
        f = req.db.one("SELECT * FROM files WHERE id = ? AND org_id = ?", (req.params["fid"], org(req)))
        if not f:
            raise not_found("File")
        if not can(req.user, "capture.read"):
            # trainees may stream demonstration video of a *published* procedure only
            ok = req.db.one("SELECT 1 FROM procedures WHERE capture_id = ? AND published_version_id IS NOT NULL", (f["capture_id"],))
            if not ok or f["kind"] != "video":
                raise forbidden()
        path = storage.resolve(req.app.settings.upload_dir, org(req), f["stored_name"])
        if not path.is_file():
            raise not_found("File content")
        size = path.stat().st_size
        rng = storage.parse_range(req.headers.get("Range"), size)
        headers = {"Content-Type": f["mime"], "Accept-Ranges": "bytes", "Cache-Control": "private, no-store",
                   "Content-Disposition": f'inline; filename="{f["original_name"]}"'}
        if rng:
            headers["Content-Range"] = f"bytes {rng[0]}-{rng[1]}/{size}"
            return Response(206, None, headers, file_path=path, file_range=rng)
        return Response(200, None, headers, file_path=path)

    @r.route("DELETE", "/api/files/{fid}")
    def file_del(req):
        require(req, "capture.write")
        f = req.db.one("SELECT * FROM files WHERE id = ? AND org_id = ?", (req.params["fid"], org(req)))
        if not f:
            raise not_found("File")
        storage.resolve(req.app.settings.upload_dir, org(req), f["stored_name"]).unlink(missing_ok=True)
        req.db.execute("DELETE FROM files WHERE id = ?", (f["id"],))
        audit.record(req.db, org(req), req.user["id"], "capture.file_deleted", "capture", f["capture_id"],
                     f"Deleted {f['kind']} “{f['original_name']}”")
        return {"ok": True}

    @r.route("POST", "/api/captures/{cid}/extract")
    def extract(req):
        require(req, "extraction.run")
        return capture.extract(req.db, registry, org(req), req.user, req.params["cid"], req.json().get("provider", "rule_based"))

    @r.route("GET", "/api/samples/capture")
    def sample(req):
        require(req, "capture.write")
        from .seed.content import SIGNATURE_CAPTURE, SIGNATURE_CAPTURE_JA
        return SIGNATURE_CAPTURE_JA if req.query.get("lang") == "ja" else SIGNATURE_CAPTURE

    # -- knowledge library -----------------------------------------------------------------------------
    @r.route("GET", "/api/procedures")
    def procs(req):
        return {"procedures": procedures.list_procedures(req.db, org(req), req.user)}

    @r.route("POST", "/api/procedures")
    def proc_create(req):
        require(req, "procedure.create")
        return procedures.create_manual(req.db, org(req), req.user, req.json())

    @r.route("GET", "/api/procedures/{pid}")
    def proc_get(req):
        return procedures.get_procedure(req.db, org(req), req.user, req.params["pid"], req.query.get("version"))

    @r.route("POST", "/api/procedures/{pid}/revisions")
    def revise(req):
        require(req, "procedure.edit")
        return procedures.new_revision(req.db, org(req), req.user, req.params["pid"], req.json().get("change_summary"))

    @r.route("GET", "/api/procedures/{pid}/diff")
    def diff(req):
        return procedures.diff_versions(req.db, org(req), req.user, req.query.get("a", ""), req.query.get("b", ""))

    @r.route("GET", "/api/procedures/{pid}/export")
    def export(req):
        fmt = req.query.get("format", "md")
        if fmt not in ("md", "json"):
            raise bad_request("format must be md or json")
        body, ctype, fname = procedures.export(req.db, org(req), req.user, req.params["pid"], req.query.get("version"), fmt)
        return Response.text(body, ctype, filename=fname if req.query.get("download") else None)

    @r.route("GET", "/api/procedures/{pid}/insights")
    def proc_insights(req):
        require(req, "procedure.read_unpublished")
        common.procedure(req.db, org(req), req.params["pid"])
        return procedures.step_insights(req.db, org(req), req.params["pid"])

    @r.route("POST", "/api/procedures/{pid}/feedback")
    def feedback(req):
        return procedures.add_feedback(req.db, org(req), req.user, req.params["pid"], req.json())

    @r.route("PATCH", "/api/feedback/{fid}")
    def feedback_resolve(req):
        require(req, "feedback.resolve")
        return procedures.resolve_feedback(req.db, org(req), req.user, req.params["fid"], req.json().get("status"))

    @r.route("PUT", "/api/versions/{vid}/content")
    def save(req):
        require(req, "procedure.edit")
        data = req.json()
        return procedures.save_content(req.db, org(req), req.user, req.params["vid"], data.get("content"), data.get("note"))

    @r.route("POST", "/api/versions/{vid}/validate")
    def validate(req):
        require(req, "procedure.read_unpublished")
        from .domain.procedure_schema import approval_blockers, normalize_content
        content = req.json().get("content")
        return {**normalize_content(content).as_dict(), "approval_blockers": approval_blockers(content or {})}

    @r.route("POST", "/api/versions/{vid}/transition")
    def trans(req):
        data = req.json()
        return procedures.transition(req.db, org(req), req.user, req.params["vid"], data.get("action", ""), data.get("comment"))

    @r.route("POST", "/api/versions/{vid}/confirm")
    def confirm(req):
        require(req, "procedure.approve")
        data = req.json()
        return procedures.confirm_items(req.db, org(req), req.user, req.params["vid"], data.get("item_ids"),
                                        bool(data.get("confirmed", True)))

    @r.route("POST", "/api/versions/{vid}/open-questions/{oq}/resolve")
    def resolve_oq(req):
        require(req, "procedure.approve")
        data = req.json()
        return procedures.resolve_open_question(req.db, org(req), req.user, req.params["vid"], req.params["oq"],
                                                data.get("resolution", ""), bool(data.get("add_as_tip", True)))

    @r.route("GET", "/api/versions/{vid}/translations/{loc}")
    def tr_get(req):
        return translations.get(req.db, org(req), req.user, req.params["vid"], req.params["loc"])

    @r.route("PUT", "/api/versions/{vid}/translations/{loc}")
    def tr_save(req):
        require(req, "translation.edit")
        return translations.save(req.db, org(req), req.user, req.params["vid"], req.params["loc"], req.json())

    @r.route("POST", "/api/versions/{vid}/translations/{loc}/review")
    def tr_review(req):
        return translations.review(req.db, org(req), req.user, req.params["vid"], req.params["loc"])

    # -- training & assessment ------------------------------------------------------------------------
    @r.route("GET", "/api/training/modules")
    def modules(req):
        return {"modules": training.list_modules(req.db, org(req), req.user),
                "remediation": competency.remediation_for(req.db, org(req), req.user["id"])}

    @r.route("GET", "/api/training/modules/{pid}")
    def module(req):
        return training.get_module(req.db, org(req), req.user, req.params["pid"])

    @r.route("POST", "/api/training/modules/{pid}/progress")
    def progress(req):
        return training.update_progress(req.db, org(req), req.user, req.params["pid"], req.json())

    @r.route("POST", "/api/training/modules/{pid}/check")
    def check(req):
        data = req.json()
        return training.practice_check(req.db, org(req), req.user, req.params["pid"], data.get("item_id", ""), data.get("choice"))

    @r.route("POST", "/api/training/modules/{pid}/attempts")
    def attempt_start(req):
        return training.start_attempt(req.db, org(req), req.user, req.params["pid"])

    @r.route("POST", "/api/attempts/{aid}/hint")
    def attempt_hint(req):
        return training.hint(req.db, org(req), req.user, req.params["aid"], req.json().get("item_id", ""))

    @r.route("POST", "/api/attempts/{aid}/submit")
    def attempt_submit(req):
        return training.submit_attempt(req.db, org(req), req.user, req.params["aid"], req.json())

    @r.route("GET", "/api/attempts/{aid}")
    def attempt_get(req):
        return training.get_attempt(req.db, org(req), req.user, req.params["aid"])

    @r.route("POST", "/api/attempts/{aid}/signoff")
    def attempt_signoff(req):
        return competency.signoff(req.db, org(req), req.user, req.params["aid"], req.json())

    @r.route("GET", "/api/competency/matrix")
    def matrix(req):
        return competency.matrix(req.db, org(req), req.user)

    @r.route("POST", "/api/remediation/{tid}/complete")
    def remediation_done(req):
        return competency.complete_remediation(req.db, org(req), req.user, req.params["tid"])

    # -- risk / graph / assistant -------------------------------------------------------------------------
    @r.route("GET", "/api/risk")
    def risk(req):
        require(req, "risk.view")
        return insights.risk_radar(req.db, org(req), req.user)

    @r.route("GET", "/api/graph")
    def graph_get(req):
        return graph.build(req.db, org(req), req.user)

    @r.route("POST", "/api/assistant/ask")
    def ask(req):
        data = req.json()
        return assistant.ask(req.db, org(req), req.user, data.get("question", ""), registry, data.get("procedure_id"))

    # -- mentorship ------------------------------------------------------------------------------------------
    @r.route("GET", "/api/mentorship")
    def mentor_overview(req):
        return mentorship.overview(req.db, org(req), req.user)

    @r.route("POST", "/api/mentorship/requests")
    def mentor_request(req):
        return mentorship.create_request(req.db, org(req), req.user, req.json())

    @r.route("POST", "/api/mentorship/requests/{rid}/respond")
    def mentor_respond(req):
        return mentorship.respond(req.db, org(req), req.user, req.params["rid"], req.json())

    @r.route("POST", "/api/mentorship/requests/{rid}/sessions")
    def mentor_schedule(req):
        return mentorship.schedule(req.db, org(req), req.user, req.params["rid"], req.json())

    @r.route("PATCH", "/api/mentorship/sessions/{sid}")
    def mentor_session(req):
        return mentorship.update_session(req.db, org(req), req.user, req.params["sid"], req.json())

    @r.route("POST", "/api/mentorship/sessions/{sid}/followups")
    def mentor_followup(req):
        return mentorship.add_followup(req.db, org(req), req.user, req.params["sid"], req.json())

    @r.route("PATCH", "/api/followups/{tid}")
    def followup_toggle(req):
        return mentorship.toggle_followup(req.db, org(req), req.user, req.params["tid"], bool(req.json().get("done")))

    @r.route("GET", "/api/demo/status")
    def demo_status(req):
        """Live progress of the 7-act signature demo, computed from real records."""
        if not req.app.settings.demo_mode:
            raise forbidden("Demo mode is disabled")
        db, o = req.db, org(req)
        cap = db.one("SELECT * FROM capture_sessions WHERE id = 'cap_bore' AND org_id = ?", (o,))
        if not cap:
            raise not_found("Signature demo data (run python run.py --reset)")
        proc = db.one("SELECT * FROM procedures WHERE id = ?", (cap["procedure_id"],)) if cap["procedure_id"] else None
        attempt = db.one("SELECT id, outcome, signoff_status FROM assessment_attempts WHERE user_id = 'usr_nguyen' AND procedure_id = ? "
                         "AND status = 'submitted' ORDER BY submitted_at DESC LIMIT 1", (proc["id"],)) if proc else None
        comp = db.one("SELECT c.status FROM competency_records c JOIN skills s ON s.id = c.skill_id WHERE c.user_id = 'usr_nguyen' "
                      "AND s.code = 'SK-BORE'", ())
        risk = next((s for s in insights.risk_radar(db, o, {"role": "admin", "id": ""})["skills"] if s["code"] == "SK-BORE"), None)
        tanaka = db.one("SELECT retirement_date FROM users WHERE id = 'usr_tanaka'")
        from datetime import date
        days = (date.fromisoformat(tanaka["retirement_date"]) - date.today()).days if tanaka and tanaka["retirement_date"] else None
        published = bool(proc and proc["published_version_id"])
        acts = [
            {"act": 1, "title": "The risk", "persona": "Keiko Morita (admin)", "persona_id": "usr_morita", "route": "#/risk",
             "how": "Knowledge Risk shows Precision bore inspection as critical: one holder retiring, no procedure, no successor.",
             "state": f"SK-BORE risk now {risk['score']} ({risk['band']})" if risk else "", "done": True},
            {"act": 2, "title": "Capture", "persona": "Kenji Watanabe (trainer)", "persona_id": "usr_watanabe", "route": "#/capture/cap_bore",
             "how": "Open Tanaka's capture, attach the recorded transcript (sample button or upload samples/*.vtt).",
             "state": "transcript attached" if cap["transcript"].strip() else "transcript missing", "done": bool(cap["transcript"].strip())},
            {"act": 3, "title": "Structure", "persona": "Kenji Watanabe (trainer)", "persona_id": "usr_watanabe", "route": "#/capture/cap_bore",
             "how": "Run extraction. Steps, tips, failure modes and questions appear with evidence badges and open questions.",
             "state": f"procedure {proc['code']} created" if proc else "not extracted", "done": bool(proc)},
            {"act": 4, "title": "Verify", "persona": "Hiroshi Tanaka (expert)", "persona_id": "usr_tanaka",
             "route": f"#/procedures/{proc['id']}" if proc else "#/library",
             "how": "Tanaka answers the open questions, corrects a step, confirms inferred/safety items, approves and publishes.",
             "state": "published" if published else "awaiting expert review", "done": published},
            {"act": 5, "title": "Transfer", "persona": "Nguyen Van An (trainee)", "persona_id": "usr_nguyen",
             "route": f"#/academy/{proc['id']}" if proc else "#/academy",
             "how": "Nguyen works through guided mode, the challenge scenarios and the final simulated assessment.",
             "state": f"latest attempt: {attempt['outcome']}" if attempt else "no attempt yet", "done": bool(attempt)},
            {"act": 6, "title": "Measure", "persona": "Kenji Watanabe (trainer)", "persona_id": "usr_watanabe", "route": "#/competency",
             "how": "The matrix shows Nguyen pending sign-off; the trainer reviews the evidence and validates (or assigns remediation).",
             "state": f"Nguyen SK-BORE: {comp['status']}" if comp else "no competency record", "done": bool(comp and comp["status"] == "validated")},
            {"act": 7, "title": "Preserve", "persona": "Keiko Morita (admin)", "persona_id": "usr_morita", "route": "#/risk",
             "how": "Risk drops for SK-BORE; the remaining gaps (single holder, retirement) stay visible with next actions.",
             "state": f"SK-BORE risk {risk['score']} ({risk['band']})" if risk else "", "done": bool(risk and risk["score"] < 90)},
        ]
        return {"acts": acts, "days_to_retirement": days}

    # -- settings / admin --------------------------------------------------------------------------------------
    @r.route("GET", "/api/settings")
    def settings(req):
        return admin.org_settings(req.db, org(req), req.user, registry)

    @r.route("GET", "/api/audit")
    def audit_log(req):
        return {"events": admin.audit_log(req.db, org(req), req.user)}

    @r.route("GET", "/api/export/org")
    def export_org(req):
        return Response.text(admin.export_org(req.db, org(req), req.user), "application/json; charset=utf-8",
                             filename=f"kizuna-org-export-{now_iso()[:10]}.json")

    @r.route("GET", "/api/export/training-records.csv")
    def export_training(req):
        return Response.text(admin.training_records_csv(req.db, org(req), req.user), "text/csv; charset=utf-8",
                             filename=f"training-records-{now_iso()[:10]}.csv")

    return r


def create_app(settings):
    from .ai.registry import Registry
    from .db import migrate
    from .web import App
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    migrate(settings.db_path)
    registry = Registry(settings)
    router = build_router(registry)
    return App(settings, router, lambda: DB(settings.db_path), auth.authenticate)
