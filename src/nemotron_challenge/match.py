"""Match entries to Wikipedia articles with BM25 candidates, embeddings, and reranking."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from .clients import RetrievalClient, ServiceError, WikiClient
from .config import MATCH_LOGIT_THRESHOLD, Settings, WIKIPEDIA_REVISION
from .contracts import ArtifactRecord, SourceReference
from .data import load_manifest
from .pipeline import append_jsonl, read_jsonl, retry_call, write_json
from .storage import LanceArtifactStore

EVIDENCE_NAME = "evidence.jsonl"
MATCHES_NAME = "matches.jsonl"
SHORTLIST_SIZE = 8
CANDIDATES = 30


def build_query(entry: dict[str, Any]) -> str:
    """BM25 query: heading plus opening text, within 512 chars and 64 words."""
    text = f"{entry['heading']} {entry['body']}"
    text = re.sub(r"\s+", " ", text).strip()
    return " ".join(text.split()[:64])[:512]


def embed_documents(retrieval: RetrievalClient, texts: list[str]) -> list[list[float]]:
    """Embed document texts in batches within the service limit of 16 items."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), 16):
        batch = texts[start : start + 16]
        vectors.extend(retry_call(lambda: retrieval.embed(batch, input_type="document")))
    return vectors


def shortlist(retrieval: RetrievalClient, entry_text: str, hits: list[Any], keep: int = SHORTLIST_SIZE) -> list[dict[str, Any]]:
    """Dot product of unit vectors. The query text is capped at 2000 chars by the client."""
    query_vector = retry_call(lambda: retrieval.embed([entry_text[:2000]], input_type="query"))[0]
    documents = [hit.excerpt[:32000] for hit in hits]
    vectors = embed_documents(retrieval, documents)
    scored = [
        {"hit": hit, "similarity": sum(a * b for a, b in zip(query_vector, vector))}
        for hit, vector in zip(hits, vectors)
    ]
    return sorted(scored, key=lambda row: -row["similarity"])[:keep]


def rerank_candidates(retrieval: RetrievalClient, entry_text: str, rows: list[dict[str, Any]], top_n: int = SHORTLIST_SIZE) -> list[dict[str, Any]]:
    """Rerank the shortlist. Result rows index into rows; scores are raw logits."""
    top_n = min(top_n, len(rows))
    reply = retry_call(
        lambda: retrieval.rerank(entry_text[:2000], [row["hit"].excerpt[:32000] for row in rows], top_n=top_n)
    )
    return [{"row": rows[item["index"]], "logit": item["relevance_score"]} for item in reply]


def decide(reranked: list[dict[str, Any]], threshold: float) -> dict[str, Any] | None:
    """Return the best candidate at or above the threshold. Scores are raw logits."""
    if not reranked:
        return None
    best = max(reranked, key=lambda row: row["logit"])
    return best if best["logit"] >= threshold else None


def fetch_article(wiki: WikiClient, page_id: str, max_chars: int = 20000) -> dict[str, Any]:
    """Read a full article through the paginated endpoint. Keep provenance."""
    parts: list[str] = []
    offset = 0
    while True:
        page = retry_call(lambda: wiki.article(page_id, offset=offset, max_chars=max_chars))
        parts.append(page.text)
        if page.next_offset is None:
            return {
                "page_id": page.page_id,
                "revision_id": page.revision_id,
                "title": page.title,
                "url": page.url,
                "provenance": page.provenance.model_dump(),
                "license": page.license,
                "total_chars": page.total_chars,
                "text": "".join(parts),
            }
        offset = page.next_offset


