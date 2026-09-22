"""The exam level of a topic page (docs/STUDENT-APP.md AC-U16): what code decides and checks, with no model."""

from __future__ import annotations

from app.modules.learn import exam, lessons, pacing

CUBIC = exam.ExamItem(
    id="cubic",
    source_ref="0580/41/MJ25/Q14(c)",
    origin="past_paper",
    stem="By drawing a suitable straight line on the grid, solve the equation x³ - 5x² - x + 14 = 0.",
    context="14 The table shows some values for y = 5x² - x³ - 4.",
    marks=4,
    command_word="solve",
    has_diagram=True,
    answer_spec={
        "type": "numeric",
        "answer": "x = −1.7 to −1.4\nx = 2\nx = 4.4 to 4.7",
        "accuracy": "sf3",
        "accept_ranges": [["-1.7", "-1.4"], ["4.4", "4.7"]],
    },
    mark_scheme={
        "text": (
            "y = 10 − x ruled\nB1 for [y =] 10 − x soi\nA1 for any two values\nIf 0 scored, SC1 for 3 correct values"
        )
    },
)
HCF = exam.ExamItem(
    id="hcf",
    source_ref="0580/22/MJ25/Q8",
    origin="past_paper",
    stem="Find the highest common factor (HCF) of 36 and 54.",
    context=None,
    marks=2,
    command_word="find",
    has_diagram=False,
    answer_spec={"type": "numeric", "answer": "18", "accuracy": "sf3", "accept_ranges": []},
    mark_scheme={"text": "B1 for answer 2, 3, 6 or 9\nor M1 for answer 2 × 3^2 oe"},
)


def draft(steps: list[tuple[str, str]], final: str) -> exam.WalkthroughDraft:
    return exam.WalkthroughDraft(
        steps=[exam.WalkthroughStep(text=t, mark=m) for t, m in steps], final_answer=final, tip=""
    )


GOOD_CUBIC = [
    ("The curve drawn is $y = 5x^2 - x^3 - 4$, so draw the line $y = 10 - x$.", "B1"),
    ("Read off where they cross.", ""),
    ("The crossings are at $x = -1.6$, $x = 2$ and $x = 4.5$.", "A1"),
]


def test_how_examined_counts_past_papers_only() -> None:
    template = exam.ExamItem("t", "template/x/0", "template", "s", None, 1, "find", False, {}, {})
    how = exam.how_examined([CUBIC, HCF, template])
    assert how == exam.HowExamined(
        asked=2,
        marks_min=2,
        marks_max=4,
        papers=["Paper 2", "Paper 4"],
        years=["2025"],
        command_words=["solve", "find"],
    )
    assert exam.how_examined([template]) is None


def test_scheme_answers_are_read_as_a_student_would_write_them() -> None:
    assert "1.25" in exam.official_answers("1.25 or 1.250… oe")
    assert "x = −1.7, x = 2, x = 4.4" in exam.official_answers(CUBIC.answer_spec["answer"])
    # A line describing working is not a value.
    assert all("ruled" not in a for a in exam.official_answers("ruled line y =2x+1\n−0.35 to −0.45")[1:])


def test_the_worked_question_is_the_richest_one_code_can_check() -> None:
    needs_part_a = exam.ExamItem(
        "part", "0580/21/MJ25/Q6(b)", "past_paper", "Use your graph to solve these.", None, 5, "use", True,
        HCF.answer_spec, HCF.mark_scheme,
    )  # fmt: skip
    assert exam.pick_worked([HCF, CUBIC, needs_part_a]) is CUBIC  # graph-by-drawing with its curve stated
    assert exam.pick_worked([HCF, needs_part_a]) is HCF
    no_codes = exam.ExamItem("n", "0580/22/MJ25/Q9", "past_paper", "Find 2 + 3.", None, 3, "find", False,
                             {"type": "numeric", "answer": "5"}, {"text": "5 cao"})  # fmt: skip
    assert exam.pick_worked([no_codes]) is None  # the scheme names no marks to tag steps with


