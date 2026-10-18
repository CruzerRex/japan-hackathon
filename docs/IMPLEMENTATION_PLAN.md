# Kizuna Forge — Implementation Plan

## 1. Repository audit (2026-10-18)

| Item | Finding |
|---|---|
| Working directory | `D:\japan` — **empty**. No README, manifests, source, tests or config existed. |
| Version control | `git` is **not installed** on this machine, so the project could not be initialised as a repository. All files are plain files; run `git init` once git is available. A `.gitignore` is provided. |
| Node.js / npm | **Not installed**. |
| Python | Python **3.15.0** (python.org install manager), SQLite **3.53.4** with **FTS5** available. |
| Existing frontend/backend/DB/AI/auth/deploy | None — nothing to preserve or migrate. |

Nothing existed to reuse, so the stack was chosen from scratch to fit this machine and the target customer.

## 2. Stack decision

**Backend: Python standard library only** (`http.server`, `sqlite3`, `hashlib`, `json`, `unittest`).
**Frontend: dependency-free ES-module single-page app** (no bundler, no npm).
**Optional:** the official `anthropic` Python SDK, loaded lazily only when the Claude extraction / assistant provider is enabled.

Rationale:

1. **Runs on a normal laptop with zero installs.** The only prerequisite is Python ≥ 3.10. Judges and pilot customers can run `python run.py --reset` and get a seeded system.
2. **Fits the customer.** Japanese SMEs that treat craft knowledge as a trade secret often want on-premises or private deployment. A single-process app with a single SQLite file is easy to install, back up (copy one file), and audit.
3. **No wheel risk.** Python 3.15 is brand new; native-extension packages such as `pydantic-core` may not ship wheels for it yet. A stdlib core cannot be broken by that.
4. **A clear path to scale** (documented in `ARCHITECTURE.md`): the service layer is persistence-agnostic SQL, so it can move to PostgreSQL and a WSGI/ASGI server without rewriting the domain logic.

Trade-off accepted: we hand-write a small router, validators and SVG charts instead of using frameworks. Each piece is small, covered by tests, and kept in its own module.

## 3. Build order (vertical slice first)

| Priority | Work | Status |
|---|---|---|
| P0 | Config, structured logging, SQLite migrations, HTTP router, sessions + RBAC, audit log | done |
| P0 | Domain rules: review state machine, procedure schema validation, scoring rules, risk rules | done |
| P0 | Capture Studio: drafts, metadata, consent, transcript, uploads, timestamp markers, expert notes | done |
| P0 | Extraction pipeline: provider interface, offline rule-based extractor, Claude provider, evidence verifier, prompt-injection screening | done |
| P0 | Library: structured editor, validation, review/approve/reject/publish, versions | done |
| P0 | Training Academy: guided mode, challenge mode, final assessment, results | done |
| P0 | Competency engine: attempts, critical-step gating, trainer sign-off, remediation | done |
| P0 | Seeded demo org + signature scenario | done |
| P1 | Evidence citations, knowledge graph, risk radar, competency matrix, assistant (BM25 RAG), versions/diff, exports | done |
| P2 | Mentorship workflow, EN/JA UI, linked translations with safety review flags, settings | done |
| P2 | Deployment hardening (Postgres, object storage, SSO) | documented, not built |

## 4. Verification approach

- `python -m unittest discover -s tests` — unit tests for business rules and integration tests that drive the real HTTP API against a temporary database.
- Browser walkthrough of the 7-act signature demo, with reload checks for persistence.
- Results are recorded in `docs/TEST_REPORT.md`.
