"""Password hashing with scrypt (Python standard library, no extra dependencies).

Stored format: ``scrypt$<n>$<r>$<p>$<salt_hex>$<hash_hex>``
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_N, _R, _P = 2**14, 8, 1
_DKLEN = 64


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_hex, hash_hex = stored.split("$")
    except (ValueError, AttributeError):
        return False
    if algo != "scrypt":
        return False
    digest = hashlib.scrypt(
        password.encode(),
        salt=bytes.fromhex(salt_hex),
        n=int(n),
        r=int(r),
        p=int(p),
        dklen=len(hash_hex) // 2,
    )
    return hmac.compare_digest(digest.hex(), hash_hex)


def is_hashed(value: str) -> bool:
    return isinstance(value, str) and value.startswith("scrypt$")
