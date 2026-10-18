"""Integration tests against the real HTTP server and a freshly seeded database.

The `SignatureFlowTests` class walks the complete 7-act demo through the API:
capture → extract → expert review → publish → train → assess → sign-off → risk.
"""
import json
import unittest

from tests.helpers import LiveServer

SERVER: LiveServer | None = None


def setUpModule():
    global SERVER
    SERVER = LiveServer()


def tearDownModule():
    SERVER.stop()


class AuthAndSecurityTests(unittest.TestCase):
    def test_requires_authentication(self):
        c = SERVER.client()
        status, body = c.get("/api/dashboard")
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthenticated")

    def test_password_login(self):
        c = SERVER.client()
        self.assertEqual(c.post("/api/auth/login", {"email": "watanabe@minato.example", "password": "wrong"})[0], 401)
        status, _ = c.post("/api/auth/login", {"email": "watanabe@minato.example", "password": "kizuna-demo-2026"})
        self.assertEqual(status, 200)
        self.assertEqual(c.get("/api/me")[1]["user"]["role"], "trainer")
        self.assertNotIn("password_hash", json.dumps(c.get("/api/me")[1]))

    def test_csrf_header_required_for_mutations(self):
        c = SERVER.client("usr_watanabe")
        status, body = c.post("/api/captures", {"title": "x"}, csrf=False)
        self.assertEqual(status, 403)

    def test_role_based_authorisation(self):
        trainee = SERVER.client("usr_ishikawa")
        self.assertEqual(trainee.get("/api/captures")[0], 403)
        self.assertEqual(trainee.post("/api/captures", {"title": "x"})[0], 403)
        self.assertEqual(trainee.get("/api/risk")[0], 403)
        self.assertEqual(trainee.get("/api/export/org")[0], 403)
        # trainees never see unpublished procedures
        procs = trainee.get("/api/procedures")[1]["procedures"]
        self.assertTrue(procs)
        self.assertTrue(all(p["published_version_id"] for p in procs))
        pr4 = [p for p in SERVER.client("usr_watanabe").get("/api/procedures")[1]["procedures"] if p["code"] == "PR-004"][0]
        self.assertEqual(trainee.get(f"/api/procedures/{pr4['id']}")[0], 404)
        # a trainer cannot approve (expert/admin only)
        vid = pr4["latest_version_id"]
        status, body = SERVER.client("usr_watanabe").post(f"/api/versions/{vid}/transition", {"action": "approve"})
        self.assertEqual(status, 403)

    def test_tenant_isolation(self):
        other = SERVER.client("usr_hokuto_admin")
        procs = other.get("/api/procedures")[1]["procedures"]
        self.assertEqual([p["code"] for p in procs], ["PR-001"])
        self.assertEqual(procs[0]["title"], "Mould venting check (other tenant)")
        self.assertEqual(other.get("/api/procedures/prc_lathe")[0], 404)
        self.assertEqual(other.get("/api/captures/cap_bore")[0], 404)
        self.assertEqual(other.get("/api/people/usr_tanaka")[0], 404)
        minato = SERVER.client("usr_morita")
        self.assertEqual(minato.get("/api/procedures/prc_hokuto")[0], 404)
        answer = minato.post("/api/assistant/ask", {"question": "How do I check mould vent holes?"})[1]
        self.assertNotIn("Confidential Hokuto", json.dumps(answer))

    def test_upload_validation(self):
        c = SERVER.client("usr_watanabe")
        status, body = c.request("PUT", "/api/captures/cap_kisage/files?kind=video&name=fake.mp4", raw=b"not really a video file at all",
                                 headers={"Content-Type": "video/mp4"})
        self.assertEqual(status, 415)
        status, _ = c.request("PUT", "/api/captures/cap_kisage/files?kind=video&name=evil.exe", raw=b"MZ....",
                              headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(status, 415)
        mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
        status, body = c.request("PUT", "/api/captures/cap_kisage/files?kind=video&name=demo.mp4", raw=mp4, headers={"Content-Type": "video/mp4"})
        self.assertEqual(status, 200)
        fid = body["id"]
        status, data = c.request("GET", f"/api/files/{fid}", headers={"Range": "bytes=0-7"})
        self.assertEqual(status, 206)
        self.assertEqual(SERVER.client("usr_hokuto_admin").get(f"/api/files/{fid}")[0], 404)
        self.assertEqual(SERVER.client("usr_ishikawa").get(f"/api/files/{fid}")[0], 403)

    def test_invalid_inputs(self):
        c = SERVER.client("usr_watanabe")
        self.assertEqual(c.post("/api/captures", {"title": "  "})[0], 400)
        self.assertEqual(c.request("POST", "/api/captures", raw=b"{not json", headers={"Content-Type": "application/json"})[0], 400)
        self.assertEqual(c.post("/api/captures/cap_kisage/markers", {"t_seconds": "abc", "label": "x"})[0], 400)
        self.assertEqual(c.get("/api/nope")[0], 404)

    def test_unconfigured_ai_is_reported_not_faked(self):
        c = SERVER.client("usr_watanabe")
        status, body = c.post("/api/captures/cap_lathe/extract", {"provider": "claude"})
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "extraction_not_configured")

    def test_consent_required_before_extraction(self):
        c = SERVER.client("usr_watanabe")
        cap = c.post("/api/captures", {"title": "No consent yet", "expert_id": "usr_saito", "transcript": "[00:00:01] Saito: Clean the chuck."})[1]
        status, body = c.post(f"/api/captures/{cap['id']}/extract", {"provider": "rule_based"})
        self.assertEqual(status, 422)
        self.assertEqual(body["error"]["code"], "consent_required")

    def test_assistant_admits_unknown(self):
        r = SERVER.client("usr_nguyen").post("/api/assistant/ask", {"question": "What is the torque for the tailstock quill clamp?"})[1]
        self.assertFalse(r["answerable"])
        self.assertEqual(r["citations"], [])


    def test_assistant_answers_with_citations(self):
        c = SERVER.client("usr_oshiro")
        r = c.post("/api/assistant/ask", {"question": "Which procedure teaches spindle run-out?"})[1]
        self.assertTrue(r["answerable"])
        self.assertIn("PR-002", [ci["procedure_code"] for ci in r["citations"]])
        r = c.post("/api/assistant/ask", {"question": "What common mistakes should I look for when clearing chips?"})[1]
        self.assertTrue(r["answerable"])
        self.assertTrue(any(ci["kind"] == "mistake" for ci in r["citations"]))
        # unpublished (PR-004, under review) knowledge is never retrieved for a trainee
        r = c.post("/api/assistant/ask", {"question": "How do I dress the grinding wheel with the diamond?"})[1]
        self.assertTrue(all(ci["status"] == "PUBLISHED" for ci in r["citations"]))
        self.assertNotIn("PR-004", [ci["procedure_code"] for ci in r["citations"]])


