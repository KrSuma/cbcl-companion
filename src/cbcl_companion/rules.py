"""Deterministic layer. Classifies every score using the report's own thresholds.

Nothing here calls an LLM. If a number appears in the parent guide, it must
originate from this module's output.
"""
from __future__ import annotations

from .schema import Facts, ReportData, ScaleFact

# K-CBCL thresholds as printed on the report.
COMPOSITE_SUBCLINICAL = 60   # 60–62 준임상
COMPOSITE_CLINICAL = 63      # ≥63 임상
SYNDROME_SUBCLINICAL = 60    # 60–69 준임상
SYNDROME_CLINICAL = 70       # ≥70 임상

THRESHOLDS_NOTE = (
    "종합척도(내재화·외현화·총 문제행동): T<60 정상, 60–62 준임상, ≥63 임상. "
    "개별 증후군 척도: T<60 정상, 60–69 준임상, ≥70 임상. "
    "T점수는 평균 50, 표준편차 10."
)

# Approximate percentile for a T-score under a normal distribution (mean 50, sd 10).
_PCT_TABLE = {
    50: 50, 51: 54, 52: 58, 53: 62, 54: 66, 55: 69, 56: 73, 57: 76, 58: 79, 59: 82,
    60: 85, 61: 86, 62: 88, 63: 90, 64: 92, 65: 93, 66: 95, 67: 96, 68: 96, 69: 97,
    70: 98, 71: 98, 72: 99, 73: 99, 74: 99, 75: 99,
}

# Plain-language meaning per scale. These are fixed strings, not model output,
# so the model has a vetted anchor for every scale it explains.
PLAIN_MEANING = {
    "internalizing": "걱정, 위축, 몸이 아프다는 호소처럼 마음 속으로 향하는 어려움",
    "externalizing": "규칙을 어기거나 공격적인 행동처럼 겉으로 드러나는 어려움",
    "total": "검사 문항 전체를 합친 전반적인 수준",
    "withdrawn": "혼자 있는 것을 더 좋아하거나 먼저 나서지 않는 모습",
    "somatic": "뚜렷한 이유 없이 머리나 배가 아프다고 하는 등 몸으로 나타나는 불편",
    "anxious_depressed": "걱정이 많거나 긴장하고, 기분이 가라앉는 모습",
    "social_immaturity": "나이에 비해 어른에게 기대거나 또래보다 어리게 행동하는 모습",
    "thought": "남들이 이해하기 어려운 생각이나 반복되는 행동",
    "attention": "집중을 오래 유지하거나 한 가지 일을 끝까지 하는 것의 어려움",
    "delinquent": "거짓말, 규칙 어기기처럼 규칙과 관련된 행동",
    "aggressive": "싸움, 고집, 화를 내는 등 공격적인 행동",
}

# Which parent comment keyword links to which scale (for grounding, not inference).
_COMMENT_LINKS = {
    "attention": ["산만", "집중", "끝까지", "딴짓", "숙제"],
    "social_immaturity": ["친구", "어울리", "어리게", "의존", "매달"],
    "withdrawn": ["친구", "혼자", "어울리", "말이 없", "소극"],
    "anxious_depressed": ["걱정", "불안", "긴장", "무서워", "잘 울", "울어", "울음", "우울", "슬퍼"],
    "somatic": ["배가 아프", "머리가 아프", "아프다고", "토할"],
    "thought": ["이상한", "반복", "강박", "엉뚱"],
    "delinquent": ["거짓말", "규칙", "훔", "말을 안 들", "몰래"],
    "aggressive": ["싸우", "싸움", "화를", "때리", "소리를 지르", "고집", "공격"],
}


def composite_band(t: int) -> str:
    if t >= COMPOSITE_CLINICAL:
        return "임상"
    if t >= COMPOSITE_SUBCLINICAL:
        return "준임상"
    return "정상"


def syndrome_band(t: int) -> str:
    if t >= SYNDROME_CLINICAL:
        return "임상"
    if t >= SYNDROME_SUBCLINICAL:
        return "준임상"
    return "정상"


def percentile_note(t: int) -> str:
    if t < 50:
        return "또래 평균 이하"
    pct = _PCT_TABLE.get(min(t, 75), 99)
    return f"또래 100명 중 약 {pct}번째"


def _link_comment(key: str, comments: list[str]) -> str | None:
    for kw in _COMMENT_LINKS.get(key, []):
        for c in comments:
            if kw in c:
                return c
    return None


def build_facts(report: ReportData) -> Facts:
    composites = [
        ScaleFact(
            key=c.key, label=c.label, t=c.t, band=composite_band(c.t),
            percentile_note=percentile_note(c.t),
            plain_meaning=PLAIN_MEANING.get(c.key, c.components),
            group=c.components,
        )
        for c in report.composites
    ]
    syndromes = [
        ScaleFact(
            key=s.key, label=s.label, t=s.t, band=syndrome_band(s.t),
            percentile_note=percentile_note(s.t),
            plain_meaning=PLAIN_MEANING.get(s.key, s.label),
            group=s.group,
            linked_parent_comment=_link_comment(s.key, report.parent_comments),
        )
        for s in report.syndromes
    ]
    flagged = sorted([s for s in syndromes if s.band != "정상"], key=lambda s: -s.t)
    normal = [s for s in syndromes if s.band == "정상"]
    all_scales = composites + syndromes
    return Facts(
        child_name=report.child.name,
        child_sex=report.child.sex,
        child_age=report.child.age_label,
        test_date=report.child.test_date,
        composites=composites,
        syndromes_flagged=flagged,
        syndromes_normal=normal,
        any_clinical=any(s.band == "임상" for s in all_scales),
        any_subclinical=any(s.band == "준임상" for s in all_scales),
        highest_syndrome=flagged[0] if flagged else None,
        not_administered=list(report.not_administered),
        parent_comments=list(report.parent_comments),
        thresholds_note=THRESHOLDS_NOTE,
    )


def facts_summary_line(facts: Facts) -> str:
    """One-line summary for the counselor handoff note."""
    comp = ", ".join(f"{c.label} {c.t}({c.band})" for c in facts.composites)
    flagged = ", ".join(f"{s.label} {s.t}" for s in facts.syndromes_flagged) or "없음"
    clinical = "임상 범위 해당 있음" if facts.any_clinical else "임상 범위 해당 없음"
    return f"{clinical}. 종합: {comp}. 준임상 이상 개별척도: {flagged}."
