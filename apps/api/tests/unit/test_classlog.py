"""What did class cover today? The suggestions and the school week are rules (classlog/service.py)."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from app.modules.classlog import service


def test_school_days_are_monday_to_friday() -> None:
    assert service.school_day(date(2026, 11, 13)) is True  # Friday
    assert service.school_day(date(2026, 11, 14)) is False  # Saturday
    assert service.school_day(date(2026, 11, 16)) is True  # Monday


def test_suggestions_carry_on_from_the_last_class_inside_the_term_list() -> None:
    a, b, c, d, e, f = (uuid4() for _ in range(6))
    order = [a, b, c, d, e, f]
    assert service.suggest(order, term=set(), last=None) == [a, b, c, d]  # nothing logged: from the start
    assert service.suggest(order, term=set(), last=c) == [c, d, e, f]  # classes usually carry on
    assert service.suggest(order, term=set(), last=f) == [f, a, b, c]  # and wrap round
    assert service.suggest(order, term={b, d, e}, last=d) == [d, e, b]  # only the school's term list
    assert service.suggest(order, term={b, d}, last=a) == [b, d]  # last class outside the term list
