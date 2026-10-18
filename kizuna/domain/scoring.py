"""Deterministic, documented competency scoring.

Formula (all values 0–100):

    accuracy            = Σ weight(correct items) / Σ weight(all items) × 100
    critical_completion = critical items passed / critical items × 100   (100 if none)
    hint_penalty        = min(hints × HINT_PENALTY, MAX_HINT_PENALTY)
    score               = KNOWLEDGE_WEIGHT × accuracy + CRITICAL_WEIGHT × critical_completion − hint_penalty

    outcome = "critical_failure"  if any critical item is answered wrongly   (critical gate,
                                  independent of the numeric score)
            = "passed"            if score ≥ PASS_THRESHOLD
            = "failed"            otherwise

A "passed" outcome is never a validated competency by itself: it moves the
learner to `pending_signoff` and a trainer must approve the evidence. This is a
*simulated* knowledge assessment, not a hands-on certification.
"""
from __future__ import annotations

SCORING_RULES = {
    "version": "KF-SCORE-2026.1",
    "knowledge_weight": 0.6,
    "critical_weight": 0.4,
    "hint_penalty_points": 2.0,
    "max_hint_penalty": 10.0,
    "pass_threshold": 80.0,
    "critical_gate": True,
    "requires_trainer_signoff": True,
}


def assessment_items(content: dict) -> list[dict]:
    """Flatten questions and scenarios into gradeable items (stable order)."""
    items = []
    for q in content.get("questions", []):
        items.append({"id": q["id"], "kind": "question", "prompt": q["prompt"], "options": list(q["options"]),
                      "answer_index": q["answer_index"], "critical": bool(q.get("critical")),
                      "weight": float(q.get("weight", 1)), "skill": q.get("skill"), "step_id": q.get("step_id"),
                      "explanation": q.get("explanation", "")})
    for sc in content.get("scenarios", []):
        correct = next(i for i, o in enumerate(sc["options"]) if o["correct"])
        items.append({"id": sc["id"], "kind": "scenario", "prompt": sc["situation"],
                      "options": [o["text"] for o in sc["options"]], "answer_index": correct,
                      "critical": bool(sc.get("critical")), "weight": 1.0, "skill": sc.get("skill"),
                      "step_id": sc.get("step_id"), "explanation": sc.get("explanation", ""),
                      "option_feedback": [o.get("feedback", "") for o in sc["options"]]})
    return items


def score_attempt(content: dict, answers: dict, hints_used: list | None = None, rules: dict | None = None,
                  default_skill: str | None = None) -> dict:
    rules = rules or SCORING_RULES
    hints_used = list(dict.fromkeys(hints_used or []))
    items = assessment_items(content)
    if not items:
        raise ValueError("This module has no assessment items")

    graded = []
    total_w = correct_w = 0.0
    crit_total = crit_passed = 0
    per_skill: dict[str, dict] = {}
    for it in items:
        chosen = answers.get(it["id"])
        try:
            chosen = int(chosen) if chosen is not None else None
        except (TypeError, ValueError):
            chosen = None
        ok = chosen == it["answer_index"]
        total_w += it["weight"]
        correct_w += it["weight"] if ok else 0
        if it["critical"]:
            crit_total += 1
            crit_passed += 1 if ok else 0
        skill = it["skill"] or default_skill or "general"
        ps = per_skill.setdefault(skill, {"correct": 0, "total": 0})
        ps["total"] += 1
        ps["correct"] += 1 if ok else 0
        graded.append({**it, "chosen": chosen, "is_correct": ok, "hint_used": it["id"] in hints_used})

    accuracy = round(correct_w / total_w * 100, 1) if total_w else 0.0
    critical_completion = round(crit_passed / crit_total * 100, 1) if crit_total else 100.0
    hint_penalty = min(len(hints_used) * rules["hint_penalty_points"], rules["max_hint_penalty"])
    score = round(max(0.0, rules["knowledge_weight"] * accuracy + rules["critical_weight"] * critical_completion
                      - hint_penalty), 1)
    failed_critical = [g["id"] for g in graded if g["critical"] and not g["is_correct"]]
    if rules["critical_gate"] and failed_critical:
        outcome = "critical_failure"
    elif score >= rules["pass_threshold"]:
        outcome = "passed"
    else:
        outcome = "failed"
    for s in per_skill.values():
        s["pct"] = round(s["correct"] / s["total"] * 100, 1)
    review_steps = list(dict.fromkeys(g["step_id"] for g in graded if not g["is_correct"] and g["step_id"]))
    return {
        "rules_version": rules["version"],
        "items": graded,
        "accuracy": accuracy,
        "critical_total": crit_total,
        "critical_passed": crit_passed,
        "critical_completion": critical_completion,
        "hints_used": len(hints_used),
        "hint_penalty": hint_penalty,
        "score": score,
        "outcome": outcome,
        "failed_critical": failed_critical,
        "per_skill": per_skill,
        "review_steps": review_steps,
        "breakdown": {
            "knowledge_component": round(rules["knowledge_weight"] * accuracy, 1),
            "critical_component": round(rules["critical_weight"] * critical_completion, 1),
            "hint_penalty": -hint_penalty,
        },
    }


#: How competency status responds to an attempt outcome.
OUTCOME_TO_STATUS = {"passed": "pending_signoff", "failed": "reassessment_required",
                     "critical_failure": "remediation"}

#: How competency status responds to a trainer decision.
SIGNOFF_TO_STATUS = {"approve": "validated", "reject": "rejected", "remediate": "remediation",
                     "reassess": "reassessment_required"}
SIGNOFF_TO_ATTEMPT = {"approve": "approved", "reject": "rejected", "remediate": "remediation", "reassess": "reassess"}
