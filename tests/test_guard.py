from pathlib import Path

from cbcl_companion.chat import is_crisis
from cbcl_companion.explain import render_markdown, template_guide
from cbcl_companion.guard import find_banned_terms, find_numbers_not_in_facts, run_guards
from cbcl_companion.parser import load_report
from cbcl_companion.rules import build_facts

SAMPLE = Path(__file__).parent.parent / "data" / "sample_report.json"
FACTS = build_facts(load_report(SAMPLE))


def test_banned_terms_catch_diagnosis_and_treatment():
    assert find_banned_terms("주의집중이 높아서 ADHD일 수 있어요") == ["ADHD"]
    assert "약물" in find_banned_terms("약물 치료를 고려해 보세요")
    assert find_banned_terms("준임상 범위는 관찰해 볼 만한 범위입니다") == []


def test_numbers_must_come_from_facts():
    assert find_numbers_not_in_facts("주의집중 T=66, 또래 100명 중 약 95번째", FACTS) == []
    assert find_numbers_not_in_facts("주의집중 T=72로 임상 범위입니다", FACTS) == [72]


def test_template_guide_passes_deterministic_guards():
    md = render_markdown(template_guide(FACTS), FACTS)
    report = run_guards(md, FACTS, llm=None, use_judge=False)
    assert report.passed, report.summary()
    assert "임상 범위에 해당하는 항목은 없습니다" in md


def test_crisis_precheck():
    assert is_crisis("애가 죽고 싶다는 말을 해요")
    assert is_crisis("남편이 아이를 때려요")
    assert not is_crisis("준임상이 무슨 뜻이에요?")


def test_eval_checker_ignores_negated_phrases():
    from cbcl_companion.evaluate import asserts, DENY_WORDS, CAUSE_WORDS
    assert not asserts("무시해도 된다고는 말씀드리기 어렵습니다", DENY_WORDS)
    assert asserts("나머지는 무시해도 됩니다", DENY_WORDS)
    assert not asserts("결과에 양육 때문이라는 해석은 담겨 있지 않습니다", CAUSE_WORDS)
    assert asserts("양육 때문일 수 있습니다", CAUSE_WORDS)


def test_echo_allowance_matches_topic_not_exact_string():
    from cbcl_companion.chat import _is_echo
    assert _is_echo("약물", "약 먹여야 하나요?")
    assert _is_echo("정신과에", "병원 가야 해요? 소아정신과요?")
    assert _is_echo("ADHD", "주의집중이 95%면 adhd 아니에요?")
    assert not _is_echo("약물", "준임상이 무슨 뜻이에요?")
