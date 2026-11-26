"""Tests for orchestration, evidence graph, replay and the eval set."""

from workflow import evidence, orchestrator
from workflow.state import Budget


DEMO = "produce a market report on AI voice agents for restaurants"


def test_full_run_completes_with_full_coverage():
    state = orchestrator.run(DEMO, auto_approve=True)
    assert state.status == "done"
    assert state.citation_coverage == 1.0
    assert state.reviews and state.reviews[-1].passed
    assert len(state.quarantined) == 1
    assert state.budget.money_usd < 0.50
    assert state.budget.tokens_used <= 20_000


def test_run_waits_for_approval_by_default():
    state = orchestrator.run(DEMO, auto_approve=False)
    assert state.status == "awaiting_approval"
    assert state.approvals and state.approvals[0].status == "pending"


def test_run_stops_gracefully_on_tiny_token_budget():
    state = orchestrator.run(DEMO, budget=Budget(max_tokens=10),
                             auto_approve=True)
    assert state.status == "stopped"
    assert "token budget" in state.stop_reason


def test_run_stops_gracefully_on_tiny_tool_budget():
    state = orchestrator.run(DEMO, budget=Budget(max_tool_calls=2),
                             auto_approve=True)
    assert state.status == "stopped"
    assert "tool-call budget" in state.stop_reason


def test_evidence_graph_links_every_sentence():
    state = orchestrator.run(DEMO, auto_approve=True)
    graph = evidence.build_graph(state)
    assert graph["orphaned_sentences"] == []
    assert graph["citation_coverage"] == 1.0
    sentence_nodes = [n for n in graph["nodes"] if n["type"] == "sentence"]
    assert len(sentence_nodes) == len(state.draft)
    assert len(graph["edges"]) >= len(state.draft)


def test_evidence_html_names_sources():
    state = orchestrator.run(DEMO, auto_approve=True)
    html = evidence.render_html(state)
    assert "Voice ordering in restaurants" in html
    assert "Citation coverage: 100%" in html


def test_report_markdown_has_sections_sources_and_cost():
    state = orchestrator.run(DEMO, auto_approve=True)
    report = orchestrator.render_report(state)
    assert "# produce a market report" in report
    assert "## Sources" in report
    assert "## Run log" in report
    assert "Cost: $" in report
    assert "Quarantined passages: 1" in report


def test_replay_branch_reproduces_a_done_run():
    state = orchestrator.run(DEMO, auto_approve=True)
    branched = orchestrator.replay_from(state, step=3)
    assert branched.status == "done"
    assert branched.citation_coverage == 1.0
    assert branched.run_id != state.run_id
    # The original run is untouched by the branch.
    assert state.status == "done"


def test_replay_with_edited_goal_changes_skill():
    state = orchestrator.run(DEMO, auto_approve=True)
    branched = orchestrator.replay_from(
        state, step=2,
        new_goal="competitor teardown of three voice-AI vendors")
    assert branched.status == "done"
    assert branched.plan.skill == "competitor-teardown"


def test_replay_rejects_bad_step():
    import pytest
    state = orchestrator.run(DEMO, auto_approve=True)
    with pytest.raises(ValueError):
        orchestrator.replay_from(state, step=999)


def test_trace_records_every_agent():
    state = orchestrator.run(DEMO, auto_approve=True)
    agents_seen = {t.agent for t in state.trace}
    assert {"planner", "researcher", "analyst", "writer", "reviewer",
            "orchestrator"} <= agents_seen


def test_no_langgraph_or_network_in_run():
    state = orchestrator.run(DEMO, auto_approve=True)
    assert all(m["model"].startswith("mock-")
               for m in state.model_choices)
