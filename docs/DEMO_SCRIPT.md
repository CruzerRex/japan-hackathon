# Five-Minute Judging Demo — "Tanaka-san retires in March"

**Setup (before judges arrive):** `python run.py --reset`, open http://127.0.0.1:8000, choose **Keiko Morita (admin)**.
The **Demo tour** button in the top bar lists the seven acts, shows live ✓ status for each from the database, and switches persona in one click.

> Everything shown is a **simulated** organisation (Minato Precision Works). Say so once at the start; the banner says it too.

---

### 0:00 — Hook (20 s)
"Hiroshi Tanaka has inspected spindle-housing bores for 41 years. He can tell a housing is still warm by touching it. He retires on 31 March. Nothing he knows is written down. That is Japan's skills-transfer problem in one person."

### Act 1 · The risk (40 s) — *Keiko Morita, admin*
1. **Overview.** The KPIs come from live data: 5 of 9 skills are at risk, and there is a review queue.
2. Click **Precision bore inspection** in "Skills at risk" to open **Knowledge Risk**. It scores **99 · critical**.
3. Open **Why?** to show the four factors: 1 holder (25), retiring in about 5 months (20), no procedure (25), no successor (20), × 1.1 criticality.
4. "The score is explainable and comes with actions, not just a number. And we never infer a retirement date: an admin entered it."

### Act 2 · Capture (40 s) — *Kenji Watanabe, trainer* (Demo tour → Act 2)
1. **Knowledge Capture → SH-62 final bore inspection.** Metadata, recorded **consent with scope**, and Tanaka's demonstration markers (hand-feel check at 00:01:24, zero at the turning point at 00:02:40) are already there.
2. Click **Insert sample (simulated)**, or **Upload .vtt** with `samples/SH-62_bore_inspection_tanaka.vtt`. The app detects 16 timestamped lines.
3. Point at **Tacit knowledge**: tips, mistakes and troubleshooting in Tanaka's words.

### Act 3 · Structure (40 s)
1. Section 6 → **Run extraction** (offline rule-based provider; Claude appears if configured).
2. The result reads: 11 steps, 4 demonstrated, **11/11 evidence-verified**, tips, mistakes, troubleshooting branches, assessment items, **2 open questions**.
3. "Status is AI_PROCESSED, so this is not training material yet. Video analysed by AI: **no**. We say that explicitly."
4. **Open for expert review.**

### Act 4 · Verify (60 s) — *Hiroshi Tanaka, expert*
1. Each step carries an evidence badge (**Demonstrated / Said / Written note / Expert-authored / AI-inferred**) and the verbatim quote. Click **▶ 00:01:24** to jump to that line in the transcript.
2. **Tacit knowledge questions:** the extractor flagged "rock the gauge *a little*". Tanaka answers: *"Rock about 5° either side, just enough to see the needle reverse."* That answer becomes an expert-authored tip.
3. **Edit** one step to show the correction is recorded as an expert edit.
4. **Confirm all steps with verified evidence**, then confirm the **safety** items one by one. The checklist goes green.
5. **Submit for expert review → Approve** (the comment is recorded) **→ Publish as training**.
6. "Try approving earlier and the server refuses with the list of blockers. AI output can never approve itself."

### Act 5 · Transfer (60 s) — *Nguyen Van An, trainee (Specified Skilled Worker from Vietnam)*
1. **Training Academy → PR-005.** The *simulated assessment* banner is visible.
2. **Guided mode:** step, *why*, check, the expert's quote, tips and mistakes. Click **Understood** through a couple of steps.
3. **Challenge mode:** "The taper is more than 5 microns, what do you do?" Pick a wrong answer to show feedback that cites Tanaka.
4. **Final assessment:** options are shuffled per attempt and answer keys stay on the server. Use one **hint** (−2 points) and submit.
5. The result page shows the score breakdown with its formula, the critical gate, per-skill results and "Passed — awaiting trainer sign-off".
6. Optional: **Ask Kizuna** → "Why do we let the housing soak before measuring?" gives verbatim approved passages with citations.

### Act 6 · Measure (30 s) — *Kenji Watanabe, trainer*
1. **Competency Matrix → Awaiting your sign-off → Review.**
2. Add feedback, then **Approve — validate competency**. Nguyen's SK-BORE cell turns **VAL**.
3. "The AI never certifies anyone. The score is evidence; the trainer's recorded decision validates."

### Act 7 · Preserve (30 s) — *Keiko Morita, admin*
1. **Knowledge Risk:** SK-BORE drops from **99 to 61**. The documentation gap is 0 and there is one validated successor.
2. Two gaps remain visible on purpose: still a single holder, and still retiring, each with its next action (pair a second engineer, schedule a mentoring session).
3. **Knowledge Graph:** select *Precision bore inspection* to see Tanaka → PR-005 → steps → evidence → Training module → Nguyen.
4. **Export:** Markdown SOP or JSON with evidence. **Settings → Data & privacy** offers the full organisation archive.

### Close (20 s)
"Capture, verify, train, measure, preserve, in one closed loop where every instruction traces back to the master who taught it. That is how a 40-person shop keeps a 40-year skill."

---

**Backup talking points**
- Tenant isolation: sign in as *Sato Jun (other tenant)* from the sign-in page; Minato's data is invisible.
- Prompt injection: upload `samples/injection_test_transcript.txt` to a capture and extract. The instruction is flagged and ignored.
- Continuous improvement: **PR-002 → Learning insights** shows learner error rates per step and a learner's "unclear step" flag feeding the next revision.
- Versioning: **PR-001 → History**. v2 added the warm-up step after first-part size drift; **Compare** shows the diff.
- Japanese: switch the top bar to 日本語; PR-001 has a reviewed Japanese translation linked to v2.
- Japanese capture: create a new capture, click **日本語サンプル**, record consent and extract. Tanaka's demonstration in Japanese yields Japanese steps (「ボアとセッティングリングの清掃」), branches (「テーパが5ミクロンを超える場合は…」), tacit questions about 「少し」 and 「慣れれば」, and a Japanese assessment. Upload `samples/injection_test_transcript_ja.txt` to show a Japanese injection being flagged and kept out.
