"""CLI entry point: cbcl facts | explain | chat | eval"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .chat import ChatSession, render_handoff
from .explain import generate_guide, render_markdown, template_guide
from .llm import LLM, Settings
from .parser import load_report
from .rules import build_facts


def _load(path: str):
    report = load_report(Path(path))
    return report, build_facts(report)


def cmd_facts(args):
    _, facts = _load(args.report)
    print(json.dumps(facts.model_dump(), ensure_ascii=False, indent=2))


def cmd_explain(args):
    _, facts = _load(args.report)
    if args.template:
        guide, source = template_guide(facts), "template"
        md = render_markdown(guide, facts)
        print(md)
        print(f"\n[source: {source}]", file=sys.stderr)
        return
    llm = LLM(Settings())
    guide, report, source = generate_guide(facts, llm, use_judge=not args.no_judge)
    md = render_markdown(guide, facts)
    print(md)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(md, encoding="utf-8")
        Path(args.out).with_suffix(".json").write_text(guide.model_dump_json(indent=2), encoding="utf-8")
    print("\n" + report.summary(), file=sys.stderr)
    print(f"[source: {source}]\n" + llm.tracker.table(), file=sys.stderr)


def cmd_chat(args):
    _, facts = _load(args.report)
    llm = LLM(Settings())
    session = ChatSession(facts, llm)
    print(f"[{facts.child_name} 보고서 기준 상담 전 질문 도우미. 종료: /quit, 메모 보기: /note]\n")
    questions = args.ask or []
    interactive = not questions
    while True:
        if interactive:
            try:
                q = input("보호자> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
        else:
            if not questions:
                break
            q = questions.pop(0)
            print(f"보호자> {q}")
        if not q:
            continue
        if q == "/quit":
            break
        if q == "/note":
            print(render_handoff(session.handoff_note()))
            continue
        turn = session.ask(q)
        print(f"도우미> {turn.reply}\n   [{turn.category} | 불안:{turn.anxiety_level} | 상담사 전달:{turn.log_for_counselor}]\n")
    print("\n" + render_handoff(session.handoff_note()))
    print("\n" + llm.tracker.table(), file=sys.stderr)


def cmd_eval(args):
    from .evaluate import run_eval
    run_eval(report_path=Path(args.report), cases_path=Path(args.cases), model=args.model, out_dir=Path(args.out))


def main(argv=None):
    p = argparse.ArgumentParser(prog="cbcl", description="K-CBCL parent companion PoC")
    p.add_argument("--report", default="data/sample_report.json", help="report .json or .pdf")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("facts", help="print the deterministic facts the LLM receives").set_defaults(fn=cmd_facts)

    e = sub.add_parser("explain", help="generate the parent guide (Feature A)")
    e.add_argument("--template", action="store_true", help="no API call; deterministic fallback only")
    e.add_argument("--no-judge", action="store_true", help="skip the LLM judge pass")
    e.add_argument("--out", help="write markdown (+ .json) here")
    e.set_defaults(fn=cmd_explain)

    c = sub.add_parser("chat", help="pre-consultation Q&A (Feature B)")
    c.add_argument("--ask", action="append", help="scripted question (repeatable); omit for interactive")
    c.set_defaults(fn=cmd_chat)

    ev = sub.add_parser("eval", help="run the guardrail eval set")
    ev.add_argument("--cases", default="eval/cases.jsonl")
    ev.add_argument("--model", default=None, help="override chat model for this run")
    ev.add_argument("--out", default="eval/results")
    ev.set_defaults(fn=cmd_eval)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
