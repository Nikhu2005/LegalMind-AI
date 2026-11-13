"""Password hashing with salted scrypt (standard library, no extra dependencies)."""
from __future__ import annotations

import hashlib
import hmac
import os

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_KEY_BYTES = 64
SALT_BYTES = 16
_HASH_PREFIX = "scrypt"


def hash_password(password: str) -> str:
    """Return a self-describing hash string: scrypt$N$r$p$salt$digest."""
    salt = os.urandom(SALT_BYTES)
    digest = _derive(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return "$".join([
        _HASH_PREFIX,
        str(SCRYPT_N),
        str(SCRYPT_R),
        str(SCRYPT_P),
        salt.hex(),
        digest.hex(),
    ])


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a password against a hash produced by hash_password."""
    try:
        prefix, n, r, p, salt_hex, digest_hex = stored_hash.split("$")
    except ValueError:
        return False

    if prefix != _HASH_PREFIX:
        return False

    candidate = _derive(password, bytes.fromhex(salt_hex), int(n), int(r), int(p))
    return hmac.compare_digest(candidate, bytes.fromhex(digest_hex))


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=SCRYPT_KEY_BYTES,
    )
