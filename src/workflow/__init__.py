"""Multi-Agent Workflow System — a team of specialised agents that plan,
research, write, review and deliver finished work with tools and
guardrails. Offline and deterministic: mock models, a bundled knowledge
base, plain-Python state machine (no LangGraph). Every claim in the
output links back to its source in an evidence graph; the reviewer
enforces a 1-5 rubric with a pass bar of 4 on every criterion.
"""

from __future__ import annotations

from . import agents, approvals, evidence, orchestrator, router, security, skills, tools
from .eval import run_eval
from .orchestrator import replay_from, render_report, run
from .state import Budget, RunState

__all__ = [
    "agents", "approvals", "evidence", "orchestrator", "replay_from",
    "render_report", "router", "run", "run_eval", "security", "skills",
    "tools", "Budget", "RunState",
]

__version__ = "1.0.0"
