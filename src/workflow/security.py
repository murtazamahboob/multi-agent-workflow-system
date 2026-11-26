"""Prompt-injection defence (blueprint Block 4).

Fetched text is data, never instructions. Any passage that tries to
issue instructions — ignore previous instructions, reveal the system
prompt, send something somewhere, adopt a new persona — is quarantined:
it never becomes evidence, never reaches the draft, and is logged with
the pattern that caught it.
"""

from __future__ import annotations

import re

_PATTERNS = [
    (r"ignore (all |any )?(previous|prior|above) instructions",
     "ignore-previous-instructions"),
    (r"disregard (all )?(previous|prior|above) instructions",
     "disregard-instructions"),
    (r"reveal (your )?(system prompt|instructions|prompt)",
     "reveal-system-prompt"),
    (r"you are now (an? |a )?\w+", "persona-override"),
    (r"email .* to \S+@\S+", "exfiltration-email"),
    (r"send .* to \S+@\S+", "exfiltration-send"),
    (r"override (your )?(safety|instructions|rules)", "override"),
    (r"do not (tell|mention|reveal).*user", "conceal-from-user"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), name) for p, name in _PATTERNS]


def scan(text: str) -> list[str]:
    """Return the names of every injection pattern found in *text*."""
    return [name for rx, name in _COMPILED if rx.search(text)]


def is_clean(text: str) -> bool:
    return not scan(text)


def quarantine_record(source_id: str, passage: str, hits: list[str]) -> dict:
    return {"source_id": source_id, "pattern": ",".join(hits),
            "passage": passage[:160]}
