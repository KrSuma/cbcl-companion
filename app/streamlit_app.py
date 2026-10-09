"""Streamlit demo: parent guide (Feature A) + pre-consultation Q&A (Feature B)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st

from cbcl_companion.chat import ChatSession, render_handoff
from cbcl_companion.explain import generate_guide, render_markdown
from cbcl_companion.llm import LLM, Settings
from cbcl_companion.parser import load_report
from cbcl_companion.glossary import TOOLTIP_CSS, wrap_terms
from cbcl_companion.rules import build_facts, composite_band, syndrome_band

ROOT = Path(__file__).resolve().parents[1]


def _md(text: str) -> None:
    """Markdown with glossary terms made hoverable."""
    st.markdown(wrap_terms(text), unsafe_allow_html=True)


def render_original_report(report, pdf_path):
    """The report as the parent receives it, in the report's own order and wording."""
    c, n = report.child, report.narrative
    st.markdown(TOOLTIP_CSS, unsafe_allow_html=True)
    _md("<p style='letter-spacing:.2em;color:gray;font-size:.8em;margin-bottom:0'>K-CBCL · KOREAN CHILD BEHAVIOR CHECKLIST</p>")
    _md("### 한국 아동 · 청소년 행동평가척도 검사 결과 보고서")
    st.caption("보호자 보고형 · 만 4~17세 대상 · 한국판 표준화 규준 적용")
    _md(
        f"| 이름 | 성별 / 연령 | 적용 규준 | 검사일 |\n|---|---|---|---|\n"
        f"| {c.name} | {c.sex}아 / {c.age_label} | {c.norm_group} | {c.test_date.replace('-', '.')} |"
    )
    _md("##### 검사 개요 및 해석 기준")
    _md("K-CBCL은 한국판으로 표준화된 행동평가 도구로, 주 양육자가 보고한 아동·청소년의 <b>사회능력</b>과 <b>문제행동 증후군</b>을 또래 규준과 비교해 평가합니다. 각 척도는 연령·성별 규준에 따라 T점수(평균 50, 표준편차 10)로 환산됩니다.")
    _md(
        "| 범위 | 내재화 · 외현화 · 총 문제행동 | 개별 증후군 척도 | 해석 |\n|---|---|---|---|\n"
        "| 정상 범위 | T < 60 (≤ 84%tile) | T < 60 (≤ 84%tile) | 연령 평균 수준 |\n"
        "| 준임상 범위 | T 60–62 (85–89%tile) | T 60–69 (85–97%tile) | 상승, 선별·관찰 요망 |\n"
        "| 임상 범위 | T ≥ 63 (≥ 90%tile) | T ≥ 70 (≥ 98%tile) | 임상적 개입 고려 |"
    )
    st.caption("※ K-CBCL 표준 해석 기준. 종합척도는 63T(90%tile), 개별 증후군 척도는 70T(98%tile)를 임상 기준으로 한다.")

    _md("##### Ⅰ. 사회능력 척도")
    if n and n.social_competence_note:
        st.info(n.social_competence_note)
    else:
        _md("미실시" if "사회능력 척도" in report.not_administered else "—")

    _md("##### Ⅱ. 문제행동 종합 지표")
    cols = st.columns(len(report.composites))
    for col, x in zip(cols, report.composites):
        with col:
            _md(f"<b>{x.label}</b>  \n<span style='color:gray;font-size:.85em'>{x.components}</span>")
            _md(f"<span style='font-size:2em;font-weight:600'>{x.t}</span> <span style='color:gray'>T</span> &nbsp; {composite_band(x.t)} 범위")
    if n and n.composite_summary:
        _md(n.composite_summary)

    _md("##### Ⅲ. 증후군 척도 프로파일")
    rows = "\n".join(f"| {x.group} 증후군 | {x.label} | {x.items}문항 | {x.t} | {syndrome_band(x.t)} |" for x in report.syndromes)
    _md("| 군 | 척도 | 문항 수 | T | 범위 |\n|---|---|---|---|---|\n" + rows)
    st.caption("준임상 기준(60T) · 임상 기준(70T)")

    if n and n.special_scales:
        _md("##### Ⅳ. 특수 척도 (SPECIAL SCALES)")
        for line in n.special_scales:
            _md(line)

    if n and n.observations:
        _md("##### Ⅴ. 주요 관찰 소견")
        for o in n.observations:
            _md(f"<b>{o.title}</b> &nbsp;<span style='color:#b45309;font-size:.85em'>{o.tag}</span>")
            for pt in o.points:
                _md(f"- {pt}")

    if n and n.interpretation:
        _md("##### Ⅵ. 종합 해석")
        for para in n.interpretation:
            _md(para)

    if report.parent_comments:
        _md("##### Ⅶ. 보호자 참고 의견")
        for q in report.parent_comments:
            _md(f"> *{q}*")

    if n and n.caveats:
        _md("##### 해석 시 유의사항")
        for cv in n.caveats:
            _md(f"- {cv}")

    st.caption(f"K-CBCL 한국 아동·청소년 행동평가척도 검사 결과 보고서 · 검사일 {c.test_date.replace('-', '.')} · 규준: {c.norm_group}")
    if pdf_path and hasattr(st, "pdf"):
        _md("##### 원본 PDF")
        st.pdf(str(pdf_path))


