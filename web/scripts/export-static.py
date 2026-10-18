"""Export the pipeline artifacts as static JSON for the web app (VITE_API_MODE=static).

Uses the backend's own WebAdapter and recorded-run loader, so every file has the
same shape as the live API. No model is called. The files follow the format in
web/API.md, "Static mode":

    topics.json, meta.json, cases.json, chat-recorded.json,
    compare/index.json (entry_id -> file), compare/<file>.json

Run from the repository root:
    uv run python web/scripts/export-static.py --commit df45ca8 --out web/static-data
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from nemotron_challenge.agent_runner import recorded_run
from nemotron_challenge.config import MATCH_LOGIT_THRESHOLD
from nemotron_challenge.web_adapter import WebAdapter

READS = ["artifacts/extract", "artifacts/match", "artifacts/compare", "artifacts/claims", "artifacts/agent"]


def export_name(entry_id: str) -> str:
    """Every character outside [A-Za-z0-9_-] becomes "_" (# breaks a URL)."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", entry_id) + ".json"


def write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True, help="The commit whose artifacts to export")
    parser.add_argument("--out", type=Path, default=Path("web/static-data"))
    args = parser.parse_args()

    # The working tree must hold exactly the artifacts of that commit.
    changed = subprocess.run(["git", "diff", "--quiet", args.commit, "--", *READS]).returncode
    if changed:
        raise SystemExit(f"artifacts/ differs from {args.commit}. Check out that commit's artifacts first.")
    commit = subprocess.check_output(["git", "rev-parse", args.commit], text=True).strip()

    adapter = WebAdapter(Path("artifacts"))
    out: Path = args.out
    if out.exists():
        for old in sorted(out.rglob("*"), reverse=True):
            old.unlink() if old.is_file() else old.rmdir()

    # Topics, with the entry_id each slug belongs to (the adapter builds slugs in entry order).
    topics = adapter.topics()
    used: set[str] = set()
    slug_to_entry = {}
    for entry in adapter.entries():
        _, slug = adapter._label_and_slug(entry, used)
        slug_to_entry[slug] = entry
    for topic in topics["topics"]:
        topic["entryId"] = slug_to_entry[topic["slug"]]["entry_id"]
    write(out / "topics.json", topics)

    meta = adapter.meta()
    meta["matchLogitThreshold"] = MATCH_LOGIT_THRESHOLD
    write(out / "meta.json", meta)
    write(out / "cases.json", adapter.cases())

    # One comparison per entry. Static hosts cannot call /api/scans, so the scan's
    # Parse blocks travel inside the comparison and the image path is relative.
    index = {}
    for topic in topics["topics"]:
        entry = slug_to_entry[topic["slug"]]
        compare = adapter.compare(topic["slug"])
        if compare is None:
            continue
        compare["topic"]["entryId"] = entry["entry_id"]
        filename = entry.get("filename") or ""
        blocks = adapter.page_blocks(filename) if filename else None
        compare["britannica"]["blocks"] = (blocks or {}).get("blocks", [])
        compare["britannica"]["pageHeader"] = (blocks or {}).get("pageHeader") or entry.get("page_header")
        compare["britannica"]["entryId"] = entry["entry_id"]
        compare["britannica"]["scanSha256"] = entry.get("scan_sha256")
        compare["britannica"]["imageUrl"] = f"scans/{filename}" if filename else None
        name = export_name(entry["entry_id"])
        write(out / "compare" / name, compare)
        index[entry["entry_id"]] = name
    write(out / "compare" / "index.json", index)

    # Recorded agent runs, one per case, read from artifacts/agent/runs/<case_id>.
    runs = []
    cases_path = Path("artifacts/agent/cases.json")
    for case in json.loads(cases_path.read_text(encoding="utf-8")) if cases_path.exists() else []:
        run = recorded_run(Path("artifacts"), case.get("question", ""))
        if run and Path(run["runDir"]).name == case.get("case_id"):
            runs.append({"question": case["question"], **{k: run[k] for k in ("answer", "citations", "grounding", "trace", "runDir")}})
    write(out / "chat-recorded.json", {"runs": runs})

    write(out / "SOURCE.json", {
        "commit": commit,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script": "web/scripts/export-static.py",
        "entries": len(index),
        "recordedRuns": len(runs),
    })
    print(f"exported {len(index)} comparisons and {len(runs)} recorded runs from {commit[:7]} to {out}")


if __name__ == "__main__":
    main()
