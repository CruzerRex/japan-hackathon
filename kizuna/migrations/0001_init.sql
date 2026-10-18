-- Kizuna Forge initial schema.
-- Every tenant-owned table carries org_id; services always filter by the
-- caller's org_id (tenant isolation is enforced in the service layer and
-- covered by integration tests).

CREATE TABLE organizations (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    name_ja          TEXT,
    industry         TEXT,
    location         TEXT,
    employee_count   INTEGER,
    plan_tier        TEXT NOT NULL DEFAULT 'pilot',
    is_simulated     INTEGER NOT NULL DEFAULT 0,
    recording_policy TEXT,
    retention_days   INTEGER NOT NULL DEFAULT 3650,
    created_at       TEXT NOT NULL
);

CREATE TABLE users (
    id                    TEXT PRIMARY KEY,
    org_id                TEXT NOT NULL REFERENCES organizations(id),
    email                 TEXT NOT NULL UNIQUE,
    name                  TEXT NOT NULL,
    name_ja               TEXT,
    role                  TEXT NOT NULL CHECK (role IN ('admin','expert','trainer','trainee')),
    title                 TEXT,
    department            TEXT,
    locale                TEXT NOT NULL DEFAULT 'en',
    languages             TEXT,
    years_experience      INTEGER,
    bio                   TEXT,
    retirement_date       TEXT,
    retirement_entered_by TEXT REFERENCES users(id),
    retirement_entered_at TEXT,
    password_hash         TEXT NOT NULL,
    active                INTEGER NOT NULL DEFAULT 1,
    created_at            TEXT NOT NULL
);
CREATE INDEX idx_users_org ON users(org_id);

CREATE TABLE auth_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE skills (
    id          TEXT PRIMARY KEY,
    org_id      TEXT NOT NULL REFERENCES organizations(id),
    code        TEXT NOT NULL,
    name        TEXT NOT NULL,
    name_ja     TEXT,
    category    TEXT NOT NULL,
    criticality INTEGER NOT NULL CHECK (criticality BETWEEN 1 AND 5),
    description TEXT,
    UNIQUE (org_id, code)
);

-- People who hold a skill (experts, trainers). proficiency >= 4 counts as a
-- "knowledge holder" for risk purposes.
CREATE TABLE expert_skills (
    user_id     TEXT NOT NULL REFERENCES users(id),
    skill_id    TEXT NOT NULL REFERENCES skills(id),
    proficiency INTEGER NOT NULL CHECK (proficiency BETWEEN 1 AND 5),
    PRIMARY KEY (user_id, skill_id)
);

CREATE TABLE assets (
    id      TEXT PRIMARY KEY,
    org_id  TEXT NOT NULL REFERENCES organizations(id),
    kind    TEXT NOT NULL CHECK (kind IN ('machine','tool','gauge','material')),
    name    TEXT NOT NULL,
    name_ja TEXT,
    detail  TEXT
);

