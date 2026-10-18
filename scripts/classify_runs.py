"""Rebuild artifacts/agent/classification.json from the saved runs (task 7).

Every row carries the corrected citation checks, tool-use counts, the label the
case studies use, and a one-line rationale. Run again after new probe runs.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from nemotron_challenge.agent_runner import check_answer

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "artifacts" / "agent" / "runs"
DB = REPO / "data" / "hermes" / "state.db"

LABELS = {
    "scan-check-1": ("success", "The vision check ran end to end and returned mismatch on the word the extraction inserted."),
    "success-3": ("success", "Full funnel: found the right pair, reported distinctive terms, cited entry and Wikipedia revision."),
    "success-4": ("success", "Cited both sources with token counts; every cited id appears in tool output."),
    "failure-1": ("success", "Clean refusal on an absent topic; cited ids verified against tool output."),
    "failure-2": ("success", "Clean refusal for a fabricated entry id; no fabrication."),
    "scan-check-2": ("failure", "Unmet task: the tools expose no text for unmatched entries, and the agent did not use challenge_scan_check on the page id it had; no fabrication, but the goal was not met."),
    "probe-1": ("success", "The quoted sentence is verbatim in the stored article; revision id correct."),
    "probe-2": ("success", "Declined to invent a rerank logit; reported the metric that exists."),
    "probe-3": ("success", "Correctly rejected the premise, quoted both texts verbatim, listed the real term frequencies."),
    "success-2": ("success", "Candidates for the premise do not exist; the agent searched, then refused honestly."),
    "success-1": ("failure", "108 tool calls chasing an unsatisfiable premise; two challenge_scan_check calls with unusable quotes."),
    "failure-3": ("failure", "Three challenge_scan_check calls with malformed page ids ('page-0452'); repeated tool misuse."),
}


def main() -> None:
    connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row

    def messages(session_id: str) -> dict:
        rows = connection.execute(
            "select role, content, tool_name from messages where session_id = ? order by id",
            (session_id,),
        ).fetchall()
        return {"messages": [dict(row) for row in rows]}

    rows = []
    for case_dir in sorted(path for path in RUNS.iterdir() if path.is_dir()):
        session_path = case_dir / "session.json"
        answer_path = case_dir / "answer.txt"
        if not session_path.exists() or not answer_path.exists():
            continue
        session = json.loads(session_path.read_text(encoding="utf-8"))
        answer = answer_path.read_text(encoding="utf-8")
        session_id = session.get("id")
        checks = check_answer(answer, messages(session_id) if session_id else None)
        tool_rows = messages(session_id)["messages"] if session_id else []
        not_found = sum(1 for row in tool_rows
                        if row["role"] == "tool" and '"status": "not_found"' in str(row["content"]))
        tool_errors = sum(1 for row in tool_rows
                          if row["role"] == "tool" and str(row["content"]).startswith('{"error"'))
        label, rationale = LABELS.get(case_dir.name, ("review", "Not classified yet."))
        rows.append({
            "case_id": case_dir.name,
            "label": label,
            "rationale": rationale,
            "has_citation": checks["has_citation"],
            "has_entry_citation": checks["has_entry_citation"],
            "has_wiki_citation": checks["has_wiki_citation"],
            "unsupported_ids": checks["unsupported_ids"],
            "not_found_calls": not_found,
            "tool_errors": tool_errors,
            "tool_messages": sum(1 for row in tool_rows if row["role"] == "tool"),
            "session_id": session_id,
        })
    target = REPO / "artifacts" / "agent" / "classification.json"
    target.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {target} with {len(rows)} rows")
    for row in rows:
        print(f"  {row['case_id']:14s} {row['label']:8s} cite={row['has_citation']} not_found={row['not_found_calls']} tool_calls={row['tool_messages']}")


if __name__ == "__main__":
    main()
