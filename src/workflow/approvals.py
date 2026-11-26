"""Human-in-the-loop approval inbox (blueprint Part 3 upgrade).

Agents pause at risky steps — publishing, emailing, spending money —
and wait for a human. Nothing risky happens while a request is pending.
"""

from __future__ import annotations

from .state import ApprovalRequest, RunState

RISKY_KINDS = ("publish", "email", "spend")


def request(state: RunState, kind: str, description: str) -> ApprovalRequest:
    if kind not in RISKY_KINDS:
        raise ValueError(f"unknown approval kind: {kind}")
    req = ApprovalRequest(id=f"appr-{len(state.approvals) + 1}",
                          kind=kind, description=description)
    state.approvals.append(req)
    state.log("orchestrator", "approval_requested",
              f"{kind}: {description}")
    return req


def decide(state: RunState, request_id: str, approve: bool,
           decided_by: str = "human") -> ApprovalRequest:
    for req in state.approvals:
        if req.id == request_id:
            req.status = "approved" if approve else "rejected"
            req.decided_by = decided_by
            state.log("orchestrator",
                      "approval_approved" if approve else "approval_rejected",
                      req.description)
            return req
    raise KeyError(request_id)


def pending(state: RunState) -> list[ApprovalRequest]:
    return [a for a in state.approvals if a.status == "pending"]


def all_approved(state: RunState, kind: str | None = None) -> bool:
    reqs = [a for a in state.approvals
            if kind is None or a.kind == kind]
    return bool(reqs) and all(a.status == "approved" for a in reqs)
