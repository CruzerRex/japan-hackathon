"""Unit tests for business rules: review state machine, schema validation,
approval gates, competency scoring and knowledge-risk scoring."""
import unittest
from datetime import date

from kizuna.domain import workflow
from kizuna.domain.procedure_schema import approval_blockers, normalize_content, parse_timestamp, publish_blockers
from kizuna.domain.risk import assess_skill, band
from kizuna.domain.scoring import SCORING_RULES, score_attempt


def content(**kw):
    base = {
        "title": "Test procedure", "skills": ["SK-X"],
        "steps": [
            {"step_id": "step-001", "title": "Clean", "instruction": "Clean the bore.", "source_type": "transcript",
             "evidence_quote": "Clean the bore with alcohol.", "evidence_verified": True},
            {"step_id": "step-002", "title": "Measure", "instruction": "Measure six points.", "source_type": "inference",
             "critical_checkpoint": True},
        ],
        "questions": [
            {"id": "q1", "prompt": "Normal?", "options": ["a", "b"], "answer_index": 0, "step_id": "step-001"},
            {"id": "q2", "prompt": "Critical?", "options": ["a", "b", "c"], "answer_index": 2, "critical": True, "step_id": "step-002"},
        ],
        "scenarios": [{"id": "s1", "situation": "Out of tolerance", "critical": True,
                       "options": [{"text": "Stop", "correct": True}, {"text": "Continue", "correct": False}]}],
    }
    base.update(kw)
    return base


class WorkflowTests(unittest.TestCase):
    def test_happy_path(self):
        s = workflow.AI_PROCESSED
        for action in ("submit", "approve", "publish"):
            s = workflow.check_transition(s, action).target
        self.assertEqual(s, workflow.PUBLISHED)

    def test_cannot_publish_unreviewed(self):
        for state in (workflow.DRAFT, workflow.AI_PROCESSED, workflow.EXPERT_REVIEW, workflow.NEEDS_REVISION):
            with self.assertRaises(workflow.TransitionError):
                workflow.check_transition(state, "publish")

    def test_cannot_approve_without_review(self):
        with self.assertRaises(workflow.TransitionError):
            workflow.check_transition(workflow.AI_PROCESSED, "approve")

    def test_rejected_is_terminal(self):
        self.assertEqual(workflow.available_actions(workflow.REJECTED), [])
        self.assertEqual(workflow.available_actions(workflow.SUPERSEDED), [])

    def test_revision_loop(self):
        self.assertEqual(workflow.check_transition(workflow.EXPERT_REVIEW, "request_revision").target, workflow.NEEDS_REVISION)
        self.assertEqual(workflow.check_transition(workflow.NEEDS_REVISION, "submit").target, workflow.EXPERT_REVIEW)
        self.assertTrue(workflow.TRANSITIONS["reject"].needs_comment)


class SchemaTests(unittest.TestCase):
    def test_malformed_input_is_contained(self):
        r = normalize_content("not an object")
        self.assertFalse(r.ok)
        r = normalize_content({"title": "", "steps": [{"title": "x"}, "junk"],
                               "questions": [{"prompt": "bad", "options": ["only one"], "answer_index": 3}]})
        self.assertFalse(r.ok)
        paths = {i.path for i in r.errors}
        self.assertIn("title", paths)
        self.assertIn("steps[0].instruction", paths)
        self.assertEqual(r.content["questions"], [])  # invalid question dropped, not crashed

    def test_inference_never_counts_as_verified(self):
        r = normalize_content(content())
        step2 = r.content["steps"][1]
        self.assertEqual(step2["source_type"], "inference")
        self.assertFalse(step2["evidence_verified"])

    def test_claimed_source_without_quote_is_unverified(self):
        r = normalize_content({"title": "t", "steps": [{"title": "a", "instruction": "b", "source_type": "transcript",
                                                         "evidence_verified": True}]})
        self.assertFalse(r.content["steps"][0]["evidence_verified"])
        self.assertTrue(any("evidence_quote" in w.path for w in r.warnings))

    def test_bad_timestamp_and_confidence_are_cleaned(self):
        r = normalize_content({"title": "t", "steps": [{"title": "a", "instruction": "b", "source_timestamp": "99:99",
                                                         "confidence": "high"}]})
        s = r.content["steps"][0]
        self.assertIsNone(s["source_timestamp"])
        self.assertEqual(s["confidence"], 0.5)
        self.assertEqual(parse_timestamp("00:01:24"), 84)
        self.assertEqual(parse_timestamp("1:24"), 84)

    def test_approval_requires_human_confirmation(self):
        c = content()
        blockers = approval_blockers(c)
        self.assertEqual(len([b for b in blockers if b.startswith("Step")]), 2)
        for s in c["steps"]:
            s["expert_confirmed"] = True
        self.assertEqual(approval_blockers(c), [])

    def test_open_questions_block_approval(self):
        c = content(open_questions=[{"text": "How tight is snug?"}])
        for s in c["steps"]:
            s["expert_confirmed"] = True
        self.assertTrue(any("Open question" in b for b in approval_blockers(c)))

    def test_publish_requires_assessment(self):
        self.assertTrue(publish_blockers(content(questions=[])))
        self.assertEqual(publish_blockers(content()), [])


