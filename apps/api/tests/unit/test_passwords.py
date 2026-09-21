"""Password hashing and strength rules (app/core/passwords.py, docs/STUDENT-APP.md AC-U11).

The passwords here are fixtures written for this test.
"""

from __future__ import annotations

import pytest

from app.core import passwords

GOOD = "a-long-enough-one"


def test_a_hash_verifies_its_own_password_and_nothing_else() -> None:
    hashed = passwords.hash_password(GOOD)
    assert hashed != GOOD and GOOD not in hashed  # the password itself is never stored
    assert passwords.verify_password(hashed, GOOD)
    assert not passwords.verify_password(hashed, GOOD.upper())
    assert not passwords.verify_password(hashed, "")
    # Two hashes of the same password differ: each carries its own salt.
    assert passwords.hash_password(GOOD) != hashed


def test_a_damaged_or_empty_hash_refuses_rather_than_raising() -> None:
    assert not passwords.verify_password("not-a-hash", GOOD)
    assert not passwords.verify_password("", GOOD)
    assert passwords.needs_rehash("not-a-hash")
    assert not passwords.needs_rehash(passwords.hash_password(GOOD))


@pytest.mark.parametrize("password", ["short", "", "x" * 201, "password", "Password1 ".strip().lower()])
def test_obvious_and_out_of_range_passwords_are_refused(password: str) -> None:
    with pytest.raises(passwords.WeakPassword):
        passwords.check_strength(password)


def test_a_password_that_is_just_the_email_is_refused() -> None:
    with pytest.raises(passwords.WeakPassword):
        passwords.check_strength("her.name@example.com", email="Her.Name@example.com")
    passwords.check_strength(GOOD, email="her.name@example.com")  # a good one raises nothing
