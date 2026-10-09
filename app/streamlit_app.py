"""Streamlit demo: parent guide (Feature A) + pre-consultation Q&A (Feature B)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st

from cbcl_companion.chat import ChatSession, render_handoff
from cbcl_companion.explain import generate_guide, render_markdown, template_guide
from cbcl_companion.llm import LLM, Settings
from cbcl_companion.parser import load_report
from cbcl_companion.rules import build_facts

ROOT = Path(__file__).resolve().parents[1]

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
st.caption("보고서를 대체하지 않습니다. 보고서를 읽는 데 도움을 주고, 상담 전 궁금한 점을 정리해 드립니다.")

with st.sidebar:
    st.header("입력")
    src = st.radio("보고서", ["샘플 JSON", "PDF 업로드"])
    if src == "PDF 업로드":
        up = st.file_uploader("K-CBCL 보고서 PDF", type=["pdf"])
        if up:
            p = ROOT / "outputs" / "uploaded.pdf"
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(up.read())
            report = load_report(p)
        else:
            report = None
    else:
        report = load_report(ROOT / "data" / "sample_report.json")
    st.divider()
    st.header("모델")
    settings = Settings()
    settings.model_explain = st.text_input("해설 모델", settings.model_explain)
    settings.model_chat = st.text_input("대화 모델", settings.model_chat)
    settings.model_judge = st.text_input("검수 모델", settings.model_judge)
    use_judge = st.checkbox("LLM 검수 사용", value=True)
    offline = st.checkbox("API 없이 템플릿만 (오프라인)", value=False)

if report is None:
    st.info("왼쪽에서 보고서를 선택하세요.")
    st.stop()

facts = build_facts(report)
if "llm" not in st.session_state:
    st.session_state.llm = LLM(settings)
llm: LLM = st.session_state.llm
llm.settings = settings

tab_a, tab_b, tab_i, tab_f = st.tabs(["쉬운 말 해설", "상담 전 질문 챗봇", "내부 공유용", "규칙 계층 facts"])

with tab_a:
    st.subheader(f"{facts.child_name} · {facts.child_sex} · {facts.child_age} · 검사일 {facts.test_date}")
    if st.button("해설 생성", type="primary"):
        with st.spinner("생성 중..."):
            if offline:
                guide, report_g, source = template_guide(facts), None, "template"
            else:
                guide, report_g, source = generate_guide(facts, llm, use_judge=use_judge)
        st.session_state.guide = (guide, report_g, source)
    if "guide" in st.session_state:
        guide, report_g, source = st.session_state.guide
        st.markdown(render_markdown(guide, facts))
        with st.expander(f"검증 결과 (source: {source})"):
            st.code(report_g.summary() if report_g else "template: deterministic, no judge")
            st.code(llm.tracker.table())

with tab_b:
    if "session" not in st.session_state or st.session_state.get("session_child") != facts.child_name:
        st.session_state.session = ChatSession(facts, llm)
        st.session_state.session_child = facts.child_name
    session: ChatSession = st.session_state.session
    for q, a in session.transcript:
        st.chat_message("user").write(q)
        st.chat_message("assistant").write(a)
    q = st.chat_input("궁금한 점을 물어보세요 (예: 준임상이 무슨 뜻이에요?)")
    if q:
        st.chat_message("user").write(q)
        with st.spinner("..."):
            turn = session.ask(q)
        st.chat_message("assistant").write(turn.reply)
        st.caption(f"{turn.category} · 불안 {turn.anxiety_level} · 상담사 전달 {'예' if turn.log_for_counselor else '아니오'}")

with tab_i:
    st.caption("보호자에게는 보이지 않는 화면. 상담사와 운영팀이 봅니다.")
    st.subheader("상담사 전달 메모 (자동 생성)")
    session: ChatSession = st.session_state.get("session") or ChatSession(facts, llm)
    st.code(render_handoff(session.handoff_note()))
    st.subheader("사용량/비용")
    st.code(llm.tracker.table())

with tab_f:
    st.caption("LLM이 받는 유일한 입력. 숫자와 범위는 모두 여기서 결정됩니다.")
    st.json(facts.model_dump())
