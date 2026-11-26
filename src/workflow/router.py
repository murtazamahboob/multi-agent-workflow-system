"""Cost-aware model router (blueprint Part 3 upgrade).

Chooses a cheap or a strong mock model per step by difficulty and by
what the budget still allows. Routine steps go cheap; planning and
review go strong when the task is hard. When money runs low, everything
falls back to cheap — the run degrades instead of dying.
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import Budget

MODELS = {
    "mock-cheap": {"price_per_1k_tokens": 0.0005, "max_difficulty": 2,
                   "label": "cheap (routine steps)"},
    "mock-strong": {"price_per_1k_tokens": 0.004, "max_difficulty": 5,
                    "label": "strong (planning and review)"},
}

# Difficulty per agent step, 1 (routine) to 5 (hard judgement).
STEP_DIFFICULTY = {
    "plan": 4, "research": 2, "analyse": 3, "write": 3, "review": 5,
    "revise": 3, "baseline": 2,
}


def estimate_tokens(text: str) -> int:
    """Deterministic token estimate: ~1.3 tokens per word."""
    words = len(text.split())
    return max(1, int(words * 1.3))


@dataclass
class ModelChoice:
    model: str
    reason: str
    tokens: int
    cost_usd: float


def route(step: str, text: str, budget: Budget) -> ModelChoice:
    difficulty = STEP_DIFFICULTY.get(step, 3)
    tokens = estimate_tokens(text)
    cheap = MODELS["mock-cheap"]
    strong = MODELS["mock-strong"]
    cheap_cost = tokens / 1000 * cheap["price_per_1k_tokens"]
    strong_cost = tokens / 1000 * strong["price_per_1k_tokens"]
    money_left = budget.max_money_usd - budget.money_usd

    if difficulty <= cheap["max_difficulty"] and strong_cost > money_left:
        model, cost, reason = "mock-cheap", cheap_cost, \
            "routine step, cheap model is good enough"
    elif difficulty <= cheap["max_difficulty"]:
        model, cost, reason = "mock-cheap", cheap_cost, \
            "routine step, cheap model is good enough"
    elif strong_cost <= money_left:
        model, cost, reason = "mock-strong", strong_cost, \
            "hard step, strong model within budget"
    else:
        model, cost, reason = "mock-cheap", cheap_cost, \
            "strong model unaffordable, degraded to cheap"
    return ModelChoice(model=model, reason=reason, tokens=tokens,
                       cost_usd=round(cost, 6))


def charge(budget: Budget, choice: ModelChoice, seconds: float = 1.0) -> None:
    budget.charge(choice.tokens, choice.cost_usd, seconds=seconds)