class ScoringTests(unittest.TestCase):
    def test_perfect_score(self):
        r = score_attempt(normalize_content(content()).content, {"q1": 0, "q2": 2, "s1": 0})
        self.assertEqual(r["score"], 100.0)
        self.assertEqual(r["outcome"], "passed")

    def test_documented_formula_and_hint_penalty(self):
        c = normalize_content(content(questions=content()["questions"] + [
            {"id": "q3", "prompt": "x", "options": ["a", "b"], "answer_index": 0},
            {"id": "q4", "prompt": "y", "options": ["a", "b"], "answer_index": 0}])).content
        r = score_attempt(c, {"q1": 0, "q2": 2, "s1": 0, "q3": 0, "q4": 1}, hints_used=["q1"])
        # accuracy 4/5 = 80 ; critical 2/2 = 100 ; 0.6*80 + 0.4*100 - 2 = 86
        self.assertEqual(r["accuracy"], 80.0)
        self.assertEqual(r["score"], 86.0)
        self.assertEqual(r["outcome"], "passed")
        self.assertEqual(r["hint_penalty"], SCORING_RULES["hint_penalty_points"])

    def test_critical_gate_overrides_score(self):
        c = normalize_content(content(questions=content()["questions"] + [
            {"id": f"x{i}", "prompt": "p", "options": ["a", "b"], "answer_index": 0} for i in range(10)])).content
        answers = {f"x{i}": 0 for i in range(10)} | {"q1": 0, "q2": 2, "s1": 1}  # misses one critical scenario
        r = score_attempt(c, answers)
        self.assertGreaterEqual(r["accuracy"], 90)
        self.assertEqual(r["outcome"], "critical_failure")
        self.assertEqual(r["failed_critical"], ["s1"])

    def test_unanswered_items_are_incorrect(self):
        r = score_attempt(normalize_content(content()).content, {})
        self.assertEqual(r["score"], 0.0)
        self.assertEqual(r["outcome"], "critical_failure")

    def test_hint_penalty_capped(self):
        c = normalize_content(content()).content
        r = score_attempt(c, {"q1": 0, "q2": 2, "s1": 0}, hints_used=[f"h{i}" for i in range(20)])
        self.assertEqual(r["hint_penalty"], SCORING_RULES["max_hint_penalty"])


class RiskTests(unittest.TestCase):
    skill = {"id": "s", "code": "SK-BORE", "name": "Bore", "criticality": 5}

    def test_single_retiring_holder_undocumented_is_critical(self):
        r = assess_skill(self.skill, [{"id": "u", "name": "Tanaka", "proficiency": 5, "retirement_date": "2027-03-31"}],
                         {"status": "none", "procedures": []}, {"validated": [], "in_progress": []}, date(2026, 10, 18))
        self.assertEqual([f["points"] for f in r["factors"]], [25, 20, 25, 20])
        self.assertEqual(r["score"], 99)
        self.assertEqual(r["band"], "critical")
        self.assertTrue(r["recommendations"])

    def test_documentation_and_successor_reduce_risk(self):
        r = assess_skill(self.skill, [{"id": "u", "name": "Tanaka", "proficiency": 5, "retirement_date": "2027-03-31"}],
                         {"status": "published", "procedures": [{"id": "p", "code": "PR-005", "title": "t", "status": "PUBLISHED"}]},
                         {"validated": ["Nguyen"], "in_progress": []}, date(2026, 10, 18))
        self.assertEqual(r["score"], round((25 + 20 + 0 + 10) * 1.1))
        self.assertEqual(r["band"], "high")

    def test_no_retirement_inference_without_date(self):
        r = assess_skill(self.skill, [{"id": "u", "name": "A", "proficiency": 5, "retirement_date": None}],
                         {"status": "none", "procedures": []}, {"validated": [], "in_progress": []}, date(2026, 10, 18))
        self.assertEqual(r["factors"][1]["points"], 0)

    def test_well_covered_skill_is_low(self):
        holders = [{"id": str(i), "name": str(i), "proficiency": 5, "retirement_date": None} for i in range(3)]
        r = assess_skill({**self.skill, "criticality": 3}, holders,
                         {"status": "published", "procedures": [{"id": "p", "code": "P", "title": "t", "status": "PUBLISHED"}]},
                         {"validated": ["a", "b"], "in_progress": []}, date(2026, 10, 18))
        self.assertEqual(r["score"], 0)
        self.assertEqual(band(r["score"]), "low")
        self.assertEqual(r["recommendations"], [])


if __name__ == "__main__":
    unittest.main()
