from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from .db import row_to_dict


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or now_utc()).replace(microsecond=0).isoformat()


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    _, salt, expected = encoded.split("$", 2)
    actual = hash_password(password, salt)
    return hmac.compare_digest(actual, encoded)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_token(conn, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = iso(now_utc() + timedelta(days=7))
    conn.execute(
        "INSERT INTO auth_tokens(user_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (user_id, hash_token(token), expires_at),
    )
    return token


def authenticate_token(conn, bearer: str | None) -> dict | None:
    if not bearer or not bearer.startswith("Bearer "):
        return None
    token_hash = hash_token(bearer.removeprefix("Bearer ").strip())
    row = conn.execute(
        """
        SELECT users.*
        FROM auth_tokens
        JOIN users ON users.id = auth_tokens.user_id
        WHERE auth_tokens.token_hash = ? AND auth_tokens.expires_at > ?
        """,
        (token_hash, iso()),
    ).fetchone()
    return row_to_dict(row)