class SignatureFlowTests(unittest.TestCase):
    """Acts 1–7 of the demo, persisted end-to-end through the API."""

    def test_full_knowledge_transfer_loop(self):
        admin, trainer, expert, trainee = (SERVER.client(u) for u in ("usr_morita", "usr_watanabe", "usr_tanaka", "usr_nguyen"))

        # ACT 1 — risk
        bore = lambda: next(s for s in admin.get("/api/risk")[1]["skills"] if s["code"] == "SK-BORE")  # noqa: E731
        before = bore()
        self.assertEqual(before["band"], "critical")
        self.assertEqual(before["documentation"]["status"], "none")

        # ACT 2 — capture
        sample = trainer.get("/api/samples/capture")[1]
        status, cap = trainer.patch("/api/captures/cap_bore", {"transcript": sample["transcript"], "transcript_source": "sample"})
        self.assertEqual(status, 200)
        self.assertTrue(cap["completeness"]["checks"]["source"])

        # ACT 3 — structure
        status, ex = trainer.post("/api/captures/cap_bore/extract", {"provider": "rule_based"})
        self.assertEqual(status, 200, ex)
        pid, vid = ex["procedure_id"], ex["version_id"]
        self.assertEqual(ex["meta"]["stats"]["steps"], ex["meta"]["stats"]["steps_verified"])
        proc = expert.get(f"/api/procedures/{pid}")[1]
        self.assertEqual(proc["version"]["status"], "AI_PROCESSED")
        c = proc["version"]["content"]
        self.assertTrue(all(s["evidence_quote"] for s in c["steps"]))
        # unreviewed knowledge is invisible to trainees and cannot be trained on
        self.assertEqual(trainee.get(f"/api/procedures/{pid}")[0], 404)
        self.assertEqual(trainee.get(f"/api/training/modules/{pid}")[0], 404)
        self.assertEqual(expert.post(f"/api/versions/{vid}/transition", {"action": "publish"})[0], 409)

        # ACT 4 — verify
        self.assertEqual(expert.post(f"/api/versions/{vid}/transition", {"action": "submit"})[0], 200)
        status, body = expert.post(f"/api/versions/{vid}/transition", {"action": "approve"})
        self.assertEqual(status, 422)
        self.assertTrue(body["error"]["details"]["blockers"])
        for oq in c["open_questions"]:
            self.assertEqual(expert.post(f"/api/versions/{vid}/open-questions/{oq['id']}/resolve",
                                         {"resolution": "Rock about 5 degrees each side until the needle reverses."})[0], 200)
        c = expert.get(f"/api/procedures/{pid}")[1]["version"]["content"]
        c["steps"][3]["instruction"] += " Keep the gauge handle in the insulated grip."
        status, saved = expert.put(f"/api/versions/{vid}/content", {"content": c, "note": "clarified zeroing"})
        self.assertEqual(status, 200)
        self.assertTrue(saved["content"]["steps"][3]["expert_edited"])
        step_ids = [s["step_id"] for s in saved["content"]["steps"]]
        r = expert.post(f"/api/versions/{vid}/confirm", {"item_ids": step_ids})[1]
        # confirming steps must not implicitly confirm linked safety items
        self.assertTrue(any(b.startswith("Safety item") for b in r["blockers"]))
        safety_ids = [s["id"] for s in saved["content"]["safety"]]
        r = expert.post(f"/api/versions/{vid}/confirm", {"item_ids": safety_ids})[1]
        self.assertEqual(r["blockers"], [])
        self.assertEqual(expert.post(f"/api/versions/{vid}/transition", {"action": "reject"})[0], 400)  # comment required
        self.assertEqual(expert.post(f"/api/versions/{vid}/transition", {"action": "approve", "comment": "ok"})[0], 200)
        self.assertEqual(expert.post(f"/api/versions/{vid}/transition", {"action": "publish"})[0], 200)

        # ACT 5 — transfer
        mod = trainee.get(f"/api/training/modules/{pid}")[1]
        dumped = json.dumps(mod["content"])
        self.assertNotIn("answer_index", dumped)
        self.assertNotIn('"correct"', dumped)
        steps = [s["step_id"] for s in mod["content"]["steps"]]
        self.assertTrue(trainee.post(f"/api/training/modules/{pid}/progress", {"completed_steps": steps, "guided_completed": True})[1]["guided_completed_at"])
        att = trainee.post(f"/api/training/modules/{pid}/attempts")[1]
        # trainee learns answers only through practice checks (grounded feedback), then answers the shuffled items
        key = {}
        for it in att["items"]:
            fb = trainee.post(f"/api/training/modules/{pid}/check", {"item_id": it["id"], "choice": 0})[1]
            self.assertIn("explanation", fb)
            original = next((q for q in mod["content"]["questions"] if q["id"] == it["id"]), None) or \
                next(s for s in mod["content"]["scenarios"] if s["id"] == it["id"])
            key[it["id"]] = it["options"].index(original["options"][fb["correct_index"]])
        status, res = trainee.post(f"/api/attempts/{att['attempt_id']}/submit", {"answers": key, "duration_s": 600})
        self.assertEqual(status, 200)
        self.assertEqual(res["result"]["score"], 100.0)
        self.assertEqual(res["attempt"]["signoff_status"], "pending")
        self.assertEqual(trainee.post(f"/api/attempts/{att['attempt_id']}/submit", {"answers": key})[0], 409)

        # persistence: a brand-new session sees the same stored result
        again = SERVER.client("usr_nguyen").get(f"/api/attempts/{att['attempt_id']}")[1]
        self.assertEqual(again["result"]["score"], 100.0)
        self.assertEqual(SERVER.client("usr_oshiro").get(f"/api/attempts/{att['attempt_id']}")[0], 403)

        # ACT 6 — measure
        matrix = trainer.get("/api/competency/matrix")[1]
        cell = matrix["cells"]["usr_nguyen:skl_bore"]
        self.assertEqual(cell["status"], "pending_signoff")
        self.assertEqual(trainee.post(f"/api/attempts/{att['attempt_id']}/signoff", {"decision": "approve"})[0], 403)
        status, so = trainer.post(f"/api/attempts/{att['attempt_id']}/signoff", {"decision": "approve", "feedback": "Observed live."})
        self.assertEqual(status, 200)
        self.assertEqual(so["competency_status"], "validated")
        self.assertEqual(trainer.get("/api/competency/matrix")[1]["cells"]["usr_nguyen:skl_bore"]["status"], "validated")

        # ACT 7 — preserve
        after = bore()
        self.assertLess(after["score"], before["score"])
        self.assertEqual(after["documentation"]["status"], "published")
        self.assertIn("Nguyen Van An", after["successors"]["validated"])
        self.assertGreater(after["factors"][0]["points"], 0, "single-holder gap must stay visible")
        status = admin.get("/api/demo/status")[1]
        self.assertTrue(all(a["done"] for a in status["acts"]))

        # Assistant now answers from the approved procedure, with citations
        ans = trainee.post("/api/assistant/ask", {"question": "Why do we let the housing soak before measuring?"})[1]
        self.assertTrue(ans["answerable"])
        self.assertTrue(any(ci["procedure_id"] == pid for ci in ans["citations"]))
        self.assertTrue(all(ci["status"] == "PUBLISHED" for ci in ans["citations"]))

        # Exports
        status, md = trainee.get(f"/api/procedures/{pid}/export?format=md")
        self.assertEqual(status, 200)
        self.assertIn("Zero the bore gauge", md)
        status, js = trainee.get(f"/api/procedures/{pid}/export?format=json")
        self.assertEqual(js["content"]["steps"][0]["evidence_quote"], c["steps"][0]["evidence_quote"])


