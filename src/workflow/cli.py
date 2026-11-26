"""CLI for the Multi-Agent Workflow System.

Usage:
    maws demo [--output-dir DIR]     bundled market-report demo
    maws run "goal" [--auto-approve] [--no-approval]
    maws eval [--output-dir DIR]     30-task scoreboard vs baseline
    maws replay [--step N]           replay/branch demo on the demo run
    maws skills                      list the skill library
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import evidence, orchestrator, skills
from .eval import render_scoreboard, run_eval
from .state import Budget

DEMO_GOAL = "produce a market report on AI voice agents for restaurants"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    print(f"wrote {path}")


def cmd_demo(args: argparse.Namespace) -> int:
    out = Path(args.output_dir)
    state = orchestrator.run(DEMO_GOAL, auto_approve=True)
    _write(out / "report.md", orchestrator.render_report(state))
    _write(out / "report.json", json.dumps(state.to_dict(), indent=2))
    _write(out / "evidence-graph.html", evidence.render_html(state))
    print(f"status: {state.status}  coverage: "
          f"{state.citation_coverage:.0%}  "
          f"revise loops: {state.revise_loops}  "
          f"cost: ${state.budget.money_usd:.4f}  "
          f"quarantined: {len(state.quarantined)}")
    return 0 if state.status == "done" else 1


def cmd_run(args: argparse.Namespace) -> int:
    budget = Budget(max_tokens=args.max_tokens)
    state = orchestrator.run(args.goal, budget=budget,
                             auto_approve=args.auto_approve,
                             require_approval=not args.no_approval)
    print(orchestrator.render_report(state))
    return 0 if state.status == "done" else 1


def cmd_eval(args: argparse.Namespace) -> int:
    out = Path(args.output_dir)
    summary = run_eval(history_path=out / "eval-history.json")
    _write(out / "eval.json", json.dumps(summary, indent=2))
    _write(out / "scoreboard.md", render_scoreboard(summary))
    m, b = summary["multi_agent"], summary["baseline"]
    print(f"tasks: {summary['tasks']}")
    print(f"multi-agent: pass {m['pass_rate']:.0%}, rubric "
          f"{m['mean_rubric']}, coverage {m['mean_citation_coverage']:.0%}, "
          f"${m['mean_cost_usd']:.4f}/task")
    print(f"baseline:    pass {b['pass_rate']:.0%}, rubric "
          f"{b['mean_rubric']}, coverage {b['mean_citation_coverage']:.0%}, "
          f"${b['mean_cost_usd']:.4f}/task")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    state = orchestrator.run(DEMO_GOAL, auto_approve=True)
    step = args.step or max(1, len(state.trace) // 2)
    branched = orchestrator.replay_from(state, step, auto_approve=True)
    print(f"original run: {len(state.trace)} steps, status {state.status}")
    print(f"branched run: rewound to step {step}, "
          f"{len(branched.trace)} steps, status {branched.status}, "
          f"coverage {branched.citation_coverage:.0%}")
    return 0 if branched.status == "done" else 1


def cmd_skills(_args: argparse.Namespace) -> int:
    for name, skill in skills.SKILLS.items():
        print(f"- {name}: {', '.join(skill['sections'])}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="maws", description="Multi-Agent Workflow System")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="bundled market-report demo")
    demo.add_argument("--output-dir", default="outputs")
    demo.set_defaults(func=cmd_demo)

    run_p = sub.add_parser("run", help="run the workflow on a goal")
    run_p.add_argument("goal")
    run_p.add_argument("--auto-approve", action="store_true")
    run_p.add_argument("--no-approval", action="store_true")
    run_p.add_argument("--max-tokens", type=int, default=20_000)
    run_p.set_defaults(func=cmd_run)

    eval_p = sub.add_parser("eval", help="30-task scoreboard vs baseline")
    eval_p.add_argument("--output-dir", default="outputs")
    eval_p.set_defaults(func=cmd_eval)

    replay_p = sub.add_parser("replay", help="replay/branch the demo run")
    replay_p.add_argument("--step", type=int, default=None)
    replay_p.set_defaults(func=cmd_replay)

    skills_p = sub.add_parser("skills", help="list the skill library")
    skills_p.set_defaults(func=cmd_skills)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
