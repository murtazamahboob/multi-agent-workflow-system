"""Tests for the 30-task eval scoreboard and the CLI."""

from workflow import knowledge
from workflow.cli import main


def test_eval_set_has_30_tasks():
    tasks = knowledge.eval_tasks()
    assert len(tasks) == 30
    assert len({t["id"] for t in tasks}) == 30
    assert all(t["reference_keywords"] for t in tasks)


def test_eval_multi_agent_beats_baseline():
    from workflow.eval import run_eval
    summary = run_eval()
    assert summary["tasks"] == 30
    m, b = summary["multi_agent"], summary["baseline"]
    assert m["pass_rate"] == 1.0
    assert m["mean_citation_coverage"] == 1.0
    assert m["mean_rubric"] > b["mean_rubric"]
    assert m["mean_citation_coverage"] > b["mean_citation_coverage"]
    assert b["pass_rate"] == 0.0
    assert m["mean_cost_usd"] > 0


def test_eval_scoreboard_renders(tmp_path):
    from workflow.eval import render_scoreboard, run_eval
    summary = run_eval()
    text = render_scoreboard(summary)
    assert "Eval scoreboard" in text
    assert "Multi-agent" in text
    assert "eval-voice-agents-restaurants-1" in text


def test_cli_demo_writes_outputs(tmp_path):
    assert main(["demo", "--output-dir", str(tmp_path)]) == 0
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "evidence-graph.html").exists()
    assert "Voice ordering" in (tmp_path / "report.md").read_text()


def test_cli_run_with_auto_approve(tmp_path):
    assert main(["run", "lead research report for small-business outreach",
                 "--auto-approve", "--no-approval"]) == 0


def test_cli_skills_lists_library(capsys):
    assert main(["skills"]) == 0
    assert "market-report" in capsys.readouterr().out


def test_cli_replay_succeeds():
    assert main(["replay"]) == 0