class JapaneseCaptureTests(unittest.TestCase):
    def test_japanese_sample_capture_to_review(self):
        trainer, expert = SERVER.client("usr_watanabe"), SERVER.client("usr_tanaka")
        sample = trainer.get("/api/samples/capture?lang=ja")[1]
        self.assertIn("田中：", sample["transcript"])
        status, cap = trainer.post("/api/captures", {
            "title": sample["title"], "expert_id": "usr_tanaka", "machine": sample["machine"],
            "transcript": sample["transcript"], "transcript_source": "sample", "tips": sample["tips"],
            "mistakes": sample["mistakes"], "troubleshooting": sample["troubleshooting"], "safety_notes": sample["safety_notes"]})
        self.assertEqual(status, 200)
        trainer.patch(f"/api/captures/{cap['id']}", {"consent_given": True, "consent_scope": "社内教育目的に限り使用"})
        for t, kind, label, note in sample["markers"]:
            trainer.post(f"/api/captures/{cap['id']}/markers", {"t_seconds": t, "kind": kind, "label": label, "note": note})
        status, ex = trainer.post(f"/api/captures/{cap['id']}/extract", {"provider": "rule_based"})
        self.assertEqual(status, 200, ex)
        self.assertEqual(ex["meta"]["stats"]["steps"], ex["meta"]["stats"]["steps_verified"])
        proc = expert.get(f"/api/procedures/{ex['procedure_id']}")[1]
        c = proc["version"]["content"]
        self.assertEqual(c["language"], "ja")
        self.assertEqual(proc["version"]["status"], "AI_PROCESSED")
        self.assertTrue(any("「少し」" in q["text"] for q in c["open_questions"]))
        self.assertTrue(proc["approval_blockers"])  # still needs the expert, in any language
        status, md = expert.get(f"/api/procedures/{ex['procedure_id']}/export?format=md")
        self.assertIn("ボアとセッティングリングの清掃", md)


