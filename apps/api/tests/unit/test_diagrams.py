"""The diagrams a lesson may carry, and the checks that decide which survive (AC-U14).

The numbers here are fixtures for this test. The rule under test is that a model supplies numbers and nothing
else: everything drawn is computed here, and anything that cannot be computed is refused.
"""

from __future__ import annotations

import pytest

from app.modules.learn import diagrams, lessons

ALL = set(diagrams.KINDS)


def test_a_venn_of_two_numbers_is_worked_out_here_not_by_the_model() -> None:
    drawn = diagrams.check("venn_factors", {"first": 24, "second": 36}, allowed=ALL).data
    assert drawn["hcf"] == 12 and drawn["lcm"] == 72
    assert drawn["shared"] == [{"prime": 2, "power": 2}, {"prime": 3, "power": 1}]
    assert drawn["only_first"] == [{"prime": 2, "power": 1}]  # 24 keeps one extra 2
    assert drawn["only_second"] == [{"prime": 3, "power": 1}]  # 36 keeps one extra 3


def test_a_kind_this_subject_does_not_use_is_refused() -> None:
    with pytest.raises(diagrams.DiagramError):
        diagrams.check("wave", {"wavelength_m": 2, "amplitude_cm": 3}, allowed={"venn_factors"})


def test_the_prompts_own_example_numbers_are_refused() -> None:
    # A model handed a worked shape will copy it; the same picture then appears on unrelated topics.
    for kind, example in diagrams.EXAMPLES.items():
        with pytest.raises(diagrams.DiagramError):
            diagrams.check(kind, example, allowed=ALL)


def test_arrows_on_a_body_must_be_forces_and_the_resultant_is_computed() -> None:
    forces = [
        {"label": "push", "magnitude": 12, "direction": "right"},
        {"label": "friction", "magnitude": 4.5, "direction": "left"},
    ]
    drawn = diagrams.check("force_arrows", {"body": "crate", "unit": "N", "forces": forces}, allowed=ALL).data
    assert drawn["resultant"] == {"x": 7.5, "y": 0.0, "size": 7.5}
    # A current is not a force, however neatly it would draw.
    with pytest.raises(diagrams.DiagramError):
        diagrams.check("force_arrows", {"unit": "A", "forces": forces}, allowed=ALL)


def test_a_wave_whose_speed_frequency_and_wavelength_disagree_is_refused() -> None:
    good = {"wavelength_m": 3, "amplitude_cm": 4, "frequency_hz": 20, "speed_ms": 60}
    assert diagrams.check("wave", good, allowed=ALL).data["speed_ms"] == 60
    with pytest.raises(diagrams.DiagramError):  # v = f λ would be 60, not 90
        diagrams.check("wave", {**good, "speed_ms": 90}, allowed=ALL)
    # With no frequency given there is nothing to contradict, and the picture still draws.
    assert diagrams.check("wave", {"wavelength_m": 3, "amplitude_cm": 4}, allowed=ALL).data["speed_ms"] is None


def test_a_triangle_must_be_right_angled_and_a_bar_models_parts_must_be_named() -> None:
    assert diagrams.check("right_triangle", {"base": 6, "height": 8}, allowed=ALL).data["hypotenuse"] == 10
    with pytest.raises(diagrams.DiagramError):
        diagrams.check("right_triangle", {"base": 6, "height": 8, "hypotenuse": 11}, allowed=ALL)
    parts = [{"label": "Part 1", "value": 3}, {"label": "Part 2", "value": 7}]
    with pytest.raises(diagrams.DiagramError):  # "Part 1 / Part 2" is a picture of nothing
        diagrams.check("bar_model", {"parts": parts}, allowed=ALL)


def test_a_number_line_must_hold_everything_it_marks() -> None:
    line = {"start": 0, "end": 10, "values": [2.5, 7], "shade_from": 2.5, "shade_to": 7}
    assert diagrams.check("number_line", line, allowed=ALL).data["values"] == [2.5, 7]
    with pytest.raises(diagrams.DiagramError):
        diagrams.check("number_line", {**line, "values": [42]}, allowed=ALL)
    with pytest.raises(diagrams.DiagramError):
        diagrams.check("number_line", {**line, "shade_from": 7, "shade_to": 2.5}, allowed=ALL)


