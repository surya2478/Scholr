"""Dialectical Crucible Engine for Cambridge IGCSE Sociology 0495.

Provides multi-perspective roundtable debates (Functionalism vs Marxism vs Feminism vs Interactionism)
and structured AO3 evaluation scaffolds for 10- and 15-mark essay questions.
"""

from __future__ import annotations

from pydantic import BaseModel


class SociologistAvatar(BaseModel):
    name: str
    perspective: str  # Functionalism, Marxism, Feminism, Interactionism, Positivism
    core_thesis: str
    key_concept: str
    empirical_evidence: str


class CrucibleTopic(BaseModel):
    id: str
    syllabus_unit: str
    essay_question: str
    marks_available: int
    avatars: list[SociologistAvatar]
    synthesis_guidelines: list[str]
    ao3_level_4_descriptor: str


CRUCIBLE_TOPICS: list[CrucibleTopic] = [
    CrucibleTopic(
        id="crucible-edu-01",
        syllabus_unit="Education",
        essay_question=(
            "To what extent does the education system promote social mobility in modern industrial societies?"
        ),
        marks_available=15,
        avatars=[
            SociologistAvatar(
                name="Talcott Parsons",
                perspective="Functionalist",
                core_thesis=(
                    "The school acts as a focal socializing agency, bridging the family and wider society. "
                    "It operates on meritocratic principles, rewarding ability and effort with occupational roles."
                ),
                key_concept="Meritocracy & Role Allocation",
                empirical_evidence=(
                    "Davis and Moore: unequal rewards in society motivate the most talented individuals "
                    "to train for vital positions."
                ),
            ),
            SociologistAvatar(
                name="Bowles & Gintis",
                perspective="Marxist",
                core_thesis=(
                    "Education is an instrument of capitalist reproduction, not social mobility. Through the "
                    "correspondence principle, schools reward obedience and conformity, preparing working-class "
                    "students for subservient manual labour."
                ),
                key_concept="Correspondence Principle & Social Reproduction",
                empirical_evidence=(
                    "Schooling in Capitalist America study: high grades correlated with subservience "
                    "rather than raw creative intellect."
                ),
            ),
            SociologistAvatar(
                name="Michelle Stanworth",
                perspective="Feminist",
                core_thesis=(
                    "Social mobility through education has historically been unequal for girls due to gendered subject "
                    "packaging and hidden stereotyping. Even when girls outperform boys, the glass ceiling restricts "
                    "career advancement."
                ),
                key_concept="Gendered Stereotyping & Glass Ceiling",
                empirical_evidence=(
                    "Interviews with teachers revealed boys were viewed as naturally capable while girls' success "
                    "was attributed merely to quiet conformity."
                ),
            ),
        ],
        synthesis_guidelines=[
            "Acknowledge the meritocratic claim (qualifications do open doors for some working-class students).",
            "Contrast with persistent structural barriers (cultural capital, tuition fees, private school networks).",
            (
                "Conclude with a nuanced evaluative judgement (e.g., education enables individual mobility "
                "but does not eliminate class inequalities)."
            ),
        ],
        ao3_level_4_descriptor=(
            "Level 4 (12-15 marks): Balanced evaluation with effective use of competing theoretical perspectives, "
            "precise sociological concepts, and a justified conclusion directly addressing 'To what extent'."
        ),
    ),
    CrucibleTopic(
        id="crucible-fam-01",
        syllabus_unit="Family",
        essay_question="To what extent has the nuclear family lost its functions in modern industrial society?",
        marks_available=15,
        avatars=[
            SociologistAvatar(
                name="Talcott Parsons",
                perspective="Functionalist",
                core_thesis=(
                    "The nuclear family has not lost its functions; it has specialized into two vital, irreducible "
                    "functions: primary socialization of children and stabilization of adult personalities "
                    "('warm bath' theory)."
                ),
                key_concept="Functional Specialization & Warm Bath Theory",
                empirical_evidence="Isolated nuclear family fits geographically mobile workforce in modern economies.",
            ),
            SociologistAvatar(
                name="Eli Zaretsky",
                perspective="Marxist",
                core_thesis=(
                    "The family creates a safe illusion that cushions workers against the exploitation of "
                    "capitalism, while functioning as an essential unit of consumer consumption that generates profits."
                ),
                key_concept="Unit of Consumption & Ideological Cushion",
                empirical_evidence=(
                    "Pester power advertising targets children to pressure working-class parents "
                    "into purchasing luxury consumer goods."
                ),
            ),
            SociologistAvatar(
                name="Ann Oakley",
                perspective="Feminist",
                core_thesis=(
                    "The conventional nuclear family serves patriarchy by forcing women into unpaid domestic and "
                    "emotional labour, perpetuating inequality under the guise of natural maternal instinct."
                ),
                key_concept="Patriarchal Oppression & Double Burden",
                empirical_evidence=(
                    "Housewife study: 70% of housewives reported dissatisfaction and isolation in "
                    "home-centred nuclear routines."
                ),
            ),
        ],
        synthesis_guidelines=[
            (
                "Distinguish between lost economic/educational functions (now performed by state/schools) "
                "and retained emotional functions."
            ),
            (
                "Recognize increasing family diversity (single-parent, reconstituted, cohabiting) which challenges "
                "the dominance of the traditional nuclear model."
            ),
            "Reach a clear concluding judgement assessing whether functions have vanished or simply adapted.",
        ],
        ao3_level_4_descriptor=(
            "Level 4 (12-15 marks): Evaluates whether welfare institutions have replaced family functions or merely "
            "partnered with them, weighing Functionalist optimism against critical Marxist and Feminist critiques."
        ),
    ),
]


def list_crucible_topics(syllabus_unit: str | None = None) -> list[CrucibleTopic]:
    """Retrieve Sociology roundtable debate topics."""
    if not syllabus_unit:
        return CRUCIBLE_TOPICS
    return [t for t in CRUCIBLE_TOPICS if t.syllabus_unit.lower() == syllabus_unit.lower()]


def get_crucible_topic(topic_id: str) -> CrucibleTopic | None:
    """Retrieve a single crucible topic by ID."""
    for t in CRUCIBLE_TOPICS:
        if t.id == topic_id:
            return t
    return None
