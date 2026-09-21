"""Topic lessons (docs/STUDENT-APP.md AC-U3–U5) and streams (AC-U1): the guard decides what may be stored.

Excerpts and drafts below are fixture text written for these tests, not from any textbook.
"""

from __future__ import annotations

from app.modules.learn import lessons
from app.modules.subjects import config as subject_config

EXCERPTS = [
    lessons.Excerpt(
        "c1",
        "Fixture Maths Book",
        13,
        "A factor of a whole number divides into it exactly with nothing left over, so the factors of twenty "
        "are one two four five ten and twenty and they come in pairs.",
    ),
    lessons.Excerpt(
        "c2",
        "Fixture Sociology Book",
        60,
        "Oakley (1974) described how gender roles are learnt in the family through canalisation.",
    ),
]


def draft(**overrides: object) -> lessons.LessonDraft:
    values: dict[str, object] = {
        "summary": "Factors divide a number exactly and come in pairs.",
        "sections": [
            {"heading": "Pairs", "body": "Every factor has a partner that multiplies to the number.", "sources": [1]}
        ],
        "key_terms": [{"term": "Factor", "meaning": "Divides a number exactly.", "sources": [1]}],
        "worked_examples": [],
        "pitfalls": ["Forgetting 1 and the number itself."],
    }
    values.update(overrides)
    return lessons.LessonDraft.model_validate(values)


def test_a_cited_section_in_our_own_words_is_kept_with_book_and_page() -> None:
    out = lessons.guard(draft(), EXCERPTS, example_check="none", names_need_citation=False)
    assert out.usable
    assert out.sections[0]["sources"] == [{"chunk_id": "c1", "title": "Fixture Maths Book", "page": 13}]
    assert out.key_terms[0]["term"] == "Factor"


def test_uncited_and_copied_sections_are_dropped() -> None:
    copied = (
        "A factor of a whole number divides into it exactly with nothing left over, so the factors of twenty are one."
    )
    out = lessons.guard(
        draft(
            sections=[
                {"heading": "No source", "body": "Something with no citation at all.", "sources": []},
                {"heading": "Out of range", "body": "Cites an excerpt it was never given.", "sources": [9]},
                {"heading": "Copied", "body": copied, "sources": [1]},
            ]
        ),
        EXCERPTS,
        example_check="none",
        names_need_citation=False,
    )
    assert not out.usable
    assert (out.report.dropped_uncited, out.report.dropped_copied) == (2, 1)


def test_a_named_study_must_be_in_the_excerpts_it_cites() -> None:
    sections = [
        {"heading": "Supported", "body": "Oakley (1974) showed roles are learnt early.", "sources": [2]},
        {"heading": "Invented", "body": "Smith (2011) proved the opposite.", "sources": [2]},
        {"heading": "Wrong excerpt", "body": "Oakley (1974) again, but citing the maths book.", "sources": [1]},
    ]
    out = lessons.guard(draft(sections=sections), EXCERPTS, example_check="none", names_need_citation=True)
    assert [s["heading"] for s in out.sections] == ["Supported"]
    assert out.report.dropped_unsupported_name == 2
    # A subject that does not require citations for named studies keeps them (AC-K4 is Sociology's rule).
    loose = lessons.guard(draft(sections=sections), EXCERPTS, example_check="none", names_need_citation=False)
    assert loose.report.kept_sections == 3


def test_a_name_without_a_year_is_held_to_the_same_rule() -> None:
    sources = "Göran Therborn described seven family systems. Marxist writers disagree."
    assert lessons.unsupported_names("The sociologist Goran Therborn named seven.", sources) == []
    assert lessons.unsupported_names("Many Marxists would reject this.", sources) == []  # plural of a cited word
    assert lessons.unsupported_names("As Parsons argued, families stabilise adults.", sources) == ["Parsons"]
    # A capital at the start of a sentence is grammar, not a name.
    assert lessons.unsupported_names("Families differ. However, most share roles.", sources) == []


def test_summary_and_pitfalls_with_an_invented_name_are_removed() -> None:
    out = lessons.guard(
        draft(
            summary="As Jones (2001) said, factors pair up.", pitfalls=["Jones (2001) warned about this.", "Keep it"]
        ),
        EXCERPTS,
        example_check="none",
        names_need_citation=True,
    )
    assert out.summary == "" and out.pitfalls == ["Keep it"]


