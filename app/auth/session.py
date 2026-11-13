"""Signed, expiring session tokens stored in an httpOnly cookie."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH)

SESSION_COOKIE_NAME = "legalmind_session"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


def _secret() -> bytes:
    secret = os.environ.get("SESSION_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError(
            "SESSION_SECRET must be set to at least 32 characters in .env."
        )
    return secret.encode("utf-8")


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(body: str) -> str:
    return hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()


def create_session_token(user_id: int, now: float | None = None) -> str:
    issued_at = time.time() if now is None else now
    payload = {"uid": user_id, "exp": int(issued_at) + SESSION_MAX_AGE_SECONDS}
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(body)}"


def read_session_user_id(token: str | None, now: float | None = None) -> int | None:
    """Return the user id for a valid, unexpired token; otherwise None."""
    if not token or "." not in token:
        return None

    body, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(body), signature):
        return None

    try:
        payload = json.loads(_b64decode(body))
    except (ValueError, json.JSONDecodeError):
        return None

    current_time = time.time() if now is None else now
    if payload.get("exp", 0) < current_time:
        return None

    user_id = payload.get("uid")
    return user_id if isinstance(user_id, int) else None
