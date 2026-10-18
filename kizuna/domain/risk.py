"""Explainable knowledge-loss risk scoring.

Each skill receives points from four transparent factors, then a criticality
multiplier. Every factor reports its inputs, points and a recommended action,
so the UI can show *why* a skill is at risk and what would reduce the risk.

    base  = holder_concentration (0–30) + retirement_exposure (0–20)
          + documentation_gap (0–25)    + successor_gap (0–20)          (max 95)
    score = min(100, round(base × (0.6 + 0.1 × criticality)))

Retirement exposure only uses retirement dates explicitly entered by an
authorised administrator. Nothing is inferred from age or other personal data.
"""
from __future__ import annotations

from datetime import date

RISK_RULES = {
    "version": "KF-RISK-2026.1",
    "holder_points": {0: 30, 1: 25, 2: 10},  # 3+ holders -> 0
    "holder_min_proficiency": 4,
    "retirement_points": 20,
    "retirement_full_weight_months": 12,
    "retirement_half_weight_months": 24,
    "documentation_points": {"none": 25, "in_progress": 15, "published": 0},
    "successor_points": {"none": 20, "in_training_only": 15, "one": 10},  # 2+ validated -> 0
    "bands": [(70, "critical"), (50, "high"), (30, "moderate"), (0, "low")],
}


def _months_until(d: str | None, today: date) -> float | None:
    if not d:
        return None
    try:
        target = date.fromisoformat(d[:10])
    except ValueError:
        return None
    return (target - today).days / 30.44


def band(score: int) -> str:
    for threshold, name in RISK_RULES["bands"]:
        if score >= threshold:
            return name
    return "low"


def assess_skill(skill: dict, holders: list[dict], documentation: dict, successors: dict,
                 today: date | None = None) -> dict:
    """
    skill:         {id, code, name, criticality}
    holders:       [{id, name, proficiency, retirement_date}] (proficiency >= 4 only)
    documentation: {"status": "none"|"in_progress"|"published", "procedures": [{id, code, title, status}]}
    successors:    {"validated": [names], "in_progress": [names]}
    """
    today = today or date.today()
    r = RISK_RULES
    factors = []

    # 1. Holder concentration ------------------------------------------------------
    n = len(holders)
    pts = r["holder_points"].get(n, 0)
    names = ", ".join(h["name"] for h in holders) or "nobody"
    factors.append({
        "key": "holder_concentration", "label": "Expert concentration", "points": pts, "max": 30,
        "detail": f"{n} recorded knowledge holder(s) at proficiency ≥ {r['holder_min_proficiency']}: {names}.",
        "action": None if pts == 0 else {
            "type": "mentorship", "label": "Pair a second engineer with " + (holders[0]["name"] if holders else "an external expert"),
            "route": "#/mentorship"},
    })

    # 2. Retirement exposure ----------------------------------------------------------
    weights = []
    soonest = None
    for h in holders:
        m = _months_until(h.get("retirement_date"), today)
        if m is None:
            weights.append(0.0)
            continue
        if m <= r["retirement_full_weight_months"]:
            weights.append(1.0)
        elif m <= r["retirement_half_weight_months"]:
            weights.append(0.5)
        else:
            weights.append(0.0)
        if m <= r["retirement_half_weight_months"] and (soonest is None or m < soonest[1]):
            soonest = (h, m)
    exposure = (sum(weights) / n) if n else 0.0
    pts = round(r["retirement_points"] * exposure)
    if soonest:
        h, m = soonest
        detail = (f"{h['name']} has a planned retirement date of {h['retirement_date']} "
                  f"(~{max(0, round(m, 1))} months). {sum(1 for w in weights if w)} of {n} holder(s) retire within 24 months.")
    else:
        detail = "No holder has an entered retirement date within 24 months."
    factors.append({
        "key": "retirement_exposure", "label": "Retirement exposure", "points": pts, "max": r["retirement_points"],
        "detail": detail,
        "action": None if pts == 0 else {"type": "capture", "label": f"Schedule knowledge capture with {soonest[0]['name']} before {soonest[0]['retirement_date']}",
                                         "route": "#/capture"},
    })

    # 3. Documentation gap ---------------------------------------------------------------
    status = documentation.get("status", "none")
    pts = r["documentation_points"].get(status, 25)
    procs = documentation.get("procedures", [])
    if status == "published":
        detail = "Covered by published procedure(s): " + ", ".join(p["code"] for p in procs if p["status"] == "PUBLISHED") + "."
        action = None
    elif status == "in_progress":
        p = procs[0]
        detail = f"Procedure {p['code']} exists but is not yet approved and published (status {p['status']})."
        action = {"type": "review", "label": f"Complete expert review of {p['code']}", "route": f"#/procedures/{p['id']}"}
    else:
        detail = "No procedure documents this skill. The knowledge exists only in people's heads."
        action = {"type": "capture", "label": "Record the expert demonstration in Capture Studio", "route": "#/capture"}
    factors.append({"key": "documentation_gap", "label": "Documentation gap", "points": pts, "max": 25,
                    "detail": detail, "action": action})

    # 4. Successor gap ------------------------------------------------------------------
    v, ip = successors.get("validated", []), successors.get("in_progress", [])
    if len(v) >= 2:
        pts, detail = 0, f"{len(v)} validated successors: {', '.join(v)}."
    elif len(v) == 1:
        pts, detail = r["successor_points"]["one"], f"Only one validated successor ({v[0]})."
    elif ip:
        pts, detail = r["successor_points"]["in_training_only"], f"No validated successor yet; in progress: {', '.join(ip)}."
    else:
        pts, detail = r["successor_points"]["none"], "No validated successor and nobody in training."
    pub = next((p for p in procs if p["status"] == "PUBLISHED"), None)
    if pts == 0:
        action = None
    elif pub:
        action = {"type": "training", "label": f"Enrol another engineer in {pub['code']} and sign off results",
                  "route": f"#/academy/{pub['id']}"}
    else:
        action = {"type": "training", "label": "Publish a procedure so successors can train", "route": "#/library"}
    factors.append({"key": "successor_gap", "label": "Successor gap", "points": pts, "max": 20,
                    "detail": detail, "action": action})

    base = sum(f["points"] for f in factors)
    multiplier = round(0.6 + 0.1 * int(skill["criticality"]), 2)
    score = min(100, round(base * multiplier))
    return {
        "skill_id": skill["id"], "code": skill["code"], "name": skill["name"], "name_ja": skill.get("name_ja"),
        "category": skill.get("category"), "criticality": skill["criticality"],
        "score": score, "band": band(score), "base_points": base, "multiplier": multiplier,
        "factors": factors, "holders": holders, "documentation": documentation, "successors": successors,
        "recommendations": [f["action"] for f in sorted(factors, key=lambda f: -f["points"]) if f["action"]],
        "rules_version": RISK_RULES["version"],
    }
