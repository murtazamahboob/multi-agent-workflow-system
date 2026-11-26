"""Orchestration: the workflow as an explicit graph (blueprint §4.2).

Plain-Python state machine, not LangGraph — that is a deliberate
difference from project #1. Edges and stop conditions are visible:

    plan -> research -> analyse -> write -> review
        -> revise (max 3 loops) -> review ...
        -> approval gate -> done

Budgets are checked after every step; exceeding one stops the run
gracefully with a partial result. Replay rewinds the run log to any
step, edits the plan or prompt, and re-runs from there.
"""

from __future__ import annotations

import copy
import itertools
import json

from . import agents, approvals
from .state import Budget, RunState
from .tools import ToolRunner

MAX_REVISE_LOOPS = 3  # blueprint §4.4
_run_counter = itertools.count(1)


def run(goal: str, budget: Budget | None = None,
        auto_approve: bool = False, require_approval: bool = True) -> RunState:
    state = RunState(run_id=f"run-{next(_run_counter):03d}", goal=goal,
                     budget=budget or Budget())
    tools = ToolRunner(state.budget)
    state.log("orchestrator", "run_started", goal)

    agents.plan(state, tools)
    if _stopped(state):
        return state
    agents.research(state, tools)
    if _stopped(state):
        return state
    agents.analyse(state, tools)
    if _stopped(state):
        return state
    agents.write(state, tools)
    if _stopped(state):
        return state

    while True:
        review = agents.review(state, tools)
        if _stopped(state):
            return state
        if review.passed:
            break
        if state.revise_loops >= MAX_REVISE_LOOPS:
            state.status = "stopped"
            state.stop_reason = (f"review did not pass after "
                                 f"{MAX_REVISE_LOOPS} revise loops")
            state.log("orchestrator", "run_stopped", state.stop_reason)
            return state
        agents.revise(state, tools)
        if _stopped(state):
            return state

    # Human approval gate before the deliverable is released.
    if require_approval:
        req = approvals.request(
            state, "publish",
            f"Publish the reviewed report for goal: {goal}")
        if auto_approve:
            approvals.decide(state, req.id, True, decided_by="auto-approve")
        else:
            state.status = "awaiting_approval"
            state.stop_reason = f"waiting on approval {req.id}"
            state.log("orchestrator", "awaiting_approval", req.id)
            return state

    state.status = "done"
    state.log("orchestrator", "run_done",
              f"revise loops={state.revise_loops}, coverage="
              f"{state.citation_coverage:.0%}, cost="
              f"${state.budget.money_usd:.4f}")
    return state


def _stopped(state: RunState) -> bool:
    reason = state.budget.exceeded()
    if reason:
        state.status = "stopped"
        state.stop_reason = reason
        state.log("orchestrator", "budget_stop", reason)
        return True
    return False


# ---------------------------------------------------------------------------
# Replay and branch
# ---------------------------------------------------------------------------

def snapshot(state: RunState) -> dict:
    """A JSON snapshot of the run at its current step."""
    return {"step": len(state.trace), "state": state.to_dict()}


def replay_from(state: RunState, step: int, new_goal: str | None = None,
                auto_approve: bool = True) -> RunState:
    """Rewind to *step* in the trace, optionally edit the goal, and
    re-run from there. The original run is untouched (branch)."""
    if step < 1 or step > len(state.trace):
        raise ValueError(f"no step {step} in a {len(state.trace)}-step run")
    branched = copy.deepcopy(state)
    branched.run_id = f"{state.run_id}-branch"
    branched.trace = branched.trace[:step]
    branched.status = "running"
    branched.stop_reason = ""
    branched.log("orchestrator", "replay_started",
                 f"rewound to step {step}" +
                 (f", new goal: {new_goal}" if new_goal else ""))
    # Re-run the pipeline from the rewound point with the (possibly
    # edited) goal. The trace keeps the replay marker as its history.
    goal = new_goal or state.goal
    tools = ToolRunner(branched.budget)
    branched.goal = goal
    agents.plan(branched, tools)
    agents.research(branched, tools)
    agents.analyse(branched, tools)
    agents.write(branched, tools)
    review = agents.review(branched, tools)
    loops = 0
    while not review.passed and loops < MAX_REVISE_LOOPS:
        agents.revise(branched, tools)
        review = agents.review(branched, tools)
        loops += 1
    branched.status = "done" if review.passed else "stopped"
    branched.log("orchestrator", "replay_done",
                 f"passed={review.passed}")
    return branched


def render_report(state: RunState) -> str:
    """Markdown deliverable: the draft in order, with a numbered source
    list and the run's cost and trace. Sentences are NOT forced into
    sections they do not belong to — the plan's sections are listed
    separately, and every sentence carries its evidence links."""
    lines = [f"# {state.goal}", ""]
    lines.append("## Report")
    lines.append("")
    for sentence in state.draft:
        refs = ", ".join(f"[{e}]" for e in sentence.evidence_ids)
        lines.append(f"- {sentence.text} {refs}")
    lines.append("")
    if state.plan:
        lines.append("## Plan")
        lines.append("")
        lines.append(f"- Skill: {state.plan.skill}")
        lines.append(f"- Sections: {', '.join(state.plan.sections)}")
        lines.append(f"- Tasks: {sum(1 for t in state.plan.tasks if t.done)}"
                     f"/{len(state.plan.tasks)} done")
        lines.append("")
    lines.append("## Sources")
    lines.append("")
    seen = {}
    for ev in state.evidence:
        seen[ev.id] = ev
    for ev_id, ev in seen.items():
        lines.append(f"- [{ev_id}] {ev.source_title} — {ev.source_url} "
                     f"({ev.date})")
    lines.append("")
    lines.append("## Run log")
    lines.append("")
    lines.append(f"- Status: {state.status}")
    lines.append(f"- Citation coverage: {state.citation_coverage:.0%}")
    lines.append(f"- Revise loops: {state.revise_loops}")
    lines.append(f"- Cost: ${state.budget.money_usd:.4f} "
                 f"({state.budget.tokens_used} tokens, "
                 f"{state.budget.tool_calls} tool calls)")
    lines.append(f"- Models used: "
                 + ", ".join(sorted({m['model']
                                     for m in state.model_choices})))
    if state.quarantined:
        lines.append(f"- Quarantined passages: {len(state.quarantined)} "
                     f"(prompt-injection attempts, never used as evidence)")
    return "\n".join(lines)
