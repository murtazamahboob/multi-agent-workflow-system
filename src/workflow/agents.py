"""The five agents: Planner, Researcher, Analyst, Writer, Reviewer.

Plus the single-agent baseline the multi-agent system is measured
against. All agents are deterministic and offline: the "LLM" is the
cost-aware mock router, the "web" is the bundled knowledge base.
"""

from __future__ import annotations

import re

from . import knowledge, router, security, skills
from .state import (RUBRIC_CRITERIA, DraftSentence, Evidence, Finding, Plan,
                    Review, RunState, Task)
from .tools import ToolRunner

HYPE_WORDS = {"amazing", "revolutionary", "game-changing", "best ever",
              "incredible", "unbelievable", "perfect solution"}


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

def plan(state: RunState, tools: ToolRunner) -> Plan:
    choice = router.route("plan", state.goal, state.budget)
    router.charge(state.budget, choice, seconds=2.0)
    state.model_choices.append({"step": "plan", "model": choice.model,
                                "reason": choice.reason})
    skill_name = skills.pick_skill(state.goal)
    skill_def = skills.skill(skill_name)
    owners = ["planner", "researcher", "researcher", "researcher",
              "analyst", "writer", "reviewer"]
    tasks = []
    for i, title in enumerate(skill_def["plan_titles"]):
        tasks.append(Task(
            id=f"task-{i + 1}",
            owner=owners[i] if i < len(owners) else "writer",
            title=title,
            depends_on=[f"task-{i}"] if i else [],
            acceptance=f"{title} is complete and recorded in shared state"))
    plan_obj = Plan(goal=state.goal, skill=skill_name, tasks=tasks,
                    sections=skill_def["sections"])
    for task in plan_obj.tasks:
        if task.owner == "planner":
            task.done = True
    state.plan = plan_obj
    state.log("planner", "plan_created",
              f"skill={skill_name}, {len(tasks)} tasks, "
              f"model={choice.model}", tokens=choice.tokens,
              money=choice.cost_usd)
    return plan_obj


# ---------------------------------------------------------------------------
# Researcher
# ---------------------------------------------------------------------------

def research(state: RunState, tools: ToolRunner) -> list[Evidence]:
    choice = router.route("research", state.goal, state.budget)
    router.charge(state.budget, choice, seconds=3.0)
    state.model_choices.append({"step": "research", "model": choice.model,
                                "reason": choice.reason})
    found = tools.search(state.goal, limit=6)
    evidence: list[Evidence] = []
    if not found.get("ok"):
        state.log("researcher", "search_failed", found.get("error", ""))
        return evidence
    for result in found["results"]:
        fetched = tools.fetch(result["id"])
        if not fetched.get("ok"):
            continue
        src = fetched["source"]
        for claim, quote in src["passages"]:
            hits = security.scan(claim) + security.scan(quote)
            if hits:
                state.quarantined.append(security.quarantine_record(
                    src["id"], quote, sorted(set(hits))))
                state.log("researcher", "passage_quarantined",
                          f"{src['id']}: {','.join(sorted(set(hits)))}")
                continue
            ev = Evidence(
                id=f"ev-{len(evidence) + 1:02d}", claim=claim,
                source_title=src["title"], source_url=src["url"],
                date=src["date"], quote=quote)
            evidence.append(ev)
    # Long-term memory: past approved facts that match the goal.
    memory = tools.memory_search(state.goal)
    if memory.get("ok"):
        for hit in memory["results"]:
            state.log("researcher", "memory_hit", hit["fact"][:80])
    state.evidence = evidence
    for task in state.plan.tasks if state.plan else []:
        if task.owner == "researcher":
            task.done = True
    state.log("researcher", "research_done",
              f"{len(evidence)} evidence items from "
              f"{len(found['results'])} sources, "
              f"{len(state.quarantined)} quarantined",
              tokens=choice.tokens, money=choice.cost_usd)
    return evidence


