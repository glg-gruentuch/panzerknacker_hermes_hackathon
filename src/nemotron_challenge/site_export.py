"""Static export for the React app in static mode (handoff 2, B10).

Writes the same shapes as the FastAPI routes into ``deliverables/website/app/data``
so a static host can serve the UI without a backend. The route logic lives in
:class:`~nemotron_challenge.web_adapter.WebAdapter`; this module only calls it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_runner import extract_citations, grounding_of
from .config import Settings
from .pipeline import write_json
from .web_adapter import WebAdapter

DEFAULT_OUT_DIR = Path("deliverables/website/app/data")
NAME_SANITIZER = re.compile(r"[^A-Za-z0-9_-]")


def entry_filename(entry_id: str) -> str:
    """The B10 file name rule: characters outside [A-Za-z0-9_-] become ``_``."""
    return NAME_SANITIZER.sub("_", entry_id) + ".json"


def recorded_chat_runs(work_dir: Path) -> list[dict[str, Any]]:
    """Every saved agent run as a POST /api/chat reply, with its run directory."""
    runs_dir = Path(work_dir) / "agent" / "runs"
    rows: list[dict[str, Any]] = []
    if not runs_dir.is_dir():
        return rows
    for case_dir in sorted(path for path in runs_dir.iterdir() if path.is_dir()):
        command_path = case_dir / "command.json"
        answer_path = case_dir / "answer.txt"
        if not command_path.exists() or not answer_path.exists():
            continue
        try:
            command = json.loads(command_path.read_text(encoding="utf-8"))
        except ValueError:
            command = {}
        answer = answer_path.read_text(encoding="utf-8").strip()
        if not answer:
            continue
        citations = extract_citations(answer)
        trace: list[dict[str, Any]] = []
        trace_path = case_dir / "trace.json"
        if trace_path.exists():
            try:
                trace = json.loads(trace_path.read_text(encoding="utf-8")).get("steps", [])
            except ValueError:
                trace = []
        rows.append({
            "question": command.get("question", ""),
            "answer": answer,
            "citations": citations,
            "grounding": grounding_of(answer, citations),
            "trace": trace,
            "recorded": True,
            "caseId": case_dir.name,
            "runDir": str(case_dir),
        })
    return rows


def run_export(settings: Settings, work_dir: Path, out_dir: Path | None = None) -> dict[str, Any]:
    """Write the static app data files. No model call happens here."""
    work_dir = Path(work_dir)
    out = Path(out_dir) if out_dir is not None else DEFAULT_OUT_DIR
    adapter = WebAdapter(work_dir, db_path=settings.db_path)
    compare_dir = out / "compare"
    compare_dir.mkdir(parents=True, exist_ok=True)
    write_json(out / "topics.json", adapter.topics())
    write_json(out / "meta.json", adapter.meta())
    write_json(out / "cases.json", adapter.cases())
    index: dict[str, str] = {}
    for entry in adapter.entries():
        entry_id = entry.get("entry_id") or ""
        if not entry_id:
            continue
        payload = adapter.compare(entry_id)
        if payload is None:
            payload = {"query": entry_id, "topic": None,
                       "pending": ["no comparison payload; the entry index changed since the export"]}
        name = entry_filename(entry_id)
        write_json(compare_dir / name, payload)
        index[entry_id] = name
    write_json(compare_dir / "index.json", index)
    chat_rows = recorded_chat_runs(work_dir)
    write_json(out / "chat-recorded.json", chat_rows)
    return {
        "stage": "export",
        "out_dir": str(out),
        "entries": len(index),
        "chat_runs": len(chat_rows),
        "artifacts": str(out),
    }
