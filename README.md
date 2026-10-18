# 絆 Kizuna Forge

**Preserve mastery. Transfer skill. Keep industry moving.**

Kizuna Forge turns what a retiring veteran engineer *demonstrates, says and writes* into **evidence-linked procedures**. An expert must approve every procedure. Successors then train on them, competence is measured with transparent rules, and the system shows how much knowledge-loss risk has been removed.

Built for **JETRO problem statement PS-03** (tacit-knowledge transfer in Japanese manufacturing SMEs).

```
Expert recording → Knowledge extraction → Evidence-backed graph → Interactive training
→ Competency assessment → Expert validation → Organisational memory
```

## What makes it different

| | |
|---|---|
| **Evidence-linked knowledge** | Every step is labelled *Demonstrated*, *Said*, *Written note*, *Expert-authored* or *AI-inferred*, with the verbatim quote and timestamp. Quotes are checked against the source; anything unsupported is marked unverified. |
| **Tacit knowledge, made explicit** | Sensory cues, decision points, common mistakes and "if X then Y" branches are extracted. Vague phrases ("rock it *a little*", 「少し揺らして」) become questions the expert must answer. |
| **English and Japanese capture** | The offline extractor detects the language of each sentence and applies English or Japanese rules: 〜てください instructions, 〜たら／〜場合は branches, 〜しないでください warnings, and noun-ending titles such as 「ボアとセッティングリングの清掃」. It generates questions and scenarios in the capture's language. |
| **Humans approve** | A review state machine (DRAFT → AI_PROCESSED → EXPERT_REVIEW → APPROVED → PUBLISHED, plus REJECTED and NEEDS_REVISION). Every step needs expert confirmation, and unapproved content never reaches trainees. |
| **Closed loop** | Capture → approval → guided and challenge training → assessment with critical-step gate → trainer sign-off → competency matrix → risk radar. |
| **Explainable risk** | A four-factor knowledge-loss score per skill (holder concentration, retirement exposure, documentation gap, successor gap), with recommended actions. |
| **Owned knowledge** | Versioned procedures with diffs, Markdown and JSON SOP export, CSV training records, and a full organisation archive. |

## Prerequisites

- **Python 3.10 or newer.** Tested on Python 3.15.0 on Windows 11.
- Nothing else. No npm, no database server, no API keys, no internet connection. Fonts load from Google Fonts when online and fall back to system fonts offline.

## Quick start

```bash
python run.py --reset
```

Then open **http://127.0.0.1:8000** and pick a demo persona. `--reset` wipes and re-seeds the simulated demo organisation. A plain `python run.py` keeps existing data, and seeds automatically on first run. On Windows you can use `py` instead of `python`.

| Persona (simulated) | Role | Use it for |
|---|---|---|
| Keiko Morita | admin | Overview, risk radar, settings, exports, retirement dates |
| Hiroshi Tanaka | expert | Reviewing and approving extracted procedures (retires 2027-03-31) |
| Masao Kobayashi / Emiko Saito | expert | PR-004 awaiting review / mentoring |
| Kenji Watanabe | trainer | Capture studio, extraction, competency sign-off |
| Nguyen Van An, Yuta Ishikawa, Mei Takahashi, Ricardo Oshiro | trainee | Training Academy, assessments, mentorship |
| Sato Jun | admin of a *second* tenant | Tenant isolation check |

Password sign-in also works for every simulated account: password `kizuna-demo-2026` (emails such as `watanabe@minato.example`). The one-click persona switcher exists only in demo mode and only for simulated organisations.

The five-minute judging walkthrough is in **[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)**. In the app, the **Demo tour** button tracks the seven acts live.

## Configuration

Copy `.env.example` to `.env` and adjust. Every setting is documented there. Common ones:

| Variable | Default | Purpose |
|---|---|---|
| `KIZUNA_PORT` | `8000` | HTTP port |
| `KIZUNA_DATA_DIR` | `./data` | SQLite database and uploads |
| `KIZUNA_DEMO_MODE` | `true` | Enables the persona switcher for simulated orgs. Set `false` for real use. |
| `KIZUNA_COOKIE_SECURE` | `false` | Set `true` behind HTTPS |
| `KIZUNA_ANTHROPIC_ENABLED` | `false` | Optional Claude extraction and assistant |
| `ANTHROPIC_API_KEY` | — | Server-side only, never sent to the browser |

