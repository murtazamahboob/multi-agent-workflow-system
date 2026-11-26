"""Skill library (blueprint Part 3 upgrade).

Reusable recipes the Planner picks from by goal keywords, so one system
becomes many sellable services. Each skill defines the plan template,
the report sections and what the Reviewer should weight most.
"""

from __future__ import annotations

SKILLS = {
    "market-report": {
        "keywords": {"market", "adoption", "report", "industry", "trend"},
        "sections": ["Summary", "Market size and adoption", "What users think",
                     "Pricing", "Risks", "Recommendation"],
        "plan_titles": ["Define scope and questions", "Research adoption data",
                        "Research user attitudes", "Research pricing",
                        "Analyse numbers", "Draft report", "Review and revise"],
        "review_focus": "accuracy",
    },
    "competitor-teardown": {
        "keywords": {"competitor", "teardown", "compare", "vendor", "versus",
                     "vs"},
        "sections": ["Summary", "Vendors compared", "Feature matrix",
                     "Pricing", "Gaps and risks", "Recommendation"],
        "plan_titles": ["Define comparison criteria", "Research each vendor",
                        "Research features", "Research pricing",
                        "Analyse trade-offs", "Draft teardown",
                        "Review and revise"],
        "review_focus": "completeness",
    },
    "lead-research": {
        "keywords": {"lead", "outreach", "prospect", "contact", "sales"},
        "sections": ["Summary", "What converts", "Timing", "First contact",
                     "Risks", "Recommendation"],
        "plan_titles": ["Define ideal lead", "Research conversion factors",
                        "Research timing", "Research first contact",
                        "Analyse numbers", "Draft report", "Review and revise"],
        "review_focus": "completeness",
    },
    "cost-control": {
        "keywords": {"cost", "token", "budget", "llm", "spend", "saving"},
        "sections": ["Summary", "Where the money goes", "Routing and caching",
                     "Budgets that hold", "Risks", "Recommendation"],
        "plan_titles": ["Define cost question", "Research routing savings",
                        "Research caching", "Research budgets",
                        "Analyse numbers", "Draft report", "Review and revise"],
        "review_focus": "accuracy",
    },
    "risk-assessment": {
        "keywords": {"risk", "wrong", "safety", "compliance", "assessment"},
        "sections": ["Summary", "Failure modes", "How often they happen",
                     "Mitigations", "Risks", "Recommendation"],
        "plan_titles": ["Define risk scope", "Research failure modes",
                        "Research frequencies", "Research mitigations",
                        "Analyse numbers", "Draft report", "Review and revise"],
        "review_focus": "accuracy",
    },
    "generic-report": {
        "keywords": set(),
        "sections": ["Summary", "Findings", "Numbers", "Risks",
                     "Recommendation"],
        "plan_titles": ["Define scope", "Research findings",
                        "Research numbers", "Analyse numbers",
                        "Draft report", "Review and revise"],
        "review_focus": "completeness",
    },
}


def pick_skill(goal: str) -> str:
    """Pick the skill whose keywords overlap the goal most; generic wins
    ties and no-overlap goals."""
    from .knowledge import keywords

    goal_words = keywords(goal)
    best, best_score = "generic-report", 0
    for name, skill in SKILLS.items():
        if name == "generic-report":
            continue
        score = len(goal_words & skill["keywords"])
        if score > best_score:
            best, best_score = name, score
    return best


def skill(name: str) -> dict:
    return SKILLS[name]
