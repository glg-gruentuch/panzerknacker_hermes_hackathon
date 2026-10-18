"""Claim alignment between matched Britannica entries and Wikipedia articles.

For each matched entry:
1. Super VL extracts up to eight atomic claims from the Britannica body. Every
   quote must be an exact substring of that text; other claims are dropped and
   counted.
2. The article is split into paragraphs. Paragraphs and the claim are
   embedded; the top ten paragraphs are reranked and the top three are kept.
   Both scores are stored per paragraph.
3. Super VL judges the claim against the three paragraphs and returns a
   verdict, an exact Wikipedia quote, and an explanation (kind inference).
   A quote that fails the substring check downgrades the claim to
   not_in_wikipedia.
4. Coverage records whether any claim aligned to the article.

Model replies are cached by (entry_id, article_revision_id, prompt_hash), so a
re-run skips finished work. Failures land in failures.jsonl and are never
replaced by guessed results.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .clients import ChatClient, ProtocolError, RetrievalClient, ServiceError
from .config import SUPER_MODEL, Settings
from .contracts import ArtifactRecord, SourceReference
from .data import load_manifest
from .pipeline import read_jsonl, retry_call, write_json
from .storage import LanceArtifactStore
from .web_adapter import paragraphs

CLAIMS_NAME = "claims.jsonl"
MATCHES_NAME = "matches.jsonl"
FAILURES_NAME = "failures.jsonl"
CACHE_DIRNAME = "cache"
MAX_CONCURRENT = 8
MAX_CLAIMS = 8
EMBED_DEPTH = 10
JUDGE_DEPTH = 3
BODY_CHAR_LIMIT = 12000
CLAIM_TYPES = ("definition", "quantity", "place", "date", "cause", "practice")
VERDICTS = ("agrees", "differs", "contradicts", "not_in_wikipedia")

EXTRACT_SYSTEM = (
    "You read historical encyclopaedia text and extract atomic factual claims. "
    "You reply with one JSON object and nothing else."
)
EXTRACT_TEMPLATE = """Extract up to {maximum} atomic factual claims from the Britannica text below.

Reply with one JSON object:
{{"claims": [{{"quote": "...", "type": "definition|quantity|place|date|cause|practice", "value": 0, "unit": ""}}]}}

Rules:
- "quote" must be copied exactly from the text below, an exact substring with the same spelling and punctuation.
- One claim per sentence or clause. Keep each quote under 200 characters.
- "value" and "unit" only for type "quantity"; omit them otherwise.
- Do not add claims the text does not state. Reply with JSON only.

Text:
{body}"""

JUDGE_SYSTEM = (
    "You compare one historical encyclopaedia claim with modern Wikipedia passages. "
    "You reply with one JSON object and nothing else."
)
JUDGE_TEMPLATE = """Compare the Britannica claim with the Wikipedia passages below.

Reply with one JSON object:
{{"verdict": "agrees|differs|contradicts|not_in_wikipedia", "wikipedia_quote": "...", "explanation": "..."}}

Rules:
- agrees: a passage states the same fact.
- differs: a passage covers the fact but a detail changed (numbers, dates, places, names).
- contradicts: a passage states the opposite.
- not_in_wikipedia: no passage covers the claim.
- "wikipedia_quote" must be copied exactly from one passage below when the verdict is not not_in_wikipedia; otherwise use "".
- "explanation": one or two sentences on what changed or why nothing covers the claim.
- Reply with JSON only.

Claim (Britannica, historical): {quote}

