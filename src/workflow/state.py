"""Typed shared state for the Multi-Agent Workflow System.

The core design idea from the blueprint: agents read and write a *typed
state object* (goal, plan, evidence, draft, review notes, budget) instead
of passing long chat transcripts around. That makes every step debuggable,
replayable and testable — and it is the main architectural difference from
project #1, which passes a LangGraph message list between agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Evidence:
    """One sourced fact. A claim may only appear in the final text if an
    Evidence record like this exists for it (evidence-first rule)."""

    id: str
    claim: str
    source_title: str
    source_url: str
    date: str  # ISO date, e.g. "2026-03-14"
    quote: str


@dataclass
class DraftSentence:
    """One sentence of the draft, linked to the evidence that backs it."""

    text: str
    evidence_ids: list[str] = field(default_factory=list)

    @property
    def cited(self) -> bool:
        return bool(self.evidence_ids)


@dataclass
class Finding:
    """A structured finding from the Analyst: a number with units, backed
    by evidence and by a reproducible calculation."""

    label: str
    value: float
    unit: str
    evidence_ids: list[str] = field(default_factory=list)
    calculation: str = ""


# ---------------------------------------------------------------------------
# Plan / tasks
# ---------------------------------------------------------------------------

@dataclass
class Task:
    id: str
    owner: str  # planner | researcher | analyst | writer | reviewer
    title: str
    depends_on: list[str] = field(default_factory=list)
    acceptance: str = ""
    done: bool = False


@dataclass
class Plan:
    goal: str
    skill: str
    tasks: list[Task] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)

    def task(self, task_id: str) -> Task:
        for t in self.tasks:
            if t.id == task_id:
                return t
        raise KeyError(task_id)


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------

RUBRIC_CRITERIA = ("accuracy", "completeness", "structure", "tone",
                   "citation_coverage")
PASS_SCORE = 4  # pass at 4 or more on every criterion (blueprint §4.4)


@dataclass
class Review:
    scores: dict[str, int]
    fixes: list[str] = field(default_factory=list)
    reviewer: str = "reviewer"

    @property
    def passed(self) -> bool:
        return all(self.scores.get(c, 0) >= PASS_SCORE for c in RUBRIC_CRITERIA)

    @property
    def mean(self) -> float:
        return sum(self.scores.values()) / max(len(self.scores), 1)


# ---------------------------------------------------------------------------
# Budgets, tracing, approvals
# ---------------------------------------------------------------------------

@dataclass
class Budget:
    """Hard limits per run. Exceeding one stops the run gracefully with a
    partial result instead of running away."""

    max_tokens: int = 20_000
    max_tool_calls: int = 50
    max_money_usd: float = 0.50
    max_virtual_seconds: float = 120.0
    tokens_used: int = 0
    tool_calls: int = 0
    money_usd: float = 0.0
    virtual_seconds: float = 0.0
    warning_at: float = 0.8  # warn at 80% of the token budget

    def charge(self, tokens: int, money: float, seconds: float = 1.0) -> None:
        self.tokens_used += tokens
        self.money_usd += money
        self.virtual_seconds += seconds

    def exceeded(self) -> str | None:
        if self.tokens_used > self.max_tokens:
            return "token budget exceeded"
        if self.tool_calls > self.max_tool_calls:
            return "tool-call budget exceeded"
        if self.money_usd > self.max_money_usd:
            return "money budget exceeded"
        if self.virtual_seconds > self.max_virtual_seconds:
            return "wall-clock budget exceeded"
        return None

    def warn(self) -> bool:
        return self.tokens_used >= self.warning_at * self.max_tokens


@dataclass
class TraceEntry:
    step: int
    agent: str
    action: str
    detail: str
    tokens: int = 0
    money_usd: float = 0.0


@dataclass
class ApprovalRequest:
    id: str
    kind: str  # publish | email | spend
    description: str
    status: str = "pending"  # pending | approved | rejected
    decided_by: str = ""


# ---------------------------------------------------------------------------
# Whole-run state
# ---------------------------------------------------------------------------

@dataclass
class RunState:
    run_id: str
    goal: str
    plan: Plan | None = None
    evidence: list[Evidence] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    draft: list[DraftSentence] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    budget: Budget = field(default_factory=Budget)
    trace: list[TraceEntry] = field(default_factory=list)
    approvals: list[ApprovalRequest] = field(default_factory=list)
    quarantined: list[dict[str, str]] = field(default_factory=list)
    status: str = "running"  # running | done | stopped | awaiting_approval
    stop_reason: str = ""
    revise_loops: int = 0
    model_choices: list[dict[str, Any]] = field(default_factory=list)

    # -- helpers ---------------------------------------------------------
    def evidence_by_id(self, ev_id: str) -> Evidence | None:
        for e in self.evidence:
            if e.id == ev_id:
                return e
        return None

    def log(self, agent: str, action: str, detail: str = "",
            tokens: int = 0, money: float = 0.0) -> None:
        self.trace.append(TraceEntry(
            step=len(self.trace) + 1, agent=agent, action=action,
            detail=detail, tokens=tokens, money_usd=money))

    @property
    def citation_coverage(self) -> float:
        if not self.draft:
            return 0.0
        cited = sum(1 for s in self.draft if s.cited)
        return cited / len(self.draft)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "status": self.status,
            "stop_reason": self.stop_reason,
            "revise_loops": self.revise_loops,
            "citation_coverage": round(self.citation_coverage, 3),
            "budget": {
                "tokens_used": self.budget.tokens_used,
                "max_tokens": self.budget.max_tokens,
                "tool_calls": self.budget.tool_calls,
                "money_usd": round(self.budget.money_usd, 4),
                "virtual_seconds": self.budget.virtual_seconds,
            },
            "evidence": [e.__dict__ for e in self.evidence],
            "findings": [f.__dict__ for f in self.findings],
            "draft": [{"text": s.text, "evidence_ids": s.evidence_ids}
                      for s in self.draft],
            "reviews": [{"scores": r.scores, "fixes": r.fixes,
                         "passed": r.passed} for r in self.reviews],
            "quarantined": self.quarantined,
            "approvals": [a.__dict__ for a in self.approvals],
            "trace": [t.__dict__ for t in self.trace],
        }
