"""Describe the two failed scans with Super VL once each (handoff 2, B6).

Parse 3.5 found no typeset text on page-0452 (blank binding) and page-2243
(engraved plate); they stay recorded failures of the extract stage. This
script captures a one-shot model description of each page as
``kind: model_description`` evidence. It is not OCR, it is not an entry, and
no later stage consumes it except the site's "Parse failed" note.

Run from the repository root::

    uv run python scripts/vl_fallback.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from nemotron_challenge.clients import ChatClient, ServiceError
from nemotron_challenge.config import SUPER_MODEL, Settings
from nemotron_challenge.data import load_manifest
from nemotron_challenge.extract import DEFAULT_SCAN_DIR, image_data_url
from nemotron_challenge.pipeline import write_json

REPO = Path(__file__).resolve().parents[1]
FAILED_PAGE_IDS = [
    "britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:452",
    "britannica:309f765b1ecc83e0a7f7762e44b4a927a7555443:train:2243",
]

PROMPT = (
    "This is one page of an encyclopedia scan from 1768 to 1860. Describe what the page shows. "
    "State the page type and any printed caption you can read. If the page carries no typeset body "
    "text, say 'no typeset text'. Answer with JSON only: {\"page_type\": \"...\", \"caption\": \"...\", "
    "\"description\": \"...\"}."
)


def main() -> int:
    settings = Settings.from_env()
    manifest = load_manifest()
    wanted = set(FAILED_PAGE_IDS)
    pages = [page for page in manifest["pages"] if page["page_id"] in wanted]
    if len(pages) < len(wanted):
        print("the manifest does not carry both failed pages", file=sys.stderr)
        return 1
    out_dir = REPO / "artifacts" / "extract" / "vl-fallback"
    out_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    with ChatClient(settings.super_base_url, settings.super_api_key, settings.super_model, timeout=420) as chat:
        for page in pages:
            target = out_dir / f"{page['filename']}.json"
            if target.exists():
                try:
                    existing = json.loads(target.read_text(encoding="utf-8"))
                except ValueError:
                    existing = {}
                if existing.get("kind") == "model_description":
                    print(f"[vl-fallback] {page['filename']} already described", flush=True)
                    continue
            print(f"[vl-fallback] {page['filename']}", flush=True)
            try:
                reply = chat.complete(
                    [{"role": "user", "content": [
                        {"type": "text", "text": PROMPT},
                        {"type": "image_url",
                         "image_url": {"url": image_data_url(DEFAULT_SCAN_DIR / page["filename"])}},
                    ]}],
                    max_tokens=4000,
                    extra_body={"temperature": 0},
                )
            except (ServiceError, ValueError, OSError) as exc:
                failures += 1
                write_json(target, {"kind": "failure", "filename": page["filename"],
                                    "page_id": page["page_id"], "error": f"{type(exc).__name__}: {exc}"})
                print(f"[vl-fallback] {page['filename']} failed: {exc}", file=sys.stderr, flush=True)
                continue
            choice = reply["choices"][0]
            write_json(target, {
                "kind": "model_description",
                "filename": page["filename"],
                "page_id": page["page_id"],
                "model": reply.get("model") or SUPER_MODEL,
                "finish_reason": choice.get("finish_reason"),
                "usage": reply.get("usage"),
                "reply": reply,
            })
    print(f"[vl-fallback] done, failures={failures}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
