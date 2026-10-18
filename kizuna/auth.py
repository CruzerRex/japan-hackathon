"""Authentication (password + session cookie) and role-based authorisation.

- Passwords: PBKDF2-HMAC-SHA256, 240k iterations, per-user salt.
- Sessions: random 256-bit token in an HttpOnly, SameSite=Strict cookie; only
  the SHA-256 of the token is stored server-side.
- Authorisation: explicit permission -> roles map, checked server-side on every
  protected operation. The frontend hides controls for UX only.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from .web import ApiError, Request, forbidden

COOKIE_NAME = "kizuna_session"
PBKDF2_ITERATIONS = 240_000

ROLES = ("admin", "expert", "trainer", "trainee")

PERMISSIONS: dict[str, set[str]] = {
    "capture.write": {"admin", "expert", "trainer"},
    "capture.read": {"admin", "expert", "trainer"},
    "procedure.read_unpublished": {"admin", "expert", "trainer"},
    "procedure.create": {"admin", "expert", "trainer"},
    "procedure.edit": {"admin", "expert"},
    "procedure.submit": {"admin", "expert", "trainer"},
    "procedure.approve": {"admin", "expert"},
    "procedure.publish": {"admin", "expert", "trainer"},
    "extraction.run": {"admin", "expert", "trainer"},
    "assessment.signoff": {"admin", "trainer"},
    "competency.view_all": {"admin", "trainer", "expert"},
    "risk.view": {"admin", "trainer", "expert"},
    "people.manage": {"admin"},
    "retirement.edit": {"admin"},
    "audit.view": {"admin", "trainer"},
    "org.export": {"admin"},
    "mentorship.mentor": {"admin", "expert", "trainer"},
    "translation.edit": {"admin", "expert", "trainer"},
    "translation.review": {"admin", "expert"},
    "feedback.resolve": {"admin", "expert"},
}


def can(user: dict | None, permission: str) -> bool:
    if not user:
        return False
    return user["role"] in PERMISSIONS.get(permission, set())


def require(req: Request, permission: str) -> dict:
    if not can(req.user, permission):
        raise forbidden(f"Your role ({req.user['role'] if req.user else 'anonymous'}) cannot perform '{permission}'")
    return req.user


def permissions_for(role: str) -> list[str]:
    return sorted(p for p, roles in PERMISSIONS.items() if role in roles)


# -- passwords ------------------------------------------------------------------
def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iters)).hex()
        return hmac.compare_digest(calc, digest)
    except (ValueError, TypeError):
        return False


# -- sessions -------------------------------------------------------------------
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(req: Request, user_id: str) -> None:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    ttl = req.app.settings.session_ttl_hours
    req.db.execute(
        "INSERT INTO auth_sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (_token_hash(token), user_id, now.isoformat(), (now + timedelta(hours=ttl)).isoformat()),
    )
    req.db.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (now.isoformat(),))
    secure = "; Secure" if req.app.settings.cookie_secure else ""
    req.set_cookies.append(
        f"{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={ttl * 3600}{secure}"
    )


def destroy_session(req: Request) -> None:
    token = req.cookies.get(COOKIE_NAME)
    if token:
        req.db.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_token_hash(token),))
    req.set_cookies.append(f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0")


def authenticate(req: Request) -> None:
    token = req.cookies.get(COOKIE_NAME)
    if not token:
        raise ApiError(401, "unauthenticated", "Please sign in")
    row = req.db.one(
        """SELECT u.*, s.expires_at AS session_expires FROM auth_sessions s
           JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?""",
        (_token_hash(token),),
    )
    if not row or row["session_expires"] < datetime.now(timezone.utc).isoformat() or not row["active"]:
        raise ApiError(401, "unauthenticated", "Your session has expired. Please sign in again.")
    row.pop("password_hash", None)
    req.user = row


def public_user(u: dict) -> dict:
    return {k: v for k, v in u.items() if k not in ("password_hash", "session_expires")}