def test_a_walkthrough_must_reach_the_schemes_answer_by_the_schemes_line() -> None:
    kept, report = exam.guard_walkthrough(draft(GOOD_CUBIC, "x = -1.6, x = 2, x = 4.5"), CUBIC)
    assert kept is not None and report.kept and kept["approved"] is False  # a person reads it first
    # The sign slip Flash-Lite made three times: the answer alone would not have caught it.
    wrong_line = [("So draw the line $y = x - 10$.", "B1"), *GOOD_CUBIC[1:]]
    assert exam.guard_walkthrough(draft(wrong_line, "x = -1.6, x = 2, x = 4.5"), CUBIC)[1].reason == "wrong_line"
    # One value outside its own line's range is wrong, even if it sits in another line's range.
    assert exam.guard_walkthrough(draft(GOOD_CUBIC, "x = -1.6, x = 2.5, x = 4.5"), CUBIC)[0] is None
    assert exam.guard_walkthrough(draft(GOOD_CUBIC, "x = -1.7 to -1.4, x = 2, x = 4.4 to 4.7"), CUBIC)[0] is None


def test_marks_must_be_the_schemes_and_the_arithmetic_true() -> None:
    steps = [("$36 = 2 \\times 2 \\times 3 \\times 3$ and $54 = 2 \\times 3 \\times 3 \\times 3$.", "M1"),
             ("Common factors: $2 \\times 3 \\times 3 = 18$.", "B1")]  # fmt: skip
    assert exam.guard_walkthrough(draft(steps, "18"), HCF)[0] is not None
    assert exam.guard_walkthrough(draft([(steps[0][0], "A1"), steps[1]], "18"), HCF)[1].reason == "mark_not_in_scheme"
    slip = [("$54 = 2 \\times 2 \\times 3 \\times 3$", "M1"), steps[1]]
    assert exam.guard_walkthrough(draft(slip, "18"), HCF)[1].reason == "arithmetic"
    assert exam.guard_walkthrough(draft(steps, "9"), HCF)[1].reason == "answer_incorrect"
    too_many = [(steps[0][0], "M1"), (steps[1][0], "B1"), ("Check it.", "B1")]
    assert exam.guard_walkthrough(draft(too_many, "18"), HCF)[1].reason == "too_many_marks"
    broken = [("Yes, $18 \neq 2 \\times 9$.", "M1"), steps[1]]  # "\\neq" that JSON decoding turned into a newline
    assert exam.guard_walkthrough(draft(broken, "18"), HCF)[1].reason == "garbled"


def test_the_line_to_draw_is_computed_not_asked_for() -> None:
    assert exam.line_to_draw(CUBIC) == "y = 10 - x"
    stated = exam.ExamItem(
        "s", "0580/21/MJ24/Q18", "past_paper",
        "By drawing a suitable straight line, solve the equation $x^3 + 4x^2 - 2 = 2x$ for $-3 \\leq x \\leq 1.5$.",
        "The diagram shows the graph of $y = x^3 + 4x^2 - 2$ for $-3 \\leq x \\leq 1.5$.", 3, "solve", True, {}, {},
    )  # fmt: skip
    assert exam.line_to_draw(stated) == "y = 2 x"
    assert exam.line_to_draw(HCF) is None


def test_arithmetic_allows_rounding_to_the_places_shown() -> None:
    assert exam.arithmetic_holds(["$\\frac{1}{2} \\times \\pi \\times 6.4^2 = 64.3$"])
    assert not exam.arithmetic_holds(["$\\frac{1}{2} \\times 3.14 \\times 6.4^2 = 65.3$"])
    assert exam.arithmetic_holds(["Solve $x - 8 = 0$ to get $x = 8$."])  # letters: an equation, not a sum


def test_a_lesson_example_must_solve_the_equation_it_sets() -> None:
    # SymPy agreed with the model's own expression; the expression was the wrong one (the roots are 1 and 3).
    assert lessons.solves_problem("Use the graph to solve $x^2 - 3x + 2 = x - 1$.", "1.3, 2.7") is False
    assert lessons.solves_problem("Solve $x^2 - 3x + 2 = x - 1$.", "1, 3") is True
    assert lessons.solves_problem("Solve $x^3 + 4x^2 - 2 = 2x$ from the graph.", "-0.52, 0.87") is True
    assert lessons.solves_problem("Find $y$ when $x = 2.5$.", "1.25") is None  # substitution, not solving


