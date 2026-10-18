"""Matching policy: query limits, batch limits, thresholds, pagination."""
import json
from types import SimpleNamespace

from nemotron_challenge.config import Settings
from nemotron_challenge.match import (
    build_query,
    decide,
    embed_documents,
    fetch_article,
    run_match,
    shortlist,
    summary_of,
)


def test_build_query_respects_service_limits():
    entry = {"heading": "SHIP BUILDING", "body": "word " * 500}
    query = build_query(entry)
    assert len(query) <= 512
    assert len(query.split()) <= 64
    assert query.startswith("SHIP BUILDING")


def test_embed_documents_chunks_at_16():
    class FakeRetrieval:
        def __init__(self):
            self.sizes = []

        def embed(self, inputs, input_type):
            self.sizes.append(len(inputs))
            return [[0.0]] * len(inputs)

    fake = FakeRetrieval()
    vectors = embed_documents(fake, [f"doc {index}" for index in range(20)])
    assert fake.sizes == [16, 4]
    assert len(vectors) == 20


def test_shortlist_orders_by_dot_product():
    hits = [SimpleNamespace(page_id="1", excerpt="a"), SimpleNamespace(page_id="2", excerpt="b")]

    class FakeRetrieval:
        vectors = {"query": [1.0, 0.0], "a": [0.0, 1.0], "b": [1.0, 0.0]}

        def embed(self, inputs, input_type):
            if input_type == "query":
                return [self.vectors["query"]]
            return [self.vectors[text] for text in inputs]

    rows = shortlist(FakeRetrieval(), "query", hits, keep=2)
    assert [row["hit"].page_id for row in rows] == ["2", "1"]
    assert rows[0]["similarity"] == 1.0


def test_decide_uses_threshold_on_raw_logits():
    reranked = [{"row": {"hit": SimpleNamespace(page_id="1")}, "logit": -2.5}]
    assert decide(reranked, 0.0) is None
    assert decide(reranked, -3.0)["logit"] == -2.5
    assert decide([], 0.0) is None


def test_fetch_article_paginates_and_keeps_provenance():
    pages = {
        0: SimpleNamespace(page_id="101", revision_id="555", title="T", url="https://wiki/101",
                           text="Hello ", offset=0, returned_chars=6, total_chars=12, next_offset=6,
                           provenance=SimpleNamespace(model_dump=lambda: {"text_sha256": "a" * 64, "revision_url": "u"}),
                           license={"spdx": "CC-BY-SA-4.0"}),
        6: SimpleNamespace(page_id="101", revision_id="555", title="T", url="https://wiki/101",
                           text="world", offset=6, returned_chars=5, total_chars=12, next_offset=None,
                           provenance=SimpleNamespace(model_dump=lambda: {"text_sha256": "a" * 64, "revision_url": "u"}),
                           license={"spdx": "CC-BY-SA-4.0"}),
    }
    calls = []

    class FakeWiki:
        def article(self, page_id, offset=0, max_chars=10000):
            calls.append(offset)
            return pages[offset]

    article = fetch_article(FakeWiki(), "101")
    assert article["text"] == "Hello world"
    assert calls == [0, 6]
    assert article["provenance"]["text_sha256"] == "a" * 64


def test_summary_counts_unique_and_repeated_articles():
    rows = [{"entry_id": "e1", "article_page_id": "1"}, {"entry_id": "e2", "article_page_id": "1"},
            {"entry_id": "e3", "article_page_id": "2"}]
    summary = summary_of(rows)
    assert summary["unique_articles"] == 2
    assert summary["repeats"] == [{"article_page_id": "1", "entry_ids": ["e1", "e2"]}]


class _StubWiki:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def search(self, query, top_k=10, excerpt_chars=1000):
        return SimpleNamespace(hits=[
            SimpleNamespace(page_id="101", title="Ship", bm25_score=2.0, excerpt="A ship is a vessel."),
            SimpleNamespace(page_id="102", title="Boat", bm25_score=1.0, excerpt="A boat floats."),
        ])

    def article(self, page_id, offset=0, max_chars=10000):
        return SimpleNamespace(page_id=page_id, revision_id="777", title="Ship", url=f"https://wiki/{page_id}",
                               text="Article body about ships.", offset=0, returned_chars=25, total_chars=25,
                               next_offset=None,
                               provenance=SimpleNamespace(model_dump=lambda: {"text_sha256": "b" * 64, "revision_url": "u"}),
                               license={"spdx": "CC-BY-SA-4.0"})


class _StubRetrieval:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def embed(self, inputs, input_type):
        return [[1.0, 0.0] for _ in inputs]

    def rerank(self, query, documents, top_n=None):
        score = 5.0 if "ship" in query.lower() else -10.0
        return [{"index": index, "relevance_score": score - index} for index in range(len(documents))]


def test_run_match_end_to_end_with_stubs(tmp_path, monkeypatch):
    work = tmp_path / "artifacts"
    entries = [
        {"entry_id": "b:train:1#0000", "page_id": "b:train:1", "filename": "page-1.jpg", "scan_sha256": "c" * 64,
         "heading": "SHIP BUILDING", "heading_class": "Section-header", "page_header": "", "continued": False,
         "continued_on": None, "n_blocks": 2, "body": "Ship building in 1768."},
        {"entry_id": "b:train:1#0001", "page_id": "b:train:1", "filename": "page-1.jpg", "scan_sha256": "c" * 64,
         "heading": "VOLCANOES", "heading_class": "Section-header", "page_header": "", "continued": False,
         "continued_on": None, "n_blocks": 2, "body": "Aetna burns."},
    ]
    derived = work / "extract" / "derived"
    derived.mkdir(parents=True)
    (derived / "entries.json").write_text(json.dumps(entries), encoding="utf-8")
    manifest = {"dataset": "NationalLibraryOfScotland/encyclopaedia_britannica_illustrated",
                "revision": "309f765b1ecc83e0a7f7762e44b4a927a7555443",
                "source_url": "https://example.com", "license": "CC0-1.0", "pages": []}
    monkeypatch.setattr("nemotron_challenge.match.load_manifest", lambda: manifest)
    monkeypatch.setattr("nemotron_challenge.match.WikiClient", _StubWiki)
    monkeypatch.setattr("nemotron_challenge.match.RetrievalClient", _StubRetrieval)

    settings = Settings(wikipedia_api_url="http://stub", retrieval_base_url="http://stub", db_path=tmp_path / "db.lancedb")
    result = run_match(settings, work, threshold=0.0)

    assert result["matched"] == 1
    assert result["unmatched"] == 1
    evidence = [json.loads(line) for line in (work / "match" / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    decisions = {(row["entry_id"], row["candidate_page_id"]): row["decision"] for row in evidence}
    assert decisions[("b:train:1#0000", "101")] == "matched"
    assert decisions[("b:train:1#0001", "101")] == "unmatched"
    matches = [json.loads(line) for line in (work / "match" / "matches.jsonl").read_text(encoding="utf-8").splitlines()]
    assert matches[0]["article_page_id"] == "101"
    assert matches[0]["article_text_sha256"] == "b" * 64
    assert (work / "match" / "articles" / "101.json").exists()
    summary = json.loads((work / "match" / "summary.json").read_text(encoding="utf-8"))
    assert summary["entries_total"] == 2
    assert summary["unmatched"] == 1

    # Resume: a second run adds nothing new.
    again = run_match(settings, work, threshold=0.0)
    assert again["matched"] == 1
    assert len([json.loads(line) for line in (work / "match" / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]) == len(evidence)
