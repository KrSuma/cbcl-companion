"""Plain-language explanations for the clinical terms on a K-CBCL report.

Used by the 원본 보고서 tab for hover popups. Same anchors the guide uses, no model involved.
"""
from __future__ import annotations

import html
import re

from .rules import PLAIN_MEANING

TERMS: dict[str, str] = {
    # measurement
    "T점수": "또래 평균을 50, 표준편차를 10으로 놓고 비교한 점수. 60이면 또래 100명 중 약 85번째.",
    "T 점수": "또래 평균을 50, 표준편차를 10으로 놓고 비교한 점수. 60이면 또래 100명 중 약 85번째.",
    "%tile": "백분위. 또래 100명 중 몇 번째인지.",
    "표준편차": "점수가 평균에서 얼마나 퍼져 있는지의 단위. 이 검사에서는 10점이 1표준편차.",
    "규준": "비교 기준이 되는 같은 나이·성별 또래 집단.",
    "표준화": "많은 또래 자료로 비교 기준을 만든 것.",
    "보호자 보고형": "보호자가 체크한 답을 바탕으로 하는 검사.",
    "주 양육자": "아이를 주로 돌보는 보호자.",
    "문항": "보호자가 체크한 질문 하나. 9문항이면 9개 질문을 합친 점수.",
    # bands
    "정상 범위": "또래와 비슷한 수준.",
    "준임상 범위": "또래 평균보다 높아 관찰해 볼 만한 범위. 문제가 확정되었다는 뜻이 아님.",
    "준임상": "또래 평균보다 높아 관찰해 볼 만한 범위. 문제가 확정되었다는 뜻이 아님.",
    "임상 범위": "전문가의 개입을 고려하는 범위.",
    "임상 기준": "전문가의 개입을 고려하기 시작하는 점수. 종합척도 63, 개별척도 70.",
    "임상적 개입": "상담사·전문가가 직접 살펴보고 돕는 것.",
    "선별 기준": "관찰이 필요한지 걸러내는 점수. 60점.",
    # composites
    "내재화": PLAIN_MEANING["internalizing"] + ".",
    "외현화": PLAIN_MEANING["externalizing"] + ".",
    "총 문제행동": PLAIN_MEANING["total"] + ".",
    "문제행동 증후군": "비슷한 행동 문항을 묶은 개별 척도들.",
    "증후군 척도": "비슷한 행동 문항을 묶은 개별 척도.",
    "종합척도": "내재화·외현화·총 문제행동처럼 여러 척도를 합친 점수.",
    "개별척도": "위축, 주의집중 문제처럼 한 가지 영역만 보는 점수.",
    "개별 증후군 척도": "위축, 주의집중 문제처럼 한 가지 영역만 보는 점수.",
    # screening
    "선별 도구": "더 자세히 볼 필요가 있는지 걸러내는 검사. 진단 검사가 아님.",
    "선별 검사": "더 자세히 볼 필요가 있는지 걸러내는 검사. 진단 검사가 아님.",
    "선별 목적": "더 자세히 볼 필요가 있는지 걸러내는 용도.",
    "사회능력 척도": "친구 관계·활동·학업처럼 잘하는 면을 보는 척도. 이번에는 실시하지 않음.",
    "사회능력": "친구 관계·활동·학업처럼 잘하는 면.",
    "특수척도": "한국판에만 있는 추가 척도(정서불안정, 성문제).",
    "특수 척도": "한국판에만 있는 추가 척도(정서불안정, 성문제).",
    "정서불안정": "잘 울거나 화를 폭발하거나 감정이 급변하는 모습을 보는 척도.",
    "TRF": "교사가 작성하는 같은 검사(Teacher Report Form).",
    "YSR": "아동·청소년이 직접 작성하는 같은 검사(Youth Self-Report).",
    "재평가": "시간이 지난 뒤 같은 검사를 다시 해 보는 것.",
    # syndromes
    "위축": PLAIN_MEANING["withdrawn"] + ".",
    "신체증상": PLAIN_MEANING["somatic"] + ".",
    "우울/불안": PLAIN_MEANING["anxious_depressed"] + ".",
    "사회적 미성숙": PLAIN_MEANING["social_immaturity"] + ".",
    "사고의 문제": PLAIN_MEANING["thought"] + ".",
    "주의집중 문제": PLAIN_MEANING["attention"] + ".",
    "주의집중": PLAIN_MEANING["attention"] + ".",
    "비행": PLAIN_MEANING["delinquent"] + ".",
    "공격성": PLAIN_MEANING["aggressive"] + ".",
}

# Longest terms first so "준임상 범위" wins over "준임상", "임상 범위" over nothing shorter.
_PATTERN = re.compile("|".join(re.escape(t) for t in sorted(TERMS, key=len, reverse=True)))
_TAG_SPLIT = re.compile(r"(<[^>]+>)")

TOOLTIP_CSS = """
<style>
.kt{border-bottom:1px dotted #b45309;cursor:help;position:relative}
.kt:hover::after{content:attr(data-tip);position:absolute;left:0;top:1.5em;z-index:50;
  background:#1f2937;color:#fff;padding:.5em .7em;border-radius:6px;font-size:.85em;font-weight:400;
  line-height:1.4;width:max-content;max-width:22em;white-space:normal;box-shadow:0 4px 14px rgba(0,0,0,.25)}
div[data-testid="stMarkdownContainer"] table{overflow:visible}
</style>
"""


def wrap_terms(text: str) -> str:
    """Wrap each glossary term in a hoverable span. Text inside HTML tags is left untouched."""
    out = []
    for part in _TAG_SPLIT.split(text):
        if part.startswith("<"):
            out.append(part)
            continue
        out.append(_PATTERN.sub(
            lambda m: f'<span class="kt" data-tip="{html.escape(TERMS[m.group(0)], quote=True)}">{m.group(0)}</span>', part))
    return "".join(out)
