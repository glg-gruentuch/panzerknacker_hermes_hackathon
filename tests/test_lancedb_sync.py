"""The LanceDB evidence store: rows, scoped vector search, and the paragraph cache (B2)."""
import json

from nemotron_challenge.lancedb_sync import (
    connect,
    ensure_tables,
    paragraph_rows,
    register_paragraphs,
    row_counts,
    search_entries_fts,
    search_paragraphs,
    search_paragraphs_fts,
    sync_from_artifacts,
    write_evidence_entry,
)

DIM = 2048


def _vec(*head: float) -> list[float]:
    return list(head) + [0.0] * (DIM - len(head))


def _fixture_workdir(tmp_path):
    work = tmp_path / "artifacts"
    (work / "match" / "articles").mkdir(parents=True)
    (work / "extract" / "derived").mkdir(parents=True)
    evidence = [
        {"entry_id": "b:train:1#0000", "page_id": "b:train:1", "candidate_page_id": "101",
         "candidate_title": "Ship", "bm25_rank": 1, "bm25_score": 9.5, "embed_similarity": 0.5,
         "embed_rank": 1, "rerank_logit": -2.0, "rerank_rank": 1, "decision": "matched"},
        {"entry_id": "b:train:1#0001", "page_id": "b:train:1", "candidate_page_id": None,
         "candidate_title": None, "bm25_rank": None, "bm25_score": None, "embed_similarity": None,
         "embed_rank": None, "rerank_logit": None, "rerank_rank": None, "decision": "no-candidates"},
    ]
    (work / "match" / "evidence.jsonl").write_text(
        "\n".join(json.dumps(row) for row in evidence) + "\n", encoding="utf-8")
    entries = [{"entry_id": "b:train:1#0000", "page_id": "b:train:1", "heading": "SHIP BUILDING",
                "fragment": False, "body": "The ship ends in close contact with the sides.",
                "scan_sha256": "c" * 64}]
    (work / "extract" / "derived" / "entries.json").write_text(json.dumps(entries), encoding="utf-8")
    article = {"page_id": "101", "revision_id": "777", "title": "Shipbuilding", "url": "https://wiki/101",
               "text": "First paragraph about ships and their building.\n\nSecond paragraph about docks and ports.",
               "provenance": {"text_sha256": "d" * 64}}
    (work / "match" / "articles" / "101.json").write_text(json.dumps(article), encoding="utf-8")
    return work


def test_sync_from_artifacts_fills_every_table(tmp_path):
    work = _fixture_workdir(tmp_path)
    result = sync_from_artifacts(tmp_path / "db.lancedb", work)
    assert result["fts"] is True
    counts = row_counts(tmp_path / "db.lancedb")
    assert counts["match_evidence"] == 2
    assert counts["britannica_entries"] == 1
    assert counts["wiki_articles"] == 1
    assert counts["wiki_paragraphs"] == 2


def test_sync_from_artifacts_is_repeatable(tmp_path):
    work = _fixture_workdir(tmp_path)
    sync_from_artifacts(tmp_path / "db.lancedb", work)
    sync_from_artifacts(tmp_path / "db.lancedb", work)
    counts = row_counts(tmp_path / "db.lancedb")
    assert counts["match_evidence"] == 2
    assert counts["britannica_entries"] == 1


def test_write_evidence_entry_replaces_rows_for_one_entry(tmp_path):
    work = _fixture_workdir(tmp_path)
    sync_from_artifacts(tmp_path / "db.lancedb", work)
    db = connect(tmp_path / "db.lancedb")
    write_evidence_entry(db, "b:train:1#0000", [
        {"entry_id": "b:train:1#0000", "page_id": "b:train:1", "candidate_page_id": "202",
         "candidate_title": "Shipbuilding", "bm25_rank": 1, "bm25_score": 8.0, "embed_similarity": 0.6,
         "embed_rank": 1, "rerank_logit": -1.5, "rerank_rank": 1, "decision": "matched"},
    ])
    table = db.open_table("match_evidence")
    rows = table.search().where("entry_id = 'b:train:1#0000'").limit(10).to_list()
    assert len(rows) == 1
    assert rows[0]["candidate_page_id"] == "202"


def test_vector_search_is_scoped_to_one_page(tmp_path):
    db = connect(tmp_path / "db.lancedb")
    rows = [
        {"page_id": "a", "revision_id": "1", "section": None, "paragraph_index": 0,
         "text": "ships", "text_sha256": "x" * 64, "vector": _vec(1.0, 0.0)},
        {"page_id": "a", "revision_id": "1", "section": None, "paragraph_index": 1,
         "text": "docks", "text_sha256": "y" * 64, "vector": _vec(0.0, 1.0)},
        {"page_id": "b", "revision_id": "1", "section": None, "paragraph_index": 0,
         "text": "volcanoes", "text_sha256": "z" * 64, "vector": _vec(1.0, 0.0)},
    ]
    ensure_tables(db)["wiki_paragraphs"].add(rows)
    hits = search_paragraphs(db, "a", _vec(1.0, 0.0), limit=10)
    assert hits is not None
    assert [hit["paragraph_index"] for hit in hits] == [0, 1]
    assert hits[0]["similarity"] > hits[1]["similarity"]
    assert search_paragraphs(db, "missing", _vec(1.0, 0.0)) is None


def test_register_paragraphs_embeds_only_missing_rows(tmp_path):
    db = connect(tmp_path / "db.lancedb")
    calls: list[int] = []

    def embed_fn(texts):
        calls.append(len(texts))
        return [_vec(1.0) for _ in texts]

    rows = paragraph_rows({"page_id": "a", "revision_id": "9", "text": "one\n\ntwo"})
    assert register_paragraphs(db, "9", rows, embed_fn) == 2
    assert calls == [2]
    again = paragraph_rows({"page_id": "a", "revision_id": "9", "text": "one\n\ntwo"})
    assert register_paragraphs(db, "9", again, embed_fn) == 0
    assert calls == [2]
    changed = paragraph_rows({"page_id": "a", "revision_id": "9", "text": "one\n\nthree"})
    assert register_paragraphs(db, "9", changed, embed_fn) == 1
    assert calls == [2, 1]
    hits = search_paragraphs(db, "a", _vec(1.0), limit=5)
    assert {hit["paragraph_index"] for hit in hits} == {0, 1}


def test_register_paragraphs_fills_rows_that_have_no_vector(tmp_path):
    db = connect(tmp_path / "db.lancedb")
    rows = paragraph_rows({"page_id": "a", "revision_id": "9", "text": "one\n\ntwo"})
    ensure_tables(db)["wiki_paragraphs"].add(rows)  # disk rebuild: vectors stay empty
    assert search_paragraphs(db, "a", _vec(1.0)) is None

    def embed_fn(texts):
        return [_vec(1.0) for _ in texts]

    assert register_paragraphs(db, "9", paragraph_rows({"page_id": "a", "revision_id": "9", "text": "one\n\ntwo"}),
                               embed_fn) == 2
    hits = search_paragraphs(db, "a", _vec(1.0))
    assert hits is not None and len(hits) == 2


def test_fts_finds_entries_and_paragraphs(tmp_path):
    work = _fixture_workdir(tmp_path)
    sync_from_artifacts(tmp_path / "db.lancedb", work)
    db = connect(tmp_path / "db.lancedb")
    entries = search_entries_fts(db, "ship")
    assert entries and entries[0]["entry_id"] == "b:train:1#0000"
    paragraphs_hits = search_paragraphs_fts(db, "docks")
    assert paragraphs_hits and paragraphs_hits[0]["page_id"] == "101"