Passages:
{passages}"""

_append_lock = threading.Lock()


def prompt_material(model: str, messages: list[dict[str, Any]]) -> str:
    """Stable text for hashing one call: model, roles, and content."""
    parts = [model]
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            content = json.dumps(content, sort_keys=True, ensure_ascii=False)
        parts.append(f"{message.get('role')}:{content}")
    return "\n".join(parts)


def prompt_hash(model: str, messages: list[dict[str, Any]]) -> str:
    return hashlib.sha256(prompt_material(model, messages).encode("utf-8")).hexdigest()


def cache_key(entry_id: str, article_revision_id: str, model: str, messages: list[dict[str, Any]]) -> str:
    material = f"{entry_id}|{article_revision_id}|{prompt_hash(model, messages)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:40]


def parse_json_object(content: str) -> dict[str, Any] | None:
    """Find the JSON object in a model reply. None when there is none."""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except ValueError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        return None


def valid_claims(payload: dict[str, Any] | None, body: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Claims with exact-substring quotes and known types. Everything else is dropped."""
    claims: list[dict[str, Any]] = []
    drops = {"malformed": 0, "quote_not_found": 0, "invalid_type": 0, "over_limit": 0}
    raw = payload.get("claims") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        return claims, drops
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("quote"), str) or not item["quote"].strip():
            drops["malformed"] += 1
            continue
        quote = item["quote"].strip()
        if quote not in body:
            drops["quote_not_found"] += 1
            continue
        claim_type = item.get("type")
        if claim_type not in CLAIM_TYPES:
            drops["invalid_type"] += 1
            continue
        if len(claims) >= MAX_CLAIMS:
            drops["over_limit"] += 1
            continue
        claim: dict[str, Any] = {"quote": quote, "type": claim_type}
        if claim_type == "quantity":
            value = item.get("value")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                claim["value"] = value
            if isinstance(item.get("unit"), str) and item["unit"].strip():
                claim["unit"] = item["unit"].strip()
        claims.append(claim)
    return claims, drops


def judged_claim(claim: dict[str, Any], payload: dict[str, Any] | None, kept_texts: list[str],
                 judge_error: str = "") -> dict[str, Any]:
    """One claim enriched with the judge verdict; bad quotes downgrade."""
    judged = dict(claim)
    if payload is None:
        judged["verdict"] = "not_in_wikipedia"
        judged["wikipedia_quote"] = None
        judged["downgraded"] = True
        judged["explanation"] = {"kind": "inference",
                                 "text": f"The judge reply was unusable: {judge_error or 'no JSON object returned'}."}
        return judged
    verdict = payload.get("verdict")
    quote = payload.get("wikipedia_quote")
    if not isinstance(quote, str) or not quote.strip():
        quote = None
    explanation = payload.get("explanation")
    if isinstance(explanation, dict):
        explanation = explanation.get("text") or explanation.get("note") or json.dumps(explanation, ensure_ascii=False)
    explanation = str(explanation).strip() if explanation else ""
    quote_ok = bool(quote) and any(quote in text for text in kept_texts)
    downgraded = False
    if verdict not in VERDICTS:
        verdict = "not_in_wikipedia"
        downgraded = True
        explanation = (f"The judge reply did not carry a valid verdict. {explanation}").strip()
    if verdict != "not_in_wikipedia" and not quote_ok:
        verdict = "not_in_wikipedia"
        downgraded = True
        explanation = (f"The Wikipedia quote failed the substring check. {explanation}").strip()
    judged["verdict"] = verdict
    judged["wikipedia_quote"] = quote if quote_ok else None
    if not quote_ok and quote:
        judged["rejected_wikipedia_quote"] = quote
    judged["downgraded"] = downgraded
    judged["explanation"] = {"kind": "inference", "text": explanation}
    return judged


