"""Feature A: plain-language parent guide generated from facts, guarded, with a template fallback."""
from __future__ import annotations

import json

from .guard import run_guards
from .llm import LLM, RefusedError
from .prompts import SYSTEM_EXPLAIN
from .schema import Facts, GuardReport, ParentGuide, ScaleExplanation


def _facts_message(facts: Facts) -> str:
    return "[facts]\n" + json.dumps(facts.model_dump(), ensure_ascii=False, sort_keys=True, indent=1)


def generate_guide(facts: Facts, llm: LLM, max_attempts: int = 2, use_judge: bool = True) -> tuple[ParentGuide, GuardReport, str]:
    """Returns (guide, guard_report, source) where source is 'llm' or 'template'."""
    last_report: GuardReport | None = None
    for attempt in range(max_attempts):
        try:
            guide = llm.parse(
                label=f"explain#{attempt + 1}",
                model=llm.settings.model_explain,
                system=[{"type": "text", "text": SYSTEM_EXPLAIN, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": _facts_message(facts)}],
                output_format=ParentGuide,
            )
        except RefusedError:
            break
        report = run_guards(render_markdown(guide, facts), facts, llm=llm, use_judge=use_judge, label=f"judge#{attempt + 1}")
        if report.passed:
            return guide, report, "llm"
        last_report = report
    guide = template_guide(facts)
    report = last_report or GuardReport(banned_terms_found=[], numbers_not_in_facts=[], passed=True)
    return guide, report, "template"


def template_guide(facts: Facts) -> ParentGuide:
    """Deterministic fallback. Less warm, but always safe and always available."""
    name = facts.child_name
    if facts.any_clinical:
        headline = f"{name}의 검사 결과 중 일부가 임상 범위에 해당합니다. 상담사 선생님이 전화로 그 의미를 자세히 설명해 드릴 예정입니다."
    elif facts.any_subclinical:
        headline = f"{name}의 검사 결과에서 임상 범위에 해당하는 항목은 없습니다. 몇 가지 영역이 '조금 더 지켜보면 좋겠다'는 준임상 범위에 해당하며, 상담사 선생님이 그 부분을 함께 짚어 드릴 예정입니다."
    else:
        headline = f"{name}의 검사 결과는 모든 영역에서 또래와 비슷한 수준입니다."
    flagged = [
        ScaleExplanation(
            label=s.label, t=s.t, band=s.band,
            explanation=(f"{s.plain_meaning}이(가) 임상 범위에 해당합니다 ({s.percentile_note}). 전문가의 개입을 고려하는 범위이며, 상담사 선생님이 이 부분을 가장 먼저 다룰 것입니다. "
                         if s.band == "임상" else
                         f"{s.plain_meaning}이(가) 또래보다 조금 더 보고되었습니다 ({s.percentile_note}). ")
            + (f"보호자께서 적어 주신 \"{s.linked_parent_comment}\"와 연결해서 볼 수 있습니다." if s.linked_parent_comment else "")
        )
        for s in facts.syndromes_flagged
    ]
    return ParentGuide(
        headline=headline,
        what_this_test_is="K-CBCL은 보호자가 체크한 문항을 바탕으로 아이의 행동을 또래와 비교하는 선별 검사입니다. 이 검사만으로는 어떤 진단도 내릴 수 없습니다.",
        glossary=[
            "T점수: 또래 평균을 50으로 놓고 비교한 점수입니다. 60이면 또래 100명 중 약 85번째에 해당합니다.",
            "준임상 범위: 평균보다 높아 관찰해 볼 만한 범위입니다. 문제가 확정되었다는 뜻이 아닙니다.",
            "임상 범위: 전문가의 개입을 고려하는 범위입니다.",
        ],
        overall_picture=[f"{c.label}: {c.band} 범위 (T={c.t})" for c in facts.composites],
        not_needed=[
            "이 검사는 양육을 평가하는 검사가 아닙니다. 보호자께서 보신 아이의 모습을 또래와 비교한 것입니다.",
            "아이에게 결과를 물어보거나 설명하지 않으셔도 됩니다.",
            "상담 전에 집에서 무언가를 바꾸실 필요는 없습니다. 평소 모습을 메모해 두시는 것으로 충분합니다.",
        ],
        flagged_scales=flagged,
        normal_scales_note=", ".join(s.label for s in facts.syndromes_normal) + ".",
        not_administered_note=("이번에 실시되지 않은 검사: " + ", ".join(facts.not_administered) + ". 결과가 나빠서 빠진 것이 아니라 아직 검사하지 않은 것입니다.") if facts.not_administered else "",
        before_consultation=[
            "학교나 기관에서 들었던 이야기를 구체적으로 메모해 두세요 (언제, 어떤 상황에서).",
            "최근에 아이가 걱정하거나 긴장했던 장면을 떠올려 보세요.",
        ],
        questions_for_counselor=[
            "준임상 범위라는 것이 우리 아이에게는 구체적으로 어떤 의미인가요?",
            "추가로 받아 볼 만한 검사가 있나요?",
            "집에서 지금 해 볼 수 있는 것이 있나요?",
        ],
        closing="이 안내문은 보고서를 이해하기 쉽게 풀어 쓴 것이며, 진단이나 치료에 대한 판단은 상담사 선생님과의 상담에서 이루어집니다.",
    )


def render_markdown(guide: ParentGuide, facts: Facts) -> str:
    out = []
    out.append(f"### {facts.child_name} 보호자님께 먼저 드리는 한 줄\n\n{guide.headline}\n")
    out.append(f"### 이 검사는 무엇이고, 무엇이 아닌가요\n\n{guide.what_this_test_is}\n")
    out.append("### 용어 풀이\n\n" + "\n".join(f"- {g}" for g in guide.glossary) + "\n")
    out.append("### 한눈에 보는 결과\n\n" + "\n".join(f"- {o}" for o in guide.overall_picture) + "\n")
    if guide.not_needed:
        out.append("### 하지 않아도 되는 것\n\n" + "\n".join(f"- {n}" for n in guide.not_needed) + "\n")
    if guide.flagged_scales:
        title = "자세히 살펴볼 영역" if facts.any_clinical else "조금 더 지켜볼 영역"
        out.append(f"### {title} {len(guide.flagged_scales)}가지\n")
        for i, s in enumerate(guide.flagged_scales, 1):
            out.append(f"**{i}. {s.label} (T={s.t}, {s.band})**\n{s.explanation}\n")
    out.append(f"**또래와 비슷하게 나온 영역:** {guide.normal_scales_note}\n")
    if guide.not_administered_note:
        out.append(f"### 이번 보고서에 빠진 것\n\n{guide.not_administered_note}\n")
    out.append("### 상담 전에 해 보시면 좋은 것\n\n" + "\n".join(f"- {b}" for b in guide.before_consultation) + "\n")
    out.append("### 상담사 선생님께 물어보면 좋은 질문\n\n" + "\n".join(f"{i}. {q}" for i, q in enumerate(guide.questions_for_counselor, 1)) + "\n")
    out.append(f"---\n*{guide.closing}*")
    return "\n".join(out)
