"""Assemble the evaluation report from the saved stage artifacts."""
from __future__ import annotations

from importlib.resources import files
import json
from pathlib import Path
import subprocess
from typing import Any

from .config import (EMBED_MODEL, EMBED_REVISION, PARSE_MODEL, RERANK_MODEL,
                     RERANK_REVISION, SUPER_MODEL, WIKIPEDIA_REVISION, Settings)
from .data import DATASET, REVISION
from .pipeline import read_jsonl, write_json

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_BUILD_STATE = "not run: frontend build out of scope for this session"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _git_state() -> dict[str, Any]:
    """Record the code revision and the dirty flag with read-only git commands."""
    root = REPO_ROOT if (REPO_ROOT / ".git").exists() else Path.cwd()

    def run(*arguments: str) -> str | None:
        try:
            done = subprocess.run(["git", *arguments], cwd=root, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        return done.stdout.strip() if done.returncode == 0 else None

    status = run("status", "--porcelain")
    return {"revision": run("rev-parse", "HEAD"), "dirty": None if status is None else bool(status)}


def _manifest_checksum() -> str | None:
    try:
        resource = files("nemotron_challenge").joinpath("resources/britannica-manifest.json")
        return json.loads(resource.read_text(encoding="utf-8")).get("manifest_sha256")
    except (OSError, ValueError):
        return None


def _line_count(path: Path) -> int | None:
    if not path.exists():
        return None
    return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])


def _yes_no(value: bool | None) -> str:
    return "not recorded" if value is None else ("yes" if value else "no")


