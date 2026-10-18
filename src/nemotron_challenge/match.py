"""Match entries to Wikipedia articles with BM25 candidates, embeddings, and reranking."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .clients import RetrievalClient, ServiceError, WikiClient
from .compare import STOPWORDS
from .config import MATCH_LOGIT_THRESHOLD, WIKIPEDIA_REVISION, Settings
from .contracts import ArtifactRecord, SourceReference
from .data import load_manifest
from .pipeline import append_jsonl, read_jsonl, retry_call, write_json
from .storage import LanceArtifactStore

EVIDENCE_NAME = "evidence.jsonl"
MATCHES_NAME = "matches.jsonl"
CANDIDATES = 30
FRAGMENT_QUERY_WORDS = 8
# The shared search service rejects longer queries (a 64-word query returns 422
# with "at most 64 words"). Stay well below the boundary.
QUERY_WORD_LIMIT = 48

CONTENT_WORD = re.compile(r"[a-z][a-z\-]*")
SENTENCE_END = re.compile(r"[.!?](?:\s|$)")


def content_words(text: str) -> list[str]:
    """Meaning-carrying words: letters and hyphens, three or more characters, no stopwords."""
    words = [word.strip("-") for word in CONTENT_WORD.findall(text.lower())]
    return [word for word in words if len(word) >= 3 and word not in STOPWORDS]


def word_frequencies(entries: list[dict[str, Any]]) -> Counter[str]:
    """How many entries hold each content word (document frequency).

    Fragment queries pick their rarest words against this corpus count.
    """
    frequencies: Counter[str] = Counter()
    for entry in entries:
        for word in set(content_words(entry.get("body") or "")):
            frequencies[word] += 1
    return frequencies


def rarest_query_words(text: str, frequencies: Counter[str], limit: int = FRAGMENT_QUERY_WORDS) -> list[str]:
    """The rarest content words of a body, rarest first.

    Ties prefer the longer word, then the earlier appearance.
    """
    words = content_words(text)
    first_seen: dict[str, int] = {}
    for position, word in enumerate(words):
        first_seen.setdefault(word, position)
    ranked = sorted(first_seen, key=lambda word: (frequencies.get(word, 1), -len(word), first_seen[word]))
    return ranked[:limit]


def first_sentence(text: str) -> str:
    """Text up to and including the first sentence end. Whitespace is collapsed."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    match = SENTENCE_END.search(cleaned)
    return cleaned[: match.end()].strip() if match else cleaned


def build_query(entry: dict[str, Any], frequencies: Counter[str] | None = None) -> str:
    """BM25 query text within 512 characters and the shared word limit.

    A headword entry contributes its heading plus the first sentence of the
    body. A fragment contributes the eight rarest content words of its body.
    """
    heading = (entry.get("heading") or "").strip()
    body = (entry.get("body") or "").strip()
    if entry.get("fragment") or not heading:
        text = " ".join(rarest_query_words(body, frequencies or Counter()))
    else:
        opening = first_sentence(body)
        if opening and opening.lower().startswith(heading.lower()):
            parts = [opening]
        else:
            parts = [heading, opening]
        text = " ".join(part for part in parts if part)
    text = re.sub(r"\s+", " ", text).strip()
    return " ".join(text.split()[:QUERY_WORD_LIMIT])[:512]


def entry_query(entry: dict[str, Any]) -> str:
    """Retrieval text for one entry. Heading-only entries use the heading."""
    body = (entry.get("body") or "").strip()
    if body:
        return body
    return (entry.get("heading") or "").strip()


