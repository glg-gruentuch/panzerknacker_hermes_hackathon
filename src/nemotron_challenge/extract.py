"""Extract scans with Parse 3.5. Raw output and derived text stay separate.

Parse returns one block per line in this shape:

    <x_0.05><y_0.04>text<x_0.65><y_0.05><class_Page-header>

Blocks carry a bounding box and a page element class. The derived records keep
both. See docs/parse-notes.md for the observed classes.
"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path
from typing import Any

from .clients import ParseClient, ProtocolError, ServiceError
from .config import PARSE_MODEL, Settings
from .contracts import ArtifactRecord, SourceReference
from .data import load_manifest
from .pipeline import retry_call, write_json
from .storage import LanceArtifactStore

DEFAULT_SCAN_DIR = Path("data/raw/britannica")

MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

BLOCK = re.compile(
    r"^(?:<x_([0-9.]+)><y_([0-9.]+)>)?(?P<text>.*?)"
    r"(?:<x_([0-9.]+)><y_([0-9.]+)><class_([A-Za-z0-9_-]+)>)?$"
)
HEADING_CLASSES = {"Title", "Section-header"}
SKIP_CLASSES = {"Page-header", "Page-footer", "Page-number"}
BARE_NUMBER = re.compile(r"^\d{1,4}$")
CONTINUATION = re.compile(r"\((?:continued|concluded)[^)]*\)", re.IGNORECASE)


def image_data_url(path: Path) -> str:
    """Encode one scan as an inline data URL. The service accepts PNG or JPEG below 8 MiB."""
    path = Path(path)
    if path.suffix.lower() not in MIME:
        raise ValueError(f"{path.name} is not a PNG or JPEG scan")
    raw = path.read_bytes()
    if not raw or len(raw) > 8 * 1024 * 1024:
        raise ValueError(f"{path.name} must contain 1 byte to 8 MiB")
    return f"data:{MIME[path.suffix.lower()]};base64," + base64.b64encode(raw).decode("ascii")


def title_key(heading: str) -> str:
    """Fold a heading for continuation matching: lowercase, alphanumeric words only."""
    return re.sub(r"[^a-z0-9]+", " ", heading.lower()).strip()


def running_head_key(text: str) -> str:
    """Fold a running head for continuation matching. Drop page-number tokens."""
    return " ".join(token for token in title_key(text).split() if not token.isdigit())


def clean_heading(text: str) -> str:
    """Drop markdown artifacts from a heading line: '#', '**', '_' wrappers, trailing marks."""
    cleaned = re.sub(r"^#{1,6}\s*", "", text).strip()
    for _ in range(2):
        cleaned = re.sub(r"[\s:,;.]+$", "", cleaned).strip()
        if len(cleaned) > 4 and cleaned.startswith("**") and cleaned.endswith("**"):
            cleaned = cleaned[2:-2].strip()
        elif len(cleaned) > 2 and cleaned.startswith("_") and cleaned.endswith("_"):
            cleaned = cleaned[1:-1].strip()
    return cleaned.strip()


def parse_blocks(markdown: str) -> list[dict[str, Any]]:
    """Parse Parse markdown into blocks with class, text, and bounding box."""
    blocks: list[dict[str, Any]] = []
    for line in markdown.splitlines():
        if not line.strip():
            continue
        match = BLOCK.match(line)
        if match is None:
            blocks.append({"class": None, "text": line.strip(), "bbox": None})
            continue
        x0, y0, text, x1, y1, cls = match.groups()
        if x0 and x1:
            bbox = [[float(x0), float(y0)], [float(x1), float(y1)]]
        else:
            bbox = None
        blocks.append({"class": cls, "text": (text or "").strip(), "bbox": bbox})
    return [block for block in blocks if block["text"]]


def page_header(blocks: list[dict[str, Any]]) -> str:
    """Return the running head of a page, or an empty string."""
    for block in blocks:
        if block["class"] == "Page-header":
            return block["text"]
    return ""


def segment(markdown: str) -> tuple[list[dict[str, Any]], str]:
    """Split one Parse reply into entry records and the page running head.

    A heading block (Title or Section-header) starts an entry. Text, List-item,
    and Caption blocks attach to the entry above them. A page opening without a
    heading starts a continuation entry named after the running head. Headers,
    footers, and page numbers stay out of the entry text.
    """
    blocks = parse_blocks(markdown)
    header = page_header(blocks)
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for block in blocks:
        cls = block["class"]
        if cls in SKIP_CLASSES:
            continue
        if cls is None and BARE_NUMBER.match(block["text"]):
            continue
        if cls in HEADING_CLASSES:
            current = {"heading": clean_heading(block["text"]), "heading_class": cls, "blocks": []}
            entries.append(current)
            continue
        if current is None:
            if not header:
                continue
            current = {"heading": header, "heading_class": "Page-header", "blocks": []}
            entries.append(current)
        current["blocks"].append(block)
    for entry in entries:
        entry["page_header"] = header
        entry["body"] = "\n".join(block["text"] for block in entry["blocks"])
        entry["continued"] = bool(CONTINUATION.search(entry["heading"])) or bool(
            CONTINUATION.search(entry["body"][:120])
        )
    return [entry for entry in entries if entry["body"] or entry["heading"]], header


def join_continuations(pages: list[tuple[str, list[dict[str, Any]]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Join entries that continue across page boundaries. Log every join.

    Only the first entry of a page can join the last entry of the previous page.
    A page-opening entry with heading class Page-header joins when its running
    head matches the previous page running head or the previous entry heading.
    A repeated heading matches with its full text, including numbers, so
    numbered sub-headings do not merge.
    """
    entries: list[dict[str, Any]] = []
    joins: list[dict[str, Any]] = []
    for page_id, page_entries in pages:
        for position, entry in enumerate(page_entries):
            entry["page_id"] = page_id
            previous = entries[-1] if entries else None
            cross_page = previous is not None and previous["page_id"] != page_id and position == 0
            if cross_page and entry["heading_class"] == "Page-header":
                key = running_head_key(entry["heading"])
                if key and (key == running_head_key(previous.get("page_header", ""))
                            or key == running_head_key(previous["heading"])):
                    joins.append({"heading": entry["heading"], "joined_into": previous["entry_id"],
                                  "from_page": previous["page_id"], "page": page_id, "rule": "running-head"})
                    previous["body"] = previous["body"] + "\n" + entry["body"]
                    previous["blocks"].extend(entry["blocks"])
                    previous["continued_on"] = page_id
                    continue
            if cross_page and entry["heading_class"] != "Page-header":
                key = title_key(entry["heading"])
                if len(key) > 3 and key == title_key(previous["heading"]):
                    joins.append({"heading": entry["heading"], "joined_into": previous["entry_id"],
                                  "from_page": previous["page_id"], "page": page_id, "rule": "repeated-heading"})
                    previous["body"] = previous["body"] + "\n" + entry["body"]
                    previous["blocks"].extend(entry["blocks"])
                    previous["continued_on"] = page_id
                    continue
            entry.setdefault("entry_id", f"{page_id}#{len(entries):04d}")
            entries.append(entry)
    return entries, joins


