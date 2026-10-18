"""Run scripted Hermes comparison cases and record the evidence."""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from .config import ConfigurationError, Settings
from .pipeline import write_json

HERMES_BIN_ENV = "HERMES_BIN"
REPO = Path(__file__).resolve().parents[2]
CASE_TIMEOUT = 600
CITATION = re.compile(r"britannica:[0-9a-f]{40}:train:\d+")
ENTRY_CITATION = re.compile(r"\[(britannica:[0-9a-f]{40}:train:\d+#[0-9]{4})\]")
WIKI_CITATION = re.compile(r"\[(https?://en\.wikipedia\.org/[^\]\s]+)\]")
WIKI_REVISION = re.compile(r"\brevision(?:\s*[_ ]?id)?\s*[:#=]?\s*(\d{4,})", re.IGNORECASE)
PASSAGE_CITATION = re.compile(r"\[([BW][0-9]{1,3})\]")
SESSION_DB = REPO / "data" / "hermes" / "state.db"


def hermes_bin() -> Path:
    """Find the Hermes binary (B5): HERMES_BIN, then PATH, then a clear error.

    HERMES_BIN is read from the environment first and from the repository .env
    second, so a checkout works without a code edit. See docs/hermes.md.
    """
    override = (os.environ.get(HERMES_BIN_ENV) or dotenv_values(REPO / ".env").get(HERMES_BIN_ENV) or "").strip()
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return path
        raise ConfigurationError(f"HERMES_BIN points at a missing file: {path}")
    found = shutil.which("hermes")
    if found:
        return Path(found)
    raise ConfigurationError(
        "Hermes binary not found: set HERMES_BIN or put hermes on PATH (see docs/hermes.md)"
    )


def hermes_env() -> dict[str, str]:
    """Environment for the challenge profile: HERMES_HOME, the artifacts path, and the key."""
    env = os.environ.copy()
    env["HERMES_HOME"] = str(REPO / "data" / "hermes")
    env["PANZERKNACKER_ARTIFACTS"] = str(REPO / "artifacts")
    super_key = dotenv_values(REPO / ".env").get("SUPER_API_KEY")
    if super_key:
        env["SUPER_API_KEY"] = super_key
    return env


def run_chat(question: str, *, timeout: int = CASE_TIMEOUT) -> subprocess.CompletedProcess:
    """Run one question through the challenge Hermes profile.

    Shared by the scripted case runner and the web API. Do not copy this call.
    """
    command = [str(hermes_bin()), "chat", "-q", question, "--toolsets", "nemotron_challenge"]
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=hermes_env(), cwd=REPO)


