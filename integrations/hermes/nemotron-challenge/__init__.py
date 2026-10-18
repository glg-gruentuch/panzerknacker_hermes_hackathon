"""Native Hermes registration for the Panzerknacker comparison tools.

The tools read the saved artifacts of the pipeline: comparisons, claim
alignments, and derived scan pages. When the stored records do not cover the
request, they return an explicit insufficient evidence status. The plugin uses
the standard library only (Pillow is imported inside the crop helper), so the
profile copy stays self-contained.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ARTIFACTS_ENV = "PANZERKNACKER_ARTIFACTS"
SCANS_ENV = "PANZERKNACKER_SCANS"
API_ENV = "CHALLENGE_API_URL"

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

CLAIMS_SCHEMA = {
    "name": "challenge_claims",
    "description": (
        "Return the stored claim alignment for one matched entry: every Britannica "
        "claim with its verdict against the Wikipedia article, both quotes, and "
        "citations from both sources."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "entry_id": {
                "type": "string",
                "description": "Entry ID from challenge_search, such as britannica:...:train:107#0000.",
                "minLength": 1,
                "maxLength": 200,
            },
        },
        "required": ["entry_id"],
        "additionalProperties": False,
    },
}

SCAN_CHECK_SCHEMA = {
    "name": "challenge_scan_check",
    "description": (
        "Check a quote against the scan image of its page. Finds the text block "
        "that contains the quote, crops that region from the scan, and asks the "
        "vision model whether the printed text matches the quote. Returns match, "
        "mismatch, or unreadable, with a reason."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID of a derived scan page, such as britannica:...:train:257.",
                "minLength": 1,
                "maxLength": 200,
            },
            "quote": {
                "type": "string",
                "description": "Text to check against the scan, for example an OCR reading you want to verify.",
                "minLength": 1,
                "maxLength": 600,
            },
        },
        "required": ["page_id", "quote"],
        "additionalProperties": False,
    },
}

SOURCE_NOTE = "Britannica scans: National Library of Scotland (CC0 1.0). Wikipedia text: CC BY-SA 4.0."

VISION_PROMPT = (
    "You are shown a crop of one page of an old encyclopedia scan. Does the printed text "
    "in the image contain the following quoted text?\n\nQUOTE: {quote}\n\n"
    "Answer with JSON only, no other text: {{\"result\": \"match\" | \"mismatch\" | \"unreadable\", "
    "\"reason\": \"<short reason>\"}}. Use match when the quoted text appears in the image, "
    "mismatch when the image shows different text, and unreadable when the image cannot be read."
)


def _rows(name: str) -> list[dict[str, Any]]:
    path = _artifact_path(name)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _artifact_path(*parts: str) -> Path:
    return Path(os.environ.get(ARTIFACTS_ENV, "artifacts")).joinpath(*parts)


def _score(query: str, row: dict[str, Any]) -> int:
    terms = set(query.lower().split())
    haystack = f"{row.get('entry_title', '')} {row.get('article_title', '')}".lower()
    return sum(1 for term in terms if term in haystack)


def _api_search(base_url: str, query: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/search?q=" + urllib.parse.quote(query),
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return list(payload.get("results", []))


def handle_search(params: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    query = str(params["query"]).strip()
    api_url = os.environ.get(API_ENV, "").strip()
    if api_url:
        try:
            results = _api_search(api_url, query)
            return json.dumps({
                "status": "ok" if results else "insufficient_evidence",
                "search": "lance",
                "query": query,
                "matches": results[:5],
                "detail": "" if results else "No stored entry or paragraph matches the query terms.",
            }, ensure_ascii=False)
        except Exception:  # the backend is optional; fall through to the stored view
            pass
    ranked = [row for score, row in sorted(
        ((_score(query, row), row) for row in _rows("compare/comparisons.jsonl")), key=lambda item: -item[0]) if score > 0]
    if not query or not ranked:
        return json.dumps({"status": "insufficient_evidence", "search": "fallback", "query": query,
                           "detail": "No stored comparison matches the query terms."}, ensure_ascii=False)
    return json.dumps({
        "status": "ok",
        "search": "fallback",
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
    row = next((item for item in _rows("compare/comparisons.jsonl") if item.get("entry_id") == entry_id), None)
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


def handle_claims(params: dict[str, Any], **kwargs: Any) -> str:
    """Return the stored claim alignment for one entry, with both quotes."""
    del kwargs
    entry_id = str(params["entry_id"]).strip()
    record = next((item for item in _rows("claims/claims.jsonl") if item.get("entry_id") == entry_id), None)
    if record is None:
        return json.dumps({"status": "insufficient_evidence", "entry_id": entry_id,
                           "detail": "This entry has no stored claim alignment. Do not guess an answer."},
                          ensure_ascii=False)
    match = next((item for item in _rows("match/matches.jsonl") if item.get("entry_id") == entry_id), {})
    claims = [
        {
            "quote": claim.get("quote"),
            "type": claim.get("type"),
            "value": claim.get("value"),
            "unit": claim.get("unit"),
            "verdict": claim.get("verdict"),
            "wikipedia_quote": claim.get("wikipedia_quote"),
            "explanation": claim.get("explanation", {}),
            "downgraded": bool(claim.get("downgraded")),
        }
        for claim in record.get("claims", [])
    ]
    return json.dumps({
        "status": "ok",
        "entry_id": entry_id,
        "entry_title": match.get("entry_title", ""),
        "article_title": record.get("article_title", ""),
        "article_revision_id": record.get("article_revision_id", ""),
        "article_url": match.get("article_url", ""),
        "claims": claims,
        "section_coverage": record.get("section_coverage", []),
        "claims_dropped": record.get("claims_dropped", 0),
        "citations": [
            {"source": "britannica", "entry_id": entry_id, "page_id": record.get("page_id", "")},
            {"source": "wikipedia", "url": match.get("article_url", ""),
             "revision_id": record.get("article_revision_id", "")},
        ],
        "source_note": SOURCE_NOTE,
    }, ensure_ascii=False)


def _page_record(page_id: str) -> dict[str, Any] | None:
    derived = _artifact_path("extract", "derived")
    for path in sorted(derived.glob("page-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if data.get("page_id") == page_id:
            return data
    return None


def _find_block(entries: list[dict[str, Any]], quote: str) -> dict[str, Any] | None:
    """The first block whose text contains the quote, exactly or after long-s folding."""
    folded = quote.replace("\u017f", "s")
    for entry in entries:
        for block in entry.get("blocks", []):
            text = block.get("text") or ""
            if quote in text or folded in text.replace("\u017f", "s"):
                return block
    return None


def _crop_data_url(scan_path: Path, bbox: list[list[float]], margin: float = 0.02) -> str:
    """Crop the bbox region (normalized coordinates) and return a PNG data URL."""
    import base64
    import io

    from PIL import Image

    (x0, y0), (x1, y1) = bbox
    with Image.open(scan_path) as image:
        width, height = image.size
        box = (
            max(0, int((x0 - margin) * width)),
            max(0, int((y0 - margin) * height)),
            min(width, int((x1 + margin) * width) + 1),
            min(height, int((y1 + margin) * height) + 1),
        )
        region = image.crop(box).convert("RGB")
        buffer = io.BytesIO()
        region.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _vision_check(image_url: str, quote: str) -> str:
    """Ask the vision model whether the image contains the quote. Returns the reply text."""
    base = os.environ.get("SUPER_BASE_URL", "").rstrip("/")
    key = os.environ.get("SUPER_API_KEY", "")
    model = os.environ.get("SUPER_MODEL", "")
    if not base or not key or not model:
        raise RuntimeError("Super VL is not configured (SUPER_BASE_URL, SUPER_MODEL, SUPER_API_KEY)")
    payload = {
        "model": model,
        "max_tokens": 2000,
        "temperature": 0,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": VISION_PROMPT.format(quote=quote)},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]}],
    }
    request = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        reply = json.loads(response.read().decode("utf-8"))
    return str(reply["choices"][0]["message"]["content"])


def _parse_vision_reply(reply: str) -> tuple[str, str]:
    text = reply.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("the vision reply contains no JSON object")
    data = json.loads(text[start:end + 1])
    result = str(data.get("result", "")).strip().lower()
    if result not in {"match", "mismatch", "unreadable"}:
        raise ValueError(f"unexpected vision result: {result!r}")
    return result, str(data.get("reason", "")).strip()


def handle_scan_check(params: dict[str, Any], **kwargs: Any) -> str:
    """Crop the quote's block from the scan and ask the vision model about it."""
    del kwargs
    page_id = str(params["page_id"]).strip()
    quote = str(params["quote"]).strip()
    if not quote:
        return json.dumps({"status": "error", "page_id": page_id,
                           "detail": "quote must not be empty"}, ensure_ascii=False)
    page = _page_record(page_id)
    if page is None:
        return json.dumps({"status": "not_found", "page_id": page_id,
                           "detail": "No derived page with this ID. Use a page ID from challenge_claims "
                                     "or challenge_compare output."}, ensure_ascii=False)
    block = _find_block(page.get("entries", []), quote)
    if block is None or not block.get("bbox"):
        return json.dumps({"status": "not_found", "page_id": page_id,
                           "detail": "The quote is not in any text block with a bounding box on this page."},
                          ensure_ascii=False)
    scan_dir = Path(os.environ.get(SCANS_ENV, _artifact_path().parent / "data" / "raw" / "britannica"))
    scan_path = scan_dir / str(page.get("filename", ""))
    if not scan_path.exists():
        return json.dumps({"status": "error", "page_id": page_id,
                           "detail": f"scan not found: {scan_path}"}, ensure_ascii=False)
    try:
        data_url = _crop_data_url(scan_path, block["bbox"])
        reply = _vision_check(data_url, quote)
        result, reason = _parse_vision_reply(reply)
    except Exception as exc:  # network, credentials, image, or parse problems
        return json.dumps({"status": "error", "page_id": page_id, "quote": quote,
                           "detail": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)
    return json.dumps({
        "status": "ok",
        "page_id": page_id,
        "result": result,
        "reason": reason,
        "quote": quote,
        "bbox": block["bbox"],
        "block_text": (block.get("text") or "")[:400],
    }, ensure_ascii=False)


def register(ctx: Any) -> None:
    """Register the comparison tools through the native Hermes interface."""
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
    ctx.register_tool(
        name="challenge_claims",
        toolset="nemotron_challenge",
        schema=CLAIMS_SCHEMA,
        handler=handle_claims,
    )
    ctx.register_tool(
        name="challenge_scan_check",
        toolset="nemotron_challenge",
        schema=SCAN_CHECK_SCHEMA,
        handler=handle_scan_check,
    )
