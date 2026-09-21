"""Password hashing for ``AUTH_MODE=local`` (docs/STUDENT-APP.md D7).

Argon2id with the library's current defaults. Only hashes are ever stored, and a hash is rehashed on sign-in
when the parameters have moved on. Nothing here logs or returns a password.
"""

from __future__ import annotations

from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_LENGTH = 10
MAX_LENGTH = 200


class WeakPassword(ValueError):
    """The password is too short, too long, or too obvious to accept."""


_OBVIOUS = frozenset({"password", "password1", "12345678901", "qwertyuiop", "letmein123", "scholr1234"})


@lru_cache(maxsize=1)
def _hasher() -> PasswordHasher:
    return PasswordHasher()


def check_strength(password: str, *, email: str = "") -> None:
    """Raise :class:`WeakPassword` unless the password is long enough and not the account's own email."""
    if len(password) < MIN_LENGTH:
        raise WeakPassword(f"the password must be at least {MIN_LENGTH} characters")
    if len(password) > MAX_LENGTH:
        raise WeakPassword(f"the password must be at most {MAX_LENGTH} characters")
    folded = password.strip().lower()
    if folded in _OBVIOUS or (email and folded == email.strip().lower()):
        raise WeakPassword("that password is too easy to guess")


def hash_password(password: str) -> str:
    return _hasher().hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        return _hasher().verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _hasher().check_needs_rehash(hashed)
    except InvalidHashError:
        return True