def _session_messages(session_id: str) -> list[dict[str, Any]]:
    """Messages of one challenge-profile session, oldest first."""
    connection = sqlite3.connect(f"file:{SESSION_DB}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "select id, role, content, tool_name, tool_calls, timestamp from messages "
            "where session_id = ? order by id",
            (session_id,),
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def newest_session_since(started_after: float) -> dict[str, Any] | None:
    """The newest challenge session that started after the given epoch time."""
    if not SESSION_DB.exists():
        return None
    connection = sqlite3.connect(f"file:{SESSION_DB}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "select id, started_at, ended_at, model, message_count, tool_call_count, "
            "input_tokens, output_tokens from sessions order by started_at desc limit 1"
        ).fetchone()
    finally:
        connection.close()
    if row is None or float(row["started_at"] or 0) < started_after - 30:
        return None
    session = dict(row)
    session["messages"] = _session_messages(session["id"])
    return session


def session_tool_steps(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Tool trace steps read from a session, with per-step durations."""
    steps: list[dict[str, Any]] = []
    pending: dict[str, float] = {}
    for message in session.get("messages", []):
        if message["role"] == "assistant" and message.get("tool_calls"):
            try:
                calls = json.loads(message["tool_calls"])
            except (TypeError, ValueError):
                continue
            for call in calls:
                function = call.get("function", {}) if isinstance(call, dict) else {}
                name = function.get("name") or "tool_call"
                arguments = function.get("arguments") or ""
                pending[name] = float(message.get("timestamp") or 0)
                steps.append({"step": f"Tool call: {name}", "model": "Hermes Agent tools",
                              "detail": str(arguments)[:160], "ms": None})
        elif message["role"] == "tool" and message.get("tool_name"):
            started = pending.get(message["tool_name"])
            finished = float(message.get("timestamp") or 0)
            for step in reversed(steps):
                if step["step"] == f"Tool call: {message['tool_name']}" and step["ms"] is None:
                    step["ms"] = int(max(finished - started, 0) * 1000) if started else None
                    step["detail"] = f"{str(message.get('content') or '')[:140]}"
                    break
    return steps


def session_answer(session: dict[str, Any]) -> str:
    """The last non-empty assistant text of a session."""
    for message in reversed(session.get("messages", [])):
        if message["role"] == "assistant" and not message.get("tool_calls"):
            text = (message.get("content") or "").strip()
            if text:
                return text
    return ""


def extract_citations(answer: str, topic: str = "", adapter: Any = None) -> list[dict[str, Any]]:
    """Citations used in an answer, mapped to passage ids when possible."""
    citations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    match_index: dict[str, dict[str, Any]] = {}
    if adapter is not None:
        match_index = {row["entry_id"]: row for row in adapter.matches().values()}

    def add(source: str, passage_id: str, rerank: float | None = None) -> None:
        key = (source, passage_id)
        if key in seen:
            return
        seen.add(key)
        citations.append({"id": passage_id, "source": source, "passageId": passage_id, "rerankScore": rerank})

    for entry_id in ENTRY_CITATION.findall(answer):
        row = match_index.get(entry_id)
        add("britannica", entry_id, row.get("match_confidence") if row else None)
    for url in WIKI_CITATION.findall(answer):
        add("wikipedia", url)
    for passage_id in PASSAGE_CITATION.findall(answer):
        source = "britannica" if passage_id.startswith("B") else "wikipedia"
        add(source, passage_id)
    return citations


def grounding_of(answer: str, citations: list[dict[str, Any]]) -> str:
    """supported / partial / unsupported from the answer and its citations."""
    lowered = answer.lower()
    admits_missing = "insufficient" in lowered or "no stored comparison" in lowered or "unmatched" in lowered
    if not answer.strip():
        return "unsupported"
    if admits_missing:
        return "partial" if citations else "unsupported"
    return "supported" if citations else "partial"


def ask_agent(question: str, *, topic: str = "", adapter: Any = None, timeout: int = CASE_TIMEOUT) -> dict[str, Any]:
    """Answer one question through the challenge profile.

    Returns the answer and the tool trace. When Hermes fails, returns the
    closest recorded run with ``recorded: true`` instead. This function never
    raises for a failed run; it reports the failure in ``error``.
    """
    started = time.time()
    error = ""
    try:
        result = run_chat(question, timeout=timeout)
        session = newest_session_since(started)
        answer = session_answer(session) if session else ""
        if result.returncode != 0 or not answer:
            error = f"hermes exited with {result.returncode}"
        if answer:
            citations = extract_citations(answer, topic=topic, adapter=adapter)
            steps = session_tool_steps(session) if session else []
            total_ms = int(((session.get("ended_at") or time.time()) - (session.get("started_at") or started)) * 1000) \
                if session else int((time.time() - started) * 1000)
            steps.append({"step": "Write answer", "model": "Hermes Agent · nvidia/Nemotron-3.5-Super-VL",
                          "detail": f"{len([s for s in steps if s['step'].startswith('Tool call')])} tool calls",
                          "ms": total_ms})
            return {"answer": answer, "citations": citations, "grounding": grounding_of(answer, citations),
                    "trace": steps, "recorded": False}
    except (OSError, subprocess.SubprocessError, ConfigurationError, sqlite3.Error) as exc:
        error = f"{type(exc).__name__}: {exc}"
    recorded = recorded_run(adapter.work_dir if adapter is not None else REPO / "artifacts", question)
    if recorded is not None:
        recorded["error"] = error
        return recorded
    return {"answer": "", "citations": [], "grounding": "unsupported",
            "trace": [{"step": "Agent run failed", "model": "Hermes Agent", "detail": error, "ms": None}],
            "recorded": False, "error": error}


def recorded_run(work_dir: Path, question: str) -> dict[str, Any] | None:
    """The closest saved agent run for a question, as a chat response."""
    runs_dir = Path(work_dir) / "agent" / "runs"
    if not runs_dir.is_dir():
        return None
    wanted = {word for word in re.findall(r"[a-z]{3,}", question.lower())}
    best: tuple[float, Path] | None = None
    for case_dir in sorted(path for path in runs_dir.iterdir() if path.is_dir()):
        command_path = case_dir / "command.json"
        if not command_path.exists():
            continue
        try:
            command = json.loads(command_path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        saved = {word for word in re.findall(r"[a-z]{3,}", str(command.get("question", "")).lower())}
        overlap = len(wanted & saved) / max(len(wanted | saved), 1)
        if best is None or overlap > best[0]:
            best = (overlap, case_dir)
    if best is None or best[0] <= 0:
        return None
    case_dir = best[1]
    answer_path = case_dir / "answer.txt"
    answer = answer_path.read_text(encoding="utf-8").strip() if answer_path.exists() else ""
    if not answer:
        stdout_path = case_dir / "stdout.txt"
        answer = _answer_from_stdout(stdout_path.read_text(encoding="utf-8")) if stdout_path.exists() else ""
    if not answer:
        return None
    citations = extract_citations(answer)
    trace = []
    trace_path = case_dir / "trace.json"
    if trace_path.exists():
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8")).get("steps", [])
        except ValueError:
            trace = []
    return {"answer": answer, "citations": citations, "grounding": grounding_of(answer, citations),
            "trace": trace or [{"step": "Recorded run", "model": "Hermes Agent",
                                "detail": str(case_dir), "ms": None}],
            "recorded": True, "runDir": str(case_dir)}


def _answer_from_stdout(stdout: str) -> str:
    """Best-effort answer text from captured chat output, with the chrome removed."""
    text = stdout.replace("\r", "")
    lines = []
    for line in text.splitlines():
        if line.startswith("Warning:") or line.startswith("Query:") or line.startswith("Initializing"):
            continue
        if set(line.strip()) <= {"─", "┌", "┐", "└", "┘", "│", " "} and line.strip():
            continue
        lines.append(line)
    joined = "\n".join(lines).strip()
    if "────" in joined:
        joined = joined.rsplit("────", 1)[-1].strip()
    return joined


def load_cases(work_dir: Path) -> list[dict[str, Any]]:
    """Read the scripted cases. See plan W4.5 for the file format."""
    path = work_dir / "agent" / "cases.json"
    if not path.exists():
        raise ValueError(f"write the case list first: {path}")
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("the case list must contain at least one case")
    return cases


def check_answer(text: str, session: dict[str, Any] | None = None) -> dict[str, Any]:
    """Check one reply against the strict citation rules (B5).

    A reply passes as a citation only if it cites a Britannica entry or page ID,
    cites a Wikipedia revision ID or article URL, and every cited ID appears in
    a tool result of the session. Without a session the check falls back to
    presence only and reports ``citations_verified`` false.
    """
    lowered = text.lower()
    entry_ids = set(ENTRY_CITATION.findall(text))
    page_ids = set(CITATION.findall(text)) - {entry.split("#")[0] for entry in entry_ids}
    britannica_ids = sorted(entry_ids | page_ids)
    wiki_urls = sorted(set(WIKI_CITATION.findall(text)))
    wiki_revisions = sorted(set(WIKI_REVISION.findall(text)))
    cited_ids = [*britannica_ids, *wiki_urls, *wiki_revisions]
    tool_text = ""
    if session is not None:
        tool_text = "\n".join(
            str(message.get("content") or "")
            for message in session.get("messages", [])
            if message.get("role") == "tool"
        )
    unsupported_ids = [cited for cited in cited_ids if session is not None and cited not in tool_text]
    has_entry = bool(britannica_ids)
    has_wiki = bool(wiki_urls or wiki_revisions)
    return {
        "has_citation": bool(has_entry and has_wiki and (session is None or not unsupported_ids)),
        "has_entry_citation": has_entry,
        "has_wiki_citation": has_wiki,
        "citations_verified": session is not None,
        "cited_ids": cited_ids,
        "unsupported_ids": unsupported_ids,
        "admits_missing": "insufficient" in lowered or "unmatched" in lowered or "no stored comparison" in lowered,
    }


def run_case(case: dict[str, Any], runs_dir: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Run one question through the Hermes profile and save all evidence."""
    case_dir = runs_dir / case["case_id"]
    case_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    result = run_chat(case["question"], timeout=CASE_TIMEOUT)
    write_json(case_dir / "command.json", {"command": [str(hermes_bin()), "chat", "-q", case["question"],
                                                        "--toolsets", "nemotron_challenge"],
                                           "returncode": result.returncode,
                                           "question": case["question"], "expected": case.get("expected", "")})
    (case_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (case_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    session = None
    try:
        session = newest_session_since(started)
    except sqlite3.Error:
        session = None
    answer = ""
    if session is not None:
        answer = session_answer(session)
        write_json(case_dir / "trace.json", {"session_id": session["id"], "model": session.get("model"),
                                             "steps": session_tool_steps(session)})
        write_json(case_dir / "session.json", {key: session.get(key) for key in
                                               ("id", "started_at", "ended_at", "message_count",
                                                "tool_call_count", "input_tokens", "output_tokens")})
        if answer:
            (case_dir / "answer.txt").write_text(answer, encoding="utf-8")
    sessions = REPO / "data" / "hermes" / "sessions"
    newest = max(sessions.glob("*.jsonl"), key=lambda path: path.stat().st_mtime, default=None) if sessions.exists() else None
    if newest is not None:
        shutil.copy2(newest, case_dir / "session.jsonl")
    checks = check_answer(answer or result.stdout, session)
    expected = case.get("expected", "citation")
    passed = checks["has_citation"] if expected == "citation" else checks["admits_missing"]
    return {"case_id": case["case_id"], "returncode": result.returncode, "expected": expected, "passed": passed,
            "session_id": session["id"] if session else None, **checks}


def run_agent_cases(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Run every scripted case through the challenge Hermes profile."""
    profile = REPO / "data" / "hermes"
    if not (profile / "config.yaml").exists():
        raise ConfigurationError("set up the Hermes profile first: see docs/hermes.md and plan W4.1")
    hermes_bin()  # fail with the clear message before running any case
    env = os.environ.copy()
    env["HERMES_HOME"] = str(profile)
    env["PANZERKNACKER_ARTIFACTS"] = str(REPO / "artifacts")
    super_key = dotenv_values(REPO / ".env").get("SUPER_API_KEY")
    if super_key:
        env["SUPER_API_KEY"] = super_key
    cases = load_cases(work_dir)
    runs_dir = work_dir / "agent" / "runs"
    results = []
    for index, case in enumerate(cases, start=1):
        print(f"[agent] {index}/{len(cases)} {case['case_id']}", file=sys.stderr, flush=True)
        results.append(run_case(case, runs_dir, env))
    report = {"model": settings.super_model, "cases": results,
              "passed": sum(1 for row in results if row["passed"]), "total": len(results)}
    write_json(work_dir / "agent" / "report.json", report)
    return {"stage": "agent", "cases": report["total"], "passed": report["passed"],
            "report": str(work_dir / "agent" / "report.json")}