class ClaimsRun:
    """Shared clients, cache, and failure sink for one run."""

    def __init__(self, settings: Settings, work_dir: Path, *, workers: int = MAX_CONCURRENT,
                 deadline: float | None = None):
        self.settings = settings
        self.work_dir = Path(work_dir)
        self.claims_dir = self.work_dir / "claims"
        self.cache_dir = self.claims_dir / CACHE_DIRNAME
        self.claims_path = self.claims_dir / CLAIMS_NAME
        self.failures_path = self.claims_dir / FAILURES_NAME
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        self.workers = max(1, min(int(workers), MAX_CONCURRENT))
        self.deadline = deadline
        self.failures: list[dict[str, Any]] = []
        self.chat_calls = 0
        self.skipped = 0

    def cached_chat(self, chat: ChatClient, entry_id: str, revision_id: str, messages: list[dict[str, Any]],
                    *, max_tokens: int, stage: str) -> dict[str, Any]:
        """One cached Super VL call. Cache hits skip the model call entirely."""
        key = cache_key(entry_id, revision_id, SUPER_MODEL, messages)
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                pass

        def call_budget(budget: int) -> dict[str, Any]:
            self.chat_calls += 1
            return retry_call(lambda: chat.complete(messages, max_tokens=budget))

        try:
            try:
                reply = call_budget(max_tokens)
            except ProtocolError as exc:
                if "incomplete" not in str(exc):
                    raise
                reply = call_budget(min(max_tokens + 1500, 16384))
        except (ServiceError, ValueError) as exc:
            with _append_lock:
                self.failures.append({"entry_id": entry_id, "stage": stage,
                                      "error": f"{type(exc).__name__}: {exc}"})
            raise
        write_json(path, reply)
        return reply

    def reply_content(self, reply: dict[str, Any]) -> str:
        return reply["choices"][0]["message"]["content"]

    def process_entry(self, chat: ChatClient, retrieval: RetrievalClient, entry: dict[str, Any],
                      match: dict[str, Any], article: dict[str, Any]) -> dict[str, Any] | None:
        """Extract, retrieve, judge, and cover one matched pair."""
        if self.deadline is not None and time.time() >= self.deadline:
            with _append_lock:
                self.skipped += 1
            return None
        entry_id = entry["entry_id"]
        revision_id = match["article_revision_id"]
        body = entry.get("body") or ""
        if not body.strip():
            raise ValueError("the entry has no body text")
        paragraph_texts = paragraphs(article.get("text") or "")
        if not paragraph_texts:
            raise ValueError("the article has no paragraph text")

        # Stage 1: extract claims.
        messages = [
            {"role": "system", "content": EXTRACT_SYSTEM},
            {"role": "user", "content": EXTRACT_TEMPLATE.format(maximum=MAX_CLAIMS,
                                                                body=body[:BODY_CHAR_LIMIT])},
        ]
        reply = self.cached_chat(chat, entry_id, revision_id, messages, max_tokens=2500, stage="extract")
        claims, drops = valid_claims(parse_json_object(self.reply_content(reply)), body)

        # Stage 2: embed the paragraphs once per entry.
        vectors = embed_paragraphs(retrieval, paragraph_texts)

        judged: list[dict[str, Any]] = []
        for index, claim in enumerate(claims):
            try:
                judged.append(self._judge_claim(chat, retrieval, entry_id, revision_id, claim,
                                                paragraph_texts, vectors))
            except (ServiceError, ValueError) as exc:
                with _append_lock:
                    self.failures.append({"entry_id": entry_id, "stage": "judge", "claim_index": index,
                                          "error": f"{type(exc).__name__}: {exc}"})
                fallback = dict(claim)
                fallback["verdict"] = "not_in_wikipedia"
                fallback["wikipedia_quote"] = None
                fallback["downgraded"] = True
                fallback["explanation"] = {"kind": "inference",
                                           "text": f"The judge call failed and is recorded in failures.jsonl: {exc}"}
                fallback["evidence"] = []
                judged.append(fallback)

        covered = any(row.get("verdict") != "not_in_wikipedia" for row in judged)
        return {
            "entry_id": entry_id,
            "page_id": entry["page_id"],
            "scan_sha256": entry.get("scan_sha256", ""),
            "article_page_id": match["article_page_id"],
            "article_revision_id": revision_id,
            "article_text_sha256": match["article_text_sha256"],
            "article_title": match["article_title"],
            "claim_count": len(judged),
            "claims_dropped": sum(drops.values()),
            "claims_dropped_detail": {key: value for key, value in drops.items() if value},
            "claims": judged,
            "section_coverage": [{
                "section": "Article",
                "covered": covered,
                "claims": sum(1 for row in judged if row.get("verdict") != "not_in_wikipedia"),
                "note": "the stored article text carries no section markers",
            }],
        }

    def _judge_claim(self, chat: ChatClient, retrieval: RetrievalClient, entry_id: str, revision_id: str,
                     claim: dict[str, Any], paragraph_texts: list[str],
                     vectors: list[list[float]]) -> dict[str, Any]:
        """Retrieve passages for one claim and judge it."""
        claim_vector = retry_call(lambda: retrieval.embed([claim["quote"][:2000]], input_type="query"))[0]
        scored = sorted(
            ((sum(a * b for a, b in zip(claim_vector, vector)), index) for index, vector in enumerate(vectors)),
            key=lambda row: -row[0],
        )[:EMBED_DEPTH]
        documents = [paragraph_texts[index][:32000] for _, index in scored]
        reranked = retry_call(lambda: retrieval.rerank(claim["quote"][:2000], documents))
        logits = {item["index"]: item["relevance_score"] for item in reranked}
        kept = sorted(scored, key=lambda row: -(logits[row[1]] if logits.get(row[1]) is not None else -1e9))[:JUDGE_DEPTH]
        evidence = [
            {
                "passage_id": f"W{index + 1}",
                "position": index,
                "embed_similarity": round(similarity, 4),
                "rerank_logit": round(logits[index], 4) if logits.get(index) is not None else None,
                "kept": any(index == kept_index for _, kept_index in kept),
            }
            for similarity, index in scored
        ]
        kept_texts = [paragraph_texts[index] for _, index in kept]
        passages = "\n\n".join(f"[W{index + 1}] {paragraph_texts[index]}" for _, index in kept)

        messages = [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": JUDGE_TEMPLATE.format(quote=claim["quote"], passages=passages)},
        ]
        reply = self.cached_chat(chat, entry_id, revision_id, messages, max_tokens=1500, stage="judge")
        judged = judged_claim(claim, parse_json_object(self.reply_content(reply)), kept_texts)
        judged["evidence"] = evidence
        return judged


