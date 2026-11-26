"""Run the bundled demo: a market report on AI voice agents for
restaurants, produced by the five-agent workflow. Writes
outputs/report.md, outputs/report.json and outputs/evidence-graph.html.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workflow.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["demo", "--output-dir",
                           str(Path(__file__).resolve().parents[1] / "outputs")]))
