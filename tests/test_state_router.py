"""Tests for typed state, budgets and the cost-aware router."""

from workflow.router import estimate_tokens, route
from workflow.state import Budget, Review


def test_estimate_tokens_scales_with_words():
    assert estimate_tokens("one two three four") > estimate_tokens("one two")
    assert estimate_tokens("") >= 1


def test_router_picks_cheap_for_routine_step():
    budget = Budget(max_money_usd=0.50)
    choice = route("research", "a short query", budget)
    assert choice.model == "mock-cheap"
    assert choice.cost_usd < 0.001


def test_router_picks_strong_for_hard_step_when_affordable():
    budget = Budget(max_money_usd=0.50)
    choice = route("review", "a long draft to review carefully", budget)
    assert choice.model == "mock-strong"


def test_router_degrades_to_cheap_when_money_runs_out():
    budget = Budget(max_money_usd=0.00001)
    choice = route("review", " ".join(["word"] * 200), budget)
    assert choice.model == "mock-cheap"
    assert "degraded" in choice.reason


def test_budget_exceeded_reports_the_right_limit():
    budget = Budget(max_tokens=10)
    assert budget.exceeded() is None
    budget.charge(11, 0.0)
    assert budget.exceeded() == "token budget exceeded"


def test_budget_warns_at_80_percent():
    budget = Budget(max_tokens=100)
    assert not budget.warn()
    budget.charge(80, 0.0)
    assert budget.warn()


def test_review_passes_only_at_4_on_every_criterion():
    good = Review(scores={c: 4 for c in
                          ("accuracy", "completeness", "structure",
                           "tone", "citation_coverage")})
    assert good.passed
    bad = Review(scores={c: 5 for c in
                         ("accuracy", "completeness", "structure",
                          "tone", "citation_coverage")})
    bad.scores["tone"] = 3
    assert not bad.passed


def test_citation_coverage_counts_cited_sentences():
    from workflow.state import DraftSentence, RunState
    state = RunState(run_id="t", goal="g")
    state.draft = [DraftSentence(text="a.", evidence_ids=["ev-01"]),
                   DraftSentence(text="b.")]
    assert state.citation_coverage == 0.5