def test_lesson_markers_are_stripped_but_intervals_kept() -> None:
    assert lessons.strip_markers("It crosses the axis. [1, 3] Then $x \\in [1, 3]$.") == (
        "It crosses the axis. Then $x \\in [1, 3]$."
    )


def test_a_lesson_example_may_not_reuse_a_past_paper_question() -> None:
    excerpt = lessons.Excerpt("c1", "Book", 12, "Graphs can be used to solve equations by reading intersections.")
    reused = "By drawing a suitable straight line solve the equation x cubed plus four x squared minus two"
    lesson = lessons.LessonDraft(
        summary="s",
        sections=[lessons.DraftSection(heading="h", body="Graphs solve equations where lines cross.", sources=[1])],
        worked_examples=[
            lessons.DraftExample(problem=reused, steps=["s"], final_answer="2", answer_expression="2", sources=[1]),
            lessons.DraftExample(
                problem="Solve $2x = 4$.", steps=["s"], final_answer="2", answer_expression="4/2", level="Exam",
                sources=[1],
            ),
        ],
    )  # fmt: skip
    guarded = lessons.guard(
        lesson, [excerpt], example_check="sympy", names_need_citation=False, past_papers=[reused + " = 2x."]
    )
    assert guarded.report.dropped_examples_past_paper == 1
    assert [(e["problem"], e["level"]) for e in guarded.worked_examples] == [("Solve $2x = 4$.", "exam")]


def test_the_worked_exam_question_is_read_with_the_lesson() -> None:
    lesson = {"summary": "one two three", "sections": [], "worked_examples": []}
    plain = pacing.steps(lesson=lesson, lesson_read=False, check_marks=0, check_answered=False, exam_marks=0,
                         exam_answered=False)  # fmt: skip
    with_exam = pacing.steps(lesson=lesson, lesson_read=False, worked_marks=4, check_marks=0, check_answered=False,
                             exam_marks=0, exam_answered=False)  # fmt: skip
    assert with_exam[0].minutes == plain[0].minutes + 4


def test_a_lesson_may_not_borrow_a_past_papers_curve_or_equation() -> None:
    past = [
        poly
        for question in [
            "The diagram shows the graph of $y = x^3 + 4x^2 - 2$. Solve the equation $x^3 + 4x^2 - 2 = 2x$.",
            "By drawing a suitable straight line on the grid, solve the equation x³ + 4x² - x - 6 = 0.",
        ]
        for poly in lessons._polynomials(question)
    ]
    # Both models wrote this section: one question's curve with another's equation. Correct maths, borrowed.
    borrowed = "If the graph is $y = x^3 + 4x^2 - 2$ and you need to solve $x^3 + 4x^2 - x - 6 = 0$, rewrite it."
    assert lessons.reuses_past_paper_maths(borrowed, past)
    assert not lessons.reuses_past_paper_maths("For $y = x^3 - 2x^2 + 1$, solve $x^3 - 2x^2 - x + 3 = 0$.", past)
    assert not lessons.reuses_past_paper_maths("Solve $2x = 4$.", past)  # a straight line is nobody's question


def test_maths_written_outside_dollar_signs_is_wrapped_so_it_renders() -> None:
    """18 lessons printed "H_2O" and "12x^3" as typed (22 Sep 2026): chemistry upright, algebra and powers as maths."""
    assert lessons.wrap_bare_maths("36 g of H_2O and Ca(OH)_2 in 1 dm^3") == (
        "36 g of $\mathrm{H_2O}$ and $\mathrm{Ca(OH)_2}$ in 1 $\mathrm{dm^3}$"
    )
    assert lessons.wrap_bare_maths("Simplify 12x^3; 6.02 x 10^23 particles") == (
        "Simplify $12x^3$; 6.02 x $10^{23}$ particles"
    )
    assert (
        lessons.wrap_bare_maths("already $x^2$, in 2024, costs 3 dollars") == "already $x^2$, in 2024, costs 3 dollars"
    )
