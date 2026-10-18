"""AI Knowledge Assistant — retrieval-augmented, citation-first.

Retrieval: BM25 over passages built from *approved* knowledge only
(PUBLISHED versions for everyone; APPROVED-but-unpublished versions are
additionally visible to staff roles). Draft / AI-processed content is never
retrieved. Japanese text is tokenised with character bigrams so JA questions
can match reviewed JA translations.

Answering:
- extractive mode (default, offline): the answer is assembled verbatim from
  the retrieved passages, each with its citation;
- Claude mode (if configured): Claude writes the answer from the passages
  only; citations that do not refer to a retrieved passage are discarded.
If nothing relevant is retrieved the assistant says the knowledge base does
not contain an answer — it never guesses.
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter

from ..ai.base import ExtractionError
from ..auth import can
from ..db import DB, loads
from ..domain.evidence import screen_for_injection
from ..logging_setup import log
from . import common

logger = logging.getLogger("kizuna.assistant")

STOP = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is", "it", "you", "your", "that", "this",
        "be", "at", "as", "if", "so", "do", "does", "what", "why", "how", "which", "when", "should", "i", "we", "are",
        "can", "my", "me", "there", "any", "about", "from", "by", "before", "after", "need", "look", "step"}
CJK = re.compile(r"[぀-ヿ㐀-鿿]+")
MIN_SCORE = 1.2
MIN_COVERAGE = 0.5


def _stem(w: str) -> str:
    for suf in ("ings", "ing", "ed", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    toks = [_stem(w) for w in re.findall(r"[a-z0-9]+", text) if w not in STOP and len(w) > 1]
    for run in CJK.findall(text):
        toks += [run[i:i + 2] for i in range(max(1, len(run) - 1))]
    return toks


def _passages(db: DB, org_id: str, user: dict) -> list[dict]:
    statuses = ("PUBLISHED", "APPROVED") if can(user, "procedure.read_unpublished") else ("PUBLISHED",)
    rows = db.all(f"""SELECT v.id AS version_id, v.version_no, v.status, v.content_json, p.id AS procedure_id, p.code, p.title
                      FROM procedure_versions v JOIN procedures p ON p.id = v.procedure_id
                      WHERE v.org_id = ? AND v.status IN ({','.join('?' * len(statuses))})""", (org_id, *statuses))
    skills = common.skills_by_code(db, org_id)
    out = []

    def add(r, kind, label, text, step=None, src=None):
        out.append({"procedure_id": r["procedure_id"], "procedure_code": r["code"], "procedure_title": r["title"],
                    "version_id": r["version_id"], "version_no": r["version_no"], "status": r["status"], "kind": kind,
                    "label": label, "text": text, "step_id": step["step_id"] if step else (src or {}).get("step_id"),
                    "step_title": step["title"] if step else None,
                    "source_type": (src or step or {}).get("source_type"),
                    "source_timestamp": (src or step or {}).get("source_timestamp"),
                    "evidence_quote": ((src or step or {}).get("evidence_quote") or "")[:300] or None,
                    "evidence_verified": (src or step or {}).get("evidence_verified")})

    for r in rows:
        c = loads(r["content_json"], {}) or {}
        steps = {s["step_id"]: s for s in c.get("steps", [])}
        skill_names = [skills[s]["name"] for s in c.get("skills", []) if s in skills]
        add(r, "overview", "Purpose", f"{c.get('title', '')}. {c.get('purpose', '')} Skills taught: {', '.join(skill_names)}. "
                                      f"Machine: {c.get('machine', '')}")
        for n, s in enumerate(c.get("steps", []), 1):
            text = f"Step {n}: {s['title']}. {s['instruction']}"
            if s.get("why"):
                text += f" Why: {s['why']}"
            if s.get("quality_check"):
                text += f" Check: {s['quality_check']}"
            if s.get("tolerance"):
                text += f" Stated requirement: {s['tolerance']['text']}"
            add(r, "step", f"Step {n} · {s['title']}", text, step=s)
        for t in c.get("tips", []):
            add(r, "tip", "Expert tip" + (f" · {steps[t['step_id']]['title']}" if t.get("step_id") in steps else ""),
                f"Expert tip: {t['text']}", step=steps.get(t.get("step_id")), src=t)
        for m in c.get("mistakes", []):
            add(r, "mistake", "Common mistake" + (f" · {steps[m['step_id']]['title']}" if m.get("step_id") in steps else ""),
                f"Common mistake: {m['text']} {m.get('consequence') or ''}", step=steps.get(m.get("step_id")), src=m)
        for f in c.get("failure_modes", []):
            add(r, "failure_mode", "Troubleshooting", f"Troubleshooting: if {f['symptom']}, then {f['action']}.",
                step=steps.get(f.get("step_id")), src=f)
        for s in c.get("safety", []):
            add(r, "safety", "Safety", f"Safety: {s['text']}", step=steps.get(s.get("step_id")), src=s)
        tr = db.one("SELECT content_json FROM translations WHERE version_id = ? AND locale = 'ja' AND status = 'reviewed'",
                    (r["version_id"],))
        if tr:
            tc = loads(tr["content_json"], {}) or {}
            for sid, ts in (tc.get("steps") or {}).items():
                if sid in steps:
                    add(r, "step_ja", f"手順 · {ts.get('title', '')}", f"{ts.get('title', '')}。{ts.get('instruction', '')}",
                        step=steps[sid])
    for i, p in enumerate(out, 1):
        p["pid"] = f"P{i}"
    return out


def _bm25(passages: list[dict], query: list[str], k1: float = 1.4, b: float = 0.75) -> list[tuple[float, dict]]:
    docs = [tokenize(p["text"] + " " + (p.get("step_title") or "")) for p in passages]
    n = len(docs)
    if not n or not query:
        return []
    avg = sum(len(d) for d in docs) / n
    df = Counter()
    for d in docs:
        df.update(set(d))
    scored = []
    for p, d in zip(passages, docs):
        tf = Counter(d)
        s = 0.0
        for q in set(query):
            if q not in tf:
                continue
            idf = math.log(1 + (n - df[q] + 0.5) / (df[q] + 0.5))
            s += idf * tf[q] * (k1 + 1) / (tf[q] + k1 * (1 - b + b * len(d) / avg))
        if s > 0:
            scored.append((s, p))
    scored.sort(key=lambda x: -x[0])
    return scored


def _intent(q: str) -> str:
    ql = q.lower()
    if re.search(r"which (procedure|module|training)|what (procedure|module) teach|teaches|教える|どの手順", ql):
        return "skill_lookup"
    if re.search(r"before (attempting|taking|the|my) .*assessment|prepare|review before|試験|準備", ql):
        return "assessment_prep"
    if re.search(r"mistake|error|wrong|pitfall|ミス|間違", ql):
        return "mistakes"
    if re.search(r"^why|why is|why do|why does|reason|なぜ|理由", ql):
        return "why"
    if re.search(r"if |what (do|should) i do when|troubleshoot|problem|異常|対処", ql):
        return "troubleshooting"
    return "general"


BOOST = {"mistakes": {"mistake": 1.8}, "troubleshooting": {"failure_mode": 1.8}, "why": {"step": 1.3},
         "general": {}, "skill_lookup": {"overview": 2.5}, "assessment_prep": {"step": 1.2, "mistake": 1.4}}


def _cite(p: dict) -> dict:
    return {k: p[k] for k in ("pid", "procedure_id", "procedure_code", "procedure_title", "version_no", "status", "kind",
                              "label", "step_id", "step_title", "source_type", "source_timestamp", "evidence_quote",
                              "evidence_verified")}


def ask(db: DB, org_id: str, user: dict, question: str, registry=None, procedure_id: str | None = None) -> dict:
    question = (question or "").strip()[:800]
    if len(question) < 3:
        return {"answerable": False, "blocks": [], "citations": [], "mode": "none",
                "message": "Please ask a complete question."}
    intent = _intent(question)
    flags = screen_for_injection(question)
    passages = _passages(db, org_id, user)
    if procedure_id:
        scoped = [p for p in passages if p["procedure_id"] == procedure_id]
        passages = scoped or passages
    q = tokenize(question)
    def boost(p: dict) -> float:
        b = BOOST.get(intent, {}).get(p["kind"], 1.0)
        if intent == "why" and " Why: " in p["text"]:
            b *= 1.8  # passages that state the expert's rationale explicitly
        return b

    q_terms = set(q)

    def coverage(p: dict) -> float:
        """Share of the question's distinct terms present in the passage. A single
        generic word in common (e.g. "clamp") must not count as an answer."""
        if not q_terms:
            return 0.0
        toks = set(tokenize(p["text"] + " " + (p.get("step_title") or "")))
        return len(q_terms & toks) / len(q_terms)

    scored = [(s * boost(p), p) for s, p in _bm25(passages, q) if coverage(p) >= MIN_COVERAGE]
    scored.sort(key=lambda x: -x[0])
    top = [p for s, p in scored if s >= MIN_SCORE][:5]
    extra_blocks = []

    if intent == "assessment_prep":
        # Personalised: steps the learner previously got wrong + critical checkpoints
        rows = db.all("SELECT result_json FROM assessment_attempts WHERE user_id = ? AND status = 'submitted' "
                      + ("AND procedure_id = ? " if procedure_id else "") + "ORDER BY submitted_at DESC LIMIT 3",
                      (user["id"], procedure_id) if procedure_id else (user["id"],))
        missed = []
        for r in rows:
            for it in (loads(r["result_json"], {}) or {}).get("items", []):
                if not it.get("is_correct") and it.get("step_id"):
                    missed.append(it["step_id"])
        crit = [p for p in passages if p["kind"] == "step" and "Check:" in p["text"]
                and (not procedure_id or p["procedure_id"] == procedure_id)]
        prio = [p for p in passages if p["kind"] == "step" and p["step_id"] in missed]
        top = list({p["pid"]: p for p in (prio + crit[:4] + top)}.values())[:6]
        if missed:
            extra_blocks.append({"type": "personal", "text": f"Your recent attempts missed {len(set(missed))} step(s); they are listed first."})

    if not top:
        mentors = db.all("""SELECT DISTINCT u.name FROM expert_skills e JOIN users u ON u.id = e.user_id
                            WHERE u.org_id = ? AND e.proficiency >= 4 AND u.active = 1 LIMIT 3""", (org_id,))
        return {"answerable": False, "intent": intent, "mode": "extractive", "citations": [], "injection_flags": flags,
                "blocks": [{"type": "unknown",
                            "text": "The approved knowledge base does not contain an answer to this question. "
                                    "I won't guess about machine-specific procedures, values or safety steps."}],
                "suggestion": "Ask a mentor" + (f" such as {', '.join(m['name'] for m in mentors)}" if mentors else "")
                              + ", or request that this topic be captured."}

    answerer = registry.answerer() if registry else None
    if answerer:
        try:
            data = answerer.answer(question, top)
            valid = {p["pid"]: p for p in top}
            cites = [c for c in data.get("citations", []) if c in valid]
            if data.get("answerable") and cites:
                blocks = [{"type": "verified", "text": data["answer"], "citations": cites}]
                if data.get("general_explanation"):
                    blocks.append({"type": "general", "text": data["general_explanation"]})
                return {"answerable": True, "intent": intent, "mode": "claude", "blocks": extra_blocks + blocks,
                        "citations": [_cite(valid[c]) for c in cites], "injection_flags": flags}
            if not data.get("answerable"):
                return {"answerable": False, "intent": intent, "mode": "claude", "citations": [], "injection_flags": flags,
                        "blocks": [{"type": "unknown", "text": data.get("answer") or
                                    "The approved knowledge base does not contain an answer to this question."}]}
            log(logger, logging.WARNING, "assistant_ungrounded_answer_discarded")
        except ExtractionError as e:
            log(logger, logging.WARNING, "assistant_llm_failed", code=e.code)
            extra_blocks.append({"type": "notice", "text": f"Claude is unavailable ({e.code}); showing retrieved passages instead."})

    lead = {"mistakes": "Common mistakes recorded by experts:", "troubleshooting": "Expert troubleshooting guidance:",
            "why": "What the approved procedure says:", "skill_lookup": "These approved procedures cover it:",
            "assessment_prep": "Review these before your assessment:", "general": "Relevant approved guidance:"}[intent]
    blocks = extra_blocks + [{"type": "lead", "text": lead}]
    for p in top:
        blocks.append({"type": "verified", "text": p["text"], "citations": [p["pid"]]})
    return {"answerable": True, "intent": intent, "mode": "extractive", "blocks": blocks,
            "citations": [_cite(p) for p in top], "injection_flags": flags}