# ---------------------------------------------------------------------------
# Analyst
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def analyse(state: RunState, tools: ToolRunner) -> list[Finding]:
    choice = router.route("analyse", state.goal, state.budget)
    router.charge(state.budget, choice, seconds=2.0)
    state.model_choices.append({"step": "analyse", "model": choice.model,
                                "reason": choice.reason})
    findings: list[Finding] = []
    # Find the first evidence item reporting two percentages (a current
    # figure and the figure it is compared with), and compute the change
    # between them in the sandbox — e.g. 18% now, up from 11% a year ago.
    pair: tuple[float, float, str] | None = None
    for ev in state.evidence:
        numbers = [float(m.group(1)) for m in _NUMBER_RE.finditer(ev.quote)]
        if len(numbers) >= 2:
            pair = (numbers[0], numbers[1], ev.id)
            break
    if pair is not None:
        current, previous, ev_id = pair
        diff = tools.sandbox(f"{current} - {previous}")
        rel = tools.sandbox(
            f"round(({current} - {previous}) / {previous} * 100, 1)")
        if diff.get("ok") and rel.get("ok"):
            findings.append(Finding(
                label="Change between the compared percentages",
                value=diff["value"], unit="percentage points",
                evidence_ids=[ev_id],
                calculation=f"{current} - {previous} = {diff['value']}"))
            findings.append(Finding(
                label="Relative change between the compared percentages",
                value=rel["value"], unit="percent",
                evidence_ids=[ev_id],
                calculation=f"({current} - {previous}) / {previous} * 100"))
    findings.append(Finding(
        label="Evidence items collected", value=float(len(state.evidence)),
        unit="items", evidence_ids=[e.id for e in state.evidence[:3]],
        calculation=f"count(evidence) = {len(state.evidence)}"))
    state.findings = findings
    if state.plan:
        for task in state.plan.tasks:
            if task.owner == "analyst":
                task.done = True
    state.log("analyst", "analysis_done",
              f"{len(findings)} findings via sandbox",
              tokens=choice.tokens, money=choice.cost_usd)
    return findings


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def _sentence_for(evidence: Evidence, prefix: str = "") -> DraftSentence:
    text = f"{prefix}{evidence.claim}"
    if not text.endswith("."):
        text += "."
    return DraftSentence(text=text, evidence_ids=[evidence.id])


def write(state: RunState, tools: ToolRunner) -> list[DraftSentence]:
    choice = router.route("write", state.goal, state.budget)
    router.charge(state.budget, choice, seconds=3.0)
    state.model_choices.append({"step": "write", "model": choice.model,
                                "reason": choice.reason})
    draft: list[DraftSentence] = []
    if state.evidence:
        draft.append(_sentence_for(
            state.evidence[0],
            prefix="Summary: "))
        for ev in state.evidence[1:]:
            draft.append(_sentence_for(ev))
    if state.findings:
        f = state.findings[0]
        draft.append(DraftSentence(
            text=f"Analysis: the compared percentages differ by "
                 f"{f.value:g} {f.unit}.",
            evidence_ids=list(f.evidence_ids)))
    if state.evidence:
        draft.append(_sentence_for(
            state.evidence[-1],
            prefix="Recommendation: act on this evidence — "))
    state.draft = draft
    if state.plan:
        for task in state.plan.tasks:
            if task.owner == "writer":
                task.done = True
    state.log("writer", "draft_written",
              f"{len(draft)} sentences, coverage "
              f"{state.citation_coverage:.0%}",
              tokens=choice.tokens, money=choice.cost_usd)
    return draft


# ---------------------------------------------------------------------------
# Reviewer
# ---------------------------------------------------------------------------

def _score_from_fraction(fraction: float) -> int:
    if fraction >= 0.95:
        return 5
    if fraction >= 0.80:
        return 4
    if fraction >= 0.60:
        return 3
    if fraction >= 0.40:
        return 2
    return 1


def review(state: RunState, tools: ToolRunner) -> Review:
    choice = router.route("review", state.goal, state.budget)
    router.charge(state.budget, choice, seconds=2.0)
    state.model_choices.append({"step": "review", "model": choice.model,
                                "reason": choice.reason})
    scores, fixes = {}, []

    # Accuracy: each cited sentence's claim words must appear in its quote.
    accurate = 0
    for sentence in state.draft:
        ok = False
        for ev_id in sentence.evidence_ids:
            ev = state.evidence_by_id(ev_id)
            if ev is None:
                continue
            claim_words = knowledge.keywords(ev.claim)
            quote_words = knowledge.keywords(ev.quote)
            if claim_words & quote_words:
                ok = True
        accurate += 1 if ok else 0
    acc = accurate / max(len(state.draft), 1)
    scores["accuracy"] = _score_from_fraction(acc)
    if acc < 0.8:
        fixes.append("Drop or re-source sentences whose claims do not "
                     "match their quoted evidence.")

    # Completeness: every evidence item used, and a sentence per section.
    used = {e for s in state.draft for e in s.evidence_ids}
    comp = len(used) / max(len(state.evidence), 1)
    sections = len(state.plan.sections) if state.plan else 0
    if sections and len(state.draft) < sections:
        comp = min(comp, len(state.draft) / sections)
    scores["completeness"] = _score_from_fraction(comp)
    if comp < 0.8:
        fixes.append("Cover the unused evidence and every planned section.")

    # Structure: a summary opening, a recommendation close, 5+ sentences.
    has_summary = bool(state.draft) and \
        state.draft[0].text.startswith("Summary:")
    has_rec = bool(state.draft) and \
        "Recommendation:" in state.draft[-1].text
    struct = (has_summary + has_rec + (len(state.draft) >= 5)) / 3
    scores["structure"] = _score_from_fraction(struct)
    if struct < 0.8:
        fixes.append("Add a summary opening and a recommendation close.")

    # Tone: no hype words anywhere in the draft.
    text = " ".join(s.text.lower() for s in state.draft)
    hype = [w for w in HYPE_WORDS if w in text]
    scores["tone"] = 5 if not hype else 2
    if hype:
        fixes.append(f"Remove hype language: {', '.join(hype)}.")

    # Citation coverage: every sentence backed by evidence.
    scores["citation_coverage"] = _score_from_fraction(
        state.citation_coverage)
    if state.citation_coverage < 0.8:
        fixes.append("Add a source to every uncited sentence or drop it.")

    review_obj = Review(scores=scores, fixes=fixes)
    state.reviews.append(review_obj)
    if state.plan:
        for task in state.plan.tasks:
            if task.owner == "reviewer":
                task.done = True
    state.log("reviewer", "review_done",
              f"scores={scores} passed={review_obj.passed}",
              tokens=choice.tokens, money=choice.cost_usd)
    return review_obj


