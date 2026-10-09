"""Report loading: JSON (primary, what the product DB would provide) or best-effort PDF parsing."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .schema import Child, CompositeScore, ReportData, SyndromeScore

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


def parse_pdf(path: Path) -> ReportData:
    from pypdf import PdfReader

    text = "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
    lines = [l.strip() for l in text.splitlines()]

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
    )
