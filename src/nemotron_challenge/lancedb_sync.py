"""Mirror the JSONL artifacts into the shared LanceDB evidence store (B2).

The JSONL files stay the evidence of record. This module keeps a queryable copy
in LanceDB: every candidate row lands in ``match_evidence``, every entry in
``britannica_entries``, every article paragraph in ``wiki_paragraphs``. The
match and claims stages call in here at run time; ``sync_from_artifacts()``
rebuilds the tables from what is already on disk and calls no model.

Vectors: the runtime writers store the 2048-dim embedder vectors. The disk
rebuild cannot invent vectors that earlier runs discarded, so it leaves the
vector column empty and records that in the summary; a later stage run fills
the rows it touches.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from .web_adapter import paragraphs

VECTOR_DIM = 2048

EVIDENCE_COLUMNS = [
    ("entry_id", "string"),
    ("page_id", "string"),
    ("candidate_page_id", "string"),
    ("candidate_title", "string"),
    ("bm25_rank", "int32"),
    ("bm25_score", "float64"),
    ("embed_similarity", "float64"),
    ("embed_rank", "int32"),
    ("rerank_logit", "float64"),
    ("rerank_rank", "int32"),
    ("decision", "string"),
]

ENTRY_COLUMNS = [
    ("entry_id", "string"),
    ("page_id", "string"),
    ("heading", "string"),
    ("fragment", "bool"),
    ("body", "string"),
    ("scan_sha256", "string"),
]

PARAGRAPH_COLUMNS = [
    ("page_id", "string"),
    ("revision_id", "string"),
    ("section", "string"),
    ("paragraph_index", "int32"),
    ("text", "string"),
    ("text_sha256", "string"),
]

ARTICLE_COLUMNS = [
    ("page_id", "string"),
    ("revision_id", "string"),
    ("title", "string"),
    ("url", "string"),
    ("text", "string"),
    ("text_sha256", "string"),
]

SUMMARY_TABLES = ["artifact_provenance", "match_evidence", "britannica_entries", "wiki_articles", "wiki_paragraphs"]


def _pa_type(kind: str) -> Any:
    import pyarrow as pa

    if kind == "string":
        return pa.string()
    if kind == "int32":
        return pa.int32()
    if kind == "float64":
        return pa.float64()
    if kind == "bool":
        return pa.bool_()
    raise ValueError(f"unknown column kind: {kind}")


def _schema(columns: list[tuple[str, str]], *, vector: bool = False) -> Any:
    import pyarrow as pa

    fields = [(name, _pa_type(kind)) for name, kind in columns]
    if vector:
        fields.append(("vector", pa.list_(pa.float32(), VECTOR_DIM)))
    return pa.schema(fields)


def connect(db_path: str | Path) -> Any:
    import lancedb

    return lancedb.connect(str(db_path))


def ensure_tables(db: Any) -> dict[str, Any]:
    """Create or open the four evidence tables and return them by name."""
    return {
        "match_evidence": db.create_table("match_evidence", schema=_schema(EVIDENCE_COLUMNS), exist_ok=True),
        "britannica_entries": db.create_table("britannica_entries", schema=_schema(ENTRY_COLUMNS, vector=True),
                                              exist_ok=True),
        "wiki_articles": db.create_table("wiki_articles", schema=_schema(ARTICLE_COLUMNS), exist_ok=True),
        "wiki_paragraphs": db.create_table("wiki_paragraphs", schema=_schema(PARAGRAPH_COLUMNS, vector=True),
                                           exist_ok=True),
    }


def evidence_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize one evidence JSONL row to the table schema."""
    out: dict[str, Any] = {}
    for name, kind in EVIDENCE_COLUMNS:
        value = row.get(name)
        out[name] = None if value is None else value
    for name in ("bm25_rank", "embed_rank", "rerank_rank"):
        if out[name] is not None:
            out[name] = int(out[name])
    for name in ("bm25_score", "embed_similarity", "rerank_logit"):
        if out[name] is not None:
            out[name] = float(out[name])
    return out


def entry_row(entry: dict[str, Any], vector: list[float] | None = None) -> dict[str, Any]:
    row = {
        "entry_id": entry["entry_id"],
        "page_id": entry["page_id"],
        "heading": entry.get("heading"),
        "fragment": bool(entry.get("fragment", False)),
        "body": entry.get("body") or "",
        "scan_sha256": entry.get("scan_sha256", ""),
    }
    row["vector"] = vector
    return row


