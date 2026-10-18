"""Evidence handling: transcript parsing, quote verification and
prompt-injection screening of uploaded source material.

The evidence verifier runs on *every* extraction result regardless of which
provider produced it. A step only counts as evidence-backed when its quote is
actually found in the captured source (or, for demonstrations, a timestamp
marker exists near the cited time). Anything else is downgraded to unverified.
"""
from __future__ import annotations

import re
import unicodedata

from .procedure_schema import format_timestamp, parse_timestamp

_TS = r"(\d{1,2}:\d{2}(?::\d{2})?)(?:[.,]\d+)?"
LINE_RE = re.compile(r"^\s*[\[(]?" + _TS + r"[\])]?\s*[-–—|]?\s*(?:(?P<spk>[^:：\]]{1,40})[:：]\s*)?(?P<text>.*)$")
CUE_RE = re.compile(r"^\s*" + _TS + r"\s*-->\s*" + _TS)


def parse_transcript(text: str) -> list[dict]:
    """Parse plain timestamped text, WebVTT or SRT into segments
    [{t: seconds|None, ts: 'HH:MM:SS'|None, speaker, text, line}]."""
    segments: list[dict] = []
    cue_time = None
    for lineno, raw in enumerate((text or "").splitlines(), 1):
        line = raw.strip()
        if not line or line.upper() == "WEBVTT" or line.isdigit():
            continue
        cue = CUE_RE.match(line)
        if cue:
            cue_time = parse_timestamp(cue.group(1))
            continue
        m = LINE_RE.match(line)
        if m and parse_timestamp(m.group(1)) is not None and m.group("text").strip():
            t = parse_timestamp(m.group(1))
            spk = (m.group("spk") or "").strip() or None
            segments.append({"t": t, "ts": format_timestamp(t), "speaker": spk,
                             "text": m.group("text").strip(), "line": lineno})
            cue_time = None
            continue
        if cue_time is not None:
            spk, body = None, line
            sm = re.match(r"^([^:：]{1,40})[:：]\s*(.+)$", line)
            if sm and len(sm.group(1).split()) <= 4:
                spk, body = sm.group(1).strip(), sm.group(2).strip()
            segments.append({"t": cue_time, "ts": format_timestamp(cue_time), "speaker": spk, "text": body, "line": lineno})
            continue
        if segments:
            segments[-1]["text"] += " " + line
        else:
            segments.append({"t": None, "ts": None, "speaker": None, "text": line, "line": lineno})
    return segments


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"[\"'`“”‘’「」『』]", "", text)
    text = re.sub(r"[^\w\s.%/+-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> list[str]:
    return normalize(text).split()


def quote_found(quote: str | None, source: str, min_overlap: float = 0.9) -> bool:
    """True when the quote appears verbatim (after normalisation) in the source,
    or ≥ min_overlap of its tokens appear in one contiguous window."""
    if not quote:
        return False
    nq, ns = normalize(quote), normalize(source)
    if not nq or len(nq) < 8:
        return False
    if nq in ns:
        return True
    q, s = _tokens(quote), _tokens(source)
    if len(q) < 4 or not s:
        return False
    win = len(q) + 3
    qset = q
    for i in range(0, max(1, len(s) - len(q) + 1)):
        window = s[i:i + win]
        hits = sum(1 for tok in qset if tok in window)
        if hits / len(q) >= min_overlap:
            return True
    return False


def marker_near(ts: str | None, markers: list[dict], tolerance_s: int = 5) -> bool:
    t = parse_timestamp(ts)
    if t is None:
        return False
    return any(abs(float(m["t_seconds"]) - t) <= tolerance_s for m in markers)


def verify_item(item: dict, transcript: str, notes: str, markers: list[dict]) -> dict:
    """Return evidence verification facts for one extracted item and mutate
    item['evidence_verified'] accordingly."""
    src = item.get("source_type")
    quote = item.get("evidence_quote")
    verified = False
    reason = ""
    if src == "transcript":
        verified = quote_found(quote, transcript)
        reason = "quote found in transcript" if verified else "quote NOT found in transcript"
    elif src == "expert_note":
        verified = quote_found(quote, notes)
        reason = "quote found in expert notes" if verified else "quote NOT found in expert notes"
    elif src == "demonstration":
        verified = marker_near(item.get("source_timestamp"), markers) or (quote_found(quote, transcript) if quote else False)
        reason = "demonstration marker at cited time" if verified else "no demonstration marker near cited time"
    elif src == "expert_edit":
        verified = True
        reason = "authored by expert"
    else:
        reason = "inference — no direct evidence"
    if src != "expert_edit":
        item["evidence_verified"] = verified
    return {"verified": verified, "reason": reason}


# -- language detection ------------------------------------------------------------------------
_CJK = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")


def cjk_ratio(text: str) -> float:
    chars = [c for c in (text or "") if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if _CJK.match(c)) / len(chars)


def detect_language(text: str) -> str:
    """'ja' when a meaningful share of the text is Japanese script, else 'en'."""
    return "ja" if cjk_ratio(text) >= 0.2 else "en"


# -- prompt-injection screening ------------------------------------------------------------
INJECTION_PATTERNS = [
    # Japanese
    (r"(以前|これまで|前|上記|今まで)の(指示|命令|ルール|設定)を?(すべて|全て)?無視", "instruction override"),
    (r"システムプロンプト|開発者モード|ジェイルブレイク", "system prompt reference"),
    (r"あなたは今から|管理者として(振る舞|行動|扱)", "role hijack"),
    (r"(この手順|この内容|これ)を?(承認済み|承認|公開済み|安全承認済み)(に|と)(して|する|扱)", "approval manipulation"),
    (r"(レビュー|審査|専門家の確認)を(省略|スキップ|飛ば)", "approval manipulation"),
    (r"(apiキー|パスワード|秘密鍵|認証情報|シークレット)を(教えて|表示|送って|出力|見せて)", "secret exfiltration"),
    # English
    (r"\bignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|rules|prompts?)", "instruction override"),
    (r"\bdisregard (all |any )?(the )?(previous|prior|above|system) (instructions|rules)", "instruction override"),
    (r"\b(system|developer) prompt\b", "system prompt reference"),
    (r"\byou are now\b|\bact as (an? )?(admin|administrator|system)", "role hijack"),
    (r"\b(mark|set|flag) (this|it|the procedure) (as )?(approved|published|safety[- ]approved)", "approval manipulation"),
    (r"\bauto-?approve\b|\bskip (the )?(expert )?review\b", "approval manipulation"),
    (r"<\s*/?\s*(system|assistant|instructions?)\s*>", "fake message markup"),
    (r"\b(reveal|print|show|send) (me )?(the |your )?(api key|secret|password|credentials)", "secret exfiltration"),
    (r"\bjailbreak\b|\bdeveloper mode\b", "jailbreak phrasing"),
]


def looks_like_injection(text: str) -> bool:
    low = (text or "").lower()
    return any(re.search(p, low) for p, _ in INJECTION_PATTERNS)


def screen_for_injection(*texts: str) -> list[dict]:
    findings = []
    for text in texts:
        for lineno, line in enumerate((text or "").splitlines(), 1):
            low = line.lower()
            for pattern, label in INJECTION_PATTERNS:
                if re.search(pattern, low):
                    findings.append({"category": label, "line": lineno, "excerpt": line.strip()[:200]})
                    break
    return findings