def test_sympy_keeps_only_examples_whose_answer_it_reproduces() -> None:
    examples = [
        {
            "problem": "Hypotenuse of 5 and 12.",
            "steps": ["a", "b"],
            "final_answer": "13",
            "answer_expression": "sqrt(5^2+12^2)",
            "sources": [1],
        },
        {
            "problem": "Same, wrong.",
            "steps": ["a"],
            "final_answer": "14",
            "answer_expression": "sqrt(5^2+12^2)",
            "sources": [1],
        },
        {"problem": "3 s.f.", "steps": ["a"], "final_answer": "7.07", "answer_expression": "sqrt(50)", "sources": [1]},
        {
            "problem": "Too few s.f.",
            "steps": ["a"],
            "final_answer": "7.1",
            "answer_expression": "sqrt(50)",
            "sources": [1],
        },
        {
            "problem": "Algebra.",
            "steps": ["a"],
            "final_answer": "$2x+7$",
            "answer_expression": "2*x + 7",
            "sources": [1],
        },
        {"problem": "No expression.", "steps": ["a"], "final_answer": "4", "answer_expression": "", "sources": [1]},
        {
            "problem": "Unparseable.",
            "steps": ["a"],
            "final_answer": "4",
            "answer_expression": "__import__('os')",
            "sources": [1],
        },
    ]
    out = lessons.guard(draft(worked_examples=examples), EXCERPTS, example_check="sympy", names_need_citation=False)
    assert [e["final_answer"] for e in out.worked_examples] == ["13", "7.07", "$2x+7$"]
    assert all(e["checked"] == "sympy" for e in out.worked_examples)
    assert (out.report.dropped_examples_wrong, out.report.dropped_examples_unchecked) == (3, 1)


def test_list_answers_are_checked_value_by_value() -> None:
    check = lessons.example_checks_out
    assert check("1, 2, 3, 4, 6, 9, 12, 18, 36", "1, 2, 3, 4, 6, 9, 12, 18, 36")  # factors of 36
    assert check("1, 8, 27, 64, 125", "1**3, 2**3, 3**3, 4**3, 5**3")
    assert check("125, 64, 27, 8, 1", "1**3, 2**3, 3**3, 4**3, 5**3")  # same values, other order
    assert not check("1, 8, 27, 64, 124", "1**3, 2**3, 3**3, 4**3, 5**3")  # one wrong value
    assert not check("1, 8, 27", "1**3, 2**3, 3**3, 4**3")  # one missing
    # A thousands separator is not a list: $16,240 is one (wrong) value, $3,200 one right one.
    assert not check("$16,240", "15000*(1.04^2)")  # 16 224
    assert check("$3,200", "20000*0.08*2")


def test_words_around_a_value_are_read_past_but_the_value_must_still_be_right() -> None:
    check = lessons.example_checks_out
    assert check("The perimeter is $4w + 10$ cm.", "4*w + 10")
    assert check("15 tiles", "sqrt(225)")
    assert check("LCM = 360", "360")
    assert check("{1, 3, 5, 7, 9}", "set([1, 3, 5, 7, 9])")
    assert check("12 m and 42 m", "2*(54/9), 7*(54/9)")
    # Reading past words never rescues a wrong value, or a count that does not match.
    assert not check("The perimeter is $4w + 12$ cm.", "4*w + 10")
    assert not check("16 tiles", "sqrt(225)")
    assert not check("12 m and 42 m", "2*(54/9)")
    assert not check("HCF = 60, LCM = 360", "60")
    assert not check("-5 is less than -2", "'-5 is less than -2'")


def test_a_part_still_garbled_after_repair_is_dropped() -> None:
    # "\br" is not a LaTeX command, so the repair cannot restore it: BACKSPACE + "r" would show as garbage.
    bad = {"problem": "Work out $(12 \x08r / 4)$.", "steps": ["a"], "final_answer": "3", "answer_expression": "12/4"}
    good = {"problem": "Work out $12 \\div 4$.", "steps": ["a"], "final_answer": "3", "answer_expression": "12/4"}
    out = lessons.guard(
        draft(worked_examples=[{**bad, "sources": [1]}, {**good, "sources": [1]}]),
        EXCERPTS,
        example_check="sympy",
        names_need_citation=False,
    )
    assert [e["problem"] for e in out.worked_examples] == [good["problem"]]
    assert out.report.dropped_garbled == 1
    stored, removed = lessons.drop_garbled({"sections": [], "worked_examples": [{**bad, "sources": []}]})
    assert removed == 1 and stored["worked_examples"] == []