def embed_paragraphs(retrieval: RetrievalClient, texts: list[str]) -> list[list[float]]:
    """Embed article paragraphs in batches within the service limit of 16 items."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), 16):
        batch = texts[start : start + 16]
        vectors.extend(retry_call(lambda batch=batch: retrieval.embed(batch, input_type="document")))
    return vectors


def load_article(work_dir: Path, page_id: str) -> dict[str, Any]:
    """The stored Wikipedia article for one match."""
    path = Path(work_dir) / "match" / "articles" / f"{page_id}.json"
    if not path.exists():
        raise ValueError(f"the stored article {page_id} is missing; run the match stage")
    return json.loads(path.read_text(encoding="utf-8"))


def append_claims(path: Path, records: list[dict[str, Any]]) -> None:
    """Append claim records to the JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def store_record(manifest: dict[str, Any], match: dict[str, Any], record: dict[str, Any],
                 claims_path: Path) -> ArtifactRecord:
    """The evidence-store row for one claims record."""
    return ArtifactRecord(
        record_id=f"claims:{record['entry_id']}",
        stage="claims",
        sources=[
            SourceReference(
                dataset=manifest["dataset"],
                dataset_revision=manifest["revision"],
                source_id=record["page_id"],
                source_url=manifest["source_url"],
                content_sha256=record.get("scan_sha256") or "0" * 64,
                license=str(manifest.get("license") or "CC0-1.0"),
            ),
            SourceReference(
                dataset="wikimedia/structured-wikipedia",
                dataset_revision="417c267bb457fa645c22eb3b5c77764963194c70",
                source_id=record["article_page_id"],
                source_url=match.get("article_url", ""),
                content_sha256=record["article_text_sha256"],
                license="CC-BY-SA-4.0",
            ),
        ],
        artifact_path=str(claims_path),
        metadata={"claims": record["claim_count"], "verdicts": {
            verdict: sum(1 for claim in record["claims"] if claim.get("verdict") == verdict)
            for verdict in VERDICTS}},
    )