CREATE TABLE capture_sessions (
    id                  TEXT PRIMARY KEY,
    org_id              TEXT NOT NULL REFERENCES organizations(id),
    expert_id           TEXT NOT NULL REFERENCES users(id),
    created_by          TEXT NOT NULL REFERENCES users(id),
    title               TEXT NOT NULL,
    task_category       TEXT,
    machine             TEXT,
    tools_json          TEXT NOT NULL DEFAULT '[]',
    materials_json      TEXT NOT NULL DEFAULT '[]',
    skill_ids_json      TEXT NOT NULL DEFAULT '[]',
    experience_level    TEXT,
    transcript          TEXT NOT NULL DEFAULT '',
    transcript_source   TEXT NOT NULL DEFAULT 'none',
    expert_notes        TEXT NOT NULL DEFAULT '',
    tips                TEXT NOT NULL DEFAULT '',
    mistakes            TEXT NOT NULL DEFAULT '',
    troubleshooting     TEXT NOT NULL DEFAULT '',
    safety_notes        TEXT NOT NULL DEFAULT '',
    consent_given       INTEGER NOT NULL DEFAULT 0,
    consent_scope       TEXT,
    consent_recorded_by TEXT REFERENCES users(id),
    consent_at          TEXT,
    status              TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','extracted','archived')),
    procedure_id        TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX idx_capture_org ON capture_sessions(org_id);

CREATE TABLE capture_markers (
    id         TEXT PRIMARY KEY,
    capture_id TEXT NOT NULL REFERENCES capture_sessions(id) ON DELETE CASCADE,
    t_seconds  REAL NOT NULL,
    kind       TEXT NOT NULL CHECK (kind IN ('step','tip','mistake','checkpoint','safety')),
    label      TEXT NOT NULL,
    note       TEXT NOT NULL DEFAULT '',
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE files (
    id            TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES organizations(id),
    capture_id    TEXT REFERENCES capture_sessions(id) ON DELETE SET NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('video','image','document','transcript')),
    original_name TEXT NOT NULL,
    stored_name   TEXT NOT NULL,
    mime          TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    sha256        TEXT NOT NULL,
    uploaded_by   TEXT REFERENCES users(id),
    created_at    TEXT NOT NULL
);

CREATE TABLE procedures (
    id                   TEXT PRIMARY KEY,
    org_id               TEXT NOT NULL REFERENCES organizations(id),
    code                 TEXT NOT NULL,
    title                TEXT NOT NULL,
    owner_expert_id      TEXT REFERENCES users(id),
    capture_id           TEXT REFERENCES capture_sessions(id),
    latest_version_id    TEXT,
    published_version_id TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    UNIQUE (org_id, code)
);

CREATE TABLE procedure_versions (
    id                   TEXT PRIMARY KEY,
    procedure_id         TEXT NOT NULL REFERENCES procedures(id),
    org_id               TEXT NOT NULL REFERENCES organizations(id),
    version_no           INTEGER NOT NULL,
    status               TEXT NOT NULL CHECK (status IN ('DRAFT','AI_PROCESSED','EXPERT_REVIEW','NEEDS_REVISION','APPROVED','PUBLISHED','REJECTED','SUPERSEDED')),
    content_json         TEXT NOT NULL,
    extractor            TEXT,
    extraction_meta_json TEXT NOT NULL DEFAULT '{}',
    change_summary       TEXT,
    based_on_version_id  TEXT,
    created_by           TEXT REFERENCES users(id),
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    approved_by          TEXT REFERENCES users(id),
    approved_at          TEXT,
    published_by         TEXT REFERENCES users(id),
    published_at         TEXT,
    UNIQUE (procedure_id, version_no)
);

CREATE TABLE review_events (
    id          TEXT PRIMARY KEY,
    org_id      TEXT NOT NULL,
    version_id  TEXT NOT NULL REFERENCES procedure_versions(id),
    actor_id    TEXT REFERENCES users(id),
    from_status TEXT,
    to_status   TEXT NOT NULL,
    comment     TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE training_progress (
    id                  TEXT PRIMARY KEY,
    org_id              TEXT NOT NULL,
    user_id             TEXT NOT NULL REFERENCES users(id),
    procedure_id        TEXT NOT NULL REFERENCES procedures(id),
    version_id          TEXT NOT NULL REFERENCES procedure_versions(id),
    completed_steps     TEXT NOT NULL DEFAULT '[]',
    step_checks         TEXT NOT NULL DEFAULT '{}',
    challenge_results   TEXT NOT NULL DEFAULT '{}',
    guided_completed_at TEXT,
    started_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    UNIQUE (user_id, version_id)
);

CREATE TABLE assessment_attempts (
    id                 TEXT PRIMARY KEY,
    org_id             TEXT NOT NULL,
    user_id            TEXT NOT NULL REFERENCES users(id),
    procedure_id       TEXT NOT NULL REFERENCES procedures(id),
    version_id         TEXT NOT NULL REFERENCES procedure_versions(id),
    attempt_no         INTEGER NOT NULL,
    status             TEXT NOT NULL CHECK (status IN ('in_progress','submitted')),
    started_at         TEXT NOT NULL,
    submitted_at       TEXT,
    duration_s         INTEGER,
    hints_used         TEXT NOT NULL DEFAULT '[]',
    answers_json       TEXT NOT NULL DEFAULT '{}',
    result_json        TEXT,
    knowledge_accuracy REAL,
    critical_total     INTEGER,
    critical_passed    INTEGER,
    score              REAL,
    outcome            TEXT CHECK (outcome IN ('passed','failed','critical_failure')),
    signoff_status     TEXT NOT NULL DEFAULT 'not_applicable'
                       CHECK (signoff_status IN ('not_applicable','pending','approved','rejected','remediation','reassess'))
);
CREATE INDEX idx_attempts_user ON assessment_attempts(user_id);

CREATE TABLE competency_records (
    id               TEXT PRIMARY KEY,
    org_id           TEXT NOT NULL,
    user_id          TEXT NOT NULL REFERENCES users(id),
    skill_id         TEXT NOT NULL REFERENCES skills(id),
    status           TEXT NOT NULL CHECK (status IN ('in_training','pending_signoff','validated','remediation','reassessment_required','rejected')),
    score            REAL,
    latest_attempt_id TEXT REFERENCES assessment_attempts(id),
    validated_by     TEXT REFERENCES users(id),
    validated_at     TEXT,
    feedback         TEXT,
    updated_at       TEXT NOT NULL,
    UNIQUE (user_id, skill_id)
);

CREATE TABLE signoffs (
    id         TEXT PRIMARY KEY,
    org_id     TEXT NOT NULL,
    attempt_id TEXT NOT NULL REFERENCES assessment_attempts(id),
    trainer_id TEXT NOT NULL REFERENCES users(id),
    decision   TEXT NOT NULL CHECK (decision IN ('approve','reject','remediate','reassess')),
    feedback   TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE remediation_tasks (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL,
    user_id      TEXT NOT NULL REFERENCES users(id),
    skill_id     TEXT REFERENCES skills(id),
    procedure_id TEXT REFERENCES procedures(id),
    attempt_id   TEXT REFERENCES assessment_attempts(id),
    step_ids     TEXT NOT NULL DEFAULT '[]',
    description  TEXT NOT NULL,
    assigned_by  TEXT REFERENCES users(id),
    status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','done')),
    due_date     TEXT,
    created_at   TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE knowledge_feedback (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL,
    procedure_id TEXT NOT NULL REFERENCES procedures(id),
    version_id   TEXT REFERENCES procedure_versions(id),
    step_id      TEXT,
    source       TEXT NOT NULL CHECK (source IN ('assessment','trainer','learner','expert')),
    note         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','addressed','dismissed')),
    created_by   TEXT REFERENCES users(id),
    created_at   TEXT NOT NULL,
    resolved_by  TEXT REFERENCES users(id),
    resolved_at  TEXT
);

CREATE TABLE mentorship_requests (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL,
    mentee_id    TEXT NOT NULL REFERENCES users(id),
    mentor_id    TEXT NOT NULL REFERENCES users(id),
    skill_id     TEXT REFERENCES skills(id),
    procedure_id TEXT REFERENCES procedures(id),
    message      TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL CHECK (status IN ('requested','accepted','declined','completed','cancelled')),
    response_note TEXT,
    created_at   TEXT NOT NULL,
    responded_at TEXT
);

CREATE TABLE mentoring_sessions (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL,
    request_id      TEXT NOT NULL REFERENCES mentorship_requests(id),
    scheduled_at    TEXT NOT NULL,
    duration_min    INTEGER NOT NULL DEFAULT 60,
    mode            TEXT NOT NULL CHECK (mode IN ('onsite','remote')),
    location        TEXT,
    agenda          TEXT NOT NULL DEFAULT '',
    notes           TEXT NOT NULL DEFAULT '',
    mentor_feedback TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL CHECK (status IN ('scheduled','completed','cancelled')),
    created_by      TEXT REFERENCES users(id),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE followup_tasks (
    id          TEXT PRIMARY KEY,
    org_id      TEXT NOT NULL,
    session_id  TEXT NOT NULL REFERENCES mentoring_sessions(id),
    description TEXT NOT NULL,
    owner_id    TEXT REFERENCES users(id),
    due_date    TEXT,
    done        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

-- Translations stay linked to the exact source version they were made from.
CREATE TABLE translations (
    id             TEXT PRIMARY KEY,
    org_id         TEXT NOT NULL,
    version_id     TEXT NOT NULL REFERENCES procedure_versions(id),
    locale         TEXT NOT NULL,
    content_json   TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('draft','needs_safety_review','reviewed')),
    translator_kind TEXT NOT NULL DEFAULT 'manual',
    created_by     TEXT REFERENCES users(id),
    reviewed_by    TEXT REFERENCES users(id),
    reviewed_at    TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    UNIQUE (version_id, locale)
);

CREATE TABLE audit_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id      TEXT NOT NULL,
    actor_id    TEXT,
    action      TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id   TEXT,
    summary     TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_audit_org ON audit_events(org_id, id);
