"""Account endpoints: signup, email login, Google sign-in, session check and logout."""
from __future__ import annotations

import os
import re
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from starlette.responses import Response

from app.auth.passwords import hash_password, verify_password
from app.auth.session import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    create_session_token,
    read_session_user_id,
)
from app.auth.user_store import (
    DuplicateEmailError,
    create_user,
    find_user_for_login,
    get_user_by_id,
    upsert_google_user,
)


router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_EMAIL_LENGTH = 254
OAUTH_STATE_COOKIE = "legalmind_oauth_state"
OAUTH_STATE_MAX_AGE_SECONDS = 10 * 60

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
DEFAULT_GOOGLE_REDIRECT_URI = "http://127.0.0.1:5173/api/auth/google/callback"
DEFAULT_FRONTEND_URL = "http://127.0.0.1:5173/"


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=MAX_EMAIL_LENGTH)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=MAX_EMAIL_LENGTH)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def _set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(user_id),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )


@router.post("/signup", status_code=201, response_model=UserResponse)
def signup(request: SignupRequest, response: Response) -> dict:
    name = request.name.strip()
    email = _normalise_email(request.email)

    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be empty.")

    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")

    try:
        user = create_user(email, name, hash_password(request.password))
    except DuplicateEmailError:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    _set_session_cookie(response, user["id"])
    return user


@router.post("/login", response_model=UserResponse)
def login(request: LoginRequest, response: Response) -> dict:
    found = find_user_for_login(_normalise_email(request.email))

    if found is None or not verify_password(request.password, found[1]):
        raise HTTPException(
            status_code=401,
            detail="Email or password is incorrect.",
        )

    user, _ = found
    _set_session_cookie(response, user["id"])
    return user


@router.get("/me", response_model=UserResponse)
def current_user(request: Request) -> dict:
    user_id = read_session_user_id(request.cookies.get(SESSION_COOKIE_NAME))
    user = get_user_by_id(user_id) if user_id is not None else None

    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in.")
    return user


@router.post("/logout")
def logout() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


# ============================================================
# GOOGLE SIGN-IN
# ============================================================


def _google_config() -> tuple[str, str, str]:
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = os.environ.get(
        "GOOGLE_REDIRECT_URI", DEFAULT_GOOGLE_REDIRECT_URI
    ).strip()

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="Google sign-in is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.",
        )
    return client_id, client_secret, redirect_uri


def _frontend_url() -> str:
    return os.environ.get("FRONTEND_URL", DEFAULT_FRONTEND_URL).strip()


def _google_failure(reason: str) -> RedirectResponse:
    separator = "&" if "?" in _frontend_url() else "?"
    return RedirectResponse(
        url=f"{_frontend_url()}{separator}auth_error={reason}",
        status_code=302,
    )


@router.get("/google/login")
def google_login() -> RedirectResponse:
    client_id, _, redirect_uri = _google_config()
    state = secrets.token_urlsafe(24)

    query = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    })
    response = RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}", status_code=302)
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state,
        max_age=OAUTH_STATE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/google/callback")
def google_callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
    client_id, client_secret, redirect_uri = _google_config()

    expected_state = request.cookies.get(OAUTH_STATE_COOKIE, "")
    if not code or not state or not secrets.compare_digest(state, expected_state):
        return _google_failure("state")

    try:
        token_response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]

        profile_response = httpx.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
    except (httpx.HTTPError, KeyError, ValueError):
        return _google_failure("google")

    email = _normalise_email(profile.get("email", ""))
    if not profile.get("email_verified") or not EMAIL_PATTERN.match(email):
        return _google_failure("unverified")

    name = (profile.get("name") or email.split("@", 1)[0]).strip()[:100]
    user = upsert_google_user(email, name, google_sub=str(profile["sub"]))

    response = RedirectResponse(url=_frontend_url(), status_code=302)
    _set_session_cookie(response, user["id"])
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    return response
