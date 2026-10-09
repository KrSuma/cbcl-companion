"""Pydantic models: report input, derived facts, LLM structured outputs."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Band = Literal["정상", "준임상", "임상"]


# ---------- Input: the report as data ----------

class Child(BaseModel):
    name: str
    sex: str
    age_label: str
    norm_group: str
    test_date: str


class CompositeScore(BaseModel):
    key: str
    label: str
    t: int
    components: str = ""


class SyndromeScore(BaseModel):
    key: str
    label: str
    group: str
    t: int
    items: int = 0


class Observation(BaseModel):
    title: str                      # e.g. "주의집중 문제 · T = 66"
    tag: str                        # e.g. "개별척도 준임상 (60–69T)"
    points: list[str] = Field(default_factory=list)


class Narrative(BaseModel):
    """The report's clinician-written prose. Shown on the 원본 보고서 tab only; the pipeline never reads it."""
    social_competence_note: Optional[str] = None
    composite_summary: Optional[str] = None
    special_scales: list[str] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    interpretation: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class ReportData(BaseModel):
    child: Child
    composites: list[CompositeScore]
    syndromes: list[SyndromeScore]
    not_administered: list[str] = Field(default_factory=list)
    parent_comments: list[str] = Field(default_factory=list)
    narrative: Optional[Narrative] = None


# ---------- Derived: facts the rules layer hands to the LLM ----------

class ScaleFact(BaseModel):
    key: str
    label: str
    t: int
    band: Band
    percentile_note: str
    plain_meaning: str
    group: str = ""
    linked_parent_comment: Optional[str] = None


class Facts(BaseModel):
    child_name: str
    child_sex: str
    child_age: str
    test_date: str
    composites: list[ScaleFact]
    syndromes_flagged: list[ScaleFact]
    syndromes_normal: list[ScaleFact]
    any_clinical: bool
    any_subclinical: bool
    highest_syndrome: Optional[ScaleFact]
    not_administered: list[str]
    parent_comments: list[str]
    thresholds_note: str


# ---------- LLM output: Feature A (parent guide) ----------

class ScaleExplanation(BaseModel):
    label: str = Field(description="척도 이름. facts에 있는 label 그대로.")
    t: int = Field(description="T점수. facts에 있는 값 그대로.")
    band: str = Field(description="범위. facts에 있는 band 그대로.")
    explanation: str = Field(description="보호자용 2~4문장 설명. 진단명 금지.")


class ParentGuide(BaseModel):
    headline: str = Field(description="첫 줄. 임상 범위 해당 여부를 정직하게, 차분하게 한 문장으로.")
    what_this_test_is: str = Field(description="검사가 무엇이고 무엇이 아닌지. 2~3문장.")
    glossary: list[str] = Field(description="T점수, 준임상 등 용어 풀이. 각 항목 1~2문장.")
    overall_picture: list[str] = Field(description="종합 지표 3개를 한 줄씩 쉬운 말로.")
    not_needed: list[str] = Field(description="'하지 않아도 되는 것' 2~3개. 이 검사가 무엇이 아닌지에 대한 사실만: 양육을 평가하지 않음, 아이에게 결과를 캐묻지 않아도 됨, 상담 전 집에서 바꿔야 할 것 없음. 원인 언급 금지.")
    flagged_scales: list[ScaleExplanation] = Field(description="준임상/임상 척도별 설명. facts 순서대로.")
    normal_scales_note: str = Field(description="정상 범위 척도들을 한 문장으로.")
    before_consultation: list[str] = Field(description="상담 전 준비 2~4가지.")
    questions_for_counselor: list[str] = Field(description="상담사에게 물어볼 질문 3~5개.")
    closing: str = Field(description="진단/치료 판단은 상담사와의 상담에서 이루어진다는 안내 한 문장.")


# ---------- LLM output: Feature B (chat turn) ----------

ChatCategory = Literal[
    "glossary",          # 용어/수치 의미 질문
    "reassurance",       # 불안 표현, 안심 요청
    "clinical_question", # 진단/치료/약물 등 상담사 영역
    "practical",         # 상담 전 준비, 생활 팁
    "logistics",         # 상담 일정/절차
    "other",
]


class ChatTurn(BaseModel):
    reply: str = Field(description="보호자에게 보여줄 답변. 한국어, 3~6문장.")
    category: ChatCategory
    anxiety_level: Literal["low", "mid", "high"] = Field(description="보호자 메시지에서 느껴지는 불안 수준")
    log_for_counselor: bool = Field(description="상담사가 상담 때 다뤄야 할 질문이면 true")
    counselor_note: Optional[str] = Field(default=None, description="상담사에게 전달할 한 줄 메모 (log_for_counselor가 true일 때)")


# ---------- Guard ----------

class JudgeVerdict(BaseModel):
    diagnoses_or_prescribes: bool = Field(description="진단명을 부여하거나 치료/약물을 권하면 true")
    claims_beyond_report: bool = Field(description="보고서 facts에 없는 결과/수치/판단을 주장하면 true")
    tone_alarming: bool = Field(description="불필요하게 불안을 키우는 표현이 있으면 true")
    reasoning: str = Field(description="한 줄 근거")


class GuardReport(BaseModel):
    banned_terms_found: list[str]
    numbers_not_in_facts: list[int]
    judge: Optional[JudgeVerdict] = None
    passed: bool

    def summary(self) -> str:
        lines = [
            f"guard: banned_terms      {'PASS' if not self.banned_terms_found else 'FAIL ' + str(self.banned_terms_found)}",
            f"guard: numbers_in_facts  {'PASS' if not self.numbers_not_in_facts else 'FAIL ' + str(self.numbers_not_in_facts)}",
        ]
        if self.judge:
            j = self.judge
            ok = not (j.diagnoses_or_prescribes or j.claims_beyond_report or j.tone_alarming)
            lines.append(f"guard: llm_judge         {'PASS' if ok else 'FAIL'}  \"{j.reasoning}\"")
        return "\n".join(lines)


# ---------- Counselor handoff ----------

class HandoffEntry(BaseModel):
    question: str
    category: ChatCategory
    anxiety_level: str
    note: Optional[str] = None


class HandoffNote(BaseModel):
    child_name: str
    child_sex: str
    child_age: str
    test_date: str
    report_summary: str
    entries: list[HandoffEntry]
    themes: list[str]
    anxiety_before: Optional[int] = None   # 1~5, 원본 보고서를 본 직후
    anxiety_after: Optional[int] = None    # 1~5, 쉬운 말 해설을 읽은 후
