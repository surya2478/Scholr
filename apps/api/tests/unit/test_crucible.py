"""Unit tests for the Sociology 0495 Dialectical Crucible Engine."""

from __future__ import annotations

from app.modules.curriculum.crucible import get_crucible_topic, list_crucible_topics


def test_list_and_filter_crucible_topics() -> None:
    all_topics = list_crucible_topics()
    assert len(all_topics) >= 2

    edu_topics = list_crucible_topics("Education")
    assert len(edu_topics) == 1
    assert edu_topics[0].syllabus_unit == "Education"
    assert "social mobility" in edu_topics[0].essay_question

    fam_topics = list_crucible_topics("Family")
    assert len(fam_topics) == 1
    assert fam_topics[0].syllabus_unit == "Family"


def test_crucible_topic_avatars_and_descriptors() -> None:
    topic = get_crucible_topic("crucible-edu-01")
    assert topic is not None
    assert len(topic.avatars) == 3

    perspectives = {a.perspective for a in topic.avatars}
    assert "Functionalist" in perspectives
    assert "Marxist" in perspectives
    assert "Feminist" in perspectives

    assert "Level 4" in topic.ao3_level_4_descriptor
    assert len(topic.synthesis_guidelines) >= 3
