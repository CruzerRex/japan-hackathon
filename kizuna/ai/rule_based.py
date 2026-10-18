"""Offline, deterministic knowledge extractor (English and Japanese).

This is a transparent heuristic pipeline (no machine learning, no network).
It genuinely parses the captured material — it does not return canned output:

1. Parse the timestamped transcript into segments and sentences.
2. Detect the language of each sentence (Japanese script share) and classify
   it with documented lexical rules for that language into: step, rationale
   ("why"), checkpoint, tolerance, tip (tacit cue), common mistake,
   troubleshooting branch, safety warning, prerequisite, or filler.
3. Group step sentences per timestamped segment into ordered steps; attach
   the other classes to the step they were spoken with.
4. Corroborate steps with the expert's timestamped demonstration markers
   (a matching marker's label becomes the step title).
5. Ingest the expert's written notes (tips / mistakes / troubleshooting /
   safety) as `expert_note` evidence and link them to steps by word overlap
   (words for English, kanji/katakana bigrams for Japanese).
6. Detect vague tacit phrases ("until it feels right", 「少し」「慣れれば」)
   and raise them as open questions for the expert to make explicit.
7. Generate assessment questions and troubleshooting scenarios *only* from the
   extracted content, in the capture's language, so every question traces
   back to evidence.

Confidence is rule-based and capped at 0.85 (see `_confidence`). Everything is
marked `requires_expert_review`.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

from ..domain.evidence import cjk_ratio, detect_language, parse_transcript
from ..domain.procedure_schema import format_timestamp, parse_timestamp
from .base import CaptureInput, ExtractionError


def _is_ja(text: str) -> bool:
    return cjk_ratio(text) >= 0.2


class Rule:
    """An English pattern and a Japanese pattern behind one `.search()`.
    Japanese text is NFKC-normalised (full-width digits/letters) before matching."""

    def __init__(self, en: str, ja: str, en_flags=re.I):
        self.en = re.compile(en, en_flags)
        self.ja = re.compile(ja)

    def search(self, s: str):
        if _is_ja(s):
            return self.ja.search(unicodedata.normalize("NFKC", s))
        return self.en.search(s)


# -- English lexicon -----------------------------------------------------------------------------
VERBS = {
    "adjust", "align", "apply", "attach", "blow", "bring", "calibrate", "check", "clamp", "clean", "close",
    "compare", "confirm", "dress", "dry", "enter", "feel", "fit", "hold", "insert", "inspect", "keep", "label",
    "leave", "let", "listen", "load", "lock", "log", "look", "loosen", "lower", "lubricate", "make", "mark",
    "measure", "mount", "move", "note", "open", "place", "press", "put", "raise", "read", "record", "release",
    "remove", "repeat", "replace", "reset", "return", "rock", "rotate", "run", "select", "set", "slide",
    "soak", "spray", "stabilise", "stabilize", "start", "stop", "swing", "take", "tighten", "touch", "turn",
    "use", "verify", "wait", "warm", "watch", "wipe", "write", "zero", "seat", "sweep", "tap", "lift",
    "sign", "finish", "tag", "hang", "call", "send", "cross", "wrap", "withdraw", "clear", "top", "report",
    "escalate", "quarantine", "isolate", "wash", "sharpen", "scrape", "blue", "reinsert", "reclean", "rezero",
}
ACTION_VERBS = VERBS | {"do", "get", "go", "ask", "tell", "contact", "notify", "reject", "discard"}
CHECK_START = {"check", "verify", "confirm"}
TITLE_TRIM = {"the", "a", "an", "on", "in", "at", "of", "to", "for", "with", "and", "into", "from", "that", "are",
              "is", "all", "within", "your", "by", "or", "until", "before", "after", "it", "this"}
DISCOURSE = re.compile(
    r"^(?:(?:ok(?:ay)?|alright|right|so|and|now|then|next|first(?:ly)?|second(?:ly)?|third(?:ly)?|finally|"
    r"after that|once that'?s done|once done|at this point|step \d+|lastly)[,:]?\s+)+", re.I)
MODAL = re.compile(r"^(?:you|we|i)\s+(?:need to|have to|must|should|want to|always|then|now|will|'ll)\s+", re.I)
TROUBLE = re.compile(r"^(?:and |but |so )?(?:if|when|whenever)\s+(.+?),\s*(?:then\s+)?(.+)$", re.I)

# -- Japanese lexicon ------------------------------------------------------------------------------
JA_DISCOURSE = re.compile(r"^(?:(?:まず|最初に|初めに|次に|それから|そして|続いて|最後に|では|はい|さて|ここで|その後|あとは)[、,]?\s*)+")
JA_STEP_END = re.compile(r"(?:ください|下さい|しましょう|します|ます|する|すること|しておく|ておく)[。！!]?$")
JA_NONSTEP_END = re.compile(r"(?:ないでください|ないで下さい|てはいけません|てはいけない|ないこと|あります|います|なります|"
                            r"わかります|分かります|れます|できます|思います|ません|です|でした|ですね)[。！!]?$")
JA_TROUBLE = re.compile(r"^(?:もし|万一|万が一)?(.+?(?:たら|なら|ならば|場合は|場合には|ときは|時は))[、,]\s*(.+)$")
JA_TITLE = re.compile(r"^(.{1,30}?)を(.{0,24}?)(?<![一-龥ァ-ヶー])([一-龥ァ-ヶー]{2,6}[ぁ-ゔ]{0,2})(?:して|し、|しま|する|させ)")
# quantities right before the verbal noun ("60分温度安定させる") are not part of the title noun
JA_TITLE_QTY = re.compile(r"(?:少なくとも|約|およそ)?\d+(?:\.\d+)?(?:分|秒|時間|回)(?:以上|以下|間)?(?=[一-龥ァ-ヶー])")
JA_CONTINUATION = re.compile(r"^(?:それでも|まだ|なお|それでもまだ)")

# -- shared rules (English | Japanese) ---------------------------------------------------------------
ESCALATION = Rule(r"\b(stop|call|tag|hold tag|nonconforming|report|quarantine|escalate|do not use)\b",
                  r"(止め|停止|呼ん|呼び|連絡|報告|保留|不適合|赤札|使用禁止|隔離)")
SAFETY = Rule(r"\b(lock ?out|tag ?out|loto|e-?stop|emergency stop|machine guard|guard|safety glasses|goggles|"
              r"gloves|ppe|hazard|pinch|burn|isolat\w*|never reach|power (?:is )?off|de-?energi[sz]\w*)\b",
              r"(保護メガネ|安全メガネ|保護眼鏡|保護具|手袋|非常停止|ロックアウト|タグアウト|電源を(切|遮断)|遮断|危険|挟まれ|"
              r"巻き込まれ|やけど|火傷|安全カバー|ガード|リフトアシスト|吊り具|腰を痛め)")
MISTAKE = Rule(r"\b(mistake|common error|people often|beginners?|new (?:guys|people|engineers)|newcomers?|"
               r"don'?t|do not|never|avoid|the trap|wrong|a lot of people)\b",
               r"(間違い|ミス|よくある|やりがち|新人|初心者|してはいけ|てはいけ|しないで|ないでください|絶対に|やってはダメ|禁止)")
TIP = Rule(r"\b(tip|trick|secret|my rule|i always|you'?ll feel|you will feel|you can feel|listen|sound|"
           r"by ear|by touch|watch for|look for|rule of thumb|old-timers|the way i|you'?ll hear|you can hear|"
           r"turns? around|feels?)\b",
           r"(コツ|秘訣|私のルール|私は必ず|経験則|感じ|感触|手触り|音|聞こえ|聞いて|引っかか|反転|ポイントは|目安)")
WHY = Rule(r"^(?:because|that'?s because|the reason|this is why|that'?s why|that way|otherwise|so that)\b",
           r"(^(?:なぜなら|理由は|というのも|そうしないと|そうすれば)|(?:から|ため)です[。]?$)")
CHECK = Rule(r"\b(must be|should be|has to be|have to be|within|no more than|not exceed|tolerance|spec|"
             r"before you move on|before moving on|confirm|verify|make sure)\b",
             r"(確認|以内|公差|規格|範囲内|でなければならない|次に進む前|合否|照合|点検)")
PREREQ = Rule(r"\b(before you start|before starting|you(?:'ll| will)? need|make sure you have|prerequisite)\b",
              r"(始める前に|作業前に|作業の前に|準備するもの|必要なもの|用意してください|用意します)")
PURPOSE = Rule(r"\b(purpose|the goal|we do this|the point of this)\b", r"(目的は|目的です|ねらいは|狙いは)")
TOLERANCE = Rule(
    r"((?:±|plus or minus|\+/-|plus\s*0\s*to\s*plus\s*)?\s*\d+(?:\.\d+)?\s*(?:to|-|–)?\s*(?:plus\s*)?\d*(?:\.\d+)?\s*"
    r"(?:µm|μm|um\b|microns?|mm\b|millimet(?:er|re)s?|°c|degrees(?: c(?:elsius)?)?|n·m|newton[- ]met(?:er|re)s?|"
    r"minutes?|seconds?))",
    r"((?:±|プラス\s*0\s*から\s*プラス\s*)?\d+(?:\.\d+)?\s*(?:から|〜|~|-)?\s*(?:プラス)?\d*(?:\.\d+)?\s*"
    r"(?:ミクロン|μm|マイクロメートル|ミリ(?:メートル)?|mm|℃|°C|度|分|秒|N·m|ニュートンメートル|kg))")
TOL_CTX = Rule(r"\b(within|tolerance|spec|must|should|drawing|calls for|at least|no more than|limit)\b",
               r"(以内|公差|規格|図面|必ず|以上|以下|範囲|指示|超え|少なくとも)")
CRITICAL = Rule(r"\b(must|has to|have to|before you move on|before moving on)\b",
                r"(必ず|なければならない|なければいけない|次に進む前|進む前に)")
VAGUE = Rule(r"\b(feels? right|until it feels|about right|a bit|a little|the usual|you(?:'ll)? (?:just )?know|"
             r"by experience|by eye|sounds? right|looks? right|firmly|snug|properly|enough|carefully|"
             r"you get used to it)\b",
             r"(少し|ちょっと|適当に|ちょうどいい|ちょうど良い|いい感じ|しっかり|きちんと|慣れれば|慣れると|感覚で|"
             r"大体|だいたい|十分に|軽く|適度に|いつもの)")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|(?<=[。！？])\s*")
STOP = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is", "it", "you", "your", "that",
        "this", "be", "at", "as", "if", "so", "then", "we", "i", "do", "not", "are", "from", "by", "its"}
_KANJI_KATA = re.compile(r"[゠-ヿ㐀-鿿]{2,}")


# -- language-aware helpers ---------------------------------------------------------------------------
def _clean(sentence: str) -> str:
    s = sentence.strip()
    if _is_ja(s):
        return JA_DISCOURSE.sub("", s)
    s = DISCOURSE.sub("", s)
    s = MODAL.sub("", s)
    return s[:1].upper() + s[1:] if s else s


def _first_word(s: str) -> str:
    m = re.match(r"(?:re-)?[A-Za-z]+", s, re.I)
    return m.group(0).lower().replace("-", "") if m else ""


def _ja_instruction(s: str) -> bool:
    return bool(JA_STEP_END.search(s)) and not JA_NONSTEP_END.search(s) and not s.endswith(("？", "?"))


def _is_step(sentence: str) -> bool:
    c = _clean(sentence)
    if _is_ja(c):
        return "を" in c and _ja_instruction(c)
    return _first_word(c) in VERBS


def _is_check_instruction(instr: str) -> bool:
    if _is_ja(instr):
        return bool(re.search(r"(確認|点検|照合|チェック)", instr))
    return _first_word(instr) in CHECK_START


def _title(instruction: str) -> str:
    """English: first clause, ≤7 words, no dangling function words.
    Japanese: noun-ending work-instruction style 「〇〇の清掃」 when the
    sentence has an object + verbal noun, else the first clause."""
    if _is_ja(instruction):
        s = _clean(unicodedata.normalize("NFKC", instruction))
        m = JA_TITLE.match(JA_TITLE_QTY.sub("", s))
        if m:
            obj = re.split(r"[、,]", m.group(1))[-1].strip()
            t = f"{obj}の{m.group(3)}" if obj else m.group(3)
            return t[:28]
        head = re.split(r"[、,。]", s, maxsplit=1)[0]
        head = head if len(head) >= 6 else s
        head = re.sub(r"(して|て)?(ください|下さい)[。]?$|(します|ます|する)[。]?$|。$", "", head)
        return head[:24] or "手順"
    s = re.split(r"[,;:(]| — | - |\. ", instruction, maxsplit=1)[0]
    words = s.rstrip(".!").split()[:7]
    while len(words) > 2 and (words[-1].lower() in TITLE_TRIM or re.fullmatch(r"[\d.]+", words[-1])):
        words.pop()
    t = " ".join(words)
    return t[:1].upper() + t[1:] if t else "Step"


def _stem(w: str) -> str:
    for suf in ("ings", "ing", "ed", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _words(text: str) -> set[str]:
    """English content words, plus kanji/katakana bigrams for Japanese text
    (hiragana is mostly particles and inflection, so it is ignored)."""
    out = {_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 2}
    for run in _KANJI_KATA.findall(unicodedata.normalize("NFKC", text or "")):
        out.update(run[i:i + 2] for i in range(len(run) - 1))
    return out


def _ja_symptom(cond: str) -> str:
    s = re.sub(r"^(?:もし|万一|万が一)", "", cond.strip())
    s = re.sub(r"たら$", "た", s)
    s = re.sub(r"(?:ならば|なら|場合には|場合は|ときは|時は)$", "", s)
    return s.strip("、, ")


def _is_trouble(sentence: str) -> tuple[str, str] | None:
    """`If/when <condition>, <instruction>` (EN) or `〜たら／〜場合は、<指示>` (JA).
    The action must itself be an instruction. Returns (condition, action)."""
    s = sentence.strip()
    if _is_ja(s):
        m = JA_TROUBLE.match(_clean(s))
        if not m:
            return None
        action = m.group(2).strip()
        if not _ja_instruction(action):
            return None
        return _ja_symptom(m.group(1)), action.rstrip("。")
    m = TROUBLE.match(s)
    if not m:
        return None
    action = _clean(m.group(2))
    if _first_word(action) not in ACTION_VERBS:
        return None
    return m.group(1).strip().rstrip(","), action.rstrip(".")


def _overlap(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def _confidence(timestamped: bool, imperative: bool, demonstrated: bool, has_check: bool) -> float:
    """Documented rule: 0.45 base, +0.15 timestamped source, +0.15 explicit
    imperative, +0.10 corroborating demonstration marker, +0.05 explicit
    checkpoint; capped at 0.85 for a heuristic extractor."""
    c = 0.45 + (0.15 if timestamped else 0) + (0.15 if imperative else 0) + (0.10 if demonstrated else 0) \
        + (0.05 if has_check else 0)
    return round(min(c, 0.85), 2)


def _shuffle(options: list[str], correct: int, key: str) -> tuple[list[str], int]:
    """Deterministic option shuffle so the correct answer is not always first."""
    order = sorted(range(len(options)), key=lambda i: hashlib.sha256(f"{key}:{i}".encode()).hexdigest())
    return [options[i] for i in order], order.index(correct)


def _lines(text: str) -> list[str]:
    out = []
    for raw in (text or "").splitlines():
        s = re.sub(r"^\s*(?:[-*•・]|\d+[.)])\s*", "", raw).strip()
        if len(s) > 3:
            out.append(s)
    return out


def _q(text: str) -> str:
    return f"「{text}」"


# -- generated-text templates per language ---------------------------------------------------------------
TEXT = {
    "en": {
        "q_check": "Before moving on from “{title}”, what must be confirmed?",
        "wrong_checks": ["Nothing specific — move on as soon as the action is done", "Only check it if the supervisor asks"],
        "src": "Source ({ts}): “{quote}”", "note": "expert note",
        "q_mistake_step": "During “{title}”, which of these did the expert identify as a common mistake?",
        "q_mistake": "Which of these did the expert identify as a common mistake?",
        "mistake_expl": "Expert warning ({ts}): “{text}”",
        "q_seq": "Which step comes immediately after “{a}”?",
        "seq_expl": "The demonstrated order is “{a}” → “{b}”.",
        "where_step": "During “{title}”", "where_none": "During the procedure",
        "scenario": "{where}, {symptom}. What is the appropriate next action?",
        "unsafe": ["Continue the procedure and mention it at the end of the shift",
                   "Adjust the recorded value so it matches the expected result"],
        "fb_ok": "Matches the expert's guidance for this situation.",
        "fb_other": "This is the expert's response to a different situation.",
        "fb_bad": "Not acceptable: it hides or ignores an abnormal condition instead of resolving it.",
        "sc_expl": "Expert guidance ({ts}): “{quote}”",
        "oq_vague": "What observable cue or measurable criterion defines “{phrase}” here?",
        "oq_vague_reason": "Tacit judgement at {ts}: “{quote}”",
        "oq_vague_step": "What observable cue or measurable criterion defines “{phrase}” in step “{title}”?",
        "oq_vague_step_reason": "Tacit judgement in the expert's instruction needs an explicit criterion.",
        "unknown_time": "unknown time",
        "oq_trouble": "What should the operator do when: “{line}”?",
        "oq_trouble_reason": "Troubleshooting note has no explicit response action.",
        "oq_purpose": "State the purpose of this procedure in one or two sentences.",
        "oq_purpose_reason": "No explicit purpose statement was found in the source.",
        "continuation": "{symptom} and it persists after: {action}",
        "scope": "{category} on {machine}", "procedure": "Procedure",
    },
    "ja": {
        "q_check": "「{title}」から次に進む前に、何を確認しなければなりませんか？",
        "wrong_checks": ["特になし。作業が終わればすぐ次に進む", "上司に言われたときだけ確認する"],
        "src": "出典（{ts}）：「{quote}」", "note": "熟練者のメモ",
        "q_mistake_step": "「{title}」で、熟練者がよくある間違いとして挙げたのはどれですか？",
        "q_mistake": "熟練者がよくある間違いとして挙げたのはどれですか？",
        "mistake_expl": "熟練者の注意（{ts}）：「{text}」",
        "q_seq": "「{a}」の直後に行う手順はどれですか？",
        "seq_expl": "実演された順序は「{a}」→「{b}」です。",
        "where_step": "「{title}」の途中で", "where_none": "作業中に",
        "scenario": "{where}、{symptom}。次に取るべき適切な行動はどれですか？",
        "unsafe": ["そのまま作業を続け、シフトの終わりに報告する", "期待値に合うように記録値を修正する"],
        "fb_ok": "この状況に対する熟練者の指示と一致しています。",
        "fb_other": "これは別の状況に対する熟練者の対応です。",
        "fb_bad": "不適切です。異常を解決せず、隠したり無視したりしています。",
        "sc_expl": "熟練者の指示（{ts}）：「{quote}」",
        "oq_vague": "ここでの「{phrase}」を判断するための、観察できる手がかりや測定できる基準は何ですか？",
        "oq_vague_reason": "{ts}の暗黙知：「{quote}」",
        "oq_vague_step": "手順「{title}」の「{phrase}」を判断するための、観察できる手がかりや測定できる基準は何ですか？",
        "oq_vague_step_reason": "熟練者の指示に含まれる感覚的な判断を、明確な基準にする必要があります。",
        "unknown_time": "時刻不明",
        "oq_trouble": "「{line}」のとき、作業者は何をすべきですか？",
        "oq_trouble_reason": "トラブル対応メモに具体的な対処が書かれていません。",
        "oq_purpose": "この手順の目的を1〜2文で記述してください。",
        "oq_purpose_reason": "原典に目的の記述が見つかりませんでした。",
        "continuation": "{symptom}（「{action}」の後も解消しない）",
        "scope": "{machine}における{category}", "procedure": "手順",
    },
}


class RuleBasedExtractor:
    name = "rule_based"
    label = "Offline rule-based extractor"
    kind = "deterministic"

    def status(self) -> dict:
        return {"available": True, "name": self.name, "label": self.label, "kind": self.kind,
                "reason": "Runs locally without network access. Deterministic English and Japanese lexical rules; "
                          "lower recall than an LLM."}

    # ------------------------------------------------------------------------------------
    def extract(self, cap: CaptureInput) -> dict:
        if not (cap.transcript.strip() or cap.notes_blob.strip() or cap.markers):
            raise ExtractionError("invalid_input", "Add a transcript, expert notes or demonstration markers before extracting")
        lang = detect_language(cap.transcript if cap.transcript.strip() else cap.notes_blob)
        T = TEXT[lang]
        segments = parse_transcript(cap.transcript)
        primary_skill = cap.skills[0]["code"] if cap.skills else None
        skill_codes = [s["code"] for s in cap.skills]
        markers = sorted(cap.markers, key=lambda m: float(m["t_seconds"]))
        used_markers: set[int] = set()

        steps: list[dict] = []
        safety, tips, mistakes, fms, prereqs, open_qs = [], [], [], [], [], []
        purpose = ""

        def marker_for(t) -> tuple[int, dict] | None:
            if t is None:
                return None
            best = None
            for i, m in enumerate(markers):
                if m["kind"] in ("step", "checkpoint", "safety") and abs(float(m["t_seconds"]) - t) <= 5:
                    if best is None or abs(float(m["t_seconds"]) - t) < abs(float(best[1]["t_seconds"]) - t):
                        best = (i, m)
            return best

        def best_step_by_text(text: str):
            best, score = None, 0.0
            for s in steps:
                sc = _overlap(text, s["title"] + " " + s["instruction"])
                if sc > score:
                    best, score = s, sc
            return best if score >= 0.3 else None

        for seg in segments:
            sentences = [s.strip() for s in SENT_SPLIT.split(seg["text"]) if s.strip()]
            seg_step = None
            pending: list[tuple[str, str]] = []
            for sent in sentences:
                if not purpose and PURPOSE.search(sent):
                    purpose = sent
                    continue
                if SAFETY.search(sent):
                    pending.append(("safety", sent))
                    continue
                if _is_trouble(sent):
                    pending.append(("trouble", sent))
                    continue
                if PREREQ.search(sent):
                    prereqs.append((sent, seg))
                    continue
                if WHY.search(sent):
                    pending.append(("why", sent))
                    continue
                if MISTAKE.search(sent) and not _is_step(sent):
                    pending.append(("mistake", sent))
                    continue
                if _is_step(sent):
                    instr = _clean(sent)
                    if seg_step is None:
                        mk = marker_for(seg["t"])
                        if mk:
                            used_markers.add(mk[0])
                        seg_step = {
                            # an expert-written demonstration label is a better title than a parsed clause
                            "title": mk[1]["label"].strip()[:60] if mk else _title(instr),
                            "instruction": instr, "why": "", "quality_check": "",
                            "source_type": "demonstration" if mk else "transcript",
                            "source_timestamp": seg["ts"], "evidence_quote": sent,
                            "safety_critical": False, "critical_checkpoint": False,
                            "requires_expert_review": True, "skills": [primary_skill] if primary_skill else [],
                            "tolerance": None, "_demonstrated": bool(mk),
                            "_marker_label": mk[1]["label"] if mk else None,
                        }
                        steps.append(seg_step)
                    else:
                        sep = "" if _is_ja(instr) else " "
                        seg_step["instruction"] += sep + instr
                        seg_step["evidence_quote"] += sep + sent
                    if CHECK.search(sent) or _is_check_instruction(instr):
                        sep = "" if _is_ja(instr) else " "
                        seg_step["quality_check"] = (seg_step["quality_check"] + sep + instr).strip()
                        if CRITICAL.search(sent):
                            seg_step["critical_checkpoint"] = True
                    if TOLERANCE.search(sent) and TOL_CTX.search(sent):
                        seg_step["tolerance"] = {"text": instr.rstrip(".。"), "evidence_quote": sent}
                    continue
                if TOLERANCE.search(sent) and TOL_CTX.search(sent):
                    pending.append(("tolerance", sent))
                    continue
                if CHECK.search(sent):
                    pending.append(("check", sent))
                    continue
                if TIP.search(sent):
                    pending.append(("tip", sent))
                    continue
                if VAGUE.search(sent):
                    pending.append(("vague", sent))
            # Attach pending items. Rationale/checks/tolerances belong to the step just
            # demonstrated; tips/mistakes/troubleshooting spoken outside a step are linked
            # by wording, or left general rather than guessed.
            for kind, sent in pending:
                if seg_step is not None:
                    target = seg_step
                elif kind in ("why", "check", "tolerance"):
                    target = steps[-1] if steps else None
                elif kind == "trouble":
                    target = best_step_by_text(_is_trouble(sent)[0])  # link by the condition only
                else:
                    target = best_step_by_text(sent)
                ev = {"source_type": "transcript", "source_timestamp": seg["ts"], "evidence_quote": sent}
                sid = id(target) if target is not None else None
                sep = "" if _is_ja(sent) else " "
                if kind == "safety":
                    safety.append({"text": _clean(sent), **ev, "_step": sid})
                    if target is not None:
                        target["safety_critical"] = True
                elif kind == "trouble":
                    symptom, action = _is_trouble(sent)
                    prev = fms[-1] if fms and fms[-1]["source_timestamp"] == seg["ts"] else None
                    if prev and (re.match(r"^(it|this|that|they)\b", symptom, re.I) or JA_CONTINUATION.match(symptom)):
                        # "If it is still out, ..." / 「それでも外れている場合は」 continues the previous branch
                        pa = prev["action"] if lang == "ja" else prev["action"][:1].lower() + prev["action"][1:]
                        symptom = T["continuation"].format(symptom=prev["symptom"], action=pa)
                        sid = prev["_step"]
                    fms.append({"symptom": symptom, "likely_cause": "", "action": action, **ev, "_step": sid})
                elif kind == "why" and target is not None:
                    target["why"] = (target["why"] + sep + sent).strip()
                elif kind == "mistake":
                    mistakes.append({"text": sent.strip(), "consequence": "", **ev, "_step": sid})
                elif kind in ("check", "tolerance") and target is not None:
                    target["quality_check"] = (target["quality_check"] + sep + sent).strip()
                    if CRITICAL.search(sent):
                        target["critical_checkpoint"] = True
                    if kind == "tolerance":
                        target["tolerance"] = {"text": _clean(sent).rstrip(".。"), "evidence_quote": sent}
                        target["critical_checkpoint"] = True
                elif kind == "tip":
                    tips.append({"text": sent.strip(), **ev, "_step": sid})
                if VAGUE.search(sent) and len(open_qs) < 6:
                    phrase = VAGUE.search(sent).group(0)
                    open_qs.append({"text": T["oq_vague"].format(phrase=phrase),
                                    "reason": T["oq_vague_reason"].format(ts=seg["ts"] or T["unknown_time"], quote=sent.strip()[:160]),
                                    "_step": sid})
            # Vague phrases inside step sentences themselves
            if seg_step is not None and VAGUE.search(seg_step["evidence_quote"]) and len(open_qs) < 6:
                phrase = VAGUE.search(seg_step["evidence_quote"]).group(0)
                if not any(oq["_step"] == id(seg_step) and phrase in oq["text"] for oq in open_qs):
                    open_qs.append({"text": T["oq_vague_step"].format(phrase=phrase, title=seg_step["title"]),
                                    "reason": T["oq_vague_step_reason"], "_step": id(seg_step)})

        # Demonstration markers that no spoken step covered become their own steps
        for i, m in enumerate(markers):
            if i in used_markers or m["kind"] != "step":
                continue
            instr = (m.get("note") or m["label"]).strip()
            steps.append({
                "title": m["label"].strip()[:60], "instruction": instr, "why": "", "quality_check": "",
                "source_type": "demonstration", "source_timestamp": format_timestamp(m["t_seconds"]),
                "evidence_quote": None, "safety_critical": False, "critical_checkpoint": False,
                "requires_expert_review": True, "skills": [primary_skill] if primary_skill else [],
                "tolerance": None, "_demonstrated": True, "_marker_label": m["label"],
            })
        # Non-step markers become tips / mistakes / safety with demonstration evidence
        for m in markers:
            ev = {"source_type": "demonstration", "source_timestamp": format_timestamp(m["t_seconds"]),
                  "evidence_quote": None, "_step": None, "_t": float(m["t_seconds"])}
            sep = "：" if _is_ja(m["label"]) else ": "
            text = (m["label"] + (sep + m["note"] if m.get("note") else "")).strip()
            if m["kind"] == "tip":
                tips.append({"text": text, **ev})
            elif m["kind"] == "mistake":
                mistakes.append({"text": text, "consequence": "", **ev})
            elif m["kind"] == "safety":
                safety.append({"text": text, **ev})

        steps.sort(key=lambda s: (s["source_timestamp"] is None, s["source_timestamp"] or ""))

        # Expert-written notes ------------------------------------------------------------------
        def link_by_text(text: str):
            best, score = None, 0.0
            for s in steps:
                sc = _overlap(text, s["title"] + " " + s["instruction"])
                if sc > score:
                    best, score = s, sc
            return id(best) if best is not None and score >= 0.25 else None

        def note_ev(line: str) -> dict:
            return {"source_type": "expert_note", "source_timestamp": None, "evidence_quote": line}

        for line in _lines(cap.tips):
            tips.append({"text": line, **note_ev(line), "_step": link_by_text(line)})
        for line in _lines(cap.mistakes):
            mistakes.append({"text": line, "consequence": "", **note_ev(line), "_step": link_by_text(line)})
        for line in _lines(cap.safety_notes):
            safety.append({"text": line, **note_ev(line), "_step": link_by_text(line)})
        for line in _lines(cap.troubleshooting):
            tr = _is_trouble(line)
            if not tr:
                m = re.match(r"^(.+?)\s*(?:->|→|=>|:|：)\s*(.+)$", line)
                tr = (m.group(1).strip(), _clean(m.group(2)).rstrip(".。")) if m else None
            if tr:
                fms.append({"symptom": tr[0], "likely_cause": "", "action": tr[1], **note_ev(line), "_step": link_by_text(line)})
            else:
                open_qs.append({"text": T["oq_trouble"].format(line=line[:120]), "reason": T["oq_trouble_reason"],
                                "_step": link_by_text(line)})
        for line in _lines(cap.expert_notes):
            if SAFETY.search(line):
                safety.append({"text": line, **note_ev(line), "_step": link_by_text(line)})
            elif MISTAKE.search(line):
                mistakes.append({"text": line, "consequence": "", **note_ev(line), "_step": link_by_text(line)})
            else:
                tips.append({"text": line, **note_ev(line), "_step": link_by_text(line)})

        # Demonstration-only tips get linked to the step closest in time
        for coll in (tips, mistakes, safety):
            for it in coll:
                if it.get("_t") is not None and it["_step"] is None and steps:
                    nearest = min(steps, key=lambda s: abs((parse_timestamp(s["source_timestamp"]) or 1e9) - it["_t"]))
                    it["_step"] = id(nearest)

        if not steps:
            raise ExtractionError("invalid_input", "No operational steps could be identified. Add timestamped "
                                  "transcript lines with explicit actions, or step markers, then retry.")

        # Assign ids and resolve links ------------------------------------------------------------
        ref = {}
        for n, s in enumerate(steps, 1):
            s["step_id"] = f"step-{n:03d}"
            ref[id(s)] = s["step_id"]
            s["confidence"] = _confidence(s["source_timestamp"] is not None, s["source_type"] != "demonstration" or
                                          bool(s["evidence_quote"]), s["_demonstrated"], bool(s["quality_check"]))
        for coll in (safety, tips, mistakes, fms, open_qs):
            for it in coll:
                it["step_id"] = ref.get(it.pop("_step", None))
                it.pop("_t", None)
        for s in steps:
            s.pop("_demonstrated", None)
            s.pop("_marker_label", None)
            if s["safety_critical"]:
                s["critical_checkpoint"] = True
        prerequisites = [_clean(p[0]) for p in prereqs]

        category = cap.task_category or T["procedure"]
        content = {
            "title": cap.title,
            "purpose": purpose or "",
            "scope": T["scope"].format(category=category, machine=cap.machine) if cap.machine else (cap.task_category or ""),
            "machine": cap.machine,
            "language": lang,
            "prerequisites": prerequisites,
            "equipment": [{"name": t, "kind": "tool"} for t in cap.tools] + [{"name": m, "kind": "material"} for m in cap.materials],
            "skills": skill_codes,
            "steps": steps,
            "safety": safety,
            "tips": tips,
            "mistakes": mistakes,
            "failure_modes": fms,
            "open_questions": open_qs,
        }
        if not purpose:
            content["open_questions"].insert(0, {"text": T["oq_purpose"], "reason": T["oq_purpose_reason"], "step_id": None})
        content["questions"], content["scenarios"] = self._assessment(content, primary_skill, lang)
        return content

    # ------------------------------------------------------------------------------------
    def _assessment(self, c: dict, skill: str | None, lang: str = "en") -> tuple[list[dict], list[dict]]:
        T = TEXT[lang]
        steps = c["steps"]
        by_id = {s["step_id"]: s for s in steps}
        questions: list[dict] = []
        checks = [s for s in steps if s["quality_check"]]
        checks.sort(key=lambda s: (not s["critical_checkpoint"], not s["safety_critical"]))
        for s in checks[:4]:
            others = [o["quality_check"][:180] for o in checks if o is not s][:2] + T["wrong_checks"]
            opts = [s["quality_check"][:180]] + others[:3]
            opts, ans = _shuffle(opts, 0, s["step_id"] + "chk")
            questions.append({
                "prompt": T["q_check"].format(title=s["title"]),
                "options": opts, "answer_index": ans, "step_id": s["step_id"], "skill": skill,
                "critical": bool(s["critical_checkpoint"] or s["safety_critical"]), "origin": "generated",
                "explanation": T["src"].format(ts=s["source_timestamp"] or T["note"], quote=(s["evidence_quote"] or s["instruction"])[:220])})
        for m in [m for m in c["mistakes"] if m["source_type"] == "transcript"][:3]:
            step = by_id.get(m["step_id"]) if m["step_id"] else None
            practices = [o["title"] for o in steps if o["step_id"] != m["step_id"]][1:4]
            if len(practices) < 2:
                continue
            opts, ans = _shuffle([m["text"]] + practices, 0, m["text"])
            questions.append({
                "prompt": T["q_mistake_step"].format(title=step["title"]) if step else T["q_mistake"],
                "options": opts, "answer_index": ans, "step_id": m["step_id"], "skill": skill, "critical": False,
                "origin": "generated",
                "explanation": T["mistake_expl"].format(ts=m["source_timestamp"] or m["source_type"].replace("_", " "), text=m["text"][:220])})
        if len(steps) >= 4:
            for idx in (0, len(steps) // 2):
                a, b = steps[idx], steps[idx + 1]
                distract = [s["title"] for s in steps if s not in (a, b)][-3:]
                opts, ans = _shuffle([b["title"]] + distract, 0, a["step_id"] + "seq")
                questions.append({
                    "prompt": T["q_seq"].format(a=a["title"]),
                    "options": opts, "answer_index": ans, "step_id": b["step_id"], "skill": skill, "critical": False,
                    "origin": "generated", "explanation": T["seq_expl"].format(a=a["title"], b=b["title"])})
        for n, q in enumerate(questions, 1):
            q["id"] = f"q-{n:03d}"

        scenarios = []
        fms = c["failure_modes"]
        for n, fm in enumerate(fms[:5], 1):
            if not fm["action"]:
                continue
            step = by_id.get(fm["step_id"]) if fm["step_id"] else None
            where = T["where_step"].format(title=step["title"]) if step else T["where_none"]
            other = [o["action"] for o in fms if o is not fm and o["action"] and o["action"] != fm["action"]][:2]
            texts = ([fm["action"]] + other + T["unsafe"])[:4]
            order, _ = _shuffle(list(range(len(texts))), 0, f"sc{n}{fm['symptom']}")
            options = []
            for i in order:
                fb = T["fb_ok"] if i == 0 else T["fb_other"] if i <= len(other) else T["fb_bad"]
                options.append({"text": texts[i], "correct": i == 0, "feedback": fb})
            scenarios.append({
                "id": f"sc-{n:03d}", "situation": T["scenario"].format(where=where, symptom=fm["symptom"].rstrip(".。")),
                "options": options, "step_id": fm["step_id"], "skill": skill,
                "critical": bool((step and (step["safety_critical"] or step["critical_checkpoint"])) or ESCALATION.search(fm["action"])),
                "origin": "generated",
                "explanation": T["sc_expl"].format(ts=fm["source_timestamp"] or fm["source_type"].replace("_", " "),
                                                   quote=(fm["evidence_quote"] or fm["action"])[:220])})
        return questions, scenarios
