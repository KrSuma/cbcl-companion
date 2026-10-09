"""Feature B: pre-consultation Q&A grounded in facts, with crisis pre-check and counselor handoff."""
from __future__ import annotations

import json
import re

from .guard import find_banned_terms, find_numbers_not_in_facts, llm_judge
from .llm import LLM, RefusedError
from .prompts import CRISIS_PATTERNS, CRISIS_RESPONSE, ECHO_GROUPS, SYSTEM_CHAT
from .rules import facts_summary_line
from .schema import ChatTurn, Facts, HandoffEntry, HandoffNote

_CRISIS_RE = re.compile("|".join(CRISIS_PATTERNS))

SAFE_FALLBACK_REPLY = (
    "그 질문은 상담사 선생님이 직접 답해 드리는 것이 가장 정확합니다. "
    "상담 때 꼭 다룰 수 있도록 메모해 두었습니다. 그 전까지 궁금한 용어나 결과의 의미는 계속 물어보셔도 됩니다."
)


def _is_echo(term: str, user_text: str) -> bool:
    """A banned term counts as echoed when the parent's own message raised that topic."""
    low = user_text.lower()
    for g in ECHO_GROUPS:
        if term in g["terms"] and any(t in low for t in g["triggers"]):
            return True
    return term.lower() in low


def is_crisis(text: str) -> bool:
    return bool(_CRISIS_RE.search(text))


class ChatSession:
    def __init__(self, facts: Facts, llm: LLM):
        self.facts = facts
        self.llm = llm
        self.history: list[dict] = []          # API messages
        self.entries: list[HandoffEntry] = []  # counselor handoff
        self.transcript: list[tuple[str, str]] = []
        self.crisis_flagged = False
        facts_json = json.dumps(facts.model_dump(), ensure_ascii=False, sort_keys=True)
        # Stable prefix: system prompt + facts, both cached across turns.
        self._system = [
            {"type": "text", "text": SYSTEM_CHAT, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"[facts]\n{facts_json}", "cache_control": {"type": "ephemeral"}},
        ]

    def ask(self, user_text: str) -> ChatTurn:
        if is_crisis(user_text):
            self.crisis_flagged = True
            turn = ChatTurn(
                reply=CRISIS_RESPONSE, category="other", anxiety_level="high",
                log_for_counselor=True, counselor_note=f"[긴급] 보호자 메시지에 위기 신호: \"{user_text[:80]}\"",
            )
            self._record(user_text, turn)
            return turn

        self.history.append({"role": "user", "content": user_text})
        try:
            turn = self.llm.parse(
                label=f"chat#{len(self.transcript) + 1}",
                model=self.llm.settings.model_chat,
                system=self._system,
                messages=self.history,
                output_format=ChatTurn,
                effort="low",
                max_tokens=2000,
            )
        except RefusedError:
            turn = ChatTurn(reply=SAFE_FALLBACK_REPLY, category="clinical_question", anxiety_level="mid",
                            log_for_counselor=True, counselor_note=f"모델 거부로 폴백: \"{user_text[:80]}\"")
        # Guards on every turn. A banned term the PARENT used (e.g. "약", "ADHD") may be echoed
        # while declining; those replies go to the cheap judge instead of straight to fallback.
        banned = find_banned_terms(turn.reply)
        echoed = [t for t in banned if _is_echo(t, user_text)]
        reason = None
        if [t for t in banned if t not in echoed]:
            reason = "금지어 " + ",".join(t for t in banned if t not in echoed)
        elif find_numbers_not_in_facts(turn.reply, self.facts):
            reason = "facts 밖 숫자 " + ",".join(map(str, find_numbers_not_in_facts(turn.reply, self.facts)))
        elif echoed:
            try:
                v = llm_judge(self.llm, self.facts, turn.reply, label=f"judge#{len(self.transcript) + 1}")
                if v.diagnoses_or_prescribes or v.claims_beyond_report:
                    reason = "심사: " + v.reasoning[:80]
            except RefusedError:
                reason = "심사 모델 거부"
        if reason:
            turn = ChatTurn(reply=SAFE_FALLBACK_REPLY, category="clinical_question", anxiety_level=turn.anxiety_level,
                            log_for_counselor=True, counselor_note=f"[가드 폴백: {reason}] " + (turn.counselor_note or user_text[:80]))
        self.history.append({"role": "assistant", "content": turn.reply})
        self._record(user_text, turn)
        return turn

    def _record(self, user_text: str, turn: ChatTurn) -> None:
        self.transcript.append((user_text, turn.reply))
        if turn.log_for_counselor:
            self.entries.append(HandoffEntry(
                question=user_text, category=turn.category,
                anxiety_level=turn.anxiety_level, note=turn.counselor_note,
            ))

    def handoff_note(self) -> HandoffNote:
        f = self.facts
        themes = []
        joined = " ".join(q for q, _ in self.transcript)
        for kw, theme in [("학교", "학교와 집의 차이"), ("친구", "또래 관계"), ("약", "약물/치료 여부"),
                          ("검사", "추가 검사"), ("원인", "원인에 대한 궁금증"), ("집중", "주의집중")]:
            if kw in joined:
                themes.append(theme)
        return HandoffNote(
            child_name=f.child_name, child_sex=f.child_sex, child_age=f.child_age, test_date=f.test_date,
            report_summary=facts_summary_line(f),
            entries=list(self.entries),
            themes=themes,
            not_administered_mentioned=any("미실시" in r or "실시되지 않" in r for _, r in self.transcript),
        )


def render_handoff(note: HandoffNote) -> str:
    lines = [
        f"[상담 전 보호자 메모] {note.child_name} / {note.child_sex} / {note.child_age} / 검사일 {note.test_date}",
        f"보고서 요약: {note.report_summary}",
        "보호자가 물어본 질문:",
    ]
    if not note.entries:
        lines.append("  (상담사 전달이 필요한 질문 없음)")
    for i, e in enumerate(note.entries, 1):
        tag = {"clinical_question": "진단/치료 질문 → 상담사 답변 필요", "reassurance": "불안 표현",
               "glossary": "용어 질문", "practical": "준비/생활", "logistics": "일정/절차", "other": "기타"}[e.category]
        lines.append(f"  {i}. \"{e.question}\" ({tag}, 불안: {e.anxiety_level})")
        if e.note:
            lines.append(f"     메모: {e.note}")
    if note.themes:
        lines.append("보호자 관심사: " + ", ".join(note.themes))
    lines.append(f"미실시 척도 안내 여부: {'안내함' if note.not_administered_mentioned else '안내 안 함'}")
    return "\n".join(lines)
