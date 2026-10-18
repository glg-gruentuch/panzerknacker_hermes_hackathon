"""Native Hermes registration for the Panzerknacker comparison tools.

Both tools read the saved comparison artifacts of the pipeline. When the stored
records do not cover the request, they return an explicit insufficient evidence
status. The plugin uses the standard library only, so the profile copy stays
self-contained.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ARTIFACTS_ENV = "PANZERKNACKER_ARTIFACTS"

SEARCH_SCHEMA = {
    "name": "challenge_search",
    "description": (
        "Search the stored Britannica-to-Wikipedia comparisons. Returns the best "
        "matching entries with their article titles and match confidence."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Topic words to search for in stored comparisons.",
                "minLength": 1,
                "maxLength": 2000,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

COMPARE_SCHEMA = {
    "name": "challenge_compare",
    "description": (
        "Return the stored comparison for one entry ID: Britannica excerpt, Wikipedia "
        "article, distinctive terms, and citations from both sources."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "entry_id": {
                "type": "string",
                "description": "Entry ID from challenge_search, such as britannica:...:train:13#0000.",
                "minLength": 1,
                "maxLength": 200,
            },
        },
        "required": ["entry_id"],
        "additionalProperties": False,
    },
}

SOURCE_NOTE = "Britannica scans: National Library of Scotland (CC0 1.0). Wikipedia text: CC BY-SA 4.0."


def _rows() -> list[dict[str, Any]]:
    path = Path(os.environ.get(ARTIFACTS_ENV, "artifacts")) / "compare" / "comparisons.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _score(query: str, row: dict[str, Any]) -> int:
    terms = set(query.lower().split())
    haystack = f"{row.get('entry_title', '')} {row.get('article_title', '')}".lower()
    return sum(1 for term in terms if term in haystack)


def handle_search(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    query = str(params["query"]).strip()
    ranked = [row for score, row in sorted(
        ((_score(query, row), row) for row in _rows()), key=lambda item: -item[0]) if score > 0]
    if not query or not ranked:
        return json.dumps({"status": "insufficient_evidence", "query": query,
                           "detail": "No stored comparison matches the query terms."}, ensure_ascii=False)
    return json.dumps({
        "status": "ok",
        "query": query,
        "matches": [
            {
                "entry_id": row["entry_id"],
                "entry_title": row["entry_title"],
                "article_title": row.get("article_title", ""),
                "match_confidence": row.get("match_confidence"),
            }
            for row in ranked[:5]
        ],
    }, ensure_ascii=False)


def handle_compare(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    entry_id = str(params["entry_id"]).strip()
    row = next((item for item in _rows() if item.get("entry_id") == entry_id), None)
    if row is None:
        return json.dumps({"status": "insufficient_evidence", "entry_id": entry_id,
                           "detail": "This entry has no stored comparison. Do not guess an answer."},
                          ensure_ascii=False)
    return json.dumps({
        "status": "ok",
        "entry_id": entry_id,
        "entry_title": row.get("entry_title", ""),
        "article_title": row.get("article_title", ""),
        "match_confidence": row.get("match_confidence"),
        "method": row.get("method", ""),
        "britannica": row.get("britannica", {}),
        "wikipedia": row.get("wikipedia", {}),
        "distinctive": row.get("distinctive", {}),
        "citations": row.get("citations", []),
        "source_note": SOURCE_NOTE,
    }, ensure_ascii=False)


def register(ctx: Any) -> None:
    """Register both comparison tools through the native Hermes interface."""
    ctx.register_tool(
        name="challenge_search",
        toolset="nemotron_challenge",
        schema=SEARCH_SCHEMA,
        handler=handle_search,
    )
    ctx.register_tool(
        name="challenge_compare",
        toolset="nemotron_challenge",
        schema=COMPARE_SCHEMA,
        handler=handle_compare,
    )
