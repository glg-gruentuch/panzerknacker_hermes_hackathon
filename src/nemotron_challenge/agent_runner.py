"""Run scripted Hermes comparison cases and record the evidence."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from .config import ConfigurationError, Settings
from .pipeline import write_json

HERMES_BIN = Path("/opt/hermes/.venv/bin/hermes")
REPO = Path(__file__).resolve().parents[2]
CASE_TIMEOUT = 600
CITATION = re.compile(r"britannica:[0-9a-f]{40}:train:\d+")


def load_cases(work_dir: Path) -> list[dict[str, Any]]:
    """Read the scripted cases. See plan W4.5 for the file format."""
    path = work_dir / "agent" / "cases.json"
    if not path.exists():
        raise ValueError(f"write the case list first: {path}")
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("the case list must contain at least one case")
    return cases


def check_answer(text: str) -> dict[str, bool]:
    """Check one reply for a citation or an explicit missing-evidence statement."""
    lowered = text.lower()
    return {
        "has_citation": bool(CITATION.search(text)),
        "admits_missing": "insufficient" in lowered or "unmatched" in lowered or "no stored comparison" in lowered,
    }


def run_case(case: dict[str, Any], runs_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    """Run one question through the Hermes profile and save all evidence."""
    case_dir = runs_dir / case["case_id"]
    case_dir.mkdir(parents=True, exist_ok=True)
    command = [str(HERMES_BIN), "chat", "-q", case["question"], "--toolsets", "nemotron_challenge"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=CASE_TIMEOUT, env=env, cwd=REPO)
    write_json(case_dir / "command.json", {"command": command, "returncode": result.returncode,
                                           "question": case["question"], "expected": case.get("expected", "")})
    (case_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (case_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    sessions = REPO / "data" / "hermes" / "sessions"
    newest = max(sessions.glob("*.jsonl"), key=lambda path: path.stat().st_mtime, default=None) if sessions.exists() else None
    if newest is not None:
        shutil.copy2(newest, case_dir / "session.jsonl")
    checks = check_answer(result.stdout)
    expected = case.get("expected", "citation")
    passed = checks["has_citation"] if expected == "citation" else checks["admits_missing"]
    return {"case_id": case["case_id"], "returncode": result.returncode, "expected": expected, "passed": passed, **checks}


def run_agent_cases(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Run every scripted case through the challenge Hermes profile."""
    profile = REPO / "data" / "hermes"
    if not (profile / "config.yaml").exists():
        raise ConfigurationError("set up the Hermes profile first: see docs/hermes.md and plan W4.1")
    if not HERMES_BIN.exists():
        raise ConfigurationError(f"Hermes binary not found at {HERMES_BIN}")
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
