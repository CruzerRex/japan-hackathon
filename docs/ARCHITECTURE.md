# Kizuna Forge — Architecture

## 1. Overview

```
 Browser (ES-module SPA, no build step)                         Python 3.10+ standard library only
┌──────────────────────────────────────────┐   JSON/HTTPS   ┌─────────────────────────────────────────────┐
│ web/js/app.js   shell, router, assistant │ ─────────────▶ │ kizuna/web.py   router, static, errors,     │
│ web/js/pages/*  one module per screen    │  cookie session│                 security headers, CSRF       │
│ web/js/ui.js    escaping templates, UI   │ ◀───────────── │ kizuna/auth.py  sessions + RBAC              │
│ web/js/charts.js, graph (SVG)            │                │ kizuna/api.py   routes → services            │
└──────────────────────────────────────────┘                │ kizuna/services/*  application services      │
                                                            │ kizuna/domain/*    pure business rules       │
                                                            │ kizuna/ai/*        provider adapters         │
                                                            │ kizuna/storage.py  protected file store      │
                                                            │ kizuna/db.py + migrations/  SQLite (WAL)     │
                                                            └─────────────────────────────────────────────┘
```

| Layer | Location | Responsibility |
|---|---|---|
| Presentation | `web/` | Rendering and interaction only. Every value is escaped by the `html` tagged template. Controls are hidden by role for convenience, never for security. |
| HTTP / transport | `kizuna/web.py`, `kizuna/api.py` | Routing, JSON parsing with size limits, error envelope `{error:{code,message,details}}`, CSP and security headers, ETag static files, HTTP Range for video. |
| Authentication / authorisation | `kizuna/auth.py` | PBKDF2 password hashes, hashed session tokens, `PERMISSIONS` map, `require()` on every protected route. |
| Application services | `kizuna/services/*.py` | Use cases (capture, extraction, review, training, sign-off, risk, graph, mentorship, assistant, export). Every query is scoped by `org_id`. |
| Business rules | `kizuna/domain/*.py` | Pure functions: review state machine, schema validation and approval gates, scoring, risk, evidence verification. Unit-tested without a database. |
| AI adapters | `kizuna/ai/*.py` | `ExtractionProvider` protocol; offline rule-based extractor; Claude provider; video adapter (not configured); the shared pipeline in `registry.py`. |
| Persistence | `kizuna/db.py`, `kizuna/migrations/*.sql` | SQLite with WAL and foreign keys, ordered SQL migrations tracked in `schema_migrations`. |
| File storage | `kizuna/storage.py` | Uploads outside the web root, random names, extension + MIME + magic-byte validation, SHA-256, size limits. |
| Observability | `kizuna/logging_setup.py`, `audit.py` | JSON-lines request and event logs without request bodies, plus an append-only business audit trail visible in Settings. |

## 2. Why this stack

The repository was empty and the machine had neither Node nor git; it had only Python 3.15. A stdlib-only server avoids native-wheel risk on a brand-new Python, needs zero installation, and matches what an SME pilot really needs: one process and one database file that is easy to back up, plus a credible on-premises story. The trade-off (hand-written router and charts) is contained in small, tested modules.

**Scaling path.** SQL in the services is portable, so the move to PostgreSQL is mechanical. Swap `ThreadingHTTPServer` for a WSGI/ASGI server behind nginx, move `storage.py` to S3-compatible object storage, and add SSO in `auth.py`. The domain and AI layers do not change.

## 3. Data model (key tables)

```
organizations ─┬─ users ── expert_skills ── skills
               ├─ capture_sessions ── capture_markers, files
               ├─ procedures ── procedure_versions (content_json) ── review_events, translations
               │                         ▲ latest_version_id / published_version_id
               ├─ training_progress, assessment_attempts ── signoffs, remediation_tasks
               ├─ competency_records (user × skill)
               ├─ knowledge_feedback (learner/trainer/analytics → next revision)
               ├─ mentorship_requests ── mentoring_sessions ── followup_tasks
               └─ audit_events
```

A procedure version stores its structured content as validated JSON (`domain/procedure_schema.py`): steps with `source_type`, `source_timestamp`, `evidence_quote`, `evidence_verified`, `confidence`, `expert_confirmed`, `safety_critical`, `critical_checkpoint` and `tolerance`, plus tips, mistakes, failure modes, safety, questions, scenarios and open questions. Keeping the whole document per version makes immutable history, diffs and exports trivial. Relationships the graph needs are derived at read time.

## 4. Review state machine

```
DRAFT ─extract─▶ AI_PROCESSED ─submit─▶ EXPERT_REVIEW ─approve─▶ APPROVED ─publish─▶ PUBLISHED ─(newer published)─▶ SUPERSEDED
                                            │  ├─reject (comment)─▶ REJECTED
                                            │  └─request_revision (comment)─▶ NEEDS_REVISION ─submit─▶ EXPERT_REVIEW
```

- **Approval gate** (`approval_blockers`): no schema errors, every extracted step confirmed by an expert (bulk confirmation only for evidence-verified, non-safety steps), every safety item confirmed, and every open question answered or dismissed.
- **Publish gate:** at least one assessment item.
- Only `PUBLISHED` versions reach trainees, assessments, the trainee assistant and the "documented" risk factor. Publishing supersedes, and never deletes, the previous version.

## 5. Extraction pipeline (`ai/registry.py`)

