"""Structured-procedure schema: validation, normalisation and approval gates.

Every procedure version stores its content as JSON in this shape. Both the
extraction providers and the human editor go through `normalize_content`, so
malformed AI output and malformed user input are handled identically.

Evidence classes (shown to users as badges):
    demonstration  – the expert *showed* it (timestamped demonstration marker / video)
    transcript     – the expert *said* it (verbatim transcript excerpt)
    expert_note    – the expert *wrote* it (notes entered in the capture studio)
    expert_edit    – the expert authored/corrected it during review
    inference      – AI/heuristic inference; not directly evidenced
Unknowns are tracked separately in `open_questions`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SOURCE_TYPES = ("demonstration", "transcript", "expert_note", "expert_edit", "inference")
EVIDENCED_SOURCES = {"demonstration", "transcript", "expert_note"}
EQUIPMENT_KINDS = ("machine", "tool", "gauge", "material", "ppe", "other")
MAX_TEXT = 4000


@dataclass
class Issue:
    level: str  # "error" | "warning"
    path: str
    message: str

    def as_dict(self) -> dict:
        return {"level": self.level, "path": self.path, "message": self.message}


@dataclass
class ValidationResult:
    content: dict
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {"ok": self.ok, "errors": [i.as_dict() for i in self.errors],
                "warnings": [i.as_dict() for i in self.warnings]}


# -- small coercion helpers -------------------------------------------------------
def _s(value: Any, limit: int = MAX_TEXT) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()[:limit]


def _opt_s(value: Any, limit: int = MAX_TEXT) -> str | None:
    v = _s(value, limit)
    return v or None


def _b(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _str_list(value: Any, limit: int = 500) -> list[str]:
    out = []
    for v in _list(value):
        s = _s(v.get("name") if isinstance(v, dict) else v, limit)
        if s:
            out.append(s)
    return out


TS_RE = re.compile(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?:\.\d+)?$")


def parse_timestamp(value: Any) -> int | None:
    """'00:01:24' / '1:24' / 84 -> seconds."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value) if value >= 0 else None
    m = TS_RE.match(str(value).strip())
    if not m:
        return None
    h, mnt, sec = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
    if sec >= 60 or (m.group(1) and mnt >= 60):
        return None
    return h * 3600 + mnt * 60 + sec


def format_timestamp(seconds: int | float | None) -> str | None:
    if seconds is None:
        return None
    seconds = int(seconds)
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def _evidence_fields(item: dict, raw: dict, path: str, issues: list[Issue], default_source: str = "inference") -> None:
    src = _s(raw.get("source_type")) or default_source
    if src not in SOURCE_TYPES:
        issues.append(Issue("warning", f"{path}.source_type", f"Unknown source type '{src}' treated as inference"))
        src = "inference"
    item["source_type"] = src
    ts_raw = raw.get("source_timestamp")
    ts = parse_timestamp(ts_raw)
    if ts_raw not in (None, "") and ts is None:
        issues.append(Issue("warning", f"{path}.source_timestamp", f"Unreadable timestamp '{ts_raw}' removed"))
    item["source_timestamp"] = format_timestamp(ts)
    item["evidence_quote"] = _opt_s(raw.get("evidence_quote"), 1200)
    verified = _b(raw.get("evidence_verified"), False)
    if src in EVIDENCED_SOURCES and not item["evidence_quote"] and src != "demonstration":
        issues.append(Issue("warning", f"{path}.evidence_quote",
                            "Claims a source but has no evidence quote; treated as unverified"))
        verified = False
    if src == "inference":
        verified = False
    item["evidence_verified"] = verified
    item["expert_confirmed"] = _b(raw.get("expert_confirmed"), False)
    item["confirmed_by"] = _opt_s(raw.get("confirmed_by"), 120) if item["expert_confirmed"] else None
    item["expert_edited"] = _b(raw.get("expert_edited"), False)
    item["edited_by"] = _opt_s(raw.get("edited_by"), 120) if item["expert_edited"] else None


def _ids(items: list[dict], prefix: str) -> None:
    key = "step_id" if prefix == "step" else "id"
    seen = set()
    for i, it in enumerate(items, 1):
        iid = it.get(key)
        if not iid or iid in seen:
            iid = f"{prefix}-{i:03d}"
            while iid in seen:
                iid += "x"
        seen.add(iid)
        it[key] = iid