def run_evaluate(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Write artifacts/evaluate/report.json and docs/evaluation.md."""
    work_dir = Path(work_dir)
    extract = _read(work_dir / "extract" / "coverage.json")
    segment = _read(work_dir / "extract" / "segment-summary.json")
    match = _read(work_dir / "match" / "summary.json")
    compare = _read(work_dir / "compare" / "summary.json")
    claims_summary = _read(work_dir / "claims" / "summary.json")
    lancedb = _read(work_dir / "lancedb-summary.json")
    pytest_result = _read(work_dir / "evaluate" / "pytest.json")
    agent = _read(work_dir / "agent" / "report.json")
    matches = read_jsonl(work_dir / "match" / "matches.jsonl")

    git_state = _git_state()
    claims_failures_path = work_dir / "claims" / "failures.jsonl"
    extract_failures_path = work_dir / "extract" / "coverage.json"
    extract_failure_dir = work_dir / "extract" / "failures"
    extract_detail_files = (sorted(path.name for path in extract_failure_dir.iterdir())
                            if extract_failure_dir.is_dir() else [])

    matches_total = claims_summary.get("matches_total")
    entries_done = claims_summary.get("entries_done")
    claims_note = (f"claims for {entries_done} of {matches_total} matches"
                   if matches_total is not None and entries_done is not None else "claims not recorded")

    report = {
        "stage": "evaluate",
        "provenance": {
            "code_revision": git_state["revision"],
            "code_dirty": git_state["dirty"],
            "models": [
                {"id": PARSE_MODEL, "revision": None, "role": "Segmentation (Parse 3.5)"},
                {"id": EMBED_MODEL, "revision": EMBED_REVISION, "role": "Embedding"},
                {"id": RERANK_MODEL, "revision": RERANK_REVISION, "role": "Reranking"},
                {"id": SUPER_MODEL, "revision": None, "role": "Claims and agent answers (Super VL)"},
            ],
            "britannica_dataset": DATASET,
            "britannica_revision": REVISION,
            "britannica_manifest_sha256": _manifest_checksum(),
            "wikipedia_revision": WIKIPEDIA_REVISION,
        },
        "coverage": {
            "pages_total": extract.get("pages_total"),
            "pages_ok": extract.get("pages_ok"),
            "pages_failed": extract.get("pages_failed"),
            "pages_with_entries": segment.get("pages_with_entries"),
            "pages_without_entries": segment.get("pages_without_entries", []),
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
        "claims": {
            "note": claims_note,
            "matches_total": matches_total,
            "entries_done": entries_done,
            "entries_failed": claims_summary.get("entries_failed"),
            "claims_total": claims_summary.get("claims_total"),
            "claims_downgraded": claims_summary.get("claims_downgraded"),
            "verdict_counts": claims_summary.get("verdict_counts"),
            "path": str(work_dir / "claims" / "summary.json"),
        },
        "comparison": {
            "pairs": compare.get("pairs"),
            "top_britannica": compare.get("top_britannica", []),
            "top_wikipedia": compare.get("top_wikipedia", []),
        },
        "agent": {"cases": agent.get("cases", []), "passed": agent.get("passed"), "total": agent.get("total")},
        "failed_calls": {
            "extract": {
                "count": len(extract.get("failures", [])),
                "path": str(extract_failures_path),
                "pages": [row.get("page_id") for row in extract.get("failures", [])],
                "detail_dir": str(extract_failure_dir),
                "detail_files": extract_detail_files,
            },
            "match": {"count": len(match.get("failures", [])), "path": str(work_dir / "match" / "summary.json")},
            "claims": {"count": _line_count(claims_failures_path), "path": str(claims_failures_path)},
        },
        "lancedb": {"path": str(work_dir / "lancedb-summary.json"), "tables": lancedb.get("tables")},
        "checks": {
            "pytest": {
                "command": pytest_result.get("command") or "uv run pytest -q",
                "date": pytest_result.get("date"),
                "summary": pytest_result.get("summary"),
            },
            "frontend_build": FRONTEND_BUILD_STATE,
        },
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
    provenance = report["provenance"]
    coverage = report["coverage"]
    lines = [
        "# Evaluation report",
        "",
        "Generated from the saved stage artifacts. Do not edit by hand; rerun the evaluate stage.",
        "",
        "## Provenance",
        "",
        f"- Code revision: {provenance['code_revision'] or 'not recorded (git unavailable)'}.",
        f"- Dirty worktree flag: {_yes_no(provenance['code_dirty'])}.",
    ]
    for model in provenance["models"]:
        lines.append(f"- {model['role']}: {model['id']} (revision {model['revision'] or 'not recorded in config'}).")
    lines += [
        f"- Britannica dataset: {provenance['britannica_dataset']} (revision {provenance['britannica_revision']}).",
        f"- Britannica manifest checksum: {provenance['britannica_manifest_sha256'] or 'not recorded'}.",
        f"- Wikipedia revision: {provenance['wikipedia_revision']}.",
        "",
        "## Coverage",
        "",
        f"- Pages processed: {coverage['pages_ok']} of {coverage['pages_total']} (failed: {coverage['pages_failed']}).",
        f"- Entries: {coverage['entries']}. Continuation joins: {coverage['joins']}.",
        f"- Pages with entries: {coverage['pages_with_entries']}.",
    ]
    without = coverage["pages_without_entries"] or []
    if without:
        lines.append(f"- Pages without entries: {len(without)} ({', '.join(str(item) for item in without)}).")
    else:
        lines.append("- Pages without entries: none.")
    lines += [
        "",
        "## Matching",
        "",
        f"- Entries processed: {report['matching']['entries_processed']}. Matched: {report['matching']['matched']}. Unmatched: {report['matching']['unmatched']}.",
        f"- Unique articles: {report['matching']['unique_articles']}. Repeated selections: {len(report['matching']['repeats'])}.",
        "",
        "## Claims",
        "",
        f"- Match coverage: {report['claims']['note']}.",
        f"- Claims total: {report['claims']['claims_total']}. Downgraded: {report['claims']['claims_downgraded']}.",
    ]
    verdicts = report["claims"]["verdict_counts"] or {}
    if verdicts:
        lines.append("- Verdicts: " + ", ".join(f"{name} {count}" for name, count in verdicts.items()) + ".")
    lines += [
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
    extract_call = report["failed_calls"]["extract"]
    match_call = report["failed_calls"]["match"]
    claims_call = report["failed_calls"]["claims"]
    lines += [
        "",
        "## Failed model calls",
        "",
        f"- Extract: {extract_call['count']} failed pages. Source: {extract_call['path']}. Raw failure details: {extract_call['detail_dir']}.",
        f"- Match: {match_call['count']} failed entries. Source: {match_call['path']}.",
        f"- Claims: {claims_call['count']} failed model calls. Source: {claims_call['path']} (line count).",
        "",
        "## LanceDB rows",
        "",
    ]
    tables = report["lancedb"]["tables"] or {}
    if tables:
        lines.append("- Rows: " + ", ".join(f"{name} {count}" for name, count in tables.items()) + ".")
    else:
        lines.append("- Rows: not recorded (artifacts/lancedb-summary.json missing).")
    pytest_info = report["checks"]["pytest"]
    lines += ["", "## Checks", ""]
    if pytest_info["summary"]:
        lines.append(f"- Pytest: {pytest_info['summary']} on {pytest_info['date']} (command: {pytest_info['command']}).")
    else:
        lines.append("- Pytest: not recorded. Run uv run pytest -q and save artifacts/evaluate/pytest.json.")
    lines += [
        f"- Frontend build (npm run build): {report['checks']['frontend_build']}.",
        "",
        "## Limits",
        "",
    ]
    lines += [f"- {item}" for item in report["limits"]]
    lines.append("")
    (docs / "evaluation.md").write_text("\n".join(lines), encoding="utf-8")
    return {"stage": "evaluate", "report": str(evaluate_dir / "report.json"),
            "marked_down": str(docs / "evaluation.md"),
            "code_revision": report["provenance"]["code_revision"],
            "code_dirty": report["provenance"]["code_dirty"],
            "coverage": report["coverage"]["pages_ok"], "matched": report["matching"]["matched"],
            "pairs": report["comparison"]["pairs"], "claims": report["claims"]["note"],
            "agent_cases": report["agent"]["total"]}