1. **Injection screen.** Instruction-like text in transcripts or notes ("ignore previous instructions", "mark this as approved", …) is reported and turned into an open question. It is never executed.
2. **Provider** (chosen explicitly, never silently swapped):
   - `rule_based` (default, offline, deterministic, **English and Japanese**). Each sentence's language is detected from its Japanese-script share, and a parallel Japanese rule set applies: 〜てください / 〜します instructions with を, 〜たら・〜場合は branches whose action is itself an instruction, 〜しないでください / 〜てはいけません mistakes, 「少し」「慣れれば」 vague phrases, units such as ミクロン, ℃ and 分. Titles take the noun-ending 「〇〇の清掃」 form, or the expert's demonstration-marker label. Japanese text is linked to steps by kanji/katakana bigram overlap. Generated questions, scenarios and open questions use the capture's language. Parses WebVTT, SRT or timestamped text. Lexical rules classify each sentence as step, rationale, checkpoint, tolerance, tip, mistake, troubleshooting branch, safety or prerequisite. Spoken steps are corroborated with demonstration markers; written notes are linked to steps by word overlap. Vague phrases ("a little", "properly") become open questions. Assessment items are generated only from extracted content. Confidence is rule-based and capped at 0.85.
   - `claude` (optional). Structured outputs against a JSON schema; the system prompt says source blocks are data, not instructions. Server-side fallbacks are enabled. Errors map to typed `ExtractionError`s (rate limit, auth, timeout, refusal, truncation, malformed output).
3. **Schema normalisation.** Malformed provider output is repaired or dropped with warnings, never trusted. Any extracted item whose text matches the injection screen is removed, whatever the provider or language.
4. **Evidence verification.** Each quote must be found in the transcript or notes (normalised exact match or ≥ 90 % token window), and each demonstration needs a marker within ±5 s. Anything else is marked unverified and its confidence lowered. A tolerance whose quote cannot be found becomes an open question.
5. **Recorded metadata:** provider, model, duration, `video_analyzed: false`, injection findings and statistics.

## 6. Security and privacy

| Control | Where |
|---|---|
| Server-side RBAC on every protected route (admin / expert / trainer / trainee) | `auth.PERMISSIONS`, `require()` |
| Tenant isolation: every query filters by the caller's `org_id`; cross-tenant IDs return 404 | services; `tests/test_api.py::test_tenant_isolation` |
| Sessions: 256-bit random token, only its SHA-256 stored, HttpOnly + SameSite=Strict (+ Secure via config) | `auth.py` |
| CSRF: mutations require the `X-Kizuna-Client` header | `web.App._dispatch_api` |
| Login throttling: 8 failures per 15 min per IP + email | `api.login` |
| Uploads: allow-listed extensions, magic-byte check, per-type size limits, random names outside the web root, tenant-checked streaming | `storage.py`, `api.file_get` |
| CSP `script-src 'self'`, X-Frame-Options DENY, nosniff; all UI output escaped | `web.SECURITY_HEADERS`, `ui.html` |
| Answer keys never sent before grading; options shuffled per attempt | `training._public_content`, `start_attempt` |
| Consent with scope required before any processing of a recording | `capture.extract` |
| Retirement dates entered only by admins; never inferred; hidden from trainees | `admin.set_retirement`, `insights.risk_radar` |
| Secrets only in server env; `.env` git-ignored | `config.py`, `.env.example` |
| Audit trail of captures, consent, extraction, review decisions, sign-offs, exports | `audit.py` |

No certification or regulatory compliance is claimed.

## 7. Assistant (RAG)

Passages are built per request from APPROVED and PUBLISHED versions the caller may see (trainees: PUBLISHED only), plus reviewed Japanese translations. Retrieval uses BM25 with simple stemming and CJK bigrams, intent boosts (mistakes, troubleshooting, why, skill lookup, assessment prep) and a query-coverage threshold. Extractive mode returns verbatim passages with citations. Claude mode composes an answer from those passages only, and citations that do not refer to a retrieved passage are dropped. If nothing qualifies, the assistant says the knowledge base has no answer and suggests a mentor.

## 8. Data portability strategy

- **Per procedure:** `GET /api/procedures/{id}/export?format=md|json` produces a human-readable SOP, or `kizuna-forge/procedure@1` JSON with full content, every evidence quote and timestamp, the approval record and the review history.
- **Training records:** `GET /api/export/training-records.csv`, one row per assessment attempt, explicitly labelled as simulated knowledge assessments.
- **Whole organisation:** `GET /api/export/org` (admin only, audited) produces `kizuna-forge/org-export@1` JSON with people (no credentials), skills and holders, every procedure version, captures, markers, file metadata and hashes, attempts with per-item results, competency records, sign-offs, remediation, translations, mentorship and the audit trail.
- Formats are plain JSON, CSV and Markdown, with stable ids and documented shapes, so a customer can leave with everything. Uploaded media stays in `data/uploads/<org>/`, and its SHA-256 is recorded in the export for integrity checks.

## 9. Deployment

- **Local / pilot:** `python run.py` (see README). Back up `data/` (one SQLite file plus uploads).
- **Private server:** run behind nginx or Caddy with TLS, `KIZUNA_COOKIE_SECURE=true`, `KIZUNA_DEMO_MODE=false`, and a process supervisor (systemd or NSSM).
- **Scale-out (future):** PostgreSQL, object storage, SSO/SAML, background worker for LLM extraction.
