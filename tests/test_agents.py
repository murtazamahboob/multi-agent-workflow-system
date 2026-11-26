"""Tests for the five agents, the skill library and approvals."""

from workflow import agents, approvals, skills
from workflow.state import Budget, DraftSentence, RunState
from workflow.tools import ToolRunner


def _state(goal="produce a market report on AI voice agents for restaurants"):
    return RunState(run_id="t", goal=goal, budget=Budget())


def test_skill_pick_market_report():
    assert skills.pick_skill(
        "produce a market report on AI voice agents for restaurants") \
        == "market-report"


def test_skill_pick_competitor_teardown():
    assert skills.pick_skill("competitor teardown of three voice-AI vendors") \
        == "competitor-teardown"


def test_skill_pick_lead_research():
    assert skills.pick_skill("lead research for small-business outreach") \
        == "lead-research"


def test_skill_pick_generic_fallback():
    assert skills.pick_skill("write about something completely unrelated") \
        == "generic-report"


def test_planner_creates_typed_plan_with_dependencies():
    state, tools = _state(), ToolRunner(Budget())
    plan = agents.plan(state, tools)
    assert plan.skill == "market-report"
    assert len(plan.tasks) == 7
    assert plan.tasks[1].depends_on == ["task-1"]
    assert plan.sections[0] == "Summary"


def test_researcher_collects_evidence_and_quarantines_injection():
    state, tools = _state(), ToolRunner(Budget())
    agents.plan(state, tools)
    evidence = agents.research(state, tools)
    assert len(evidence) >= 6
    assert all("attacker@example.org" not in e.quote for e in evidence)
    assert len(state.quarantined) == 1
    assert "ignore-previous-instructions" in state.quarantined[0]["pattern"]
    assert all(t.done for t in state.plan.tasks
               if t.owner == "researcher")


def test_researcher_requires_two_sources_for_key_claims():
    state, tools = _state(), ToolRunner(Budget())
    agents.plan(state, tools)
    agents.research(state, tools)
    urls = {e.source_url for e in state.evidence}
    assert len(urls) >= 2


def test_analyst_computes_change_in_sandbox():
    state, tools = _state(), ToolRunner(Budget())
    agents.plan(state, tools)
    agents.research(state, tools)
    findings = agents.analyse(state, tools)
    change = findings[0]
    assert change.value == 7.0  # 18% now, up from 11%
    assert change.unit == "percentage points"
    assert "18.0 - 11.0" in change.calculation


def test_writer_every_sentence_cited():
    state, tools = _state(), ToolRunner(Budget())
    agents.plan(state, tools)
    agents.research(state, tools)
    agents.analyse(state, tools)
    draft = agents.write(state, tools)
    assert len(draft) >= 5
    assert all(s.cited for s in draft)
    assert draft[0].text.startswith("Summary:")
    assert "Recommendation:" in draft[-1].text


def test_reviewer_passes_a_good_draft():
    state, tools = _state(), ToolRunner(Budget())
    agents.plan(state, tools)
    agents.research(state, tools)
    agents.analyse(state, tools)
    agents.write(state, tools)
    review = agents.review(state, tools)
    assert review.passed
    assert all(v >= 4 for v in review.scores.values())


def test_reviewer_fails_uncited_draft():
    state, tools = _state(), ToolRunner(Budget())
    agents.plan(state, tools)
    agents.research(state, tools)
    agents.analyse(state, tools)
    agents.write(state, tools)
    for i in range(4):
        state.draft.append(
            DraftSentence(text=f"Uncited claim {i} with no source."))
    review = agents.review(state, tools)
    assert not review.passed
    assert review.scores["citation_coverage"] < 4
    assert review.fixes


def test_revise_drops_uncited_sentences():
    state, tools = _state(), ToolRunner(Budget())
    agents.plan(state, tools)
    agents.research(state, tools)
    agents.analyse(state, tools)
    agents.write(state, tools)
    state.draft.append(DraftSentence(text="Uncited claim."))
    agents.review(state, tools)
    revised = agents.revise(state, tools)
    assert all(s.cited for s in revised)
    assert state.revise_loops == 1


def test_baseline_has_no_citations_and_hype():
    state, tools = _state(), ToolRunner(Budget())
    agents.run_baseline(state, tools)
    assert state.citation_coverage == 0.0
    assert any("best solution" in s.text for s in state.draft)


def test_approvals_gate_and_decide():
    state = _state()
    req = approvals.request(state, "publish", "Publish the report")
    assert req.status == "pending"
    assert approvals.pending(state) == [req]
    assert not approvals.all_approved(state, "publish")
    approvals.decide(state, req.id, True)
    assert req.status == "approved"
    assert approvals.all_approved(state, "publish")


def test_approvals_reject_unknown_kind():
    import pytest
    with pytest.raises(ValueError):
        approvals.request(_state(), "launch-missiles", "no")