### Optional: Claude provider

```bash
pip install anthropic
```

Then set `KIZUNA_ANTHROPIC_ENABLED=true` and `ANTHROPIC_API_KEY` in `.env`, and restart. "Claude (Anthropic API)" becomes selectable in the Capture Studio, and the assistant composes grounded answers. If the API is unavailable, the app reports the error; it never substitutes another provider or fabricates output. *This provider has not been exercised against the live API in this build (no key was available); see the test report.*

## Database setup

There is no separate step. On start the app applies the SQL migrations in `kizuna/migrations/` (tracked in `schema_migrations`). Commands:

```bash
python run.py --seed-only
```

re-seeds the demo database and exits.

```bash
python run.py --reset --port 8080
```

wipes and re-seeds, then serves on another port.

## Tests

```bash
python -m unittest discover -s tests -t .
```

The suite has 60 tests and runs in about 3 seconds. Unit tests cover the review state machine, schema validation, approval gates, scoring and risk rules, transcript parsing, evidence verification and injection screening, and English and Japanese extraction. Integration tests start the real HTTP server on a temporary database and cover authentication, CSRF, RBAC, tenant isolation, upload validation, consent, provider failure, the assistant, versioning and diff, and the **full 7-act signature workflow**. Results are in [docs/TEST_REPORT.md](docs/TEST_REPORT.md).

## Deployment

- **Single machine / pilot:** `python run.py --host 0.0.0.0` behind a TLS reverse proxy (Caddy or nginx), with `KIZUNA_DEMO_MODE=false` and `KIZUNA_COOKIE_SECURE=true`, kept running by systemd (Linux) or NSSM (Windows). Back up the `data/` folder.
- **Private / on-premises:** the same single process inside the customer network. No outbound connections unless Claude is enabled.
- **Scale-out path:** PostgreSQL, object storage, SSO, and a WSGI/ASGI server. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) §9.

No deployment to a hosted environment has been performed for this submission.

## Repository layout

```
run.py                     launcher (migrate, seed, serve)
kizuna/
  config.py, logging_setup.py, db.py, migrations/   configuration, logs, persistence
  web.py, api.py, auth.py, audit.py, storage.py     HTTP, routes, RBAC, audit, uploads
  domain/      workflow.py, procedure_schema.py, scoring.py, risk.py, evidence.py
  ai/          base.py, rule_based.py, anthropic_provider.py, video.py, registry.py
  services/    capture, procedures, training, competency, insights, graph, assistant,
               mentorship, translations, admin
  seed/        content.py (simulated org & procedures), seeder.py
web/           index.html, css/app.css, js/{app,api,ui,i18n,charts}.js, js/pages/*.js
tests/         test_domain.py, test_extraction.py, test_api.py, helpers.py
samples/       SH-62 transcripts (.vtt, English and Japanese) for upload, prompt-injection test transcripts (EN/JA)
docs/          PRODUCT_REQUIREMENTS, ARCHITECTURE, IMPLEMENTATION_PLAN, DEMO_SCRIPT,
               BUSINESS_MODEL, TEST_REPORT
```

## Honest limitations

- No video-understanding model is configured. Videos are stored and streamed, and experts add timestamped demonstration markers. The extraction record always states `video_analyzed: false`.
- The default extractor is rule-based: transparent and offline, but with lower recall than an LLM on unstructured speech. Its English and Japanese rules were tuned on clean, scripted demonstrations. Recall on real shop-floor speech (fillers, dialect, cross-talk, speech-to-text errors) has not been measured.
- Assessments are **simulated knowledge assessments**, not certification for operating equipment.
- All demo people, companies and procedures are fictional. Numeric values quoted in demo procedures must not be used on real parts.

## Most valuable next improvements

1. Video understanding adapter: suggested markers from a video model, which experts confirm.
2. Live-API verification and evaluation set for the Claude extractor (precision and recall against expert-annotated captures).
3. Speech-to-text ingestion for Japanese shop-floor audio (with furigana-aware term glossary).
4. PostgreSQL and object storage, plus SSO for multi-site customers.
5. Hands-on practical sign-off checklists (observed task performance) alongside the knowledge assessment.
6. Machine-assisted translation drafts (always human-reviewed) for Vietnamese and Portuguese.
