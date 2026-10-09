"""Report loading: JSON (primary, what the product DB would provide) or best-effort PDF parsing."""
from __future__ import annotations

import json
import re
from pathlib import Path

import unicodedata

from .schema import Child, CompositeScore, Narrative, Observation, ReportData, SyndromeScore

_SYNDROME_KEYS = {
    "위축": ("withdrawn", "내재화"),
    "신체증상": ("somatic", "내재화"),
    "우울/불안": ("anxious_depressed", "내재화"),
    "사회적 미성숙": ("social_immaturity", "혼합"),
    "사고의 문제": ("thought", "혼합"),
    "주의집중 문제": ("attention", "혼합"),
    "비행": ("delinquent", "외현화"),
    "공격성": ("aggressive", "외현화"),
}
_COMPOSITE_KEYS = {"내재화 문제": "internalizing", "외현화 문제": "externalizing", "총 문제행동": "total"}


def load_report(path: Path) -> ReportData:
    if path.suffix.lower() == ".pdf":
        return parse_pdf(path)
    return ReportData.model_validate(json.loads(path.read_text(encoding="utf-8")))


_TERMINATORS = (".", "。", '"', "\u201d", ")", "?")
_SPACE_ENDINGS = ("가", "는", "은", "을", "를", "에", "의", "와", "과", "로", "및", "대한", "아니라", "이며", "하며", "등")


def _width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def _unwrap(text: str) -> list[str]:
    """Re-join lines the PDF wrapped mid-sentence. A wrapped line is wide (>=125 display cols)
    and does not end in a sentence terminator. Korean wraps may split a word, so join without a
    space unless the line ends in a particle that marks a word boundary."""
    out: list[str] = []
    carry = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if carry:
            line = carry + (" " if carry.endswith(_SPACE_ENDINGS) else "") + line
            carry = ""
        if _width(line) >= 125 and not line.endswith(_TERMINATORS):
            carry = line
            continue
        out.append(line)
    if carry:
        out.append(carry)
    return out


def _between(lines: list[str], start: str, end_prefixes: tuple[str, ...]) -> list[str]:
    try:
        i = next(k for k, l in enumerate(lines) if l.startswith(start)) + 1
    except StopIteration:
        return []
    out = []
    for l in lines[i:]:
        if l.startswith(end_prefixes):
            break
        out.append(l)
    return out


def _narrative(lines: list[str]) -> Narrative:
    social = " ".join(_between(lines, "Ⅰ. 사회능력 척도", ("Ⅱ.",))) or None
    # composite summary: after the 총 문제행동 block (label, components, "58 T", "정상 범위") until Ⅲ.
    summary = None
    try:
        i = lines.index("총 문제행동") + 4
        seg = []
        for l in lines[i:]:
            if l.startswith("Ⅲ."):
                break
            seg.append(l)
        summary = " ".join(seg) or None
    except ValueError:
        pass
    special = [l for l in _between(lines, "Ⅳ. 특수 척도", ("Ⅴ.",)) if not re.fullmatch(r"[\d ]+", l)]
    obs: list[Observation] = []
    for l in _between(lines, "Ⅴ. 주요 관찰 소견", ("Ⅵ.",)):
        m = re.match(r"^(.+? · T = \d+)\s+(.+)$", l)
        if m:
            obs.append(Observation(title=m.group(1), tag=m.group(2)))
        elif obs:
            obs[-1].points.append(l)
    interp = _between(lines, "Ⅵ. 종합 해석", ("Ⅶ.",))
    caveats = [l for l in _between(lines, "해석 시 유의사항", ("K-CBCL 한국 아동·청소년 행동평가척도 검사 결과 보고서",))]
    return Narrative(social_competence_note=social, composite_summary=summary, special_scales=special,
                     observations=obs, interpretation=interp, caveats=caveats)


def parse_pdf(path: Path) -> ReportData:
    from pypdf import PdfReader

    text = "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
    lines = [l.strip() for l in text.splitlines()]
    narrative = _narrative(_unwrap(text))

    def after(label: str) -> str:
        i = lines.index(label)
        return lines[i + 1]

    name = after("이름")
    sex_age = after("성별 / 연령")              # "남아 / 만 7세 3개월"
    sex = "남" if sex_age.startswith("남") else "여"
    age_label = sex_age.split("/", 1)[1].strip()
    norm = after("적용 규준")
    test_date = after("검사일").replace(".", "-")

    composites = []
    for label, key in _COMPOSITE_KEYS.items():
        i = lines.index(label)
        comp = lines[i + 1].split("·", 1)[-1].strip()
        t = int(re.match(r"(\d+)\s*T", lines[i + 2]).group(1))
        composites.append(CompositeScore(key=key, label=label, t=t, components=comp))

    syndromes = []
    for label, (key, group) in _SYNDROME_KEYS.items():
        # label line, then "Withdrawn · 9문항", then "60 준임상"
        for i, l in enumerate(lines):
            if l == label and i + 2 < len(lines) and re.match(r"\d+\s+(정상|준임상|임상)", lines[i + 2]):
                items = int(re.search(r"(\d+)문항", lines[i + 1]).group(1))
                t = int(lines[i + 2].split()[0])
                syndromes.append(SyndromeScore(key=key, label=label, group=group, t=t, items=items))
                break

    not_adm = []
    if re.search(r"사회능력 척도\s*\n미실시", text):
        not_adm.append("사회능력 척도")
    for scale in ("정서불안정 척도", "성문제 척도"):
        if re.search(scale + r".*?미실시", text):
            not_adm.append(scale)

    comments = re.findall(r"[\"“]([^\"”]+)[\"”]", text.split("보호자 참고 의견", 1)[-1].split("해석 시 유의사항", 1)[0])

    return ReportData(
        child=Child(name=name, sex=sex, age_label=age_label, norm_group=norm, test_date=test_date),
        composites=composites, syndromes=syndromes,
        not_administered=not_adm, parent_comments=[c.strip() for c in comments],
        narrative=narrative,
    )