def embed_documents(retrieval: RetrievalClient, texts: list[str]) -> list[list[float]]:
    """Embed document texts in batches within the service limit of 16 items."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), 16):
        batch = texts[start : start + 16]
        vectors.extend(retry_call(lambda: retrieval.embed(batch, input_type="document")))
    return vectors


def shortlist(retrieval: RetrievalClient, entry_text: str, hits: list[Any],
              keep: int | None = None) -> list[dict[str, Any]]:
    """Rank every candidate by embedding similarity. ``keep`` optionally cuts the list.

    The embedder sees each excerpt as a document and the entry text as the
    query. Similarity is the dot product of unit vectors. A candidate without
    excerpt text cannot be scored; it stays in the list with a null similarity.
    """
    query_vector = retry_call(lambda: retrieval.embed([entry_text[:2000]], input_type="query"))[0]
    scored: list[dict[str, Any]] = []
    embeddable = []
    texts = []
    for hit in hits:
        excerpt = (hit.excerpt or "").strip()
        if excerpt:
            embeddable.append(hit)
            texts.append(excerpt[:32000])
        else:
            scored.append({"hit": hit, "similarity": None, "embed_rank": None})
    vectors = embed_documents(retrieval, texts) if texts else []
    for hit, vector in zip(embeddable, vectors):
        scored.append({"hit": hit, "similarity": sum(a * b for a, b in zip(query_vector, vector))})
    scored.sort(key=lambda row: (row["similarity"] is None, -(row["similarity"] or 0.0)))
    for rank, row in enumerate((row for row in scored if row["similarity"] is not None), start=1):
        row["embed_rank"] = rank
    return scored[:keep] if keep is not None else scored


def rerank_candidates(retrieval: RetrievalClient, entry_text: str, rows: list[dict[str, Any]],
                      top_n: int | None = None) -> list[dict[str, Any]]:
    """Rerank the candidate rows in one request; the service takes up to 32.

    Result rows index into rows; scores are raw logits; the reply order is the
    rerank rank. Rows without excerpt text are returned unscored.
    """
    scoreable = [row for row in rows if (row["hit"].excerpt or "").strip()]
    unscored = [{"row": row, "logit": None, "rerank_rank": None} for row in rows if not (row["hit"].excerpt or "").strip()]
    if not scoreable:
        return unscored
    reply = retry_call(
        lambda: retrieval.rerank(entry_text[:2000], [row["hit"].excerpt[:32000] for row in scoreable], top_n=top_n)
    )
    reranked = [
        {"row": scoreable[item["index"]], "logit": item["relevance_score"], "rerank_rank": rank}
        for rank, item in enumerate(reply, start=1)
    ]
    return reranked + unscored


def decide(reranked: list[dict[str, Any]], threshold: float) -> dict[str, Any] | None:
    """Return the best candidate at or above the threshold. Scores are raw logits."""
    candidates = [row for row in reranked if row.get("logit") is not None]
    if not candidates:
        return None
    best = max(candidates, key=lambda row: row["logit"])
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
                ("embed_similarity", pa.float64()),
                ("embed_rank", pa.int32()),
                ("rerank_logit", pa.float64()),
                ("rerank_rank", pa.int32()),
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
    frequencies = word_frequencies(entries)
    match_dir = work_dir / "match"
    evidence_path = match_dir / EVIDENCE_NAME
    matches_path = match_dir / MATCHES_NAME
    articles_dir = match_dir / "articles"
    done = {row["entry_id"] for row in read_jsonl(evidence_path)}
    store = LanceArtifactStore(settings.db_path)
    _evidence_table, articles_table = match_tables(settings.db_path)
    failures: list[dict[str, Any]] = []
    with WikiClient(settings.wikipedia_api_url) as wiki, RetrievalClient(
        settings.retrieval_base_url, settings.retrieval_api_key
    ) as retrieval:
        for index, entry in enumerate(entries, start=1):
            entry_id = entry["entry_id"]
            if entry_id in done:
                continue
            print(f"[match] {index}/{len(entries)} {entry_id} {(entry.get('heading') or '(fragment)')[:50]}",
                  file=sys.stderr, flush=True)
            try:
                query = build_query(entry, frequencies)
                if not query:
                    # B1 pages can carry no text (full-page pictures). Querying
                    # the wiki API with an empty string fails; record the fact.
                    append_jsonl(evidence_path, [{"entry_id": entry_id, "page_id": entry["page_id"],
                                                  "candidate_page_id": None, "candidate_title": None,
                                                  "bm25_rank": None, "bm25_score": None, "embed_similarity": None,
                                                  "embed_rank": None, "rerank_logit": None, "rerank_rank": None,
                                                  "decision": "no-candidates",
                                                  "note": "the entry has no text to query"}])
                    continue
                search = retry_call(lambda: wiki.search(query, top_k=CANDIDATES, excerpt_chars=1200))
                hits = search.hits
                if not hits:
                    append_jsonl(evidence_path, [{"entry_id": entry_id, "page_id": entry["page_id"],
                                                  "candidate_page_id": None, "candidate_title": None,
                                                  "bm25_rank": None, "bm25_score": None, "embed_similarity": None,
                                                  "embed_rank": None, "rerank_logit": None, "rerank_rank": None,
                                                  "decision": "no-candidates"}])
                    continue
                query_text = entry_query(entry)
                rows = shortlist(retrieval, query_text, hits)
                reranked = rerank_candidates(retrieval, query_text, rows)
                best = decide(reranked, threshold)
                similarity_by_id = {row["hit"].page_id: row["similarity"] for row in rows}
                embed_rank_by_id = {row["hit"].page_id: row["embed_rank"] for row in rows}
                logit_by_id = {row["row"]["hit"].page_id: row["logit"] for row in reranked}
                rerank_rank_by_id = {row["row"]["hit"].page_id: row["rerank_rank"] for row in reranked}
                evidence_rows = []
                for rank, hit in enumerate(hits, start=1):
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
                        "embed_similarity": similarity_by_id.get(hit.page_id),
                        "embed_rank": embed_rank_by_id.get(hit.page_id),
                        "rerank_logit": logit_by_id.get(hit.page_id),
                        "rerank_rank": rerank_rank_by_id.get(hit.page_id),
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
                    "fragment": bool(entry.get("fragment", False)),
                    "page_id": entry["page_id"],
                    "scan": entry.get("filename", ""),
                    "scan_sha256": entry.get("scan_sha256", ""),
                    "match_confidence": best["logit"],
                    "bm25_rank": next(row["bm25_rank"] for row in evidence_rows if row["candidate_page_id"] == hit.page_id),
                    "similarity": best["row"]["similarity"],
                    "embed_rank": best["row"]["embed_rank"],
                    "rerank_rank": rerank_rank_by_id.get(hit.page_id),
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
    coverage_path = work_dir / "extract" / "coverage.json"
    coverage: dict[str, Any] = {}
    if coverage_path.exists():
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    entry_pages = {row["page_id"] for row in entries}
    failed_pages = coverage.get("failures", [])
    summary = summary_of(all_matches)
    summary.update({
        "pages_total": coverage.get("pages_total", len(entry_pages) + len(failed_pages)),
        "pages_with_text": coverage.get("pages_ok", len(entry_pages)),
        "pages_failed": coverage.get("pages_failed", len(failed_pages)),
        "failed_pages": failed_pages,
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