def match_tables(db_path: str | Path) -> tuple[Any, Any]:
    """Create the team's match evidence and article tables in the shared database."""
    import lancedb
    import pyarrow as pa

    db = lancedb.connect(str(db_path))
    evidence = db.create_table(
        "match_evidence",
        schema=pa.schema(
            [
                ("entry_id", pa.string()),
                ("page_id", pa.string()),
                ("candidate_page_id", pa.string()),
                ("candidate_title", pa.string()),
                ("bm25_rank", pa.int32()),
                ("bm25_score", pa.float64()),
                ("similarity", pa.float64()),
                ("rerank_logit", pa.float64()),
                ("decision", pa.string()),
            ]
        ),
        exist_ok=True,
    )
    articles = db.create_table(
        "wiki_articles",
        schema=pa.schema(
            [
                ("page_id", pa.string()),
                ("revision_id", pa.string()),
                ("title", pa.string()),
                ("url", pa.string()),
                ("text", pa.string()),
                ("text_sha256", pa.string()),
            ]
        ),
        exist_ok=True,
    )
    return evidence, articles


def summary_of(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Count unique articles and repeated article selections."""
    by_article: dict[str, list[str]] = {}
    for row in rows:
        by_article.setdefault(row["article_page_id"], []).append(row["entry_id"])
    repeats = [
        {"article_page_id": page_id, "entry_ids": entry_ids}
        for page_id, entry_ids in sorted(by_article.items())
        if len(entry_ids) > 1
    ]
    return {"unique_articles": len(by_article), "repeats": repeats}


def run_match(
    settings: Settings,
    work_dir: Path,
    *,
    threshold: float = MATCH_LOGIT_THRESHOLD,
    limit: int | None = None,
) -> dict[str, Any]:
    """Match every extracted entry. Resume skips entries already in the evidence file."""
    manifest = load_manifest()
    entries_path = work_dir / "extract" / "derived" / "entries.json"
    if not entries_path.exists():
        raise ValueError("no extracted entries found; run the extract stage first")
    entries = json.loads(entries_path.read_text(encoding="utf-8"))
    if limit is not None:
        entries = entries[:limit]
    match_dir = work_dir / "match"
    evidence_path = match_dir / EVIDENCE_NAME
    matches_path = match_dir / MATCHES_NAME
    articles_dir = match_dir / "articles"
    done = {row["entry_id"] for row in read_jsonl(evidence_path)}
    store = LanceArtifactStore(settings.db_path)
    evidence_table, articles_table = match_tables(settings.db_path)
    failures: list[dict[str, Any]] = []
    with WikiClient(settings.wikipedia_api_url) as wiki, RetrievalClient(
        settings.retrieval_base_url, settings.retrieval_api_key
    ) as retrieval:
        for index, entry in enumerate(entries, start=1):
            entry_id = entry["entry_id"]
            if entry_id in done:
                continue
            print(f"[match] {index}/{len(entries)} {entry_id} {entry['heading'][:50]}", file=sys.stderr, flush=True)
            try:
                search = retry_call(lambda: wiki.search(build_query(entry), top_k=CANDIDATES, excerpt_chars=1200))
                hits = search.hits
                if not hits:
                    append_jsonl(evidence_path, [{"entry_id": entry_id, "page_id": entry["page_id"],
                                                  "candidate_page_id": None, "candidate_title": None,
                                                  "bm25_rank": None, "bm25_score": None, "similarity": None,
                                                  "rerank_logit": None, "decision": "no-candidates"}])
                    continue
                rows = shortlist(retrieval, entry["body"], hits)
                reranked = rerank_candidates(retrieval, entry["body"], rows)
                best = decide(reranked, threshold)
                shortlist_by_id = {row["hit"].page_id: row for row in rows}
                logit_by_id = {row["row"]["hit"].page_id: row["logit"] for row in reranked}
                evidence_rows = []
                for rank, hit in enumerate(hits, start=1):
                    row = shortlist_by_id.get(hit.page_id)
                    if best is not None and hit.page_id == best["row"]["hit"].page_id:
                        decision = "matched"
                    elif best is None:
                        decision = "unmatched"
                    else:
                        decision = "candidate"
                    evidence_rows.append({
                        "entry_id": entry_id,
                        "page_id": entry["page_id"],
                        "candidate_page_id": hit.page_id,
                        "candidate_title": hit.title,
                        "bm25_rank": rank,
                        "bm25_score": hit.bm25_score,
                        "similarity": row["similarity"] if row else None,
                        "rerank_logit": logit_by_id.get(hit.page_id),
                        "decision": decision,
                    })
                append_jsonl(evidence_path, evidence_rows)
                if best is None:
                    continue
                hit = best["row"]["hit"]
                article_path = articles_dir / f"{hit.page_id}.json"
                if article_path.exists():
                    article = json.loads(article_path.read_text(encoding="utf-8"))
                else:
                    article = fetch_article(wiki, hit.page_id)
                    write_json(article_path, article)
                articles_table.merge_insert("page_id").when_matched_update_all().when_not_matched_insert_all().execute([
                    {"page_id": article["page_id"], "revision_id": article["revision_id"], "title": article["title"],
                     "url": article["url"], "text": article["text"],
                     "text_sha256": article["provenance"]["text_sha256"]}
                ])
                append_jsonl(matches_path, [{
                    "entry_id": entry_id,
                    "entry_title": entry["heading"],
                    "heading_class": entry.get("heading_class", ""),
                    "page_id": entry["page_id"],
                    "scan": entry.get("filename", ""),
                    "scan_sha256": entry.get("scan_sha256", ""),
                    "match_confidence": best["logit"],
                    "bm25_rank": next(row["bm25_rank"] for row in evidence_rows if row["candidate_page_id"] == hit.page_id),
                    "similarity": best["row"]["similarity"],
                    "article_page_id": article["page_id"],
                    "article_title": article["title"],
                    "article_revision_id": article["revision_id"],
                    "article_url": article["url"],
                    "article_text_sha256": article["provenance"]["text_sha256"],
                }])
                store.put(
                    ArtifactRecord(
                        record_id=f"match:{entry_id}",
                        stage="match",
                        sources=[
                            SourceReference(
                                dataset=manifest["dataset"],
                                dataset_revision=manifest["revision"],
                                source_id=entry["page_id"],
                                source_url=manifest["source_url"],
                                content_sha256=entry.get("scan_sha256") or "0" * 64,
                                license=str(manifest.get("license") or "CC0-1.0"),
                            ),
                            SourceReference(
                                dataset="wikimedia/structured-wikipedia",
                                dataset_revision=WIKIPEDIA_REVISION,
                                source_id=article["page_id"],
                                source_url=article["provenance"].get("revision_url", article["url"]),
                                content_sha256=article["provenance"]["text_sha256"],
                                license="CC-BY-SA-4.0",
                            ),
                        ],
                        artifact_path=str(article_path),
                        metadata={"threshold": threshold, "rerank_logit": best["logit"], "article_title": article["title"]},
                    )
                )
            except (ServiceError, ValueError, OSError) as exc:
                failures.append({"entry_id": entry_id, "error": f"{type(exc).__name__}: {exc}"})
    all_matches = read_jsonl(matches_path)
    evidence_all = read_jsonl(evidence_path)
    processed = {row["entry_id"] for row in evidence_all}
    matched_ids = {row["entry_id"] for row in all_matches}
    unresolved = {row["entry_id"] for row in evidence_all if row["decision"] in {"unmatched", "no-candidates"}}
    summary = summary_of(all_matches)
    summary.update({
        "entries_total": len(entries),
        "entries_processed": len(processed),
        "matched": len(matched_ids),
        "unmatched": len(unresolved - matched_ids),
        "threshold": threshold,
        "failures": failures,
    })
    write_json(match_dir / "summary.json", summary)
    return {"stage": "match", "artifacts": str(match_dir),
            **{key: summary[key] for key in ("entries_total", "entries_processed", "matched", "unmatched", "unique_articles")}}
