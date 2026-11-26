# Multi-Agent Workflow System

A team of specialised agents that plan, research, write, review and deliver finished work with tools and guardrails — offline, deterministic, plain Python.

Give it a goal such as *"produce a market report on AI voice agents for restaurants"* and it returns a cited, reviewed deliverable. The value is not one clever prompt but a controlled workflow: roles, tools, shared state, review loops, budgets and logs.

## Why this is different

This is the blueprint's Multi-Agent Workflow System (Project 4), built **only** with the Part 3 upgrades that make it a clearly different system from the LangGraph research assistant already on this profile:

- **Evidence graph** — every sentence in the output links back to the exact source passage; exportable as JSON and as a self-contained HTML page (click a sentence, see its sources).
- **Eval-driven development** — a scoreboard of **30 tasks**, re-run on every change, comparing the multi-agent system with a single-agent baseline.
- **Cost-aware model router** — routine steps go to a cheap model, planning and review to a strong one; when money runs low the run degrades to cheap instead of dying.
- **Replay and branch** — rewind a run to any step, edit the goal, and re-run from there; the original run is untouched.
- **Human-in-the-loop approvals** — agents pause before publishing, emailing or spending; nothing risky happens while a request is pending.
- **Skill library** — reusable recipes (market report, competitor teardown, lead research, cost control, risk assessment) the Planner picks from by goal keywords.
- **Plain-Python state machine, not LangGraph** — the workflow graph, loops and stop conditions are explicit and testable. Agents share a **typed state object**, not a chat transcript.

## The agents

| Agent | Job | Tools |
|---|---|---|
| Planner | Understands the goal, picks a skill, creates a task graph with owners, dependencies and acceptance criteria | Skill library |
| Researcher | Finds and reads sources, extracts facts with URLs and dates | Search, fetch, long-term memory |
| Analyst | Compares, computes, builds findings | No-network code sandbox (arithmetic only) |
| Writer | Turns findings into the deliverable with inline citations | Template / skill sections |
| Reviewer / Critic | Checks facts against evidence, structure, tone, missing parts | Evidence list, rubric |

## Guardrails

- **Evidence first** — a claim without a source in the evidence list cannot appear in the final text; the Reviewer enforces it. Citation coverage on the demo: **100%**.
- **Reviewer rubric** — accuracy, completeness, structure, tone, citation coverage, each scored 1–5; pass at 4 or more on all. Revise loop, max 3.
- **Budgets** — hard limits on tokens (20,000), tool calls (50), wall-clock time and money ($0.50) per run, with a warning at 80% of the token budget and a graceful stop with a partial result.
- **Prompt-injection defence** — fetched text is treated as data, never instructions. Injection attempts are quarantined and logged, never used as evidence. The bundled demo contains one: an instruction to reveal the system prompt and email the report to an attacker — it is caught and quarantined.
- **Tool schemas, timeouts and safe failures** — every tool has a schema and a timeout; a failed tool returns a safe error, never crashes the run.

## Results

Bundled demo — *"produce a market report on AI voice agents for restaurants"*:

- 12 evidence items from 6 sources, 1 injection passage quarantined
- 14 sentences, **100% citation coverage**, reviewer passes first time (0 revise loops)
- Analyst: voice ordering 18% of phone orders, up from 11% a year earlier — **+7 percentage points, +63.6%**
- Cost: **$0.0002** (65 tokens, 10 tool calls), models used: mock-cheap + mock-strong

Eval scoreboard — 30 tasks, multi-agent system vs single-agent baseline:

| Metric | Multi-agent | Baseline |
|---|---|---|
| Pass rate | 100% | 0% |
| Mean rubric (1–5) | 4.95 | 1.8 |
| Mean citation coverage | 100% | 0% |
| Mean keyword coverage | 86% | 57% |
| Mean cost per task | $0.0002 | $0.0000 |

## Quickstart

```bash
pip install -r requirements.txt
pip install -e .

# Bundled demo: market report on AI voice agents for restaurants
maws demo

# Or run the demo script directly
python examples/demo.py

# Run the workflow on your own goal (pauses for approval before publishing)
maws run "competitor teardown of three voice-AI vendors"

# Auto-approve the publish step
maws run "lead research report for small-business outreach" --auto-approve

# 30-task eval scoreboard vs the single-agent baseline
maws eval

# Replay / branch the demo run from step 3
maws replay --step 3

# List the skill library
maws skills
```

## Python API

```python
from workflow import run, render_report
from workflow.eval import run_eval

state = run("produce a market report on AI voice agents for restaurants",
            auto_approve=True)
print(state.status)              # done
print(state.citation_coverage)   # 1.0
print(render_report(state))

summary = run_eval()             # 30-task scoreboard
print(summary["multi_agent"])    # pass 100%, rubric 4.95, coverage 100%
```

## Project structure

```
src/workflow/
  state.py         typed shared state, budgets, review rubric, trace
  knowledge.py     bundled mock knowledge base + 30-task eval set
  tools.py         tool schemas, timeouts, safe failures, AST sandbox
  router.py        cost-aware model router (cheap vs strong)
  security.py      prompt-injection defence (quarantine, never obey)
  skills.py        skill library: market report, teardown, lead research…
  agents.py        Planner, Researcher, Analyst, Writer, Reviewer, baseline
  orchestrator.py  plain-Python workflow graph, budgets, replay/branch
  approvals.py     human-in-the-loop approval inbox
  evidence.py      evidence graph (JSON + HTML)
  eval.py          30-task eval scoreboard vs baseline
  cli.py           `maws` command line
tests/             54 tests
examples/demo.py   bundled demo
```

## Offline by design

No LLM API key, no network, no framework. The "LLM" is a cost-aware mock router and the "web" is a bundled, deterministic knowledge base — so every run is reproducible. A real deployment swaps the mock router for model APIs and the knowledge base for a search API + fetcher without changing any agent.

## License

MIT