def paragraph_rows(article: dict[str, Any], vectors: list[list[float]] | None = None) -> list[dict[str, Any]]:
    """Rows for one article: paragraphs with their sha256 and optional vectors."""
    texts = paragraphs(article.get("text") or "")
    rows: list[dict[str, Any]] = []
    for index, text in enumerate(texts):
        row = {
            "page_id": article["page_id"],
            "revision_id": str(article["revision_id"]),
            "section": None,
            "paragraph_index": index,
            "text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
        row["vector"] = vectors[index] if vectors is not None and index < len(vectors) else None
        rows.append(row)
    return rows


def write_evidence_entry(db: Any, entry_id: str, rows: list[dict[str, Any]]) -> None:
    """Replace the evidence rows of one entry (idempotent on resume)."""
    table = ensure_tables(db)["match_evidence"]
    escaped = entry_id.replace("'", "''")
    table.delete(f"entry_id = '{escaped}'")
    if rows:
        table.add([evidence_row(row) for row in rows])


def write_entries(db: Any, rows: list[dict[str, Any]]) -> None:
    table = ensure_tables(db)["britannica_entries"]
    table.merge_insert("entry_id").when_matched_update_all().when_not_matched_insert_all().execute(rows)


def existing_paragraph_keys(table: Any, revision_id: str) -> set[tuple[int, str]]:
    """(paragraph_index, text_sha256) pairs already stored for one revision."""
    escaped = str(revision_id).replace("'", "''")
    rows = table.search().where(f"revision_id = '{escaped}'").select(["paragraph_index", "text_sha256"]).limit(100000).to_list()
    return {(int(row["paragraph_index"]), row["text_sha256"]) for row in rows}


def register_paragraphs(db: Any, revision_id: str, rows: list[dict[str, Any]],
                        embed_fn: Callable[[list[str]], list[list[float]]]) -> int:
    """Store paragraph rows, embedding only the ones that are not stored yet.

    The key is (revision_id, paragraph_index, text_sha256). Rows that exist
    with a vector are left alone; rows that exist without a vector (disk
    rebuild) are updated. Returns the number of paragraphs embedded.
    """
    table = ensure_tables(db)["wiki_paragraphs"]
    stored = existing_paragraph_keys(table, revision_id)
    escaped = str(revision_id).replace("'", "''")
    have_vector = {int(row["paragraph_index"]) for row in
                   table.search().where(f"revision_id = '{escaped}' AND vector IS NOT NULL")
                   .select(["paragraph_index"]).limit(100000).to_list()}
    missing = [row for row in rows if (row["paragraph_index"], row["text_sha256"]) not in stored]
    # A stored row whose text changed at the same index would shadow the new
    # text; drop the old version before inserting the new one.
    changed = {row["paragraph_index"] for row in missing} & {index for index, _ in stored}
    for index in sorted(changed):
        table.delete(f"revision_id = '{escaped}' AND paragraph_index = {int(index)}")
    stored = {(index, sha) for index, sha in stored if index not in changed}
    stale = [row for row in rows if (row["paragraph_index"], row["text_sha256"]) in stored
             and row["paragraph_index"] not in have_vector]
    todo = missing + stale
    if todo:
        vectors = embed_fn([row["text"] for row in todo])
        for row, vector in zip(todo, vectors):
            row["vector"] = vector
        table.merge_insert(["revision_id", "paragraph_index", "text_sha256"]) \
            .when_matched_update_all().when_not_matched_insert_all().execute(todo)
    return len(todo)


def store_paragraph_rows(db: Any, rows: list[dict[str, Any]]) -> None:
    """Upsert paragraph rows keyed by (revision_id, paragraph_index, text_sha256)."""
    table = ensure_tables(db)["wiki_paragraphs"]
    table.merge_insert(["revision_id", "paragraph_index", "text_sha256"]) \
        .when_matched_update_all().when_not_matched_insert_all().execute(rows)


def fetch_paragraph_vectors(db: Any, revision_id: str) -> dict[tuple[int, str], list[float] | None]:
    """Stored paragraph vectors for one revision, keyed by (index, text_sha256)."""
    table = ensure_tables(db)["wiki_paragraphs"]
    escaped = str(revision_id).replace("'", "''")
    rows = (table.search().where(f"revision_id = '{escaped}'")
            .select(["paragraph_index", "text_sha256", "vector"]).limit(100000).to_list())
    return {
        (int(row["paragraph_index"]), row["text_sha256"]):
            (list(row["vector"]) if row.get("vector") is not None else None)
        for row in rows
    }


def search_paragraphs(db: Any, page_id: str, claim_vector: list[float], limit: int = 10) -> list[dict[str, Any]] | None:
    """Top paragraphs for a claim through LanceDB. None when no vectors are stored.

    ``page_id`` is escaped the same way storage.py does.
    """
    table = ensure_tables(db)["wiki_paragraphs"]
    escaped = page_id.replace("'", "''")
    try:
        rows = (table.search(claim_vector)
                .metric("dot")
                .where(f"page_id = '{escaped}' AND vector IS NOT NULL", prefilter=True)
                .limit(limit)
                .to_list())
    except Exception:
        return None
    if not rows:
        return None
    return [
        {"paragraph_index": int(row["paragraph_index"]), "similarity": 1.0 - float(row.get("_distance", 1.0))}
        for row in rows
    ]


def search_entries_fts(db: Any, query: str, limit: int = 10) -> list[dict[str, Any]] | None:
    """Full-text search over britannica_entries.body. None when no FTS index exists."""
    table = ensure_tables(db)["britannica_entries"]
    try:
        rows = table.search(query, query_type="fts").limit(limit).to_list()
    except Exception:
        return None
    return [{"entry_id": row["entry_id"], "heading": row.get("heading"),
             "score": float(row.get("_score", 0.0))} for row in rows]


def search_paragraphs_fts(db: Any, query: str, limit: int = 10) -> list[dict[str, Any]] | None:
    """Full-text search over wiki_paragraphs.text. None when no FTS index exists."""
    table = ensure_tables(db)["wiki_paragraphs"]
    try:
        rows = table.search(query, query_type="fts").limit(limit).to_list()
    except Exception:
        return None
    return [{"page_id": row["page_id"], "revision_id": row["revision_id"],
             "paragraph_index": int(row["paragraph_index"]), "score": float(row.get("_score", 0.0))}
            for row in rows]


def ensure_fts_indexes(db: Any) -> bool:
    """Build the full-text indexes once per run (B3 reads them)."""
    tables = ensure_tables(db)
    try:
        tables["britannica_entries"].create_fts_index("body", replace=True)
        tables["wiki_paragraphs"].create_fts_index("text", replace=True)
        return True
    except Exception:
        return False


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sync_from_artifacts(db_path: str | Path, work_dir: Path) -> dict[str, Any]:
    """Rebuild the evidence tables from disk artifacts. Calls no model.

    match_evidence and britannica_entries are rebuilt from the JSONL files;
    wiki_paragraphs is built from the saved article JSON files when the table
    holds no vectors yet. Vectors stay empty on this path (see module docstring).
    """
    db = connect(db_path)
    match_dir = Path(work_dir) / "match"
    evidence = _read_jsonl(match_dir / "evidence.jsonl")
    if evidence:
        db.drop_table("match_evidence", ignore_missing=True)
    tables = ensure_tables(db)
    if evidence:
        tables["match_evidence"].add([evidence_row(row) for row in evidence])
    entries_path = Path(work_dir) / "extract" / "derived" / "entries.json"
    if entries_path.exists():
        entries = json.loads(entries_path.read_text(encoding="utf-8"))
        db.drop_table("britannica_entries", ignore_missing=True)
        tables = ensure_tables(db)
        if entries:
            tables["britannica_entries"].add([entry_row(entry) for entry in entries])
    articles_dir = match_dir / "articles"
    paragraphs_written = 0
    if articles_dir.is_dir():
        counts = tables["wiki_paragraphs"].count_rows()
        if counts == 0:
            rows: list[dict[str, Any]] = []
            for path in sorted(articles_dir.glob("*.json")):
                article = json.loads(path.read_text(encoding="utf-8"))
                rows.extend(paragraph_rows(article))
                tables["wiki_articles"].merge_insert("page_id") \
                    .when_matched_update_all().when_not_matched_insert_all().execute([{
                        "page_id": article["page_id"], "revision_id": str(article["revision_id"]),
                        "title": article["title"], "url": article["url"], "text": article["text"],
                        "text_sha256": article["provenance"]["text_sha256"],
                    }])
            if rows:
                tables["wiki_paragraphs"].add(rows)
            paragraphs_written = len(rows)
    fts = ensure_fts_indexes(db)
    return {"fts": fts, "paragraphs_written": paragraphs_written,
            "evidence_rows": len(evidence)}


def row_counts(db_path: str | Path) -> dict[str, int | None]:
    """Row counts of the shared tables. None when a table does not exist."""
    db = connect(db_path)
    counts: dict[str, int | None] = {}
    listed = db.list_tables()
    names = set(getattr(listed, "tables", listed))
    for name in SUMMARY_TABLES:
        counts[name] = db.open_table(name).count_rows() if name in names else None
    return counts


def write_summary(work_dir: Path, counts: dict[str, int | None], *, fts: bool, note: str) -> dict[str, Any]:
    summary = {
        "tables": counts,
        "fts_indexes": fts,
        "vector_state": "runtime stages store embedder vectors; rows rebuilt from disk keep the column empty",
        "note": note,
    }
    path = Path(work_dir) / "lancedb-summary.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary
