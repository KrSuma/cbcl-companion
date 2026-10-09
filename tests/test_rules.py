import json
from pathlib import Path

from cbcl_companion.parser import load_report
from cbcl_companion.rules import build_facts, composite_band, syndrome_band, percentile_note

SAMPLE = Path(__file__).parent.parent / "data" / "sample_report.json"


def test_bands_follow_report_thresholds():
    assert composite_band(59) == "정상"
    assert composite_band(60) == "준임상"
    assert composite_band(62) == "준임상"
    assert composite_band(63) == "임상"
    assert syndrome_band(59) == "정상"
    assert syndrome_band(60) == "준임상"
    assert syndrome_band(69) == "준임상"
    assert syndrome_band(70) == "임상"


def test_sample_report_facts_match_the_pdf():
    facts = build_facts(load_report(SAMPLE))
    assert facts.any_clinical is False
    assert facts.any_subclinical is True
    by = {c.key: c for c in facts.composites}
    assert (by["internalizing"].t, by["internalizing"].band) == (61, "준임상")
    assert (by["externalizing"].t, by["externalizing"].band) == (54, "정상")
    assert (by["total"].t, by["total"].band) == (58, "정상")
    flagged = [(s.label, s.t) for s in facts.syndromes_flagged]
    assert flagged == [("주의집중 문제", 66), ("우울/불안", 63), ("사회적 미성숙", 62), ("위축", 60)]
    assert facts.highest_syndrome.key == "attention"
    assert {s.label for s in facts.syndromes_normal} == {"신체증상", "사고의 문제", "비행", "공격성"}


def test_parent_comment_linking_is_keyword_based():
    facts = build_facts(load_report(SAMPLE))
    att = next(s for s in facts.syndromes_flagged if s.key == "attention")
    assert "산만" in att.linked_parent_comment
    soc = next(s for s in facts.syndromes_flagged if s.key == "social_immaturity")
    assert "친구" in soc.linked_parent_comment


def test_percentile_note():
    assert "95" in percentile_note(66)
    assert "85" in percentile_note(60)


def test_sample_json_carries_the_report_narrative():
    r = load_report(SAMPLE)
    n = r.narrative
    assert n is not None
    assert len(n.observations) == 5 and n.observations[1].title == "주의집중 문제 · T = 66"
    assert len(n.interpretation) == 3 and len(n.caveats) == 5 and len(n.special_scales) == 2
    # wrapped lines were re-joined correctly
    assert "대상 아동의 경우 추후" in n.social_competence_note
    assert any("유의미한 수준이 아닙니다" in p for p in n.interpretation)
    assert any("주기적 재평가가 권장됩니다" in p for p in n.interpretation)
    assert any("병행 실시가 권장됩니다" in c for c in n.caveats)