st.set_page_config(page_title="아맘때 검사 결과 안내 도우미", page_icon="🧩", layout="wide")

# Optional access gate for public deployments: set APP_PASSWORD to require it.
_required = os.getenv("APP_PASSWORD")
if _required:
    if not st.session_state.get("authed"):
        st.title("검사 결과 안내 도우미 (PoC)")
        pw = st.text_input("접근 비밀번호", type="password")
        if pw and pw == _required:
            st.session_state.authed = True
            st.rerun()
        elif pw:
            st.error("비밀번호가 올바르지 않습니다.")
        st.stop()
st.title("검사 결과 안내 도우미 (PoC)")

with st.sidebar:
    st.header("입력")
    src = st.radio("보고서", ["샘플 JSON", "PDF 업로드"])
    uploaded_pdf = None
    if src == "PDF 업로드":
        up = st.file_uploader("K-CBCL 보고서 PDF", type=["pdf"])
        if up:
            p = ROOT / "outputs" / "uploaded.pdf"
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(up.read())
            report = load_report(p)
            uploaded_pdf = p
        else:
            report = None
    else:
        report = load_report(ROOT / "data" / "sample_report.json")

if report is None:
    st.info("왼쪽에서 보고서를 선택하세요.")
    st.stop()

facts = build_facts(report)
if "llm" not in st.session_state:
    st.session_state.llm = LLM(Settings())
llm: LLM = st.session_state.llm

if "session" not in st.session_state or st.session_state.get("session_child") != facts.child_name:
    st.session_state.session = ChatSession(facts, llm)
    st.session_state.session_child = facts.child_name
session: ChatSession = st.session_state.session

FAB_CSS = """
<style>
div[class*="st-key-chat_fab"]{position:fixed !important;bottom:28px !important;right:28px !important;
  left:auto !important;top:auto !important;width:auto !important;z-index:1000 !important}
div[class*="st-key-chat_fab"] [data-testid="stPopover"]{width:auto !important}
div[class*="st-key-chat_fab"] button{border-radius:999px !important;padding:.65em 1.2em !important;
  box-shadow:0 6px 18px rgba(0,0,0,.3) !important;background:#1f2937 !important;color:#fff !important;
  border:none !important;font-weight:600 !important}
div[class*="st-key-chat_fab"] button:hover{background:#111827 !important;color:#fff !important}
</style>
"""


SUGGESTED = ["준임상이 무슨 뜻이에요?", "상담 전까지 집에서 뭘 하면 좋을까요?", "상담 때 뭘 물어보면 좋을까요?"]


def anxiety_rating(session: ChatSession, when: str, prompt: str) -> None:
    """One-question self-rating (1~5). Stored on the session and shown in the counselor memo."""
    st.markdown("---")
    st.markdown(f"**{prompt}**")
    choice = st.segmented_control("걱정 정도", options=[1, 2, 3, 4, 5], default=None,
                                  key=f"rating_{when}", label_visibility="collapsed")
    st.caption("1 = 거의 없음 · 5 = 매우 큼")
    if choice is not None:
        session.ratings[when] = int(choice)


