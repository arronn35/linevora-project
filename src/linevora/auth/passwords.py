"""Password hashing (PBKDF2-HMAC-SHA256, stdlib).

The password field in ``LINEVORA_USERS`` accepts two forms:
- plain text (development convenience only; backward compatible),
- a ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>`` hash (production).

To generate a hash: ``python -c "from linevora.auth.passwords import
hash_password; print(hash_password('password'))"``
"""

from __future__ import annotations

import hashlib
import hmac
import os

_PREFIX = "pbkdf2_sha256"
_ITERATIONS = 260_000


def hash_password(password: str, *, iterations: int = _ITERATIONS) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{_PREFIX}${iterations}${salt.hex()}${digest.hex()}"


def is_hashed(stored: str) -> bool:
    return stored.startswith(_PREFIX + "$")


def verify_password(stored: str, candidate: str) -> bool:
    if is_hashed(stored):
        try:
            _, iterations, salt_hex, hash_hex = stored.split("$")
            digest = hashlib.pbkdf2_hmac(
                "sha256", candidate.encode(), bytes.fromhex(salt_hex), int(iterations)
            )
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(digest.hex(), hash_hex)
    return hmac.compare_digest(stored.encode(), candidate.encode())
