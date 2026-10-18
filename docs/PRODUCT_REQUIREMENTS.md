# Kizuna Forge — Product Requirements

**Problem statement:** JETRO-PS-03 — preserving and transferring the tacit expertise of retiring veteran engineers in Japanese manufacturing SMEs.
**Tagline:** *Preserve mastery. Transfer skill. Keep industry moving.*
**Name:** 絆 *kizuna* means "bond", the link between a master and a successor.

## 1. Problem

- A large part of a veteran's value is **tacit**: when a part is "cool enough" to measure, the sound of a gauge seating properly, which reading to distrust. This knowledge rarely reaches a manual.
- In an SME, a critical skill often lives in **one person**. When that person retires, the company loses capability, quality and sometimes customers.
- Successors are increasingly **younger or international workers**, for example Specified Skilled Workers from Vietnam or Nikkei Brazilians. They need clear, bilingual and evidence-based material, plus access to the veteran while the veteran is still there.
- Generic AI chatbots make this worse, not better. They produce plausible procedures with no traceable source, and a factory cannot accept that.

## 2. Users and roles

| Role | Example (simulated) | Needs |
|---|---|---|
| **Expert** | Hiroshi Tanaka, Senior Inspection Engineer, 41 years | Record what they know with low effort; stay in control of what gets published under their name |
| **Trainer / quality manager** | Kenji Watanabe | Run capture sessions, publish modules, judge and sign off competency |
| **Trainee** | Nguyen Van An (Specified Skilled Worker), Yuta Ishikawa | Learn a procedure with the expert's reasoning, practise decisions, prove competence |
| **Administrator / director** | Keiko Morita, Director of Manufacturing | See where knowledge-loss risk is highest; prove progress; own the data |

## 3. Product principles

1. **Evidence before fluency.** Every instruction traces to what the expert *demonstrated*, *said* or *wrote*, or is visibly marked as *AI-inferred*. Unknowns become explicit open questions.
2. **Humans approve.** Generated content is never training material until an authorised expert confirms each step and approves the version.
3. **Closed loop.** Capture, approval, training, assessment, sign-off and risk all run in one system, on one data model.
4. **Explainable numbers.** Competency and risk scores follow documented rules that anyone can recompute. No opaque "AI score".
5. **Honest simulation.** Assessments are labelled as simulated knowledge checks, never as certification. Where AI is not configured, the product says so.
6. **The knowledge belongs to the company.** Every procedure is versioned and can be exported as structured data.

## 4. Functional requirements by module (as implemented)

| Module | Requirement | Implementation |
|---|---|---|
| A · Command Center | KPIs, coverage, competency progress, at-risk skills, review queue, activity; all from data | `GET /api/dashboard`; `web/js/pages/overview.js` |
| B · Capture Studio | Drafts and resume, metadata, consent, video upload and streaming, transcript (typed, uploaded .vtt/.srt/.txt, or sample), attachments, timestamped demonstration markers, tacit notes | `services/capture.py`, `storage.py`, `pages/capture.js` |
| C · Extraction | Steps, checkpoints, tolerances (only if stated), tips, mistakes, failure modes, safety, questions, scenarios, open questions; schema validation; evidence verification; injection screening; state machine | `ai/rule_based.py`, `ai/anthropic_provider.py`, `ai/registry.py`, `domain/procedure_schema.py`, `domain/evidence.py`, `domain/workflow.py` |
| D · Knowledge Graph | Experts, procedures, steps, skills, machines, tools, failure modes, checkpoints, modules, employees, evidence; interactive and navigable | `services/graph.py`, `pages/graph.js` |
| E · Training Academy | Published modules only; guided mode with knowledge checks; challenge scenarios; final assessment with hints; answer keys kept server-side | `services/training.py`, `pages/academy.js`, `pages/module.js` |
| F · Competency engine | Attempts, accuracy, critical-step gate, time, hints, per-skill results, history, trainer sign-off, remediation, matrix | `domain/scoring.py`, `services/competency.py`, `pages/attempt.js`, `pages/competency.js` |
| G · Risk radar | Explainable four-factor score with recommended actions; retirement dates entered by admin only | `domain/risk.py`, `services/insights.py`, `pages/risk.js` |
| H · Mentorship | Discovery by skill, requests, in-app scheduling, notes, mentor feedback, follow-ups, learner progress | `services/mentorship.py`, `pages/mentorship.js` |
| I · Assistant | Retrieval over approved knowledge only, citations to procedure, step and timestamp, admits unknowns, offline extractive mode or Claude | `services/assistant.py`, drawer in `app.js` |
| J · Portability | Versions, superseded history, diffs, approval records, Markdown/JSON SOP export, CSV training records, full organisation archive | `services/procedures.py`, `services/admin.py` |
| Localisation | EN/JA interface; linked, reviewable JA translations, with a four-eyes rule for safety-relevant text; offline extraction of Japanese transcripts, with Japanese assessment items | `i18n.js`, `services/translations.py`, `ai/rule_based.py` |

## 5. Non-functional requirements

- Runs on a normal laptop: Python ≥ 3.10, no other dependencies, starts in about one second.
- Security: role-based access checked on the server, tenant isolation, CSRF defence, safe uploads, audit log, no secrets in the browser (see `ARCHITECTURE.md` §6).
- Accessibility: keyboard-reachable controls, visible focus, ARIA labels on icon buttons, responsive desktop, tablet and phone layouts, reduced-motion support.

## 6. Out of scope for the prototype (stated honestly)

- Automated video understanding. The adapter exists, but no model is configured. Experts annotate videos with markers instead.
- Real calendar or SSO integration. Scheduling and authentication are in-app.
- Machine translation. Translations are entered and reviewed by people.
- Any real-world certification of hands-on competence.
