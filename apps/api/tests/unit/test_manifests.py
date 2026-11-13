from app.core.config import get_settings
from app.modules.knowledge.manifest import load_all
from app.modules.subjects.config import config_for


def test_manifests_parse_and_keys_are_unique() -> None:
    manifests = load_all()
    assert {m.subject for m in manifests} == {
        "igcse-maths",
        "igcse-sociology",
        "igcse-physics",
        "igcse-chemistry",
        "igcse-biology",
    }
    keys = [s.key for m in manifests for s in m.sources]
    assert len(keys) == len(set(keys))


def test_every_source_records_licence_owner_and_authority() -> None:
    for manifest in load_all():
        for src in manifest.sources:
            assert src.licence.strip() and src.owner.strip()
            assert src.private, "Phase 1 sources are private study copies"
            # Textbooks are tier B; Cambridge papers, mark schemes and reports are tier A.
            expected = "B" if src.content_kind == "explanation" else "A"
            assert src.authority_tier == expected, src.key


def test_every_manifest_names_a_real_subject() -> None:
    """A manifest may record material for a subject Scholr does not teach yet (0625, 0620 are `planned`),
    but never for a subject that does not exist — a typo there silently orphans the whole source list."""
    for manifest in load_all():
        config = config_for(manifest.subject)
        assert config.syllabus.code == manifest.syllabus, manifest.subject
        assert config.stage != "external", f"{manifest.subject} is learnt elsewhere; Scholr holds no corpus for it"


def test_manifest_files_exist_when_materials_present() -> None:
    settings = get_settings()
    subjects_dir = settings.resolve_path(settings.subjects_dir)
    if not subjects_dir.is_dir():
        return  # materials are private and absent in CI
    missing = [s.file for m in load_all() for s in m.sources if not (subjects_dir / s.file).is_file()]
    assert not missing, missing


def test_every_maths_question_paper_states_its_calculator_rule() -> None:
    """Improvement 5: the rule is printed on each paper's cover, so the manifest declares it per paper. 0580 Paper 2
    is non-calculator from June 2025 and allowed one before; Paper 4 always allows one."""
    [maths] = [m for m in load_all() if m.subject == "igcse-maths"]
    papers = {s.key: s for s in maths.sources if s.content_kind == "question"}
    assert papers and all(s.calculator_allowed is not None for s in papers.values())
    for key, src in papers.items():
        new_paper_2 = int((src.exam_series or "XX0")[2:]) >= 25 and (src.component or "").startswith("2")
        assert src.calculator_allowed is (not new_paper_2), key
    assert papers["0580-mj25-qp21"].calculator_allowed is False
    assert papers["0580-mj24-qp21"].calculator_allowed is True
