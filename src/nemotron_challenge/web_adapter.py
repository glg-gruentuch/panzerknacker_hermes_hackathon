"""Map saved pipeline artifacts to the web UI shapes.

The shapes follow ``web/API.md`` and ``web/src/api/types.ts``. The adapter
reads stored files only; no model call happens at request time. A stage that
has not run yet shows up as pending, never as an error.

Passage ids are the citation keys: Britannica paragraphs are ``B1...``,
Wikipedia paragraphs are ``W1...`` in reading order.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .compare import STOPWORDS, log_odds, normalize, top_terms
from .config import (EMBED_MODEL, EMBED_REVISION, MATCH_LOGIT_THRESHOLD, PARSE_MODEL, RERANK_MODEL,
                     RERANK_REVISION, SUPER_MODEL, WIKIPEDIA_REVISION)
from .data import load_manifest

# Match strength on the reranker raw logit for the hosted-NIM backend. The
# 2026-10-18 trial puts clear matches at or above STRONG_LOGIT and unrelated
# candidates below PARTIAL_LOGIT; see docs/nim-gateway.md.
STRONG_LOGIT = -4.5
PARTIAL_LOGIT = MATCH_LOGIT_THRESHOLD
CANDIDATE_LIMIT = 10


def strength_of(logit: float | None) -> str:
    """strong / partial / none for a reranker logit."""
    if logit is None:
        return "none"
    if logit >= STRONG_LOGIT:
        return "strong"
    if logit >= PARTIAL_LOGIT:
        return "partial"
    return "none"


def slugify(text: str) -> str:
    """Lowercase url slug: letters and digits, single hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def paragraphs(text: str) -> list[str]:
    """Split text on blank lines; drop empty parts."""
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


def sentence_count(text: str) -> int:
    return max(1, len(re.findall(r"[.!?](?:\s|$)", text))) if text.strip() else 0


def stats_for(text: str) -> dict[str, Any]:
    """words, sentences, average sentence length, distinct terms."""
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    sentences = sentence_count(text)
    return {
        "words": len(words),
        "sentences": sentences,
        "avgSentenceLength": round(len(words) / sentences, 1) if sentences else 0.0,
        "distinctTerms": len({word.lower() for word in words}),
    }


def wiki_url(title: str) -> str:
    """Wikipedia article URL built from a title."""
    return "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="()_-,.!")


def passage_id_for(quote: str, passages: list[dict[str, str]]) -> str | None:
    """The id of the first passage that contains the quote, case-insensitively."""
    folded = quote.lower()
    for passage in passages:
        if folded in passage["text"].lower():
            return passage["id"]
    return None


