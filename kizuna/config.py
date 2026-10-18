"""Environment-based configuration.

Values come from process environment variables, optionally pre-loaded from a
local `.env` file (never committed). See `.env.example` for documentation of
every setting.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines; existing env vars win."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = ROOT_DIR / "data"
    db_path: Path = ROOT_DIR / "data" / "kizuna.db"
    upload_dir: Path = ROOT_DIR / "data" / "uploads"
    web_dir: Path = ROOT_DIR / "web"
    demo_mode: bool = True
    session_ttl_hours: int = 12
    cookie_secure: bool = False
    max_upload_mb: int = 200
    log_level: str = "INFO"
    log_json: bool = True
    anthropic_enabled: bool = False
    anthropic_model: str = "claude-opus-5-5"
    anthropic_timeout_s: float = 90.0
    extra: dict = field(default_factory=dict)

    @property
    def anthropic_key_present(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def load_settings(env_file: Path | None = None, **overrides) -> Settings:
    _load_dotenv(env_file or (ROOT_DIR / ".env"))
    data_dir = Path(os.environ.get("KIZUNA_DATA_DIR", str(ROOT_DIR / "data")))
    s = Settings(
        host=os.environ.get("KIZUNA_HOST", "127.0.0.1"),
        port=int(os.environ.get("KIZUNA_PORT", "8000")),
        data_dir=data_dir,
        db_path=Path(os.environ.get("KIZUNA_DB_PATH", str(data_dir / "kizuna.db"))),
        upload_dir=Path(os.environ.get("KIZUNA_UPLOAD_DIR", str(data_dir / "uploads"))),
        demo_mode=_bool("KIZUNA_DEMO_MODE", True),
        session_ttl_hours=int(os.environ.get("KIZUNA_SESSION_TTL_HOURS", "12")),
        cookie_secure=_bool("KIZUNA_COOKIE_SECURE", False),
        max_upload_mb=int(os.environ.get("KIZUNA_MAX_UPLOAD_MB", "200")),
        log_level=os.environ.get("KIZUNA_LOG_LEVEL", "INFO").upper(),
        log_json=_bool("KIZUNA_LOG_JSON", True),
        anthropic_enabled=_bool("KIZUNA_ANTHROPIC_ENABLED", False),
        anthropic_model=os.environ.get("KIZUNA_ANTHROPIC_MODEL", "claude-opus-5-5"),
        anthropic_timeout_s=float(os.environ.get("KIZUNA_ANTHROPIC_TIMEOUT_S", "90")),
    )
    for k, v in overrides.items():
        setattr(s, k, v)
    return s
