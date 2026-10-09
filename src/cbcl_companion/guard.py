"""Guard layer: proves the parent-facing text never says more than the report.

Three checks, cheapest first:
1. banned terms (regex)            - deterministic, free
2. numbers must come from facts    - deterministic, free
3. LLM judge on a small model      - catches paraphrased diagnosis / invented claims
"""
from __future__ import annotations

import json
import re

from .llm import LLM
from .prompts import BANNED_TERMS, SYSTEM_JUDGE
from .schema import Facts, GuardReport, JudgeVerdict

# Small integers are allowed for list numbering, "100명 중", ages inside facts, etc.
_ALWAYS_ALLOWED = set(range(0, 11)) | {50, 60, 62, 63, 69, 70, 84, 85, 89, 90, 97, 98, 100}


def find_banned_terms(text: str) -> list[str]:
    low = text.lower()
    return [t for t in BANNED_TERMS if t.lower() in low]


def allowed_numbers(facts: Facts) -> set[int]:
    blob = json.dumps(facts.model_dump(), ensure_ascii=False)
    nums = {int(n) for n in re.findall(r"\d+", blob)}
    return nums | _ALWAYS_ALLOWED


def find_numbers_not_in_facts(text: str, facts: Facts) -> list[int]:
    allowed = allowed_numbers(facts)
    found = {int(n) for n in re.findall(r"\d+", text)}
    return sorted(found - allowed)


def llm_judge(llm: LLM, facts: Facts, text: str, label: str = "judge") -> JudgeVerdict:
    facts_json = json.dumps(facts.model_dump(), ensure_ascii=False, sort_keys=True)
    return llm.parse(
        label=label,
        model=llm.settings.model_judge,
        system=SYSTEM_JUDGE,
        messages=[{
            "role": "user",
            "content": f"[facts]\n{facts_json}\n\n[AI 텍스트]\n{text}",
        }],
        output_format=JudgeVerdict,
        effort="low",
        max_tokens=1000,
    )


def run_guards(text: str, facts: Facts, llm: LLM | None = None, use_judge: bool = True, label: str = "judge") -> GuardReport:
    banned = find_banned_terms(text)
    bad_nums = find_numbers_not_in_facts(text, facts)
    verdict = None
    if use_judge and llm is not None:
        verdict = llm_judge(llm, facts, text, label=label)
    judge_ok = verdict is None or not (
        verdict.diagnoses_or_prescribes or verdict.claims_beyond_report or verdict.tone_alarming
    )
    return GuardReport(
        banned_terms_found=banned,
        numbers_not_in_facts=bad_nums,
        judge=verdict,
        passed=(not banned and not bad_nums and judge_ok),
    )
