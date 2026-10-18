"""Assemble the evaluation report from the saved stage artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Settings
from .pipeline import read_jsonl, write_json


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def run_evaluate(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Write artifacts/evaluate/report.json and docs/evaluation.md."""
    extract = _read(work_dir / "extract" / "coverage.json")
    match = _read(work_dir / "match" / "summary.json")
    compare = _read(work_dir / "compare" / "summary.json")
    agent = _read(work_dir / "agent" / "report.json")
    matches = read_jsonl(work_dir / "match" / "matches.jsonl")
    report = {
        "stage": "evaluate",
        "coverage": {
            "pages_total": extract.get("pages_total"),
            "pages_ok": extract.get("pages_ok"),
            "pages_failed": extract.get("pages_failed"),
            "entries": extract.get("entries"),
            "joins": extract.get("joins"),
            "failures": extract.get("failures", []),
        },
        "matching": {
            "entries_processed": match.get("entries_processed"),
            "matched": match.get("matched", len(matches)),
            "unmatched": match.get("unmatched"),
            "unique_articles": match.get("unique_articles"),
            "repeats": match.get("repeats", []),
            "threshold": match.get("threshold"),
        },
        "comparison": {
            "pairs": compare.get("pairs"),
            "top_britannica": compare.get("top_britannica", []),
            "top_wikipedia": compare.get("top_wikipedia", []),
        },
        "agent": {"cases": agent.get("cases", []), "passed": agent.get("passed"), "total": agent.get("total")},
        "limits": [
            "The fixed 100-scan manifest defines the source sample; extraction failures stay listed.",
            "Match thresholds are calibrated on samples; unmatched entries are reported, not forced.",
            "OCR errors in the scans and historical spelling are documented, not corrected in place.",
            "Wikipedia text is quoted under CC BY-SA 4.0 with article revisions recorded.",
        ],
    }
    evaluate_dir = work_dir / "evaluate"
    write_json(evaluate_dir / "report.json", report)
    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    lines = [
        "# Evaluation report",
        "",
        "Generated from the saved stage artifacts. Do not edit by hand; rerun the evaluate stage.",
        "",
        "## Coverage",
        "",
        f"- Pages processed: {report['coverage']['pages_ok']} of {report['coverage']['pages_total']} (failed: {report['coverage']['pages_failed']}).",
        f"- Entries: {report['coverage']['entries']}. Continuation joins: {report['coverage']['joins']}.",
        "",
        "## Matching",
        "",
        f"- Entries processed: {report['matching']['entries_processed']}. Matched: {report['matching']['matched']}. Unmatched: {report['matching']['unmatched']}.",
        f"- Unique articles: {report['matching']['unique_articles']}. Repeated selections: {len(report['matching']['repeats'])}.",
        "",
        "## Comparison",
        "",
        f"- Compared pairs: {report['comparison']['pairs']}.",
        "",
        "## Agent cases",
        "",
    ]
    for case in report["agent"]["cases"]:
        lines.append(f"- {case['case_id']}: expected {case['expected']}, passed={case['passed']} (citation={case['has_citation']}, admits_missing={case['admits_missing']}).")
    if not report["agent"]["cases"]:
        lines.append("- No agent cases recorded yet.")
    lines += ["", "## Limits", ""]
    lines += [f"- {item}" for item in report["limits"]]
    lines.append("")
    (docs / "evaluation.md").write_text("\n".join(lines), encoding="utf-8")
    return {"stage": "evaluate", "report": str(evaluate_dir / "report.json"),
            "marked_down": str(docs / "evaluation.md"),
            "coverage": report["coverage"]["pages_ok"], "matched": report["matching"]["matched"],
            "pairs": report["comparison"]["pairs"], "agent_cases": report["agent"]["total"]}