def flat_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Drop block details for the flattened entry list. The page file keeps them."""
    return {
        "entry_id": entry["entry_id"],
        "page_id": entry["page_id"],
        "filename": entry["filename"],
        "scan_sha256": entry.get("scan_sha256", ""),
        "heading": entry["heading"],
        "heading_class": entry["heading_class"],
        "page_header": entry.get("page_header", ""),
        "continued": entry.get("continued", False),
        "continued_on": entry.get("continued_on"),
        "n_blocks": len(entry.get("blocks", [])),
        "body": entry["body"],
    }


def run_extract(settings: Settings, work_dir: Path, *, scan_dir: Path = DEFAULT_SCAN_DIR) -> dict[str, Any]:
    """Run Parse 3.5 on every manifest scan. Resume skips finished raw replies."""
    manifest = load_manifest()
    scan_dir = Path(scan_dir)
    raw_dir = work_dir / "extract" / "raw"
    derived_dir = work_dir / "extract" / "derived"
    store = LanceArtifactStore(settings.db_path)
    failures: list[dict[str, Any]] = []
    pages: list[tuple[str, list[dict[str, Any]]]] = []
    page_meta: dict[str, dict[str, Any]] = {}
    pages_ok = 0
    page_list = manifest["pages"]
    with ParseClient(settings.parse_base_url, settings.parse_api_key) as client:
        for index, page in enumerate(page_list, start=1):
            print(f"[extract] {index}/{len(page_list)} {page['filename']}", file=sys.stderr, flush=True)
            raw_path = raw_dir / f"{page['filename']}.json"
            if raw_path.exists():
                reply = json.loads(raw_path.read_text(encoding="utf-8"))
            else:
                try:
                    reply = None
                    for budget in (8744, 16000):
                        try:
                            reply = retry_call(lambda: client.parse(image_data_url(scan_dir / page["filename"]),
                                                                    max_tokens=budget))
                            break
                        except ProtocolError as exc:
                            if "incomplete" not in str(exc) or budget == 16000:
                                raise
                except (ServiceError, ValueError, OSError) as exc:
                    failures.append({"page_id": page["page_id"], "error": f"{type(exc).__name__}: {exc}"})
                    continue
                write_json(raw_path, reply)
            markdown = reply["choices"][0]["message"]["content"]
            entries, header = segment(markdown)
            for position, entry in enumerate(entries):
                entry["entry_id"] = f"{page['page_id']}#{position:04d}"
                entry["filename"] = page["filename"]
                entry["scan_sha256"] = page["image_sha256"]
            pages.append((page["page_id"], entries))
            page_meta[page["page_id"]] = {"filename": page["filename"], "page_header": header}
            pages_ok += 1
            store.put(
                ArtifactRecord(
                    record_id=f"extract:{page['page_id']}",
                    stage="extract",
                    sources=[
                        SourceReference(
                            dataset=manifest["dataset"],
                            dataset_revision=manifest["revision"],
                            source_id=page["volume_id"],
                            source_url=manifest["source_url"],
                            content_sha256=page["image_sha256"],
                            license=str(manifest.get("license") or "CC0-1.0"),
                        )
                    ],
                    artifact_path=str(raw_path),
                    metadata={"parse_model": PARSE_MODEL, "segments": len(entries), "page_header": header},
                )
            )
    entries, joins = join_continuations(pages)
    by_page: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_page.setdefault(entry["page_id"], []).append(entry)
    for page_id, meta in page_meta.items():
        write_json(
            derived_dir / f"{meta['filename']}.json",
            {"page_id": page_id, "filename": meta["filename"], "page_header": meta["page_header"],
             "entries": by_page.get(page_id, [])},
        )
    write_json(derived_dir / "entries.json", [flat_entry(entry) for entry in entries])
    write_json(derived_dir / "joins.json", joins)
    coverage = {
        "pages_total": len(page_list),
        "pages_ok": pages_ok,
        "pages_failed": len(failures),
        "entries": len(entries),
        "joins": len(joins),
        "failures": failures,
    }
    write_json(work_dir / "extract" / "coverage.json", coverage)
    return {
        "stage": "extract",
        **{key: coverage[key] for key in ("pages_total", "pages_ok", "pages_failed", "entries", "joins")},
        "artifacts": str(work_dir / "extract"),
        "failures": failures,
    }