def run_claims(settings: Settings, work_dir: Path, *, limit: int | None = None,
               deadline: float | None = None, workers: int = MAX_CONCURRENT) -> dict[str, Any]:
    """Align claims for every matched entry. Resume skips finished records."""
    work_dir = Path(work_dir)
    manifest = load_manifest()
    entries = {row["entry_id"]: row for row in json.loads(
        (work_dir / "extract" / "derived" / "entries.json").read_text(encoding="utf-8"))}
    all_matches = read_jsonl(work_dir / "match" / MATCHES_NAME)
    if not all_matches:
        raise ValueError("no matches found; run the match stage first")
    scoped = all_matches[:limit] if limit is not None else all_matches
    run = ClaimsRun(settings, work_dir, workers=workers,
                    deadline=deadline if deadline is not None else time.time() + 4.5 * 3600)
    done = {row["entry_id"]: row.get("article_revision_id") for row in read_jsonl(run.claims_path)}
    todo = [row for row in scoped if done.get(row["entry_id"]) != row["article_revision_id"]]

    started = time.time()
    processed = 0
    store = LanceArtifactStore(settings.db_path)
    with ChatClient(settings.super_base_url, settings.super_api_key, settings.super_model) as chat, \
            RetrievalClient(settings.retrieval_base_url, settings.retrieval_api_key) as retrieval, \
            ThreadPoolExecutor(max_workers=run.workers) as pool:
        pending = []
        for match in todo:
            entry = entries.get(match["entry_id"])
            if entry is None:
                with _append_lock:
                    run.failures.append({"entry_id": match["entry_id"], "stage": "entry",
                                         "error": "the entry is missing from entries.json"})
                continue
            try:
                article = load_article(work_dir, match["article_page_id"])
            except (OSError, ValueError) as exc:
                with _append_lock:
                    run.failures.append({"entry_id": match["entry_id"], "stage": "entry",
                                         "error": f"{type(exc).__name__}: {exc}"})
                continue
            pending.append((pool.submit(run.process_entry, chat, retrieval, entry, match, article), match))
        for future, match in pending:
            try:
                record = future.result()
            except (ServiceError, ValueError, OSError) as exc:
                error = f"{type(exc).__name__}: {exc}"
                with _append_lock:
                    # A failed call inside the entry is already recorded with its
                    # stage; do not append the same failure twice.
                    duplicate = any(row["entry_id"] == match["entry_id"] and row["error"] == error
                                    for row in run.failures)
                    if not duplicate:
                        run.failures.append({"entry_id": match["entry_id"], "stage": "entry",
                                             "error": error})
                continue
            if record is None:
                continue
            with _append_lock:
                append_claims(run.claims_path, [record])
            processed += 1
            store.put(store_record(manifest, match, record, run.claims_path))
            print(f"[claims] {processed}/{len(todo)} {record['entry_id']}", file=sys.stderr, flush=True)

    all_records = read_jsonl(run.claims_path)
    verdicts = {verdict: 0 for verdict in VERDICTS}
    claims_total = 0
    downgraded = 0
    for record in all_records:
        for claim in record.get("claims", []):
            claims_total += 1
            verdict = claim.get("verdict", "not_in_wikipedia")
            verdicts[verdict] = verdicts.get(verdict, 0) + 1
            if claim.get("downgraded"):
                downgraded += 1
    failed_entries = {row["entry_id"] for row in run.failures}
    summary = {
        "matches_total": len(all_matches),
        "entries_done": len(all_records),
        "entries_added_this_run": processed,
        "entries_failed": len(failed_entries),
        "claims_total": claims_total,
        "claims_downgraded": downgraded,
        "verdict_counts": verdicts,
        "failures": len(run.failures),
        "entries_skipped_by_time_cap": run.skipped,
        "time_cap_reached": run.skipped > 0,
        "runtime_seconds": round(time.time() - started, 1),
        "note": f"claims for {len(all_records)} of {len(all_matches)} matches",
    }
    with run.failures_path.open("a", encoding="utf-8") as stream:
        for row in run.failures:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write_json(work_dir / "claims" / "summary.json", summary)
    return {"stage": "claims", "artifacts": str(work_dir / "claims"),
            **{key: summary[key] for key in ("entries_done", "entries_failed", "claims_total", "failures")}}
