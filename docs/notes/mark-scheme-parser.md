# Mark-scheme table parser (IGCSE Mathematics 0580)

Status: built 2026-09-14. Deterministic, no LLM. Code: `apps/api/app/modules/assessment/mark_scheme.py`,
CLI `app.jobs.mark_scheme_parse`, integration in `past_papers.py` / `app.jobs.question_bank` (prompt
`past_paper_extract/v2`). No answer text in this note; values of any comparison live in `content/private/`.

## Why

The v1 extractor asked an LLM for each part's answer and mark scheme from the whole mark-scheme text layer.
Screening the low-cost model found wrong answer keys that passed every check (value taken from the neighbouring
row, a stacked fraction read as its numerator, a value from another part). The text layer loses the table
structure: stacked fractions split across lines, some rows have no line starting with their ref, and symbol-font
glyphs come through as private-use characters. The answer key is printed in the official table, so it should be
read, not generated.

## How the parser reads a page

1. **Columns.** A page is a table page if one line holds the header words Question, Answer, Marks, Partial (in
   that order). Column boundaries are the thin vertical rules drawn between header words. When several rules sit
   between two header words (0580/31 has a short rule inside an Answer cell), the one with the greatest total drawn
   length wins: column rules run the whole table. Header-word midpoints are only a fallback.
2. **Vertical extent.** From below the header to the lowest end of the column rules, so running headers and footers
   are excluded.
3. **Rows.** Each Question-column line is a ref (`7(b)(ii)`, fourth level `2(a)(vi)(a)` supported; a bare `(c)` or
   `(iii)` continues the previous ref). A row starts at the nearest horizontal rule above its ref in the Question
   column and ends where the next row starts. Content above the first ref on a page continues the last row of the
   previous page (rows spanning pages).
4. **Sub-rows.** Rules that cross the Answer column but not the Question column split a row into sub-rows (merged
   Question cell). A sub-row whose Marks cell holds only method marks (`M1`, `M2`, `M1dep`) is a *method* line; the
   answer is the remaining sub-rows. If every sub-row is method-only, all of it is kept as the answer.
5. **Marks.** Integers in the Marks column are summed per row; if there are none, mark codes are summed
   (`M1`, `A2`, `B2FT`, `M1dep`). Glyphs are assigned to columns one character at a time, so a span such as
   `3 M2` that crosses the Marks/Partial boundary splits correctly.
6. **Cell text.** Characters (PyMuPDF `rawdict`) are clustered into visual lines by vertical centre and ordered by
   x; spaces come from space glyphs or gaps.
   - *Stacked fractions*: a short horizontal stroke inside the cell with glyphs whose bottoms sit on it and glyphs
     whose tops hang just below it (±4.5 pt) becomes one inline token `a/b`, positioned on the bar, so it lands on
     the same line as its neighbours ("0.6 or 3/5"). Compound numerators/denominators are parenthesised. Narrowest
     bars first, so nesting works.
   - *Tall brackets*: Symbol-font bracket pieces (U+F0E6–F0FE) are paired by column; the stacked lines between them
     become `(3, −2)` (column vector) or `(x)` for a single line.
   - *Powers/subscripts*: glyphs smaller than 0.8× the cell's median size, raised/lowered relative to their line,
     become `^2` / `_1`.
   - *Recurring decimals*: MT Extra dot accents attach U+0307 to the digit underneath.
   - *Glyph mapping*: Symbol-font private-use codes U+F020–F0FF map through the Adobe Symbol encoding
     (U+F02D → −, U+F070 → π, U+F0B4 → ×, U+F0B8 → ÷, U+F0A3 → ≤, U+F0D6 → √ ...). En dashes, which these mark
     schemes use as minus signs, become U+2212. Unknown private-use glyphs become U+FFFD and are counted as a
     parse issue (0580/31 has one EuclidMathTwo glyph).
   - *Diagrams*: a drawn shape (not a thin rule) or image centred in the Answer cell sets notation `diagram` — the
     printed text (e.g. Venn labels) is not the whole answer.
7. **Derived fields** (pure functions): accepted ranges from "a to b" (ordered, so negative ranges work), accuracy
   hints (`cao`, `oe`, `isw`, `ft`, `final_answer`, `dp:1`, `sf:3` ...), notation flags (fraction, recurring, power,
   root, pi, range, multi_line, diagram), and `numbers()` for comparisons (minus signs, recurring dots, thousands
   spaces normalised).
8. **Fallback.** A document with no header row returns `None`; `looks_tabular` also requires ≥5 rows and readable
   marks on ≥90% of rows. Sociology 0495 mark schemes (prose level descriptors) return no table, and the v1 flow runs.

## Integration