def revise(state: RunState, tools: ToolRunner) -> list[DraftSentence]:
    """One revise pass: apply the reviewer's fixes deterministically."""
    choice = router.route("revise", state.goal, state.budget)
    router.charge(state.budget, choice, seconds=2.0)
    state.model_choices.append({"step": "revise", "model": choice.model,
                                "reason": choice.reason})
    last = state.reviews[-1] if state.reviews else None
    if last is None:
        return state.draft
    draft = list(state.draft)
    # Drop uncited sentences; drop hype sentences.
    kept = []
    for sentence in draft:
        low = sentence.text.lower()
        if not sentence.cited:
            continue
        if any(w in low for w in HYPE_WORDS):
            continue
        kept.append(sentence)
    # Add a sentence for every unused evidence item.
    used = {e for s in kept for e in s.evidence_ids}
    for ev in state.evidence:
        if ev.id not in used:
            kept.append(_sentence_for(ev))
    # Restore structure if it was lost.
    if kept and not kept[0].text.startswith("Summary:"):
        kept[0] = DraftSentence(
            text="Summary: " + kept[0].text, evidence_ids=kept[0].evidence_ids)
    if kept and "Recommendation:" not in kept[-1].text:
        kept.append(_sentence_for(state.evidence[-1],
                                  prefix="Recommendation: act on this evidence — "))
    state.draft = kept
    state.revise_loops += 1
    state.log("writer", "revise_done",
              f"revise loop {state.revise_loops}, {len(kept)} sentences",
              tokens=choice.tokens, money=choice.cost_usd)
    return kept


# ---------------------------------------------------------------------------
# Single-agent baseline (Phase 1 of the blueprint build plan)
# ---------------------------------------------------------------------------

def run_baseline(state: RunState, tools: ToolRunner) -> list[DraftSentence]:
    """One agent does everything end to end: no plan, no analyst, no
    reviewer, no evidence enforcement. Used only to measure the
    multi-agent system against."""
    choice = router.route("baseline", state.goal, state.budget)
    router.charge(state.budget, choice, seconds=3.0)
    found = tools.search(state.goal, limit=6)
    draft: list[DraftSentence] = []
    evidence: list[Evidence] = []
    if found.get("ok"):
        for result in found["results"][:2]:
            fetched = tools.fetch(result["id"])
            if not fetched.get("ok"):
                continue
            for claim, quote in fetched["source"]["passages"][:1]:
                hits = security.scan(claim)
                if hits:
                    continue
                # The baseline saw the source, but its draft never links
                # the claim to it — that is exactly the flaw being measured.
                evidence.append(Evidence(
                    id=f"ev-{len(evidence) + 1:02d}", claim=claim,
                    source_title=fetched["source"]["title"],
                    source_url=fetched["source"]["url"],
                    date=fetched["source"]["date"], quote=quote))
                draft.append(DraftSentence(
                    text=claim if claim.endswith(".") else claim + ".",
                    evidence_ids=[]))
    state.evidence = evidence
    # The baseline also asserts two things it never sourced.
    draft.append(DraftSentence(
        text="This is clearly the best solution on the market today."))
    draft.append(DraftSentence(
        text="Every business should adopt it immediately without hesitation."))
    state.draft = draft
    state.log("baseline", "baseline_done",
              f"{len(draft)} sentences, no review",
              tokens=choice.tokens, money=choice.cost_usd)
    return draft
