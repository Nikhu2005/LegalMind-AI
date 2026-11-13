import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import user_store
from app.auth.guard import is_public_path, require_login
from app.auth.passwords import hash_password, verify_password
from app.auth.routes import router
from app.auth.session import (
    SESSION_COOKIE_NAME,
    create_session_token,
    read_session_user_id,
)

TEST_SECRET = "test-secret-" + "x" * 32


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(user_store, "USERS_DB_PATH", tmp_path / "users.db")
    monkeypatch.setenv("SESSION_SECRET", TEST_SECRET)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    app = FastAPI()
    app.include_router(router)
    app.middleware("http")(require_login)
    app.get("/protected")(lambda: {"ok": True})
    return TestClient(app)


def valid_payload(**overrides):
    payload = {
        "name": "Asha Rao",
        "email": "asha@example.com",
        "password": "correct-horse",
    }
    payload.update(overrides)
    return payload


# ---------- passwords ----------

def test_password_hash_verifies_the_original_password_only():
    stored = hash_password("correct-horse")

    assert verify_password("correct-horse", stored)
    assert not verify_password("wrong-password", stored)


def test_password_hashes_use_a_fresh_salt_each_time():
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_rejects_malformed_and_empty_hashes():
    assert not verify_password("anything", "not-a-hash")
    assert not verify_password("anything", "")


# ---------- session tokens ----------

def test_session_token_round_trips_the_user_id(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", TEST_SECRET)

    token = create_session_token(42)

    assert read_session_user_id(token) == 42


def test_session_token_with_tampered_body_is_rejected(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", TEST_SECRET)
    token = create_session_token(42)
    body, signature = token.rsplit(".", 1)
    forged_body = body[:-2] + ("AA" if body[-2:] != "AA" else "BB")

    assert read_session_user_id(f"{forged_body}.{signature}") is None


def test_expired_session_token_is_rejected(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", TEST_SECRET)
    token = create_session_token(42, now=1_000_000)

    assert read_session_user_id(token, now=1_000_000 + 10**9) is None


def test_session_token_signed_with_another_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", TEST_SECRET)
    token = create_session_token(42)

    monkeypatch.setenv("SESSION_SECRET", "another-secret-" + "y" * 32)

    assert read_session_user_id(token) is None


def test_missing_session_secret_fails_loudly(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "too-short")

    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        create_session_token(1)


# ---------- signup ----------

def test_signup_creates_account_signs_in_and_returns_public_fields_only(client):
    response = client.post("/auth/signup", json=valid_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "asha@example.com"
    assert "password" not in body
    assert "password_hash" not in body
    assert SESSION_COOKIE_NAME in response.cookies


def test_signup_stores_a_hash_not_the_plain_password(client, tmp_path):
    client.post("/auth/signup", json=valid_payload())

    with sqlite3.connect(tmp_path / "users.db") as connection:
        (stored,) = connection.execute("SELECT password_hash FROM users").fetchone()

    assert stored != "correct-horse"
    assert verify_password("correct-horse", stored)


def test_signup_normalises_email_case_and_whitespace(client):
    response = client.post(
        "/auth/signup", json=valid_payload(email="  Asha@Example.COM ")
    )

    assert response.status_code == 201
    assert response.json()["email"] == "asha@example.com"


def test_signup_rejects_duplicate_email_case_insensitively(client):
    client.post("/auth/signup", json=valid_payload())

    response = client.post(
        "/auth/signup", json=valid_payload(email="ASHA@example.com")
    )

    assert response.status_code == 409


def test_signup_rejects_invalid_email_blank_name_and_short_password(client):
    assert client.post("/auth/signup", json=valid_payload(email="bad")).status_code == 400
    assert client.post("/auth/signup", json=valid_payload(name="   ")).status_code == 400
    assert client.post("/auth/signup", json=valid_payload(password="short")).status_code == 422


# ---------- login, session check, logout ----------

def test_login_with_correct_password_sets_session(client):
    client.post("/auth/signup", json=valid_payload())
    client.cookies.clear()

    response = client.post(
        "/auth/login",
        json={"email": "asha@example.com", "password": "correct-horse"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Asha Rao"
    assert SESSION_COOKIE_NAME in response.cookies


def test_login_with_wrong_password_is_rejected(client):
    client.post("/auth/signup", json=valid_payload())
    client.cookies.clear()

    response = client.post(
        "/auth/login",
        json={"email": "asha@example.com", "password": "not-the-password"},
    )

    assert response.status_code == 401
    assert SESSION_COOKIE_NAME not in response.cookies


def test_me_returns_user_when_signed_in_and_401_otherwise(client):
    assert client.get("/auth/me").status_code == 401

    client.post("/auth/signup", json=valid_payload())

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "asha@example.com"


def test_logout_clears_the_session(client):
    client.post("/auth/signup", json=valid_payload())

    client.post("/auth/logout")

    assert client.get("/auth/me").status_code == 401


# ---------- guard ----------

def test_api_routes_require_a_session(client):
    assert client.get("/protected").status_code == 401


def test_api_routes_allow_a_signed_in_user(client):
    client.post("/auth/signup", json=valid_payload())

    assert client.get("/protected").status_code == 200


def test_auth_routes_stay_public_for_the_guard():
    assert is_public_path("/auth/login")
    assert is_public_path("/auth/google/callback")
    assert is_public_path("/docs")
    assert not is_public_path("/search")
    assert not is_public_path("/cases")


# ---------- google ----------

def test_google_login_reports_not_configured_when_credentials_missing(client):
    response = client.get("/auth/google/login", follow_redirects=False)

    assert response.status_code == 503
    assert "GOOGLE_CLIENT_ID" in response.json()["detail"]


def test_google_login_redirects_to_google_with_state_cookie(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")

    response = client.get("/auth/google/login", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("https://accounts.google.com/")
    assert "client_id=client-id.apps.googleusercontent.com" in response.headers["location"]
    assert "legalmind_oauth_state" in response.cookies


def test_google_callback_rejects_mismatched_state(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")

    response = client.get(
        "/auth/google/callback?code=abc&state=forged",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "auth_error=state" in response.headers["location"]
    assert SESSION_COOKIE_NAME not in response.cookies


def test_google_upsert_creates_then_reuses_the_same_account(tmp_path, monkeypatch):
    monkeypatch.setattr(user_store, "USERS_DB_PATH", tmp_path / "users.db")

    first = user_store.upsert_google_user("g@example.com", "G User", google_sub="sub-1")
    second = user_store.upsert_google_user("g@example.com", "G User", google_sub="sub-1")

    assert first["id"] == second["id"]


def test_google_sign_in_links_an_existing_email_account(tmp_path, monkeypatch):
    monkeypatch.setattr(user_store, "USERS_DB_PATH", tmp_path / "users.db")
    existing = user_store.create_user("h@example.com", "H", hash_password("long-password"))

    linked = user_store.upsert_google_user("h@example.com", "H", google_sub="sub-2")

    assert linked["id"] == existing["id"]
    assert user_store.find_user_for_login("h@example.com") is not None


def test_existing_database_without_google_column_is_upgraded(tmp_path, monkeypatch):
    db_path = tmp_path / "users.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "email TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL, "
            "password_hash TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO users (email, name, password_hash, created_at) "
            "VALUES ('old@example.com', 'Old User', 'x', '2026-01-01')"
        )
    monkeypatch.setattr(user_store, "USERS_DB_PATH", db_path)

    linked = user_store.upsert_google_user("old@example.com", "Old User", google_sub="sub-old")

    assert linked["email"] == "old@example.com"
    assert user_store.get_user_by_id(linked["id"]) is not None
