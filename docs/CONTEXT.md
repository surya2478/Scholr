# Context — v2.1 (as of 14 Sep 2026)

This is seed context. In code it lives in seed files / database rows, never hard-coded.
Items marked **(verify)** were not confirmed by the user and must be checked against official Cambridge documents before being seeded.

## Student

| Field | Value |
|---|---|
| Stage | Year 10 (2026–27) |
| School | Cambridge International School, Dubai |
| Curriculum | Cambridge International (CAIE) IGCSE |
| Tier | **Extended** for Mathematics and sciences |
| Location / jurisdiction | UAE (residence) and India |
| Long-term interest | Civil Services / IAS — exploration only |

## IGCSE subjects and exam sessions

| Subject | Code | Tier | Exam session | Phase |
|---|---|---|---|---|
| Mathematics | 0580 (confirmed) | Extended | May/Jun 2028 | **Phase 1 — slice 1** |
| Sociology | 0495 (confirmed) | Untiered (verify) | **May/Jun 2027** | **Phase 1 — slice 2** |
| Physics | 0625 (verify) | Extended | May/Jun 2028 | Next slice |
| Chemistry | 0620 (verify) | Extended | May/Jun 2028 | Phase 2 |
| Biology | 0610 (verify) | Extended | May/Jun 2028 | Phase 2 |
| English | unknown | — | May/Jun 2028 | Phase 2 |
| Global Perspectives | 0457 (verify) | — | May/Jun 2028 | Phase 2 |
| Arabic | unknown (0508 First Language vs 0544 Foreign Language) | — | May/Jun 2028 | Phase 2 |

Sociology sits in option block 1 (Business Studies was the alternative and is **not** taken).

### Mathematics 0580 Extended — what the provided papers confirm

Confirmed from the May/June 2024 papers and mark schemes (older syllabus format):
- Paper 2 (Extended): 1 h 30 min, 70 marks. Paper 4 (Extended): 2 h 30 min, 130 marks. Answer all questions.
- Calculators allowed on all 2024 papers ("use a calculator where appropriate").
- Accuracy instruction: non-exact answers to 3 significant figures, angles in degrees to 1 decimal place, π = calculator value or 3.142.
- Mark scheme notation: M, A, B, SC, FT, isw, oe, cao, dep, nfww, soi.
- Assessment objectives (school planner): **AO1** Knowledge and understanding of mathematical techniques; **AO2** Analyse, interpret and communicate mathematically.

Verified 15 Sep 2026 against the official 0580 syllabus for 2028–2030 (U11 resolved): Extended candidates take **Paper 2 (non-calculator)** and **Paper 4 (calculator)**, each 2 hours and 100 marks (50% each); content areas E1–E9 are Number, Algebra and graphs, Coordinate geometry, Geometry, Mensuration, Trigonometry, Transformations and vectors, Probability, Statistics. The 2025–2027 syllabus has the same structure, so papers from June 2025 on match the 2028 exam format; the 2024 and earlier papers above are practice only for that format (calculator was allowed on all of them).

Curriculum structure in the database comes from the school planner (areas 1–4) and the Collins textbook contents (33 chapters, 194 sections with Extended markers). See `content/curriculum/igcse-maths-0580.yaml`.

### Sociology 0495 — what the provided papers confirm

Confirmed from the May/June 2024 papers and mark schemes (older syllabus format):
- Paper 1: 2 h, 80 marks. Section A theory and methods (compulsory, source-based): 2+2+4+4+8+10+15. Then Section B *or* C: 2+4+6+8+15.
- Paper 2: 1 h 45 min, 70 marks. Answer two sections (2024 options: Family, Education, Crime, Media): each 2+4+6+8+15.
- Command-word pattern per section: "What is meant by" (2), "Describe two" (4), "Explain how" (6), "Explain why" (8), "To what extent" (15).
- Short items use point-based marking; 10- and 15-mark items use levels-of-response bands.
- Assessment objectives (school planner): **AO1** Knowledge and understanding; **AO2** Interpretation and application; **AO3** Analysis and evaluation.

The coursebook (2nd ed, 2023) and the school planner follow the **2025–2027 syllabus** (verified 15 Sep 2026, U11 resolved): Research methods; Identity: self and society; Social stratification and inequality; Family; Education; Crime, deviance and social control (no Media). **Paper 1** Research Methods, Identity and Inequality — 2 h, 80 marks: Question 1 research methods (compulsory, includes data response), then Question 2 or 3. **Paper 2** Family, Education and Crime — 1 h 45 min, 80 marks: two optional structured questions from three. Papers from June 2025 on follow this structure; the 2024 and earlier papers are practice only.

## School Term 1 topic planners (Sep – Dec 2026)

### Mathematics 0580

| Units | Topics |
|---|---|
| 1 | Number |
| 2 | Algebra and graphs |
| 3 | Coordinate geometry |
| 4 | Geometry (excluding circle theorems) |

AOs in planner: AO1, AO2.
Resources: Collins Cambridge IGCSE Maths textbook, PPTs and practice worksheets, IGCSE past papers 0580, Century Tech.

### Sociology 0495

**Paper 1**
- Identity: self and society
  1. How do we learn our identity?
  2. How does society control us?
  3. What influences our social identity?
- Revision
- Research methods
  - (a) How do different sociologists interpret society?
  - (b) What types of information and data do sociologists use?
  - (c) How do sociologists investigate society?

**Paper 2**
- Education
  1. What is education and schooling?
  2. What are the roles and functions of education?
  3. What factors help to explain differences in educational achievement and experience?
- Family
  1. What are the different types of families?
  2. What is the role of the family for the individual and society?
  3. How is family life changing?