SECTIONS = [
    {"heading": "Bounds", "body": "A length of 26 cm rounded to the nearest centimetre lies between 25.5 and 26.5."}
]


def draft(**overrides: object) -> lessons.DiagramDraft:
    values: dict = {
        "kind": "number_line",
        "caption": "The stretch a rounded length could really be.",
        "data": {"start": 25, "end": 27, "values": [26], "shade_from": 25.5, "shade_to": 26.5},
        "sources": [1],
    }
    values.update(overrides)
    return lessons.DiagramDraft.model_validate(values)


def test_the_guard_keeps_a_grounded_diagram_and_marks_it_for_review() -> None:
    kept, report = lessons.guard_diagrams([draft()], SECTIONS, allowed={"number_line"}, limit=2)
    assert report["kept"] == 1
    assert kept[0]["data"]["shade_to"] == 26.5 and kept[0]["sections"] == [1]
    # Nothing is shown to her before a person has looked at it.
    assert kept[0]["approved"] is False


def test_the_guard_drops_diagrams_that_are_not_about_this_lesson() -> None:
    drafts = [
        draft(sources=[]),  # cites no section
        draft(data={"start": 340, "end": 400, "values": [370], "shade_from": 340, "shade_to": 400}),  # other numbers
        draft(caption="This shows values between 4 and 9."),  # a caption the picture contradicts
        draft(caption="A length of 26 cm rounded to the nearest centimetre lies between 25.5"),  # copied
    ]
    _, report = lessons.guard_diagrams(drafts, SECTIONS, allowed={"number_line"}, limit=4)
    assert report["kept"] == 0
    assert report["dropped_uncited"] == 1 and report["dropped_ungrounded"] == 1
    assert report["dropped_caption"] == 2


def test_only_as_many_diagrams_as_a_lesson_may_carry_are_kept() -> None:
    kept, _ = lessons.guard_diagrams([draft(), draft(), draft()], SECTIONS, allowed={"number_line"}, limit=2)
    assert len(kept) == 2


def test_a_grid_holds_its_points_and_picks_readable_ticks() -> None:
    grid = {"x_min": -6, "x_max": 6, "y_min": -6, "y_max": 6, "join": True, "points": [{"x": -2, "y": 1, "label": "P"}]}
    drawn = diagrams.check("coordinate_grid", grid, allowed=ALL).data
    assert drawn["points"] == [{"x": -2.0, "y": 1.0, "label": "P"}]
    assert drawn["x_step"] == 1 and drawn["join"] is True
    assert diagrams.check("coordinate_grid", {**grid, "x_min": -40, "x_max": 20}, allowed=ALL).data["x_step"] == 5
    with pytest.raises(diagrams.DiagramError):  # off the axes it is drawn on
        diagrams.check("coordinate_grid", {**grid, "points": [{"x": 99, "y": 0}]}, allowed=ALL)
    with pytest.raises(diagrams.DiagramError):  # too wide to label on a phone
        diagrams.check("coordinate_grid", {**grid, "x_min": -500, "x_max": 500}, allowed=ALL)


def test_a_line_writes_its_own_equation_and_refuses_a_point_that_is_not_on_it() -> None:
    line = {"gradient": 2, "intercept": 1, "x_min": -3, "x_max": 3, "points": [{"x": 1, "y": 3}]}
    drawn = diagrams.check("straight_line_graph", line, allowed=ALL).data
    assert drawn["equation"] == "y = 2x + 1"
    assert drawn["ends"] == [{"x": -3.0, "y": -5.0}, {"x": 3.0, "y": 7.0}]
    assert drawn["y_min"] < -5 and drawn["y_max"] > 7  # the window holds the whole line
    with pytest.raises(diagrams.DiagramError):
        diagrams.check("straight_line_graph", {**line, "points": [{"x": 1, "y": 9}]}, allowed=ALL)