class WebAdapter:
    """Read-only view over one artifacts directory."""

    def __init__(self, work_dir: Path | str = Path("artifacts"),
                 scan_dir: Path | str = Path("data/raw/britannica"),
                 db_path: Path | str | None = None):
        self.work_dir = Path(work_dir)
        self.scan_dir = Path(scan_dir)
        self.db_path = Path(db_path) if db_path is not None else None
        self._cache: dict[str, Any] = {}

    # -- loading ---------------------------------------------------------

    def _json(self, relative: str) -> Any:
        path = self.work_dir / relative
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _jsonl(self, relative: str) -> list[dict[str, Any]]:
        path = self.work_dir / relative
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
        return rows

    def _cached(self, key: str, loader: Any) -> Any:
        if key not in self._cache:
            self._cache[key] = loader()
        return self._cache[key]

    def entries(self) -> list[dict[str, Any]]:
        return self._cached("entries", lambda: self._json("extract/derived/entries.json") or [])

    def matches(self) -> dict[str, dict[str, Any]]:
        return self._cached(
            "matches",
            lambda: {row["entry_id"]: row for row in self._jsonl("match/matches.jsonl")},
        )

    def evidence(self) -> dict[str, list[dict[str, Any]]]:
        def load() -> dict[str, list[dict[str, Any]]]:
            grouped: dict[str, list[dict[str, Any]]] = {}
            for row in self._jsonl("match/evidence.jsonl"):
                grouped.setdefault(row["entry_id"], []).append(row)
            return grouped

        return self._cached("evidence", load)

    def comparisons(self) -> dict[str, dict[str, Any]]:
        return self._cached(
            "comparisons",
            lambda: {row["entry_id"]: row for row in self._jsonl("compare/comparisons.jsonl")},
        )

    def claims(self) -> dict[str, dict[str, Any]]:
        return self._cached(
            "claims",
            lambda: {row["entry_id"]: row for row in self._jsonl("claims/claims.jsonl")},
        )

    def article(self, page_id: str) -> dict[str, Any] | None:
        return self._json(f"match/articles/{page_id}.json")

    # -- indexes ---------------------------------------------------------

    def entry_by_id(self, entry_id: str) -> dict[str, Any] | None:
        for entry in self.entries():
            if entry.get("entry_id") == entry_id:
                return entry
        return None

    def _page_index(self) -> dict[str, dict[str, str]]:
        """page_id / filename stem / filename -> {page_id, filename}."""

        def load() -> dict[str, dict[str, str]]:
            index: dict[str, dict[str, str]] = {}
            for entry in self.entries():
                page_id = entry.get("page_id") or ""
                filename = entry.get("filename") or ""
                if not page_id or not filename:
                    continue
                record = {"page_id": page_id, "filename": filename}
                index[page_id] = record
                index.setdefault(filename, record)
                index.setdefault(filename.rsplit(".", 1)[0], record)
            return index

        return self._cached("page_index", load)

    def resolve_page(self, name: str) -> dict[str, str] | None:
        """Resolve a scan name: full page_id, filename, or filename stem."""
        name = str(name).strip()
        for suffix in (".jpg", ".jpeg", ".png", ".webp", ".json"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        return self._page_index().get(name)

    def scan_path(self, name: str) -> Path | None:
        record = self.resolve_page(name)
        if record is None:
            return None
        path = self.scan_dir / record["filename"]
        return path if path.is_file() else None

    def raw_text(self, filename: str) -> str:
        """Everything Parse read off the page, markup stripped."""
        reply = self._json(f"extract/raw/{filename}.json")
        if not isinstance(reply, dict):
            return ""
        try:
            markdown = reply["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ""
        text = re.sub(r"<x_[0-9.]+>|<y_[0-9.]+>", "", markdown)
        text = re.sub(r"<class_[A-Za-z0-9_-]+>", "", text)
        return text.strip()

    # -- topics ----------------------------------------------------------

    def _label_and_slug(self, entry: dict[str, Any], used: set[str]) -> tuple[str, str]:
        heading = (entry.get("heading") or "").strip()
        filename = entry.get("filename") or ""
        stem = "-".join(filename.split("-")[:2]) or "page"
        if heading:
            label = heading.capitalize()
            base = slugify(heading)
        else:
            header = (entry.get("page_header") or "").strip()
            label = f"Fragment ({stem})" + (f" of {header}" if header else "")
            base = f"{stem}-fragment"
        slug = base or stem
        if slug in used:
            slug = f"{slug}-{stem}"
        suffix = 2
        while slug in used:
            slug = f"{base}-{stem}-{suffix}"
            suffix += 1
        used.add(slug)
        return label, slug

    def topics(self) -> dict[str, Any]:
        """Every indexed entry as a TopicSummary, plus pending notes."""
        pending: list[str] = []
        matches = self.matches()
        if not matches:
            pending.append("the match stage has not run; match strengths are unknown")
        rows = []
        used: set[str] = set()
        for entry in self.entries():
            label, slug = self._label_and_slug(entry, used)
            match = matches.get(entry.get("entry_id", ""))
            rows.append({
                "slug": slug,
                "label": label,
                "headword": entry.get("heading") or "",
                "edition": "Not recorded",
                "year": None,
                "match": strength_of(match.get("match_confidence")) if match else "none",
                "wikipediaTitle": match.get("article_title") if match else None,
            })
        return {"topics": rows, "pending": pending}

    # -- compare ---------------------------------------------------------

    def _fold(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.lower()).strip()

    def pick_entry(self, query: str) -> dict[str, Any] | None:
        """Find the entry a user query refers to. None when nothing matches."""
        q = self._fold(query)
        if not q:
            return None
        matches = self.matches()
        best: dict[str, Any] | None = None
        best_score = 0.0
        used: set[str] = set()
        for entry in self.entries():
            entry_id = (entry.get("entry_id") or "").lower()
            page_id = (entry.get("page_id") or "").lower()
            filename = entry.get("filename") or ""
            stem = filename.rsplit(".", 1)[0].lower()
            heading = self._fold(entry.get("heading") or "")
            header = self._fold(entry.get("page_header") or "")
            label, slug = self._label_and_slug(entry, used)
            label_fold, slug_fold = self._fold(label), slug.lower()
            body = self._fold(entry.get("body") or "")[:400]
            score = 0.0
            if q in {entry_id, page_id, stem, slug_fold}:
                score = 5.0
            elif q in {label_fold, heading}:
                score = 4.0
            elif (slug_fold.startswith(q) or heading.startswith(q) or label_fold.startswith(q)):
                score = 3.0
            elif q in slug_fold or q in heading or q in label_fold or q in header or q in body:
                score = 2.0
            elif len(q.split()) > 1 and all(token in f"{label_fold} {heading} {header} {body}"
                                            for token in q.split()):
                score = 1.0
            if score <= 0:
                continue
            if entry.get("entry_id") in matches:
                score += 0.5
            if not entry.get("fragment"):
                score += 0.25
            if score > best_score:
                best, best_score = entry, score
        return best

    def _britannica_page(self, entry: dict[str, Any]) -> dict[str, Any]:
        passages = [
            {"id": f"B{index}", "section": (entry.get("heading") or "(fragment)"), "text": part}
            for index, part in enumerate(paragraphs(entry.get("body") or ""), start=1)
        ]
        return {
            "pageId": (entry.get("filename") or "").rsplit(".", 1)[0],
            "headword": entry.get("heading") or "",
            "edition": "Not recorded",
            "year": None,
            "volume": entry.get("page_id", "").split(":")[-1],
            "meta": f"nls page {entry.get('page_id', '')} · scan {entry.get('scan_sha256', '')[:12]}",
            "imageUrl": f"/api/scans/{entry.get('filename', '').rsplit('.', 1)[0]}.jpg",
            "sourceUrl": None,
            "rawText": self.raw_text(entry.get("filename") or ""),
            "passages": passages,
        }

    def _wikipedia_article(self, article: dict[str, Any]) -> dict[str, Any]:
        # The stored article text has no section markers, so passages carry no
        # `section` value instead of a guessed heading.
        passages = [
            {"id": f"W{index}", "text": part}
            for index, part in enumerate(paragraphs(article.get("text") or ""), start=1)
        ]
        return {
            "identifier": article.get("page_id", ""),
            "title": article.get("title", ""),
            "url": article.get("url", ""),
            "dateModified": article.get("provenance", {}).get("date_modified", ""),
            "passages": passages,
        }

    def _match_info(self, row: dict[str, Any] | None, candidate_count: int) -> dict[str, Any]:
        if row is None:
            return {
                "strength": "none",
                "embedScore": None,
                "rerankScore": None,
                "reasons": ["No accepted match above the rerank threshold."],
            }
        logit = row.get("match_confidence")
        return {
            "strength": strength_of(logit),
            "embedScore": row.get("similarity"),
            "rerankScore": logit,
            "reasons": [
                f"{row.get('article_title', 'article')} accepted at reranker logit {logit:.2f}, "
                f"threshold {MATCH_LOGIT_THRESHOLD}.",
                f"Funnel among {candidate_count} candidates: BM25 rank {row.get('bm25_rank')}, "
                f"embed rank {row.get('embed_rank')}, rerank rank {row.get('rerank_rank')}.",
                "Reranker nvidia/llama-nemotron-rerank-vl-1b-v2; Wikipedia text CC BY-SA 4.0.",
            ],
        }

    def _candidates(self, entry_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.evidence().get(entry_id, [])
                if row.get("candidate_page_id") or row.get("candidate_title")]
        rows.sort(key=lambda row: (row.get("rerank_logit") is None,
                                   -(row.get("rerank_logit") or -1e9),
                                   row.get("bm25_rank") or 10_000))
        return [
            {
                "title": row.get("candidate_title") or "",
                "url": wiki_url(row.get("candidate_title") or ""),
                "embedScore": row.get("embed_similarity"),
                "rerankScore": row.get("rerank_logit"),
            }
            for row in rows[:CANDIDATE_LIMIT]
        ]

    def _alignments(self, entry_id: str, brit_passages: list[dict[str, str]],
                    wiki_passages: list[dict[str, str]]) -> tuple[list[dict[str, Any]], bool]:
        record = self.claims().get(entry_id)
        if not record:
            return [], True
        alignments = []
        for index, claim in enumerate(record.get("claims") or [], start=1):
            quote_text = claim.get("quote") or ""
            wikipedia_quote = claim.get("wikipedia_quote")
            brit_pid = passage_id_for(quote_text, brit_passages)
            wiki_pid = passage_id_for(wikipedia_quote, wiki_passages) if wikipedia_quote else None
            alignments.append({
                "id": f"a{index}",
                "kind": "inference",
                "verdict": claim.get("verdict"),
                "label": claim.get("type") or "claim",
                "britannica": {"passageId": brit_pid, "quote": quote_text} if brit_pid else None,
                "wikipedia": {"passageId": wiki_pid, "quote": wikipedia_quote} if wiki_pid else None,
                "note": claim.get("explanation", {}).get("text", "") if isinstance(claim.get("explanation"), dict)
                        else str(claim.get("explanation") or ""),
                "type": claim.get("type"),
                "value": claim.get("value"),
                "unit": claim.get("unit"),
                "downgraded": bool(claim.get("downgraded", False)),
            })
        return alignments, False

    def _vocabulary(self, entry_id: str, entry: dict[str, Any],
                    article: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
        record = self.comparisons().get(entry_id)
        if record:
            brit = record.get("britannica", {})
            wiki = record.get("wikipedia", {})
            brit_tokens = max(brit.get("tokens", 0), 1)
            wiki_tokens = max(wiki.get("tokens", 0), 1)
            shared = {term for term, _ in brit.get("top_terms", [])} & {term for term, _ in wiki.get("top_terms", [])}
            return {
                "britannica": [{"term": row["term"], "count": row["count_a"],
                                "per1k": round(row["count_a"] * 1000 / brit_tokens, 2)}
                               for row in record.get("distinctive", {}).get("britannica", [])[:10]],
                "wikipedia": [{"term": row["term"], "count": row["count_b"],
                               "per1k": round(row["count_b"] * 1000 / wiki_tokens, 2)}
                              for row in record.get("distinctive", {}).get("wikipedia", [])[:10]],
                "shared": sorted(shared)[:10],
            }, False
        if article is None:
            return {"britannica": [], "wikipedia": [], "shared": []}, True
        brit_tokens, _ = normalize(entry.get("body") or "")
        wiki_tokens, _ = normalize(article.get("text") or "")
        brit_counts = Counter(token for token in brit_tokens if token not in STOPWORDS)
        wiki_counts = Counter(token for token in wiki_tokens if token not in STOPWORDS)
        brit_total = max(sum(brit_counts.values()), 1)
        wiki_total = max(sum(wiki_counts.values()), 1)
        return {
            "britannica": [{"term": row["term"], "count": row["count_a"],
                            "per1k": round(row["count_a"] * 1000 / brit_total, 2)}
                           for row in log_odds(brit_counts, wiki_counts)],
            "wikipedia": [{"term": row["term"], "count": row["count_b"],
                           "per1k": round(row["count_b"] * 1000 / wiki_total, 2)}
                          for row in log_odds(wiki_counts, brit_counts)],
            "shared": sorted({term for term, _ in top_terms(brit_tokens)} &
                             {term for term, _ in top_terms(wiki_tokens)}),
        }, False

    def _coverage(self, entry_id: str) -> tuple[list[dict[str, Any]], bool]:
        record = self.claims().get(entry_id)
        if not record:
            return [], True
        sections = record.get("section_coverage") or []
        if not sections:
            return [], True
        total = max(sum(int(row.get("claims", 0)) for row in sections), 1)
        return [
            {
                "topic": row.get("section") or "Introduction",
                "britannica": round(int(row.get("claims", 0)) / total, 3),
                "wikipedia": 1.0 if row.get("covered") else 0.0,
            }
            for row in sections
        ], False

    def _suggested_questions(self, label: str) -> list[str]:
        questions = []
        for case in self.cases().get("cases", []):
            if self._fold(case.get("topic", "")) and self._fold(case.get("topic", "")) in self._fold(label):
                questions.append(case.get("question", ""))
        return [q for q in questions if q][:3]

    def compare(self, query: str) -> dict[str, Any] | None:
        """One Comparison, or None when nothing in the index matches."""
        entry = self.pick_entry(query)
        if entry is None:
            return None
        entry_id = entry.get("entry_id", "")
        pending: list[str] = []
        match = self.matches().get(entry_id)
        article = self.article(match["article_page_id"]) if match else None
        if match and article is None:
            pending.append("the stored Wikipedia article file is missing")
        britannica = self._britannica_page(entry)
        wikipedia = self._wikipedia_article(article) if article else None
        if not self.matches():
            pending.append("the match stage has not run")
        elif match is None:
            pending.append("no accepted match for this entry; candidates come from the evidence funnel")
        candidates = self._candidates(entry_id)
        alignments, claims_pending = self._alignments(
            entry_id, britannica["passages"], wikipedia["passages"] if wikipedia else [])
        if claims_pending:
            pending.append("claims are pending; run the claims stage")
        vocabulary, vocab_pending = self._vocabulary(entry_id, entry, article)
        if vocab_pending:
            pending.append("vocabulary is pending; run the compare stage")
        coverage, coverage_pending = self._coverage(entry_id)
        if coverage_pending:
            pending.append("coverage is pending; run the claims stage")
        used: set[str] = set()
        label, slug = self._label_and_slug(entry, used)
        topic = {
            "slug": slug,
            "label": label,
            "headword": entry.get("heading") or "",
            "edition": "Not recorded",
            "year": None,
            "match": strength_of(match.get("match_confidence")) if match else "none",
            "wikipediaTitle": match.get("article_title") if match else None,
        }
        return {
            "query": query,
            "topic": topic,
            "britannica": britannica,
            "wikipedia": wikipedia,
            "match": self._match_info(match, len(self.evidence().get(entry_id, []))),
            "candidates": candidates,
            "alignments": alignments,
            "vocabulary": vocabulary,
            "coverage": coverage,
            "stats": {
                "britannica": stats_for(entry.get("body") or ""),
                "wikipedia": stats_for(article.get("text") or "") if article else None,
            },
            "suggestedQuestions": self._suggested_questions(label),
            "pending": pending,
        }

    # -- meta and cases --------------------------------------------------

    def search(self, query: str, limit: int = 10) -> dict[str, Any]:
        """Full-text search over the LanceDB tables (B3). No model call.

        Reads ``britannica_entries.body`` and ``wiki_paragraphs.text`` through
        their FTS indexes and returns ids, headings, and scores. When the store
        is missing, reports an empty result with a note instead of an error.
        """
        if not query.strip():
            return {"query": query, "results": [], "note": "empty query"}
        if self.db_path is None or not self.db_path.exists():
            return {"query": query, "results": [],
                    "note": "the LanceDB store is not configured for this app"}
        try:
            from .lancedb_sync import connect, search_entries_fts, search_paragraphs_fts

            db = connect(self.db_path)
            matches = search_entries_fts(db, query, limit=limit)
            paragraphs_hits = search_paragraphs_fts(db, query, limit=limit)
        except Exception as exc:
            return {"query": query, "results": [], "note": f"the LanceDB store is unavailable: {exc}"}
        if matches is None or paragraphs_hits is None:
            return {"query": query, "results": [],
                    "note": "the LanceDB store carries no full-text index yet; rerun the match stage"}
        results = [{"kind": "entry", "entry_id": row["entry_id"], "heading": row.get("heading"),
                    "score": row["score"]} for row in matches]
        results += [{"kind": "paragraph", "page_id": row["page_id"], "revision_id": row["revision_id"],
                     "paragraph_index": row["paragraph_index"], "score": row["score"]}
                    for row in paragraphs_hits]
        results.sort(key=lambda row: -row["score"])
        return {"query": query, "results": results[:limit]}

    def meta(self) -> dict[str, Any]:
        """Evidence-driven project meta (B4).

        A model or store appears only when a saved artifact shows that the
        pipeline used it; each row names its evidence path. The mock list in
        web/src/api/mock/ is not copied.
        """
        manifest = load_manifest()
        revision = manifest.get("revision", "")
        lancedb = self._json("lancedb-summary.json") or {}
        tables = lancedb.get("tables", {}) if isinstance(lancedb.get("tables"), dict) else {}

        def exists(relative: str) -> bool:
            return (self.work_dir / relative).exists()

        models: list[dict[str, Any]] = []
        if exists("extract/coverage.json") or any((self.work_dir / "extract" / "raw").glob("*.json")):
            models.append({"role": "Reads the page scans", "name": PARSE_MODEL,
                           "host": "Organiser shared endpoint",
                           "evidence": "artifacts/extract/coverage.json"})
        if exists("match/evidence.jsonl") or tables.get("match_evidence"):
            models.append({"role": "Embeds passages and questions",
                           "name": f"{EMBED_MODEL} (pinned revision {EMBED_REVISION[:7]})",
                           "host": "Team Nebius deployment",
                           "evidence": "artifacts/match/evidence.jsonl"})
            models.append({"role": "Reranks candidates",
                           "name": f"{RERANK_MODEL} (pinned revision {RERANK_REVISION[:7]})",
                           "host": "Team Nebius deployment",
                           "evidence": "artifacts/match/evidence.jsonl"})
        if exists("lancedb-summary.json") and any(count for count in tables.values() if count):
            models.append({"role": "Stores and searches evidence", "name": "LanceDB",
                           "host": f"Backend ({self.db_path or 'data/team.lancedb'})",
                           "evidence": "artifacts/lancedb-summary.json"})
        if exists("claims/claims.jsonl"):
            models.append({"role": "Extracts and judges claims", "name": SUPER_MODEL,
                           "host": "Nebius Token Factory", "evidence": "artifacts/claims/summary.json"})
        if exists("agent/report.json"):
            models.append({"role": "Answers questions", "name": f"{SUPER_MODEL} via Hermes Agent",
                           "host": "Nebius Token Factory", "evidence": "artifacts/agent/report.json"})
        return {
            "datasets": [
                {
                    "name": "Encyclopaedia Britannica Illustrated",
                    "source": "National Library of Scotland, via Hugging Face",
                    "url": "https://huggingface.co/datasets/NationalLibraryOfScotland/encyclopaedia_britannica_illustrated",
                    "version": f"Revision {revision[:7]} ({manifest.get('source_rows')} page scans, 1768-1860), sample of {manifest.get('sample_size')}",
                    "downloaded": "2026-10-18",
                },
                {
                    "name": "Wikipedia Structured Contents",
                    "source": "Wikimedia Foundation, served through the shared organizer BM25 API",
                    "url": "https://kaggle.com/datasets/wikimedia-foundation/wikipedia-structured-contents",
                    "version": f"Snapshot {WIKIPEDIA_REVISION[:7]}, 7,182,883 articles",
                    "downloaded": "queried live on 2026-10-18",
                },
            ],
            "models": models,
            "matchLogitThreshold": MATCH_LOGIT_THRESHOLD,
            "sample": {
                "size": manifest.get("sample_size", 100),
                "method": ("random_without_replacement, seed 20261016, sorted by source row index; "
                           "98 pages produced text, 2 non-text scans recorded as failures"),
            },
        }

    def cases(self) -> dict[str, Any]:
        report = self._json("agent/report.json")
        if not report:
            return {"cases": [], "pending": ["agent cases are pending; run the agent stage"]}
        documented = report.get("case_studies")
        if documented:
            return {"cases": documented, "pending": []}
        rows = []
        for row in report.get("cases", []):
            runs_dir = self.work_dir / "agent" / "runs" / row.get("case_id", "")
            excerpt = ""
            stdout = runs_dir / "stdout.txt"
            if stdout.exists():
                excerpt = stdout.read_text(encoding="utf-8").strip()[-600:]
            rows.append({
                "id": row.get("case_id", ""),
                "outcome": "success" if row.get("passed") else "failure",
                "title": row.get("case_id", ""),
                "topic": "",
                "question": "",
                "answerExcerpt": excerpt,
                "diagnosis": f"returncode {row.get('returncode')}, expected {row.get('expected')}",
                "lesson": "",
            })
        return {"cases": rows, "pending": ["case studies are pending; write docs/cases files"]}

    def page_blocks(self, name: str) -> dict[str, Any] | None:
        record = self.resolve_page(name)
        if record is None:
            return None
        derived = self._json(f"extract/derived/{record['filename']}.json")
        if not isinstance(derived, dict):
            return None
        blocks = []
        for entry in derived.get("entries", []):
            for block in entry.get("blocks", []):
                blocks.append({
                    "entryId": entry.get("entry_id"),
                    "class": block.get("class"),
                    "text": block.get("text"),
                    "bbox": block.get("bbox"),
                })
        return {
            "pageId": record["page_id"],
            "filename": record["filename"],
            "pageHeader": derived.get("page_header", ""),
            "blocks": blocks,
        }
