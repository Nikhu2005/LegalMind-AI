"""Require a signed-in session for every API route except the sign-in endpoints."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.auth.session import SESSION_COOKIE_NAME, read_session_user_id

PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/docs/oauth2-redirect"}
PUBLIC_PREFIXES = ("/auth/",)


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)


async def require_login(request: Request, call_next):
    if request.method == "OPTIONS" or is_public_path(request.url.path):
        return await call_next(request)

    if read_session_user_id(request.cookies.get(SESSION_COOKIE_NAME)) is None:
        return JSONResponse(
            status_code=401,
            content={"detail": "Sign in to use LegalMind."},
        )

    return await call_next(request)
