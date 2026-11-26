"""Tools with schemas, timeouts and safe failures (blueprint §4.2).

Every tool has a JSON-style schema, a timeout and a safe failure result.
Agents never run arbitrary shell commands. The Analyst's code runs in a
no-network sandbox: a small AST evaluator for arithmetic only — no
imports, no attribute access, no names other than a fixed math whitelist.
"""

from __future__ import annotations

import ast
import math
import operator

from . import knowledge
from .state import Budget

TOOL_SCHEMAS = {
    "search": {
        "description": "Search the bundled knowledge base by keyword.",
        "parameters": {"query": "string", "limit": "integer (1-6)"},
        "timeout_seconds": 20,
    },
    "fetch": {
        "description": "Fetch one source by id and return its passages.",
        "parameters": {"source_id": "string"},
        "timeout_seconds": 30,
    },
    "sandbox": {
        "description": "Evaluate an arithmetic expression safely. No "
                       "imports, no attribute access, no I/O.",
        "parameters": {"expression": "string"},
        "timeout_seconds": 60,
    },
    "memory_search": {
        "description": "Search long-term memory (past approved reports).",
        "parameters": {"query": "string"},
        "timeout_seconds": 20,
    },
}

# A tiny in-memory long-term store: past approved facts. Seeded
# deterministically; a real deployment uses SQLite + embeddings.
_MEMORY = [
    {"fact": "Voice agents must confirm allergy information before "
             "completing a food order.", "topic": "voice-agents-restaurants"},
    {"fact": "A human handover must complete in under 5 seconds for "
             "restaurant voice agents.", "topic": "voice-agents-restaurants"},
    {"fact": "Cost-aware routing cuts workflow cost by 40% to 70%.",
     "topic": "token-cost-llm"},
]


class ToolRunner:
    """Runs tools against a run budget, counting every call."""

    def __init__(self, budget: Budget):
        self.budget = budget

    def _call(self, name: str) -> dict | None:
        self.budget.tool_calls += 1
        if self.budget.exceeded():
            return {"ok": False, "error": "budget exceeded",
                    "reason": self.budget.exceeded()}
        return None

    def search(self, query: str, limit: int = 6) -> dict:
        failed = self._call("search")
        if failed:
            return failed
        try:
            results = knowledge.search(query, limit=limit)
            return {"ok": True, "results": [
                {"id": r["id"], "title": r["title"], "url": r["url"],
                 "date": r["date"]} for r in results]}
        except Exception as exc:  # safe failure, never crash the run
            return {"ok": False, "error": str(exc)}

    def fetch(self, source_id: str) -> dict:
        failed = self._call("fetch")
        if failed:
            return failed
        src = knowledge.fetch(source_id)
        if src is None:
            return {"ok": False, "error": f"unknown source {source_id}"}
        return {"ok": True, "source": src}

    def memory_search(self, query: str) -> dict:
        failed = self._call("memory_search")
        if failed:
            return failed
        words = knowledge.keywords(query)
        hits = [m for m in _MEMORY
                if words & knowledge.keywords(m["fact"])]
        return {"ok": True, "results": hits}

    def sandbox(self, expression: str) -> dict:
        """Evaluate arithmetic only. Anything else is a safe failure."""
        failed = self._call("sandbox")
        if failed:
            return failed
        try:
            value = _safe_eval(expression)
            return {"ok": True, "value": value}
        except Exception as exc:
            return {"ok": False, "error": f"sandbox rejected: {exc}"}


_ALLOWED_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_ALLOWED_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}
def _round(value: float, digits: float = 0) -> float:
    # _eval_node turns every literal into a float, but round() needs an
    # int for its second argument.
    return float(round(value, int(digits)))


_ALLOWED_FUNCS = {"round": _round, "min": min, "max": max, "abs": abs,
                   "sqrt": math.sqrt, "log": math.log}


def _safe_eval(expression: str) -> float:
    tree = ast.parse(expression, mode="eval")
    return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](
            _eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
        return _ALLOWED_UNARY[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in _ALLOWED_FUNCS and len(node.args) <= 2:
        return float(_ALLOWED_FUNCS[node.func.id](
            *[_eval_node(a) for a in node.args]))
    raise ValueError("only arithmetic and round/min/max/abs/sqrt/log allowed")
