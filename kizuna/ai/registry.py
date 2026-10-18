"""Provider registry and the extraction pipeline.

Pipeline (identical for every provider):
    screen for prompt injection â†’ provider.extract â†’ schema normalisation â†’
    evidence verification â†’ statistics
"""
from __future__ import annotations

import time

from ..domain.evidence import detect_language, looks_like_injection, quote_found, screen_for_injection, verify_item
from ..domain.procedure_schema import normalize_content
from .anthropic_provider import ClaudeAnswerer, ClaudeExtractor
from .base import CaptureInput, ExtractionError
from .rule_based import RuleBasedExtractor
from .video import NotConfiguredVideoAnalyzer


class Registry:
    def __init__(self, settings):
        self.settings = settings
        self.extractors = {"rule_based": RuleBasedExtractor(), "claude": ClaudeExtractor(settings)}
        self.video = NotConfiguredVideoAnalyzer()

    def statuses(self) -> dict:
        claude = self.extractors["claude"].status()
        return {
            "extractors": [p.status() for p in self.extractors.values()],
            "assistant": {"available": True, "mode": "claude" if claude["available"] else "extractive",
                          "reason": ("Claude composes answers from retrieved approved passages; citations are verified."
                                     if claude["available"] else
                                     "Extractive mode: answers are assembled from retrieved approved passages without an LLM.")},
            "video": self.video.status(),
        }

    def answerer(self):
        if self.extractors["claude"].status()["available"]:
            return ClaudeAnswerer(self.settings)
        return None

    def run_extraction(self, provider_name: str, cap: CaptureInput, markers: list[dict]) -> dict:
        provider = self.extractors.get(provider_name)
        if provider is None:
            raise ExtractionError("invalid_input", f"Unknown extraction provider '{provider_name}'")
        st = provider.status()
        if not st["available"]:
            raise ExtractionError("not_configured", st["reason"])
        started = time.perf_counter()
        injection = screen_for_injection(cap.transcript, cap.notes_blob)
        raw = provider.extract(cap)
        result = normalize_content(raw)
        content = result.content
        # Instruction-like injected text must never become procedure content,
        # whichever provider extracted it (it is still reported as an open question).
        dropped = 0
        for coll, fields in (("steps", ("instruction", "evidence_quote", "title")), ("tips", ("text", "evidence_quote")),
                             ("mistakes", ("text", "evidence_quote")), ("safety", ("text", "evidence_quote")),
                             ("failure_modes", ("symptom", "action", "evidence_quote"))):
            kept = [it for it in content[coll] if not any(looks_like_injection(it.get(f) or "") for f in fields)]
            dropped += len(content[coll]) - len(kept)
            content[coll] = kept
        if dropped:
            content = normalize_content(content).content
        notes = cap.notes_blob
        verification = []
        for coll in ("steps", "tips", "mistakes", "failure_modes", "safety"):
            for item in content[coll]:
                v = verify_item(item, cap.transcript, notes, markers)
                verification.append(v["verified"])
                if coll == "steps" and not v["verified"] and item["source_type"] != "inference":
                    item["confidence"] = min(item["confidence"], 0.4)
        ja = detect_language(cap.transcript if cap.transcript.strip() else notes) == "ja"
        for s in content["steps"]:
            if s.get("tolerance") and s["tolerance"].get("evidence_quote"):
                if not quote_found(s["tolerance"]["evidence_quote"], cap.transcript + "\n" + notes):
                    content["open_questions"].append({
                        "id": f"oq-tol-{s['step_id']}",
                        "text": (f"「{s['title']}」の公差を図面・仕様書と照合して確認してください。" if ja else
                                 f"Confirm the tolerance stated for \u201c{s['title']}\u201d against the drawing/specification."),
                        "reason": ("公差の引用元が原典に見つかりませんでした。" if ja else
                                   "The tolerance quote could not be found in the source material."),
                        "step_id": s["step_id"], "resolved": False, "resolution": ""})
        if injection:
            content["open_questions"].append({
                "id": "oq-injection", "step_id": None, "resolved": False, "resolution": "",
                "text": ("原典に指示のような文が含まれていたため、抽出時に無視しました。内容を確認してください。" if ja else
                         "Source material contains instruction-like text that was ignored by the extractor. Review it."),
                "reason": "; ".join(f"line {f['line']}: {f['excerpt'][:80]}" for f in injection[:3])})
        content = normalize_content(content).content
        steps = content["steps"]
        stats = {
            "steps": len(steps),
            "steps_verified": sum(1 for s in steps if s["evidence_verified"]),
            "steps_inferred": sum(1 for s in steps if s["source_type"] == "inference"),
            "steps_demonstrated": sum(1 for s in steps if s["source_type"] == "demonstration"),
            "items_total": len(verification), "items_verified": sum(verification),
            "tips": len(content["tips"]), "mistakes": len(content["mistakes"]),
            "failure_modes": len(content["failure_modes"]), "safety": len(content["safety"]),
            "questions": len(content["questions"]), "scenarios": len(content["scenarios"]),
            "open_questions": len(content["open_questions"]),
        }
        return {
            "content": content,
            "meta": {
                "provider": provider.name, "provider_label": provider.label, "provider_kind": provider.kind,
                "model": st.get("model"), "duration_ms": round((time.perf_counter() - started) * 1000),
                "video_uploaded": cap.has_video, "video_analyzed": False,
                "injection_findings": injection, "validation": result.as_dict(), "stats": stats,
            },
        }
