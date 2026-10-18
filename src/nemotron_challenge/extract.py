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
from .contracts import ArtifactRecord, EntryRecord, SourceReference
from .data import load_manifest
from .pipeline import retry_call, write_json
from .storage import LanceArtifactStore

DEFAULT_SCAN_DIR = Path("data/raw/britannica")

MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

BLOCK = re.compile(
    r"^(?:<x_([0-9.]+)><y_([0-9.]+)>)?(?P<text>.*?)"
    r"(?:<x_([0-9.]+)><y_([0-9.]+)><class_([A-Za-z0-9_-]+)>)?$"
)
# An entry starts inline with an upper-case headword: two or more capital
# letters, hyphens or spaces allowed, followed by a comma or a period.
HEADWORD = re.compile(r"^(?P<head>[A-Z][A-Z\-\s]{0,60}[A-Z])[\-\s]*[,.]")
# Title and Section-header blocks are sub-section or running-head material.
# They never start an entry. They merge into the current parent entry.
SUBSECTION_CLASSES = {"Title", "Section-header"}
SKIP_CLASSES = {"Page-header", "Page-footer", "Page-number"}
BARE_NUMBER = re.compile(r"^\d{1,4}$")
CONTINUATION = re.compile(r"\((?:continued|concluded)[^)]*\)", re.IGNORECASE)
RUNNING_HEAD_MARK = re.compile(r"\[\s*\d+\s*\]")


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
    cleaned = cleaned.replace("*", "").replace("_", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return re.sub(r"[\s:,;.]+$", "", cleaned).strip()


def clean_headword(text: str) -> str:
    """Clean a headword of OCR noise: markdown artifacts and extra whitespace."""
    return re.sub(r"\s+", " ", clean_heading(text)).strip()


def headword_of(text: str) -> str | None:
    """Return the entry headword when a block opens with one, else None.

    In the 1768 to 1860 editions, an entry starts inline with an upper-case
    headword at the start of a paragraph, for example ``ETNA, or Mount Etna,
    ...`` or ``SHIP-BUILDING, ...``. A headword holds two or more capital
    letters; hyphens and spaces are allowed. It is followed by a comma or a
    period.
    """
    match = HEADWORD.match(text)
    return clean_headword(match.group("head")) if match else None


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

    A Text block that opens with an upper-case headword starts an entry; the
    headword becomes the heading. Title and Section-header blocks are
    sub-section or running-head material; they merge into the current parent
    entry as subsections and never start an entry. Page-header blocks are
    running heads: they stay in page_header only. Text before the first
    headword on a page becomes one entry with ``fragment`` true and
    ``heading`` null. Headers, footers, and page numbers stay out of the
    entry text. Entries without content blocks are dropped, but a page that
    would otherwise have no entry keeps one empty fragment (B1).
    """
    blocks = parse_blocks(markdown)
    header = page_header(blocks)
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def ensure_entry() -> dict[str, Any]:
        nonlocal current
        if current is None:
            current = {"heading": None, "heading_class": None, "fragment": True,
                       "subsections": [], "blocks": []}
            entries.append(current)
        return current

    for block in blocks:
        cls = block["class"]
        if cls in SKIP_CLASSES:
            continue
        if cls is None and BARE_NUMBER.match(block["text"]):
            continue
        if cls in SUBSECTION_CLASSES:
            subsection = clean_heading(block["text"])
            if subsection:
                ensure_entry()["subsections"].append(subsection)
            continue
        headword = headword_of(block["text"]) if cls == "Text" else None
        if headword:
            current = {"heading": headword, "heading_class": cls, "fragment": False,
                       "subsections": [], "blocks": []}
            entries.append(current)
        else:
            current = ensure_entry()
        current["blocks"].append(block)
    kept: list[dict[str, Any]] = []
    for entry in entries:
        if not entry["blocks"]:
            continue
        entry["page_header"] = header
        entry["body"] = "\n".join(block["text"] for block in entry["blocks"])
        entry["continued"] = bool(entry["fragment"]) or bool(
            CONTINUATION.search(entry["heading"] or "")
        ) or bool(CONTINUATION.search(entry["body"][:120]))
        kept.append(entry)
    if not kept:
        # Every parsed page gets at least one entry (handoff 2, B1). A page
        # with no headword and no running head, for example a full-page
        # picture whose blocks carry no text, keeps one empty fragment. A
        # lone subsection heading keeps that subsection.
        entry = entries[0] if entries else {
            "heading": None, "heading_class": None, "fragment": True,
            "subsections": [], "blocks": []}
        entry["page_header"] = header
        entry["body"] = ""
        entry["continued"] = True
        return [entry], header
    return kept, header


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
            opens_page = position == 0 and previous is not None and previous["page_id"] != page_id
            if opens_page and previous is not None and entry.get("heading_class") == "Page-header":
                key = running_head_key(entry.get("heading") or "")
                if key and (key == running_head_key(previous.get("page_header") or "")
                            or key == running_head_key(previous.get("heading") or "")):
                    joins.append({"heading": entry["heading"], "joined_into": previous["entry_id"],
                                  "from_page": previous["page_id"], "page": page_id, "rule": "running-head"})
                    previous["body"] = previous["body"] + "\n" + entry["body"]
                    previous["blocks"].extend(entry["blocks"])
                    previous["continued_on"] = page_id
                    continue
            if opens_page and previous is not None and entry.get("heading_class") != "Page-header":
                key = title_key(entry.get("heading") or "")
                if len(key) > 3 and key == title_key(previous.get("heading") or ""):
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
        "heading": entry.get("heading"),
        "heading_class": entry.get("heading_class"),
        "fragment": bool(entry.get("fragment", False)),
        "subsections": list(entry.get("subsections", [])),
        "page_header": entry.get("page_header", ""),
        "continued": entry.get("continued", False),
        "continued_on": entry.get("continued_on"),
        "n_blocks": len(entry.get("blocks", [])),
        "body": entry.get("body", ""),
    }


def derive_outputs(
    work_dir: Path,
    pages: list[tuple[str, list[dict[str, Any]]]],
    page_meta: dict[str, dict[str, Any]],
    *,
    failures: list[dict[str, Any]],
    pages_total: int,
) -> dict[str, Any]:
    """Join, flatten, and write the derived extract artifacts for segmented pages."""
    derived_dir = work_dir / "extract" / "derived"
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
    flat = [EntryRecord.model_validate(flat_entry(entry)).model_dump() for entry in entries]
    write_json(derived_dir / "entries.json", flat)
    write_json(derived_dir / "joins.json", joins)
    pages_with = {entry["page_id"] for entry in entries}
    summary = {
        "pages_total": pages_total,
        "pages_derived": len(page_meta),
        "pages_failed": len(failures),
        "pages_with_entries": len(pages_with),
        "pages_without_entries": sorted(set(page_meta) - pages_with),
        "entries": len(flat),
        "headwords": sum(1 for row in flat if row["heading"]),
        "fragments": sum(1 for row in flat if row["fragment"]),
        "subsections": sum(len(row["subsections"]) for row in flat),
        "joins": len(joins),
        "headings_matching_running_head_pattern": sum(
            1 for row in flat if row["heading"] and RUNNING_HEAD_MARK.search(row["heading"])
        ),
        "failures": failures,
    }
    write_json(work_dir / "extract" / "segment-summary.json", summary)
    return {"entries": entries, "joins": joins, "flat": flat, "summary": summary}


def run_derive(work_dir: Path) -> dict[str, Any]:
    """Re-derive segmentation and derived files from the saved raw Parse replies.

    No model calls happen. The previous entries.json is kept as entries.v1.json
    before the first re-derive. Pages without a raw reply are reported as
    failures and are not replaced by guessed text.
    """
    manifest = load_manifest()
    raw_dir = work_dir / "extract" / "raw"
    derived_dir = work_dir / "extract" / "derived"
    entries_path = derived_dir / "entries.json"
    v1_path = derived_dir / "entries.v1.json"
    if entries_path.exists() and not v1_path.exists():
        v1_path.write_text(entries_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[derive] kept the previous entries as {v1_path}", file=sys.stderr, flush=True)
    previous_errors: dict[str, str] = {}
    coverage_path = work_dir / "extract" / "coverage.json"
    if coverage_path.exists():
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        for row in coverage.get("failures", []):
            if isinstance(row, dict) and row.get("page_id"):
                previous_errors[str(row["page_id"])] = str(row.get("error", ""))
    pages: list[tuple[str, list[dict[str, Any]]]] = []
    page_meta: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    for page in manifest["pages"]:
        raw_path = raw_dir / f"{page['filename']}.json"
        if not raw_path.exists():
            failures.append({"page_id": page["page_id"],
                             "error": previous_errors.get(page["page_id"], "no raw Parse reply on disk")})
            continue
        reply = json.loads(raw_path.read_text(encoding="utf-8"))
        markdown = reply["choices"][0]["message"]["content"]
        entries, header = segment(markdown)
        for position, entry in enumerate(entries):
            entry["entry_id"] = f"{page['page_id']}#{position:04d}"
            entry["filename"] = page["filename"]
            entry["scan_sha256"] = page["image_sha256"]
        pages.append((page["page_id"], entries))
        page_meta[page["page_id"]] = {"filename": page["filename"], "page_header": header}
    result = derive_outputs(work_dir, pages, page_meta, failures=failures, pages_total=len(manifest["pages"]))
    summary = result["summary"]
    # Keep coverage.json current after a re-derive: the evaluate stage and the
    # site read it, and stale counts from segmentation v1 misreported entries.
    coverage = {
        "pages_total": summary["pages_total"],
        "pages_ok": summary["pages_derived"],
        "pages_failed": summary["pages_failed"],
        "entries": summary["entries"],
        "headwords": summary["headwords"],
        "fragments": summary["fragments"],
        "joins": summary["joins"],
        "failures": failures,
        "refreshed_by": "run extract --derive-only (segmentation v2; no model calls)",
    }
    write_json(work_dir / "extract" / "coverage.json", coverage)
    print(f"[derive] entries={summary['entries']} headwords={summary['headwords']} "
          f"fragments={summary['fragments']} pages={summary['pages_derived']}/{summary['pages_total']}",
          file=sys.stderr, flush=True)
    return {
        "stage": "derive",
        **{key: summary[key] for key in
           ("pages_total", "pages_derived", "pages_failed", "entries", "headwords", "fragments", "joins")},
        "artifacts": str(work_dir / "extract"),
        "failures": failures,
    }


def run_extract(settings: Settings, work_dir: Path, *, scan_dir: Path = DEFAULT_SCAN_DIR) -> dict[str, Any]:
    """Run Parse 3.5 on every manifest scan. Resume skips finished raw replies."""
    manifest = load_manifest()
    scan_dir = Path(scan_dir)
    raw_dir = work_dir / "extract" / "raw"
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
    result = derive_outputs(work_dir, pages, page_meta, failures=failures, pages_total=len(page_list))
    summary = result["summary"]
    coverage = {
        "pages_total": summary["pages_total"],
        "pages_ok": pages_ok,
        "pages_failed": summary["pages_failed"],
        "entries": summary["entries"],
        "headwords": summary["headwords"],
        "fragments": summary["fragments"],
        "joins": summary["joins"],
        "failures": failures,
    }
    write_json(work_dir / "extract" / "coverage.json", coverage)
    return {
        "stage": "extract",
        **{key: coverage[key] for key in
           ("pages_total", "pages_ok", "pages_failed", "entries", "headwords", "fragments", "joins")},
        "artifacts": str(work_dir / "extract"),
        "failures": failures,
    }