def _esc(text: str) -> str:
    """Escape tildes so '60~62' is not read as strikethrough."""
    return text.replace("~", "\\~")


def floating_chat(session: ChatSession) -> None:
    """A floating 질문하기 button that opens the same chat the chatbot tab uses."""
    st.markdown(FAB_CSS, unsafe_allow_html=True)
    with st.container(key="chat_fab"):
        with st.popover("💬 궁금한 점 물어보기"):
            st.markdown("**상담 전 질문 챗봇** · 보고서 내용 안에서 답하고, 진단·치료 질문은 상담사에게 전달합니다.")
            recent = session.transcript[-3:]
            if not recent:
                st.caption("이런 질문부터 시작해 보세요")
                for i, q in enumerate(SUGGESTED):
                    if st.button(q, key=f"chip_{i}", use_container_width=True):
                        with st.spinner("..."):
                            session.ask(q)
                        st.rerun()
            for q, a in recent:
                st.markdown(f"**보호자:** {_esc(q)}")
                st.markdown(f"**도우미:** {_esc(a)}")
            with st.form("fab_form", clear_on_submit=True, border=False):
                q = st.text_input("질문", placeholder="궁금한 점을 적어 주세요", label_visibility="collapsed")
                sent = st.form_submit_button("보내기", use_container_width=True)
            if sent and q.strip():
                with st.spinner("..."):
                    session.ask(q.strip())
                st.rerun()


tab_r, tab_a, tab_b, tab_i = st.tabs(["원본 보고서", "쉬운 말 해설", "대화 기록", "내부 공유용"])

with tab_r:
    render_original_report(report, uploaded_pdf)
    anxiety_rating(session, "before", "보고서를 보신 지금, 얼마나 걱정되시나요?")

with tab_a:
    st.subheader(f"{facts.child_name} · {facts.child_sex} · {facts.child_age} · 검사일 {facts.test_date}")
    if st.button("해설 생성", type="primary"):
        with st.spinner("생성 중..."):
            guide, report_g, source = generate_guide(facts, llm)
        st.session_state.guide = (guide, report_g, source)
    if "guide" in st.session_state:
        guide, report_g, source = st.session_state.guide
        st.markdown(render_markdown(guide, facts))
        with st.expander(f"검증 결과 (source: {source})"):
            st.code(report_g.summary() if report_g else "template: deterministic, no judge")
            st.code(llm.tracker.table())
        anxiety_rating(session, "after", "해설을 읽으신 지금, 얼마나 걱정되시나요?")
    floating_chat(session)

with tab_b:
    if not session.transcript:
        st.caption("아직 나눈 대화가 없습니다. 이런 질문부터 시작해 보세요.")
        cols = st.columns(len(SUGGESTED))
        for i, (col, q) in enumerate(zip(cols, SUGGESTED)):
            if col.button(q, key=f"tab_chip_{i}", use_container_width=True):
                with st.spinner("..."):
                    session.ask(q)
                st.rerun()
    for q, a in session.transcript:
        st.chat_message("user").write(_esc(q))
        st.chat_message("assistant").write(_esc(a))
    q = st.chat_input("궁금한 점을 물어보세요 (예: 준임상이 무슨 뜻이에요?)")
    if q:
        st.chat_message("user").write(q)
        with st.spinner("..."):
            turn = session.ask(q)
        st.chat_message("assistant").write(_esc(turn.reply))
        st.caption(f"{turn.category} · 불안 {turn.anxiety_level} · 상담사 전달 {'예' if turn.log_for_counselor else '아니오'}")

with tab_i:
    st.caption("보호자에게는 보이지 않는 화면. 상담사와 운영팀이 봅니다.")
    st.subheader("상담사 전달 메모 (자동 생성)")
    st.code(render_handoff(session.handoff_note()))
    st.subheader("사용량/비용")
    st.code(llm.tracker.table())
    with st.expander("LLM 입력 facts (검증용) — 모델이 받는 유일한 입력. 숫자와 범위는 모두 규칙 계층이 결정"):
        st.json(facts.model_dump())
