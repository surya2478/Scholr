from __future__ import annotations

from app.modules.knowledge.chunking import (
    MAX_CHARS,
    PageText,
    chunk_pages,
    page_offset,
    printed_page_map,
    section_for_page,
    sections_for_span,
)

# Fixture pages written for this test.
PAGES = [
    PageText(2, "# Chapter 1\n## 1.1 Rounding\n" + "Rounding keeps a number close in value. " * 25),
    PageText(3, "### Example 1\nRound 3.14159 to 3 significant figures.\nAnswer 3.14"),
    PageText(
        4, "## Exercise 1A\n1 Round 2.718 to 2 significant figures.\n### Advice and Tips\nLook at the next digit."
    ),
    PageText(5, "# Answers to Chapter 1\n1 2.7"),
    PageText(6, "# Chapter 2\n## 2.1 Fractions\nA fraction is part of a whole."),
]


def test_examples_and_exercises_are_their_own_chunks_and_answers_are_skipped() -> None:
    drafts, skipped = chunk_pages(PAGES, "explanation")
    assert skipped == {5}
    kinds = [d.content_kind for d in drafts]
    assert kinds == ["explanation", "worked_example", "exercise", "explanation"]
    example = drafts[1]
    assert example.heading_path == "Chapter 1 > 1.1 Rounding > Example 1"
    assert example.page_start == example.page_end == 3
    exercise = drafts[2]
    assert "Advice and Tips" in exercise.content  # a sub-heading inherits the exercise kind
    assert all("Answers to" not in d.content and "1 2.7" not in d.content for d in drafts)
    assert drafts[3].heading_path == "Chapter 2 > 2.1 Fractions"


def test_long_blocks_are_split_at_paragraphs_within_the_limit() -> None:
    long_page = PageText(10, "## Big section\n" + "\n\n".join("Paragraph text here. " * 30 for _ in range(12)))
    drafts, _ = chunk_pages([long_page], "explanation")
    assert len(drafts) > 1
    assert all(len(d.content) <= MAX_CHARS for d in drafts)


def test_page_offset_uses_the_most_common_difference() -> None:
    assert page_offset([(2, "1"), (3, "2"), (10, "x"), (11, None), (40, "39")]) == 1
    assert page_offset([(5, None)]) is None


def test_printed_page_map_follows_offset_changes() -> None:
    labels = [(20, "2"), (21, None), (40, "22"), (150, "136"), (151, None), (152, "x"), (200, "186")]
    mapping = printed_page_map(labels)
    assert mapping[20] == 2 and mapping[21] == 3  # offset 18 near the start
    assert mapping[151] == 137 and mapping[152] == 138  # offset 14 after pages dropped out of the scan
    assert printed_page_map([(5, None)]) == {}


def test_section_for_page() -> None:
    starts = [(2, "a"), (10, "b")]
    assert section_for_page(1, starts) is None
    assert section_for_page(2, starts) == "a"
    assert section_for_page(9, starts) == "a"
    assert section_for_page(10, starts) == "b"


def test_a_text_layer_book_without_headings_keeps_each_page_its_own_chunk() -> None:
    from app.modules.knowledge.chunking import PageText, chunk_pages

    # A page of a real text-layer book (~2,000 characters): before, the whole headingless book became one block
    # and every chunk was dated to its first page, so none could be tagged by printed page.
    body = "Force is measured in newtons. " * 70
    drafts, _ = chunk_pages([PageText(40, body), PageText(41, body), PageText(42, body)], "explanation")
    assert [d.page_start for d in drafts] == [40, 41, 42]


def test_printed_page_numbers_are_found_from_the_book_s_own_offset() -> None:
    from app.modules.knowledge.chunking import detect_printed_labels

    # Offset 13 throughout; page 60 also shows a figure number (4) at its edge and page 61 a year, both ignored.
    pages = [(n, f"Chapter text line\nmore text\n{n - 13}") for n in range(30, 60)]
    pages += [(60, "Figure 4 shows the setup\nbody\n47"), (61, "In 1905 Einstein\nbody\nno number here")]
    labels = detect_printed_labels(pages)
    assert labels[30] == "17" and labels[60] == "47"
    assert 61 not in labels
    assert detect_printed_labels([(1, "no numbers"), (2, "none")]) == {}


def test_front_matter_before_printed_page_one_has_no_printed_page() -> None:
    from app.modules.knowledge.chunking import printed_page_map

    mapping = printed_page_map([(5, None), (30, "17"), (31, None)])
    assert 5 not in mapping, "PDF page 5 at offset 13 would be page -8"
    assert (mapping[30], mapping[31]) == (17, 18)


def test_a_chunk_spanning_several_pages_belongs_to_every_objective_starting_inside_it() -> None:
    """Chemistry 13.2 runs 261-266 as one heading: its chunks all carry page 261, yet Group I starts on 265 and
    Group VII on 266. Tagging by the first page alone left both with no chunks (22 Sep 2026)."""
    starts = [(259, "8.1"), (265, "8.2"), (266, "8.3"), (267, "8.5"), (269, "8.4")]
    assert sections_for_span(261, 266, starts) == ["8.1", "8.2", "8.3"]
    assert sections_for_span(266, 266, starts) == ["8.3"]
    assert sections_for_span(250, 258, starts) == []  # before the first objective: untagged, as before