AOs in planner: AO1, AO2, AO3.
Resources: resources and PPTs in Teams, worksheets and classwork, past exam papers, CIE textbook (**title unknown**).

Remaining Sociology topics (likely Terms 2–3): load from syllabus **(verify)**.

## External commitments

| Commitment | Load | Notes |
|---|---|---|
| IIT Foundation (external online) | ~6 h/week | Maths, Physics, Chemistry. Platform complements, never duplicates. Integration in Phase 3; schedule block known to planner from Phase 1. |
| India Explorer (target) | ~30 min/day | Phase 4. Not scheduled in Phase 1. |
| Extracurriculars | unknown | Capture in planner commitments. |

## Materials the family legitimately has

| Material | Subject | Form needed for ingestion | Status |
|---|---|---|---|
| Collins Cambridge IGCSE™ Maths Student's Book, 4th edition (781-page scan, written for 0580 from 2020) | Maths | Scanned PDF → vision OCR | Received; OCR running on Flash-Lite (first 179 pages from gemini-3.5-flash) |
| School PPTs and worksheets (Teams) | Maths, Sociology | Export files | To obtain |
| 0580 May/June 2024 papers 1–4, mark schemes, examiner report | Maths | Text PDFs | Received; extracted; Paper 21 in question bank (28 items verified), others importing |
| Century Tech (school platform) | Maths | Not ingested; import results manually | — |
| *Sociology for Cambridge IGCSE™ and O Level Coursebook*, 2nd ed (Blundell & Roberts, CUP 2023), 308-page scan | Sociology | Scanned PDF → vision OCR | Received; OCR complete (Flash-Lite except the first 41 pages) |
| 0495 May/June 2024 papers 1–2, mark schemes, examiner report | Sociology | Text PDFs | Received; extracted |
| Classwork / student notes | Both | Photos or files | Ongoing |
| Cambridge syllabus documents 0580 (2025–2027 and 2028–2030), 0495 (2025–2027) | Both | Official PDFs | Received 15 Sep 2026; curriculum verified |
| PapaCambridge past papers: 0580 Papers 21/22/41/42 and 0495 Papers 11/12/21/22 with mark schemes, May/June 2025, Oct/Nov 2024, May/June 2023 (+ examiner reports for June sessions) | Both | Text PDFs | Downloaded 15 Sep 2026; registered and text extracted; Maths mark schemes parsed |
| IIT Foundation class material | Maths/Phys/Chem | — | Phase 3 |

All materials are for this student's private use only: stored privately, never redistributed, excerpts shown in short form with page references.

## Platform decisions from the user

| Topic | Decision |
|---|---|
| LLM provider | OpenRouter. Budget is not a constraint — choose models on quality, but still track cost. |
| Parent visibility | Parents may see all content now (student and parent are aligned). Separate student and parent logins. Build scoped grants so that, when the platform goes live, parents see only the modules assigned to them. |
| First slice | Maths and Sociology (planners provided) |

## Open unknowns

| # | Question | Blocking? |
|---|---|---|
| ~~U1~~ | ~~Sociology textbook title and digital copy~~ — resolved 14 Sep 2026 | — |
| ~~U11~~ | ~~Official syllabus PDFs~~ — resolved 15 Sep 2026 (0580 2028–2030 and 0495 2025–2027 syllabuses in `subjects/`; curriculum files verified) | — |
| U12 | More past papers — partly resolved 15 Sep 2026: downloaded from PapaCambridge into `subjects/*/papacambridge/` (0580 Papers 21/22/41/42 and 0495 Papers 11/12/21/22 with mark schemes, for May/June 2025, Oct/Nov 2024 and May/June 2023; examiner reports except Oct/Nov 2024). Only June 2025 on matches the current exam format, so more 2025–2026 series and specimen papers would still help build three parallel study forms | Blocks study forms: Maths by W4 (9 Oct), Sociology by W6 (26 Oct) |
| ~~U13~~ | ~~Student display name; IIT class days/times~~ — resolved 15 Sep 2026: stored in the private household seed (three 2-hour IIT Foundation classes: Monday and Thursday afternoons, Saturday afternoon) | — |
| U2 | Week-by-week Term 1 scheme of work for Maths and Sociology (which topic in which week). **Partly resolved 19 Sep 2026:** the school's Term 1 planners (dated 5 Sep 2026, whole year group and Option 1) confirm the Term 1 topic lists already recorded above, but give no week order, so which pair of topics is taught in the same window is still unknown | Blocks validation topic selection (W4) |
| U3 | 10–20 teacher-marked Sociology answers and some marked Maths work, for calibration | Blocks Sociology evaluator sign-off (W6) |
| U4 | Parent notification channel for urgent safety incidents (email / SMS / WhatsApp). **Deferred 20 Sep 2026** at the user's request (STUDENT-APP D8): alerts stay queued and visible on the parent dashboard | Blocks any public address |
| U5 | Verified crisis/helpline resources for UAE and India. **Deferred 20 Sep 2026** with U4 | Blocks any public address |
| U6 | Hosting preference and region. **Resolved 20 Sep 2026**: the home machine for two to three months, then a small VPS (STUDENT-APP D6); sign-in is email and password with admin approval (D7) | Resolved |
| U7 | English and Arabic syllabus codes. **Partly resolved 19 Sep 2026** from the school planner: Global Perspectives is CIE **0457**; English is offered as First Language English CIE **0500** (with Literature 0475) or English as a Second Language Edexcel **4XES2** — which one she takes is not known; Arabic is taught as school levels "Arabic A/B" with no Cambridge code | Phase 2 |
| U8 | Physics/Chemistry/Biology textbooks | Next slice |
| U9 | IIT Foundation provider and what data it exposes | Phase 3 |
| U10 | Extracurricular schedule | Planner (W5), non-blocking |
