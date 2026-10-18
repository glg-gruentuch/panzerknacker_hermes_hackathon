"""Shared stage helpers: bounded retries, atomic writes, JSONL files."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

from .clients import ServiceError

T = TypeVar("T")
RETRY_LIMIT = 4
RETRY_MAX_SLEEP = 30.0


def retry_call(fn: Callable[[], T], *, attempts: int = RETRY_LIMIT) -> T:
    """Call fn and retry on 429/503 replies. Honor Retry-After. Other errors raise."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except ServiceError as exc:
            if exc.status_code not in (429, 503) or attempt == attempts:
                raise
            try:
                delay = float(exc.retry_after) if exc.retry_after else 1.0
            except ValueError:
                delay = 1.0
            time.sleep(max(0.0, min(delay, RETRY_MAX_SLEEP)))
    raise AssertionError("retry loop exhausted without a result")


def write_json(path: Path, payload: Any) -> None:
    """Write JSON through a temporary file so a failed run leaves the old file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Append records to a JSONL file. Create the parent directory when missing."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file. A missing file reads as an empty list."""
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
