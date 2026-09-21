"""Learning memory rules (pure): evidence required (AC-M3), merging duplicates, superseding contradictions."""

from __future__ import annotations

from uuid import uuid4

from app.modules.memory.rules import MAX_STATEMENTS, DigestEvent, Existing, Proposal, decide, similar

OBJ_A, OBJ_B = uuid4(), uuid4()
E1, E2, E3 = (DigestEvent(f"E{i}", uuid4(), frozenset({OBJ_A if i < 3 else OBJ_B})) for i in (1, 2, 3))
DIGEST = {e.ref: e for e in (E1, E2, E3)}


def test_statements_without_known_evidence_are_rejected() -> None:
    decision = decide(
        [
            Proposal("difficulty", "Needs help setting up equations for objective 13.4.", ()),
            Proposal("difficulty", "Needs help setting up equations for objective 13.4.", ("E9",)),
            Proposal("feeling", "Seems happy.", ("E1",)),
            Proposal("strength", "Solves objective 13.4 questions without help.", ("E1", "E1", "E2")),
        ],
        DIGEST,
        [],
    )
    assert decision.rejected == ["no_evidence", "no_evidence", "unknown_kind"]
    [new] = decision.new
    assert new.event_ids == (E1.event_id, E2.event_id) and new.objective_ids == {OBJ_A}


def test_similar_statement_merges_evidence_instead_of_duplicating() -> None:
    old = Existing(
        uuid4(),
        "difficulty",
        "Loses accuracy marks by rounding too early.",
        frozenset({E1.event_id}),
        frozenset({OBJ_A}),
    )
    decision = decide(
        [Proposal("difficulty", "Loses accuracy marks by rounding too early again.", ("E1", "E2"))], DIGEST, [old]
    )
    assert decision.new == [] and decision.merges[0].existing_id == old.id
    assert decision.merges[0].add_event_ids == (E2.event_id,)
    repeat = decide([Proposal("difficulty", "Loses accuracy marks by rounding too early.", ("E1",))], DIGEST, [old])
    assert repeat.rejected == ["duplicate"]


def test_contradiction_on_the_same_objective_supersedes() -> None:
    struggle = Existing(
        uuid4(), "difficulty", "Needs hints on quadratic factorising.", frozenset({uuid4()}), frozenset({OBJ_A})
    )
    elsewhere = Existing(uuid4(), "difficulty", "Needs hints on vectors.", frozenset({uuid4()}), frozenset({OBJ_B}))
    decision = decide(
        [Proposal("strength", "Now factorises quadratics without help.", ("E1",))], DIGEST, [struggle, elsewhere]
    )
    assert decision.new[0].supersedes == (struggle.id,)


def test_limits_and_similarity() -> None:
    many = [Proposal("note", f"Distinct observation number {i} about pacing {i * 7}.", ("E3",)) for i in range(9)]
    assert len(decide(many, DIGEST, []).new) <= MAX_STATEMENTS
    assert similar("Rounds too early in multi-step questions", "rounds too early in multi step questions")
    assert not similar("Rounds too early", "Draws accurate graphs")
