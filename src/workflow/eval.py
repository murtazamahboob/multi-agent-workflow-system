"""Eval-driven development (blueprint Part 3 upgrade).

A scoreboard of 30 tasks, re-run on every change, comparing the
multi-agent system with the single-agent baseline on the reviewer
rubric, citation coverage, reference-keyword coverage and cost per
task. History is appended to ``outputs/eval-history.json`` so the
scoreboard can be charted over time.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import agents, knowledge
from .orchestrator import run as run_multi
from .state import Budget, RunState
from .tools import ToolRunner


def _keyword_coverage(state: RunState, reference: list[str]) -> float:
    text = " ".join(s.text.lower() for s in state.draft)
    hit = sum(1 for kw in reference if kw.lower() in text)
    return hit / max(len(reference), 1)


def score_task(task: dict) -> dict:
    multi = run_multi(task["goal"], auto_approve=True,
                      require_approval=False)
    multi_review = multi.reviews[-1] if multi.reviews else None

    # Baseline in a fresh state, scored by the same reviewer.
    base_state = RunState(run_id=f"baseline-{task['id']}", goal=task["goal"],
                          budget=Budget())
    base_tools = ToolRunner(base_state.budget)
    agents.run_baseline(base_state, base_tools)
    # Give the baseline a plan so the reviewer can score structure
    # against the same sections the multi-agent system used.
    base_state.plan = multi.plan
    base_review = agents.review(base_state, base_tools)

    return {
        "id": task["id"],
        "goal": task["goal"],
        "multi": {
            "mean_rubric": round(multi_review.mean, 2)
            if multi_review else 0.0,
            "passed": bool(multi_review and multi_review.passed),
            "citation_coverage": round(multi.citation_coverage, 3),
            "keyword_coverage": round(
                _keyword_coverage(multi, task["reference_keywords"]), 3),
            "cost_usd": round(multi.budget.money_usd, 4),
            "revise_loops": multi.revise_loops,
        },
        "baseline": {
            "mean_rubric": round(base_review.mean, 2),
            "passed": base_review.passed,
            "citation_coverage": round(base_state.citation_coverage, 3),
            "keyword_coverage": round(
                _keyword_coverage(base_state, task["reference_keywords"]), 3),
            "cost_usd": round(base_state.budget.money_usd, 4),
            "revise_loops": 0,
        },
    }


def run_eval(history_path: Path | None = None) -> dict:
    tasks = knowledge.eval_tasks()
    rows = [score_task(t) for t in tasks]
    multi_pass = sum(1 for r in rows if r["multi"]["passed"])
    base_pass = sum(1 for r in rows if r["baseline"]["passed"])
    summary = {
        "tasks": len(rows),
        "multi_agent": {
            "pass_rate": round(multi_pass / len(rows), 3),
            "mean_rubric": round(
                sum(r["multi"]["mean_rubric"] for r in rows) / len(rows), 2),
            "mean_citation_coverage": round(
                sum(r["multi"]["citation_coverage"] for r in rows)
                / len(rows), 3),
            "mean_keyword_coverage": round(
                sum(r["multi"]["keyword_coverage"] for r in rows)
                / len(rows), 3),
            "mean_cost_usd": round(
                sum(r["multi"]["cost_usd"] for r in rows) / len(rows), 4),
        },
        "baseline": {
            "pass_rate": round(base_pass / len(rows), 3),
            "mean_rubric": round(
                sum(r["baseline"]["mean_rubric"] for r in rows) / len(rows),
                2),
            "mean_citation_coverage": round(
                sum(r["baseline"]["citation_coverage"] for r in rows)
                / len(rows), 3),
            "mean_keyword_coverage": round(
                sum(r["baseline"]["keyword_coverage"] for r in rows)
                / len(rows), 3),
            "mean_cost_usd": round(
                sum(r["baseline"]["cost_usd"] for r in rows) / len(rows), 4),
        },
        "rows": rows,
    }
    if history_path is not None:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history = []
        if history_path.exists():
            history = json.loads(history_path.read_text())
        history.append({k: v for k, v in summary.items()
                        if k != "rows"})
        history_path.write_text(json.dumps(history, indent=2))
    return summary


def render_scoreboard(summary: dict) -> str:
    m, b = summary["multi_agent"], summary["baseline"]
    lines = [
        "# Eval scoreboard — 30 tasks",
        "",
        "Re-run on every change. Multi-agent system vs single-agent baseline.",
        "",
        "| Metric | Multi-agent | Baseline |",
        "|---|---|---|",
        f"| Pass rate | {m['pass_rate']:.0%} | {b['pass_rate']:.0%} |",
        f"| Mean rubric (1-5) | {m['mean_rubric']} | {b['mean_rubric']} |",
        f"| Mean citation coverage | {m['mean_citation_coverage']:.0%} | "
        f"{b['mean_citation_coverage']:.0%} |",
        f"| Mean keyword coverage | {m['mean_keyword_coverage']:.0%} | "
        f"{b['mean_keyword_coverage']:.0%} |",
        f"| Mean cost per task | ${m['mean_cost_usd']:.4f} | "
        f"${b['mean_cost_usd']:.4f} |",
        "",
        "## Per-task results",
        "",
        "| Task | Multi rubric | Multi coverage | Baseline rubric | "
        "Baseline coverage |",
        "|---|---|---|---|---|",
    ]
    for row in summary["rows"]:
        lines.append(
            f"| {row['id']} | {row['multi']['mean_rubric']} | "
            f"{row['multi']['citation_coverage']:.0%} | "
            f"{row['baseline']['mean_rubric']} | "
            f"{row['baseline']['citation_coverage']:.0%} |")
    return "\n".join(lines) + "\n"
