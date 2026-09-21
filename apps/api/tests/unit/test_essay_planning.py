"""The essay-plan guard (AC-R5): a plan helps her write; anything she could hand in is stripped."""

from __future__ import annotations

import pytest

from app.modules.tutoring import planning


@pytest.mark.parametrize(
    "note",
    [
        "Functionalist view — Parsons, family socialises children",
        "Feminist critique: unpaid domestic labour",
        "Marxist: family reproduces labour power",
        "Define 'nuclear family' early",
    ],
)
def test_a_note_is_kept(note: str) -> None:
    assert not planning.is_draft(note)


@pytest.mark.parametrize(
    ("note", "why"),
    [
        (
            "Functionalists such as Parsons argue that the family serves to socialise children into the "
            "shared norms and values of society",
            "a finished sentence, long enough to hand in",
        ),
        (
            "However, feminists disagree with this view",
            "a discursive connective: it exists to join prose",
        ),
        (
            "This shows that the family is not always positive",
            "an analytical sentence, which is the mark-earning part",
        ),
        (
            "The family is important. It socialises children. It also provides support.",
            "several sentences: a paragraph in disguise",
        ),
        ("In conclusion, the family has both positive and negative effects", "a written conclusion"),
        ("", "an empty note helps nobody"),
    ],
)
def test_a_draft_is_rejected(note: str, why: str) -> None:
    assert planning.is_draft(note), why


def test_guarding_keeps_notes_and_drops_prose() -> None:
    report = planning.guard_notes(
        [
            "Parsons — socialisation function",
            "However, this view has been criticised by many sociologists writing since the 1970s",
            "Oakley — housework as unpaid work",
        ]
    )
    assert report.kept == ("Parsons — socialisation function", "Oakley — housework as unpaid work")
    assert len(report.dropped) == 1


def test_a_plan_that_was_really_a_draft_is_not_usable() -> None:
    """If everything the model returned was prose, there is no plan left to show."""
    draft = planning.PlanDraft(
        for_points=["The family performs several important functions in modern industrial society today"],
        against_points=["However, feminist sociologists have long argued the opposite of this position"],
        evidence=[],
        conclusion_direction="In conclusion, the family is both positive and negative for individuals",
        watch_out=[],
    )
    guarded = planning.guard(draft)
    assert not guarded.usable
    assert guarded.for_points == () and guarded.against_points == ()
    assert guarded.conclusion_direction == ""
    assert guarded.dropped == 3


def test_a_good_plan_survives_intact() -> None:
    draft = planning.PlanDraft(
        for_points=["Parsons — socialisation", "Murdock — four functions"],
        against_points=["Oakley — housework unequal", "Marxist — reproduces labour power"],
        evidence=["Parsons", "Oakley", "Murdock"],
        conclusion_direction="Weigh functionalist benefits against feminist critique",
        watch_out=["Both sides needed for 'discuss'"],
    )
    guarded = planning.guard(draft)
    assert guarded.usable and guarded.dropped == 0
    assert len(guarded.for_points) == 2 and len(guarded.against_points) == 2
    assert guarded.conclusion_direction


def test_the_refusal_wording_is_ours_not_the_models() -> None:
    """Held in code so the answer to "just write it for me" is the same sentence every time."""
    assert "won't write it" in planning.REFUSAL
    assert planning.REFUSAL.strip() == planning.REFUSAL


def test_lists_are_capped_so_a_plan_stays_a_plan() -> None:
    many = [f"Point {n}" for n in range(30)]
    guarded = planning.guard(
        planning.PlanDraft(
            for_points=many, against_points=many, evidence=many, conclusion_direction="Weigh both", watch_out=many
        )
    )
    assert len(guarded.for_points) == 8
    assert len(guarded.watch_out) == 3
    assert len(guarded.evidence) == 6


def test_a_trailing_full_stop_does_not_make_a_note_a_draft() -> None:
    report = planning.guard_notes(["Parsons — socialisation function."])
    assert report.kept == ("Parsons — socialisation function",)


# --- what the first live eval run taught the guard --------------------------------------------------------
# The guard removed 11 of 16 conclusion notes on its first run against the real model. Every one was an
# instruction to the student, not prose she could hand in — the rule was rejecting them purely for running
# past eight words without punctuation. These cases are the exact strings it removed.


@pytest.mark.parametrize(
    "note",
    [
        "Weigh extent of owner control against other influences on media content.",
        "Weighing direct owner control against other influences and challenges",
        "Weigh extent of owner control against professional autonomy and audience demand.",
        "Confuse direct owner control with indirect influences (e.g. advertisers)",
        "Link each point back to the wording of the question",
        "Compare functionalist and feminist accounts of the same family",
    ],
)
def test_an_instruction_to_herself_is_a_note(note: str) -> None:
    """These earn nothing if copied into a script — they tell her what to do, not what to say."""
    assert not planning.is_draft(note)


@pytest.mark.parametrize(
    "note",
    [
        "The family performs several important functions in modern industrial society today",
        "Owners control what appears in the news every single day",
        "Media ownership is concentrated in the hands of a few large companies",
    ],
)
def test_a_claim_with_a_subject_is_still_a_draft(note: str) -> None:
    """The instruction exception must not open a door for declarative prose, which is the real risk."""
    assert planning.is_draft(note)


def test_an_instruction_is_still_bounded_by_length() -> None:
    """ "Weigh..." does not license a paragraph: the overall cap still applies."""
    long_instruction = (
        "Weigh evidence for direct owner control against factors limiting this control, such as "
        "journalist autonomy and audience influence."
    )
    assert planning.is_draft(long_instruction)


def test_the_guard_says_what_it_removed() -> None:
    """A guard whose decisions cannot be inspected cannot be calibrated — this is how the eval saw its errors."""
    guarded = planning.guard(
        planning.PlanDraft(
            for_points=["Parsons — socialisation", "However, this view has been widely criticised since"],
            against_points=[],
            evidence=[],
            conclusion_direction="",
            watch_out=[],
        )
    )
    assert guarded.dropped == 1
    assert guarded.dropped_notes == ("However, this view has been widely criticised since",)