@pytest.mark.parametrize(
    ("gradient", "intercept", "equation"),
    [(1, 0, "y = x"), (-1, 4, "y = -x + 4"), (0.5, -2, "y = 1/2x - 2"), (0, 3, "y = 3"), (3, 0, "y = 3x")],
)
def test_equations_are_written_the_way_a_textbook_writes_them(gradient: float, intercept: float, equation: str) -> None:
    data = {"gradient": gradient, "intercept": intercept}
    assert diagrams.check("straight_line_graph", data, allowed=ALL).data["equation"] == equation


def test_a_caption_naming_a_range_must_match_the_stretch_that_is_shaded() -> None:
    shaded = {"start": -3, "end": 4, "values": [-2, 3], "shade_from": -2, "shade_to": 4}
    assert lessons.caption_disagrees("Values between -2 and 3, inclusive.", shaded)  # shaded to 4, not 3
    assert not lessons.caption_disagrees("Values between -2 and 4.", shaded)


def test_a_reflected_ray_leaves_at_the_angle_it_arrived() -> None:
    drawn = diagrams.check(
        "ray_diagram", {"behaviour": "reflection", "angle_of_incidence": 35, "surface": "mirror"}, allowed=ALL
    ).data
    assert (drawn["angle_in"], drawn["angle_out"]) == (35.0, 35.0)  # the law, not the model's arithmetic
    with pytest.raises(diagrams.DiagramError):  # a reflection has no refracted ray
        diagrams.check(
            "ray_diagram", {"behaviour": "reflection", "angle_of_incidence": 35, "refractive_index": 1.5}, allowed=ALL
        )


def test_a_refracted_ray_follows_snells_law() -> None:
    drawn = diagrams.check(
        "ray_diagram", {"behaviour": "refraction", "angle_of_incidence": 45, "refractive_index": 1.5}, allowed=ALL
    ).data
    assert drawn["angle_out"] == 28.1 and drawn["critical_angle"] == 41.8  # glass, as the data book has it
    # Given both angles instead, the index is worked out — and light must bend towards the normal going in.
    from_angles = diagrams.check(
        "ray_diagram",
        {"behaviour": "refraction", "angle_of_incidence": 45, "angle_of_refraction": 28.1},
        allowed=ALL,
    ).data
    assert from_angles["refractive_index"] == pytest.approx(1.5, abs=0.01)
    with pytest.raises(diagrams.DiagramError):
        diagrams.check(
            "ray_diagram",
            {"behaviour": "refraction", "angle_of_incidence": 30, "angle_of_refraction": 50},
            allowed=ALL,
        )
    with pytest.raises(diagrams.DiagramError):  # 45° into n = 1.5 is 28.1°, not 40°
        diagrams.check(
            "ray_diagram",
            {"behaviour": "refraction", "angle_of_incidence": 45, "angle_of_refraction": 40, "refractive_index": 1.5},
            allowed=ALL,
        )


def test_a_circuit_works_out_its_own_resistance_and_current() -> None:
    series = diagrams.check(
        "circuit",
        {
            "emf_v": 12,
            "arrangement": "series",
            "components": [{"label": "lamp", "resistance_ohm": 4}, {"label": "resistor", "resistance_ohm": 8}],
        },
        allowed=ALL,
    ).data
    assert (series["total_resistance_ohm"], series["current_a"]) == (12.0, 1.0)
    parallel = diagrams.check(
        "circuit",
        {
            "emf_v": 6,
            "arrangement": "parallel",
            "components": [{"label": "A", "resistance_ohm": 4}, {"label": "B", "resistance_ohm": 4}],
        },
        allowed=ALL,
    ).data
    assert (parallel["total_resistance_ohm"], parallel["current_a"]) == (2.0, 3.0)
    with pytest.raises(diagrams.DiagramError):  # 12 V across 6 Ω is 2 A, not 5
        diagrams.check("circuit", {"emf_v": 12, "components": [{"resistance_ohm": 6}], "current_a": 5}, allowed=ALL)