def test_latex_damaged_by_json_decoding_is_repaired_before_checking() -> None:
    # "\times" sent unescaped arrives as TAB + "imes"; "\frac" as FORM FEED + "rac".
    damaged = {
        "problem": "Work out $10 + 2 \times 3$ and $\x0crac{1}{2}$ of 8.",
        "steps": ["$2 \times 3 = 6$"],
        "final_answer": "16",
        "answer_expression": "10 + 2*3",
        "sources": [1],
    }
    out = lessons.guard(draft(worked_examples=[damaged]), EXCERPTS, example_check="sympy", names_need_citation=False)
    [example] = out.worked_examples
    assert example["problem"] == "Work out $10 + 2 \\times 3$ and $\\frac{1}{2}$ of 8."
    assert example["steps"] == ["$2 \\times 3 = 6$"]
    stored, changed = lessons.repair_content({"sections": [{"heading": "h", "body": "$a \times b$"}]})
    assert changed and stored["sections"][0]["body"] == "$a \\times b$"


def test_without_sympy_checking_an_example_is_kept_but_never_marked_checked() -> None:
    example = {
        "problem": "A school detention.",
        "steps": ["formal sanction"],
        "final_answer": "Formal control",
        "sources": [2],
    }
    out = lessons.guard(draft(worked_examples=[example]), EXCERPTS, example_check="none", names_need_citation=True)
    assert out.worked_examples[0]["checked"] is None


def test_every_subject_config_joins_a_declared_stream_and_listed_subjects_exist() -> None:
    streams = subject_config.load_streams()
    keys = {s.key for s in streams.streams}
    configs = subject_config.load_all()
    for config in configs.values():
        assert config.path in keys, f"{config.subject_code} names stream {config.path!r}, which is not declared"
    for stream in streams.streams:
        for code in stream.subjects:
            assert code in configs, f"stream {stream.key} lists {code}, which has no subject config"
            assert configs[code].path == stream.key
        if stream.status == "later":
            assert not subject_config.subjects_in_stream(stream.key)


def test_a_physics_answer_needs_a_real_unit_and_keeps_it_apart_from_the_number() -> None:
    def example(unit: str, answer: str = "900") -> dict:
        return {
            "problem": "Specific heat capacity of a 0.5 kg block given 4500 J for a 10 °C rise.",
            "steps": ["c = E / (m ΔT)"],
            "final_answer": answer,
            "answer_expression": "4500/(0.5*10)",
            "unit": unit,
            "sources": [1],
        }

    examples = [example("J/(kg °C)"), example("bananas"), example(""), example("none", answer="0.5")]
    examples[3]["answer_expression"] = "1/2"
    out = lessons.guard(
        draft(worked_examples=examples), EXCERPTS, example_check="sympy", names_need_citation=False, answer_units=True
    )
    assert [(e["final_answer"], e["unit"]) for e in out.worked_examples] == [("900", "J/(kg °C)"), ("0.5", "")]
    assert out.report.dropped_examples_unit == 2  # a made-up unit, and a blank one


def test_a_subject_without_units_ignores_the_unit_field() -> None:
    maths = {
        "problem": "p",
        "steps": ["s"],
        "final_answer": "13",
        "answer_expression": "13",
        "unit": "cm",
        "sources": [1],
    }
    out = lessons.guard(draft(worked_examples=[maths]), EXCERPTS, example_check="sympy", names_need_citation=False)
    assert out.worked_examples[0]["unit"] == ""


def test_a_unit_already_in_the_answer_is_not_printed_twice() -> None:
    vector = {
        "problem": "Resultant of 50 N right and 10 N left.",
        "steps": ["50 - 10 = 40"],
        "final_answer": "40 N to the right",
        "answer_expression": "50 - 10",
        "unit": "N",
        "sources": [1],
    }
    out = lessons.guard(
        draft(worked_examples=[vector]), EXCERPTS, example_check="sympy", names_need_citation=False, answer_units=True
    )
    assert (out.worked_examples[0]["final_answer"], out.worked_examples[0]["unit"]) == ("40 N to the right", "")
