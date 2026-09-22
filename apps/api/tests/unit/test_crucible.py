"""The Crucible's guard (learn/crucible.py): perspectives must be cited, may name only who the excerpts name, and
may not copy the book; it ends with questions, never an answer."""

from __future__ import annotations

from app.modules.learn import crucible, lessons

BOOK = [
    lessons.Excerpt(
        "c1", "Sociology Coursebook", 40, "Parsons argued that the family performs two irreducible functions."
    ),
    lessons.Excerpt(
        "c2", "Sociology Coursebook", 42, "Marxists see the family as serving capitalism as a unit of consumption."
    ),
]


def draft(**overrides: object) -> crucible.CrucibleDraft:
    base = {
        "perspectives": [
            {"perspective": "Functionalist", "sociologist": "Parsons", "argument": "The family keeps two key jobs.",
             "key_concept": "irreducible functions", "sources": [1]},
            {"perspective": "Marxist", "sociologist": "", "argument": "The family props up the economic system.",
             "key_concept": "consumption", "sources": [2]},
        ],
        "questions_to_weigh": ["Which view fits today's family diversity better?", "The family is necessary."],
    }  # fmt: skip
    return crucible.CrucibleDraft.model_validate({**base, **overrides})


def test_cited_perspectives_are_kept_and_only_questions_survive() -> None:
    content, report = crucible.guard(draft(), BOOK)
    assert content is not None and [p["perspective"] for p in content["perspectives"]] == ["Functionalist", "Marxist"]
    assert content["perspectives"][0]["sources"] == [{"title": "Sociology Coursebook", "page": 40}]
    assert content["questions"] == ["Which view fits today's family diversity better?"]  # a statement is dropped
    assert report["dropped_questions"] == 1


def test_a_name_the_book_does_not_give_or_no_citation_drops_the_perspective() -> None:
    invented = draft(
        perspectives=[
            {"perspective": "Functionalist", "sociologist": "Parsons", "argument": "Two jobs.", "sources": [1]},
            {"perspective": "Feminist", "sociologist": "Oakley", "argument": "Housework is unpaid.", "sources": [2]},
            {"perspective": "Marxist", "argument": "It serves capital.", "sources": []},
        ]
    )
    content, report = crucible.guard(invented, BOOK)
    assert content is None  # only one perspective survives: no debate rather than a one-sided one
    assert (report["dropped_named"], report["dropped_uncited"]) == (1, 1)


def test_a_copied_example_goes_but_the_perspective_stays_and_school_names_are_not_people() -> None:
    copied = "Marxists see the family as serving capitalism as a unit of consumption."
    content, report = crucible.guard(
        draft(
            perspectives=[
                {"perspective": "Functionalist", "sociologist": "Parsons", "argument": "The family keeps two key jobs.",
                 "sources": [1]},
                {"perspective": "Marxist", "argument": "Like the New Right, it treats the family as central, but as a "
                 "prop for the economy.", "evidence": copied, "sources": [2]},
            ]
        ),
        BOOK,
    )  # fmt: skip
    assert content is not None and content["perspectives"][1]["evidence"] == ""
    assert report["evidence_dropped"] == 1 and report["dropped_named"] == 0  # "New Right" is a school, not a person
