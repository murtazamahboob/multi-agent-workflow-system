"""Evidence graph (blueprint Part 3 upgrade).

Every sentence in the output links back to the exact source passage.
The graph is exportable as JSON and as a small self-contained HTML page
(click a sentence, see its sources), so a reader can verify any claim.
"""

from __future__ import annotations

import html
import json

from .state import RunState


def build_graph(state: RunState) -> dict:
    nodes = []
    edges = []
    for ev in state.evidence:
        nodes.append({"id": ev.id, "type": "source", "label": ev.source_title,
                      "url": ev.source_url, "date": ev.date})
    for i, sentence in enumerate(state.draft):
        sid = f"sentence-{i + 1}"
        nodes.append({"id": sid, "type": "sentence",
                      "label": sentence.text})
        for ev_id in sentence.evidence_ids:
            edges.append({"from": sid, "to": ev_id, "type": "backed_by"})
    orphaned = [f"sentence-{i + 1}" for i, s in enumerate(state.draft)
                if not s.cited]
    return {"nodes": nodes, "edges": edges, "orphaned_sentences": orphaned,
            "citation_coverage": round(state.citation_coverage, 3)}


def render_html(state: RunState) -> str:
    graph = build_graph(state)
    rows = []
    for i, sentence in enumerate(state.draft):
        links = []
        for ev_id in sentence.evidence_ids:
            ev = state.evidence_by_id(ev_id)
            if ev is None:
                continue
            links.append(
                f'<a href="{html.escape(ev.source_url)}">'
                f"{html.escape(ev.source_title)} ({ev.date})</a>"
                f"<br><q>{html.escape(ev.quote)}</q>")
        rows.append(
            f"<li>{html.escape(sentence.text)}"
            + (f"<br><small>Sources: {'; '.join(links)}</small>"
               if links else " <b>[NO SOURCE — orphan]</b>")
            + "</li>")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Evidence graph — {html.escape(state.goal)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:800px;margin:2em auto;
padding:0 1em}} q{{color:#555}} li{{margin:0.8em 0}}</style></head>
<body><h1>Evidence graph</h1><p>Goal: {html.escape(state.goal)}</p>
<p>Citation coverage: {graph['citation_coverage']:.0%} — every sentence
links to its source passage; click a source to verify it.</p>
<ol>{''.join(rows)}</ol>
<pre>{html.escape(json.dumps(graph, indent=2))}</pre>
</body></html>
"""