- `question_bank.py` parses the mark-scheme PDF for subjects in `TABULAR_MARK_SCHEMES` (maths). When the parse is
  usable, `extract_paper(..., table=...)` uses prompt **v2**: question text, answer type, exact value, accuracy and
  objective codes only, with the not-yet-extracted refs and marks listed so items align with the table. The model
  does not see the answers, so its exact value is an independent derivation that SymPy compares with the official
  answer. Each item then takes answer, marks, guidance (method lines + partial marks) and ranges from its row.
  Extractor refs with no row are dropped and reported. v1 is pinned explicitly (`prompt_version="v1"`), because the
  prompt registry otherwise serves the newest version.
- `check_paper_against_table` — paper level: every extractor ref is a row and every row was extracted; table marks
  total and item marks total equal the printed total. Item level: row has an answer and readable marks; item marks
  equal row marks; `numeric_issue` (exact value vs official answer); `answer_type_inconsistent` when a prose type
  (explanation / extended_response) is given for an answer with no prose; `mark_scheme_answer_has_diagram`.
- `--recheck` compares stored items with the table (`ref_not_in_mark_scheme`, `marks_disagree_mark_scheme`,
  `answer_disagree_mark_scheme` when a stored answer number is absent from the official answer) and uses the
  existing `recheck_transition` rules. `--recheck --dry-run` reports without changing rows.
- Saved items record `meta.answer_source = mark_scheme_table`, `mark_scheme.parsed_table = true`,
  `verified_by = extraction_checks_v2`.

## Results (May/June 2024)

| Mark scheme | Rows | Marks total / printed on QP cover | Per-row marks = QP "[n]" sequence | Parse issues |
|---|---|---|---|---|
| 0580/11 | 34 | 56 / 56 | yes (34) | none |
| 0580/21 | 28 | 70 / 70 | yes (28) | none |
| 0580/31 | 53 | 104 / 104 | yes (53) | 1 unmapped glyph |
| 0580/41 | 48 | 130 / 130 | yes (48) | none |
| 0495/11, 0495/21 | — | no table detected (fallback to v1) | — | — |

Agreement with the verified bank (Sonnet-extracted, v1), read-only:

| Paper | Verified items | Marks equal | Bank answer numbers ⊆ parsed answer | Numbers sets equal |
|---|---|---|---|---|
| 0580/21 | 27 | 27 | 27 | 25 (parsed answer also lists printed alternatives) |
| 0580/11 | 32 | 32 | 32 | 31 |

The four screening cases on 0580/21 (3(a), 5(a), 16(b), 21) parse correctly: both values of the two-value answer,
the decimal and the stacked fraction, the single integer, and the angle. `--recheck --dry-run` against the tables
demotes nothing on papers 11, 21, 31, 41. The bank's 0580/41 items (mostly unverified; stored total 132) differ from
the parsed marks on one part, where the parsed marks match the question paper's printed allocation — a bank error.

Flash-Lite (`paper_extractor_lite`, google/gemini-2.5-flash-lite) dry runs with v2:

| Paper | Items | Verified | Marks | Paper issues | Verified but disagreeing with bank | Cost |
|---|---|---|---|---|---|---|
| 0580-mj24-qp21 (before type/diagram guards) | 28 | 17 | 70/70 | none | 6 — 5 answer-type labels, 1 diagram answer | $0.010 |
| 0580-mj24-qp21 (final) | 28 | 13 | 70/70 | none | 1 — answer-type label only | $0.010 |
| 0580-mj24-qp41 (final) | 48 | 0 | 130/130 | 2 extractor refs not in mark scheme | none (item level: 31 verified, 5 differ on type label or formatting only) | $0.014 |

Wrong answer keys: **0**. All answers come from the official table; every remaining disagreement is an answer-type
label or formatting. Fewer items verify than with Sonnet v1 (13 vs 27 on paper 21) mainly because the low-cost
model's exact values are often wrong when it cannot see the answer — the checks catch these, which is the intended
trade (unverified, not wrong).

## Known limitations

- Layout rules are calibrated on the 2024 Cambridge 0580 template (TimesNewRoman + Symbol + MT Extra, filled-rect
  table rules). Other series should be re-run through `app.jobs.mark_scheme_parse` (totals and the QP "[n]" sequence
  check catch most breakage) before trusting them.
- Diagram/graph answers keep only their text labels; they are flagged, not reconstructed.
- Radicals drawn as paths (rather than a √ glyph) would be flagged as diagrams (safe direction). Overbars and
  unusual MathType constructs (matrices, nested roots) are rendered approximately.
- A bare letter label after a four-level ref (`(b)` after `2(a)(vi)(a)`) would resolve to the wrong parent; the 2024
  schemes print full refs.
- `answer_type_inconsistent` only catches prose types for value-only answers; a `numeric` label on a multi-value
  answer with no exact value still passes (seen on 0580/41).
- The "subject has tabular mark schemes" switch is a job-level set (like `ALL_COMPULSORY`); it belongs in subject
  config.