class VersioningTests(unittest.TestCase):
    def test_revision_preserves_published_version(self):
        expert = SERVER.client("usr_saito")
        before = expert.get("/api/procedures/prc_runout")[1]
        pub_id = before["procedure"]["published_version_id"]
        status, rev = expert.post("/api/procedures/prc_runout/revisions", {"change_summary": "Clarify magnetic base position"})
        self.assertEqual(status, 200)
        self.assertEqual(expert.post("/api/procedures/prc_runout/revisions", {})[0], 409)  # one open revision at a time
        d = expert.get(f"/api/procedures/prc_runout?version={rev['version_id']}")[1]
        c = d["version"]["content"]
        c["steps"][3]["instruction"] = "Mount the indicator's magnetic base on the turret face (non-rotating)."
        expert.put(f"/api/versions/{rev['version_id']}/content", {"content": c})
        diff = expert.get(f"/api/procedures/prc_runout/diff?a={pub_id}&b={rev['version_id']}")[1]
        changed = [s for s in diff["steps"] if s["change"] == "modified"]
        self.assertEqual(len(changed), 1)
        self.assertIn("instruction", changed[0]["fields"])
        # trainees still train on the published version
        mod = SERVER.client("usr_ishikawa").get("/api/training/modules/prc_runout")[1]
        self.assertEqual(mod["version"]["id"], pub_id)
        self.assertNotIn("turret face", json.dumps(mod["content"]))


if __name__ == "__main__":
    unittest.main()