def normalize_content(raw: Any) -> ValidationResult:
    issues: list[Issue] = []
    if not isinstance(raw, dict):
        return ValidationResult({"title": "", "steps": []}, [Issue("error", "$", "Procedure content must be an object")])

    c: dict[str, Any] = {
        "title": _s(raw.get("title"), 200),
        "purpose": _s(raw.get("purpose"), 1500),
        "scope": _s(raw.get("scope"), 1500),
        "machine": _s(raw.get("machine"), 300),
        "prerequisites": _str_list(raw.get("prerequisites")),
        "skills": _str_list(raw.get("skills"), 60),
        "language": raw.get("language") if raw.get("language") in ("en", "ja") else None,
    }
    if not c["title"]:
        issues.append(Issue("error", "title", "Title is required"))

    equipment = []
    for i, e in enumerate(_list(raw.get("equipment"))):
        if isinstance(e, str):
            e = {"name": e}
        if not isinstance(e, dict) or not _s(e.get("name")):
            issues.append(Issue("warning", f"equipment[{i}]", "Equipment entry without a name was dropped"))
            continue
        kind = _s(e.get("kind")) or "other"
        equipment.append({"name": _s(e.get("name"), 200), "kind": kind if kind in EQUIPMENT_KINDS else "other"})
    c["equipment"] = equipment

    # Steps -----------------------------------------------------------------
    steps = []
    for i, s in enumerate(_list(raw.get("steps"))):
        path = f"steps[{i}]"
        if not isinstance(s, dict):
            issues.append(Issue("error", path, "Step must be an object"))
            continue
        step = {
            "step_id": _s(s.get("step_id"), 40),
            "title": _s(s.get("title"), 200),
            "instruction": _s(s.get("instruction")),
            "why": _s(s.get("why"), 1500),
            "quality_check": _s(s.get("quality_check"), 1500),
            "safety_critical": _b(s.get("safety_critical")),
            "critical_checkpoint": _b(s.get("critical_checkpoint")),
            "requires_expert_review": _b(s.get("requires_expert_review"), True),
            "skills": _str_list(s.get("skills"), 60),
        }
        try:
            conf = float(s.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
            issues.append(Issue("warning", f"{path}.confidence", "Non-numeric confidence replaced with 0.5"))
        step["confidence"] = round(min(1.0, max(0.0, conf)), 2)
        _evidence_fields(step, s, path, issues)
        tol = s.get("tolerance")
        if isinstance(tol, dict) and _s(tol.get("text")):
            step["tolerance"] = {"text": _s(tol.get("text"), 300), "evidence_quote": _opt_s(tol.get("evidence_quote"), 600)}
            if not step["tolerance"]["evidence_quote"]:
                issues.append(Issue("warning", f"{path}.tolerance",
                                    "Tolerance has no source quote — must be verified against the drawing/spec by an expert"))
        else:
            step["tolerance"] = None
        if not step["title"]:
            issues.append(Issue("error", f"{path}.title", "Step title is required"))
        if not step["instruction"]:
            issues.append(Issue("error", f"{path}.instruction", "Step instruction is required"))
        steps.append(step)
    _ids(steps, "step")
    if not steps:
        issues.append(Issue("error", "steps", "At least one step is required"))
    c["steps"] = steps
    step_ids = {s["step_id"] for s in steps}

    def link(item: dict, raw_item: dict, path: str) -> None:
        sid = _s(raw_item.get("step_id"), 40) or None
        if sid and sid not in step_ids:
            issues.append(Issue("warning", f"{path}.step_id", f"References unknown step '{sid}'; link removed"))
            sid = None
        item["step_id"] = sid

    # Safety items, tips, mistakes, failure modes ------------------------------
    def collect(key: str, prefix: str, text_key: str, extra: tuple[str, ...] = ()) -> list[dict]:
        out = []
        for i, it in enumerate(_list(raw.get(key))):
            path = f"{key}[{i}]"
            if isinstance(it, str):
                it = {text_key: it}
            if not isinstance(it, dict) or not _s(it.get(text_key)):
                issues.append(Issue("warning", path, f"Entry without '{text_key}' was dropped"))
                continue
            item = {"id": _s(it.get("id"), 40), text_key: _s(it.get(text_key), 1500)}
            for k in extra:
                item[k] = _s(it.get(k), 1500)
            link(item, it, path)
            _evidence_fields(item, it, path, issues)
            out.append(item)
        _ids(out, prefix)
        return out

    c["safety"] = collect("safety", "saf", "text")
    c["tips"] = collect("tips", "tip", "text")
    c["mistakes"] = collect("mistakes", "mis", "text", ("consequence",))
    c["failure_modes"] = collect("failure_modes", "fm", "symptom", ("likely_cause", "action"))
    for i, fm in enumerate(c["failure_modes"]):
        if not fm["action"]:
            issues.append(Issue("warning", f"failure_modes[{i}].action", "Failure mode has no response action"))

    # Assessment questions -------------------------------------------------------
    questions = []
    for i, q in enumerate(_list(raw.get("questions"))):
        path = f"questions[{i}]"
        if not isinstance(q, dict):
            issues.append(Issue("warning", path, "Question must be an object; dropped"))
            continue
        options = [o for o in (_s(x, 600) for x in _list(q.get("options"))) if o]
        try:
            ans = int(q.get("answer_index"))
        except (TypeError, ValueError):
            ans = -1
        if not _s(q.get("prompt")) or len(options) < 2 or not (0 <= ans < len(options)):
            issues.append(Issue("warning", path, "Question needs a prompt, ≥2 options and a valid answer; dropped"))
            continue
        try:
            weight = float(q.get("weight", 1))
        except (TypeError, ValueError):
            weight = 1.0
        item = {"id": _s(q.get("id"), 40), "prompt": _s(q.get("prompt"), 800), "options": options[:6],
                "answer_index": ans, "explanation": _s(q.get("explanation"), 1500),
                "skill": _s(q.get("skill"), 60) or None, "critical": _b(q.get("critical")),
                "weight": max(0.25, min(5.0, weight)), "origin": _s(q.get("origin"), 20) or "generated"}
        link(item, q, path)
        questions.append(item)
    _ids(questions, "q")
    c["questions"] = questions

    scenarios = []
    for i, sc in enumerate(_list(raw.get("scenarios"))):
        path = f"scenarios[{i}]"
        if not isinstance(sc, dict):
            continue
        opts = []
        for o in _list(sc.get("options")):
            if isinstance(o, dict) and _s(o.get("text")):
                opts.append({"text": _s(o.get("text"), 600), "correct": _b(o.get("correct")),
                             "feedback": _s(o.get("feedback"), 1000)})
        if not _s(sc.get("situation")) or len(opts) < 2 or sum(o["correct"] for o in opts) != 1:
            issues.append(Issue("warning", path, "Scenario needs a situation, ≥2 options and exactly one correct option; dropped"))
            continue
        item = {"id": _s(sc.get("id"), 40), "situation": _s(sc.get("situation"), 1200), "options": opts[:5],
                "explanation": _s(sc.get("explanation"), 1500), "skill": _s(sc.get("skill"), 60) or None,
                "critical": _b(sc.get("critical")), "origin": _s(sc.get("origin"), 20) or "generated"}
        link(item, sc, path)
        scenarios.append(item)
    _ids(scenarios, "sc")
    c["scenarios"] = scenarios

    open_qs = []
    for i, oq in enumerate(_list(raw.get("open_questions"))):
        if isinstance(oq, str):
            oq = {"text": oq}
        if not isinstance(oq, dict) or not _s(oq.get("text")):
            continue
        item = {"id": _s(oq.get("id"), 40), "text": _s(oq.get("text"), 800), "reason": _s(oq.get("reason"), 800),
                "resolved": _b(oq.get("resolved")), "resolution": _s(oq.get("resolution"), 1500)}
        link(item, oq, f"open_questions[{i}]")
        open_qs.append(item)
    _ids(open_qs, "oq")
    c["open_questions"] = open_qs

    if not questions:
        issues.append(Issue("warning", "questions", "No assessment questions — the training module will have no final assessment"))
    if questions and not any(q["critical"] for q in questions) and not any(s["critical"] for s in scenarios):
        issues.append(Issue("warning", "questions", "No critical checkpoint questions are marked"))
    return ValidationResult(c, issues)


def needs_confirmation(item: dict) -> bool:
    """An item must be explicitly confirmed by an expert before approval when it
    is not backed by verified evidence, or when it is safety-critical."""
    return (item.get("source_type") == "inference" or not item.get("evidence_verified")
            or bool(item.get("safety_critical"))) and item.get("source_type") != "expert_edit"


def approval_blockers(content: dict) -> list[str]:
    """Human-readable reasons a version cannot be approved yet."""
    result = normalize_content(content)
    blockers = [f"{e.path}: {e.message}" for e in result.errors]
    c = result.content
    for s in c["steps"]:
        # Every extracted step needs a human confirmation; steps the expert
        # authored during review are confirmed by authorship.
        if s["source_type"] != "expert_edit" and not s["expert_confirmed"]:
            why = ("safety-critical" if s["safety_critical"] else "AI-inferred" if s["source_type"] == "inference"
                   else "evidence not verified" if not s["evidence_verified"] else "extracted")
            blockers.append(f"Step '{s['title']}' ({why}) must be confirmed by an expert")
    for s in c["safety"]:
        if not s["expert_confirmed"]:
            blockers.append(f"Safety item '{s['text'][:60]}' must be confirmed by an expert")
    for oq in c["open_questions"]:
        if not oq["resolved"]:
            blockers.append(f"Open question unresolved: '{oq['text'][:80]}'")
    return blockers


def publish_blockers(content: dict) -> list[str]:
    c = normalize_content(content).content
    out = []
    if not c["questions"]:
        out.append("Add at least one assessment question before publishing a training module")
    return out
