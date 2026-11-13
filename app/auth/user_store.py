"""SQLite storage for user accounts (email/password and Google sign-in)."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USERS_DB_PATH = Path("data/users.db")

# Google-only accounts store an empty password_hash, which verify_password rejects.
NO_PASSWORD_HASH = ""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    google_sub TEXT,
    created_at TEXT NOT NULL
);
"""


class DuplicateEmailError(Exception):
    """Raised when an account with the same email already exists."""


def _connect() -> sqlite3.Connection:
    USERS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(USERS_DB_PATH))
    connection.executescript(_SCHEMA)
    _add_missing_columns(connection)
    return connection


def _add_missing_columns(connection: sqlite3.Connection) -> None:
    """Upgrade databases created before google_sub existed.

    SQLite cannot add a UNIQUE column to an existing table, so the column is
    added plainly and uniqueness is enforced with a unique index.
    """
    columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
    if "google_sub" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN google_sub TEXT")
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS users_google_sub_idx ON users(google_sub)"
    )
    connection.commit()


def _public(row: tuple[Any, ...]) -> dict[str, Any]:
    user_id, email, name = row
    return {"id": user_id, "email": email, "name": name}


def create_user(
    email: str,
    name: str,
    password_hash: str,
    google_sub: str | None = None,
) -> dict[str, Any]:
    """Insert a user and return their public fields (never the password hash)."""
    created_at = datetime.now(timezone.utc).isoformat()

    with closing(_connect()) as connection:
        try:
            with connection:
                cursor = connection.execute(
                    "INSERT INTO users (email, name, password_hash, google_sub, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (email, name, password_hash, google_sub, created_at),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateEmailError(email) from error

    return {"id": cursor.lastrowid, "email": email, "name": name}


def find_user_for_login(email: str) -> tuple[dict[str, Any], str] | None:
    """Return (public user, password_hash) for an email, or None."""
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT id, email, name, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if row is None:
        return None
    return _public(row[:3]), row[3]


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT id, email, name FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    return _public(row) if row else None


def upsert_google_user(email: str, name: str, google_sub: str) -> dict[str, Any]:
    """Sign in or create the account for a verified Google identity.

    An existing email/password account with the same email is linked to Google.
    """
    with closing(_connect()) as connection:
        by_sub = connection.execute(
            "SELECT id, email, name FROM users WHERE google_sub = ?",
            (google_sub,),
        ).fetchone()
        if by_sub:
            return _public(by_sub)

        by_email = connection.execute(
            "SELECT id, email, name FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if by_email:
            with connection:
                connection.execute(
                    "UPDATE users SET google_sub = ? WHERE id = ?",
                    (google_sub, by_email[0]),
                )
            return _public(by_email)

    return create_user(email, name, NO_PASSWORD_HASH, google_sub=google_sub)
