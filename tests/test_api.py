"""The web API serves artifact shapes and pending markers without model calls."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from nemotron_challenge.api import create_app
from nemotron_challenge.config import MATCH_LOGIT_THRESHOLD

ENTRY_MATCHED = {
    "entry_id": "britannica:rev:train:13#0000",
    "page_id": "britannica:rev:train:13",
    "filename": "page-0013-aaaaaaaaaaaa.jpg",
    "scan_sha256": "a" * 64,
    "heading": "SHIP-BUILDING",
    "heading_class": "Text",
    "fragment": False,
    "subsections": ["Fractical Building"],
    "page_header": "292 SHIP-BUILDING.",
    "continued": False,
    "continued_on": None,
    "n_blocks": 2,
    "body": "SHIP-BUILDING is the art of constructing vessels.\n\nThe beams are discussed below.",
}

ENTRY_FRAGMENT = {
    "entry_id": "britannica:rev:train:14#0000",
    "page_id": "britannica:rev:train:14",
    "filename": "page-0014-bbbbbbbbbbbb.jpg",
    "scan_sha256": "b" * 64,
    "heading": None,
    "heading_class": None,
    "fragment": True,
    "subsections": [],
    "page_header": "VOLCANOES.",
    "continued": True,
    "continued_on": None,
    "n_blocks": 1,
    "body": "Aetna burns in Sicily. The mountain smokes.",
}

MATCH_ROW = {
    "entry_id": ENTRY_MATCHED["entry_id"],
    "entry_title": "SHIP-BUILDING",
    "heading_class": "Text",
    "fragment": False,
    "page_id": ENTRY_MATCHED["page_id"],
    "scan": ENTRY_MATCHED["filename"],
    "scan_sha256": "a" * 64,
    "match_confidence": -3.1,
    "bm25_rank": 1,
    "similarity": 0.71,
    "embed_rank": 2,
    "rerank_rank": 1,
    "article_page_id": "101",
    "article_title": "Shipbuilding",
    "article_revision_id": "777",
    "article_url": "https://en.wikipedia.org/wiki/Shipbuilding",
    "article_text_sha256": "d" * 64,
}

EVIDENCE_ROWS = [
    {"entry_id": ENTRY_MATCHED["entry_id"], "page_id": ENTRY_MATCHED["page_id"],
     "candidate_page_id": "101", "candidate_title": "Shipbuilding", "bm25_rank": 1, "bm25_score": 12.4,
     "embed_similarity": 0.71, "embed_rank": 2, "rerank_logit": -3.1, "rerank_rank": 1, "decision": "matched"},
    {"entry_id": ENTRY_MATCHED["entry_id"], "page_id": ENTRY_MATCHED["page_id"],
     "candidate_page_id": "102", "candidate_title": "Boat", "bm25_rank": 2, "bm25_score": 9.1,
     "embed_similarity": 0.55, "embed_rank": 1, "rerank_logit": -6.2, "rerank_rank": 2, "decision": "candidate"},
]

ARTICLE = {
    "page_id": "101", "revision_id": "777", "title": "Shipbuilding", "url": "https://en.wikipedia.org/wiki/Shipbuilding",
    "provenance": {"text_sha256": "d" * 64, "revision_url": "https://en.wikipedia.org/w/index.php?oldid=777"},
    "license": {"spdx": "CC-BY-SA-4.0"},
    "total_chars": 140,
    "text": "Shipbuilding is the construction of ships and other floating vessels.\n\nIt takes place in shipyards.",
}

COMPARISON_ROW = {
    "entry_id": ENTRY_MATCHED["entry_id"], "entry_title": "SHIP-BUILDING", "article_title": "Shipbuilding",
    "match_confidence": -3.1, "method": "test",
    "britannica": {"page_id": ENTRY_MATCHED["page_id"], "scan": ENTRY_MATCHED["filename"], "scan_sha256": "a" * 64,
                   "heading_class": "Text", "excerpt": "SHIP-BUILDING", "tokens": 11, "types": 10,
                   "type_token_ratio": 0.9, "top_terms": [["vessels", 1], ["discussed", 1]]},
    "wikipedia": {"page_id": "101", "revision_id": "777", "url": "https://en.wikipedia.org/wiki/Shipbuilding",
                  "text_sha256": "d" * 64, "excerpt": "Shipbuilding", "tokens": 14, "types": 13,
                  "type_token_ratio": 0.9, "top_terms": [["vessels", 1], ["shipyards", 1]]},
    "distinctive": {"britannica": [{"term": "art", "log_odds": 2.0, "count_a": 1, "count_b": 0}],
                    "wikipedia": [{"term": "shipyards", "log_odds": 2.2, "count_a": 0, "count_b": 1}]},
    "normalization": {"britannica": {}, "wikipedia": {}},
    "citations": [],
}

CLAIMS_ROW = {
    "entry_id": ENTRY_MATCHED["entry_id"],
    "article_revision_id": "777",
    "claims": [
        {"quote": "the art of constructing vessels", "type": "definition", "verdict": "agrees",
         "wikipedia_quote": "the construction of ships", "explanation": {"kind": "inference", "text": "Same fact."},
         "downgraded": False},
        {"quote": "The beams are discussed below.", "type": "practice", "verdict": "not_in_wikipedia",
         "wikipedia_quote": None, "explanation": {"kind": "inference", "text": "No counterpart."}, "downgraded": True},
    ],
    "section_coverage": [{"section": "Introduction", "covered": True, "claims": 1}],
}


def make_artifacts(tmp_path: Path, *, with_match: bool = True, with_claims: bool = False,
                   with_comparison: bool = True) -> Path:
    work = tmp_path / "artifacts"
    derived = work / "extract" / "derived"
    raw = work / "extract" / "raw"
    derived.mkdir(parents=True)
    raw.mkdir(parents=True)
    (derived / "entries.json").write_text(
        json.dumps([ENTRY_MATCHED, ENTRY_FRAGMENT]), encoding="utf-8")
    page_file = {
        "page_id": ENTRY_MATCHED["page_id"], "filename": ENTRY_MATCHED["filename"],
        "page_header": "292 SHIP-BUILDING.",
        "entries": [{
            "entry_id": ENTRY_MATCHED["entry_id"],
            "blocks": [{"class": "Text", "text": "SHIP-BUILDING is the art of constructing vessels.",
                        "bbox": [[0.06, 0.08], [0.53, 0.12]]}],
        }],
    }
    (derived / f"{ENTRY_MATCHED['filename']}.json").write_text(json.dumps(page_file), encoding="utf-8")
    raw_reply = {"choices": [{"finish_reason": "stop", "message": {"content":
                 "<x_0.05><y_0.04>292 SHIP-BUILDING.<x_0.65><y_0.05><class_Page-header>\n\n"
                 "<x_0.06><y_0.08>SHIP-BUILDING is the art of constructing vessels."
                 "<x_0.53><y_0.12><class_Text>"}}]}
    (raw / f"{ENTRY_MATCHED['filename']}.json").write_text(json.dumps(raw_reply), encoding="utf-8")
    if with_match:
        match_dir = work / "match"
        (match_dir / "articles").mkdir(parents=True)
        (match_dir / "matches.jsonl").write_text(json.dumps(MATCH_ROW) + "\n", encoding="utf-8")
        (match_dir / "evidence.jsonl").write_text(
            "\n".join(json.dumps(row) for row in EVIDENCE_ROWS) + "\n", encoding="utf-8")
        (match_dir / "articles" / "101.json").write_text(json.dumps(ARTICLE), encoding="utf-8")
    if with_comparison:
        compare_dir = work / "compare"
        compare_dir.mkdir(parents=True)
        (compare_dir / "comparisons.jsonl").write_text(json.dumps(COMPARISON_ROW) + "\n", encoding="utf-8")
    if with_claims:
        claims_dir = work / "claims"
        claims_dir.mkdir(parents=True)
        (claims_dir / "claims.jsonl").write_text(json.dumps(CLAIMS_ROW) + "\n", encoding="utf-8")
    return work


def make_scans(tmp_path: Path) -> Path:
    scans = tmp_path / "scans"
    scans.mkdir()
    (scans / ENTRY_MATCHED["filename"]).write_bytes(b"\xff\xd8\xff\xe0tiny scan")
    return scans


def test_topics_serve_real_headwords_and_strengths(tmp_path):
    work = make_artifacts(tmp_path)
    client = TestClient(create_app(work, make_scans(tmp_path)))
    payload = client.get("/api/topics")
    assert payload.status_code == 200
    topics = payload.json()["topics"]
    assert [topic["label"] for topic in topics] == ["Ship-building", "Fragment (page-0014) of VOLCANOES."]
    assert topics[0]["slug"] == "ship-building"
    assert topics[0]["headword"] == "SHIP-BUILDING"
    assert topics[0]["match"] == "strong"
    assert topics[0]["wikipediaTitle"] == "Shipbuilding"
    assert topics[1]["match"] == "none"
    assert payload.json()["pending"] == []


def test_topics_mark_pending_without_the_match_stage(tmp_path):
    work = make_artifacts(tmp_path, with_match=False, with_comparison=False)
    client = TestClient(create_app(work, make_scans(tmp_path)))
    payload = client.get("/api/topics").json()
    assert payload["pending"] and "match" in payload["pending"][0]
    assert all(topic["match"] == "none" for topic in payload["topics"])


def test_compare_returns_the_documented_shape(tmp_path):
    work = make_artifacts(tmp_path)
    client = TestClient(create_app(work, make_scans(tmp_path)))
    payload = client.get("/api/compare", params={"q": "ship building"}).json()
    assert payload["topic"]["label"] == "Ship-building"
    assert payload["britannica"]["pageId"] == "page-0013-aaaaaaaaaaaa"
    assert payload["britannica"]["imageUrl"] == "/api/scans/page-0013-aaaaaaaaaaaa.jpg"
    assert [passage["id"] for passage in payload["britannica"]["passages"]] == ["B1", "B2"]
    assert payload["wikipedia"]["title"] == "Shipbuilding"
    assert [passage["id"] for passage in payload["wikipedia"]["passages"]] == ["W1", "W2"]
    assert payload["match"]["strength"] == "strong"
    assert payload["match"]["rerankScore"] == -3.1
    assert [row["title"] for row in payload["candidates"]] == ["Shipbuilding", "Boat"]
    assert payload["vocabulary"]["britannica"][0]["term"] == "art"
    assert payload["stats"]["britannica"]["words"] > 0
    assert any("claims" in note for note in payload["pending"])


def test_compare_maps_claims_to_alignments_and_coverage(tmp_path):
    work = make_artifacts(tmp_path, with_claims=True)
    client = TestClient(create_app(work, make_scans(tmp_path)))
    payload = client.get("/api/compare", params={"q": "ship building"}).json()
    alignments = payload["alignments"]
    assert alignments[0]["verdict"] == "agrees"
    assert alignments[0]["britannica"]["passageId"] == "B1"
    assert alignments[0]["britannica"]["quote"] == "the art of constructing vessels"
    assert alignments[0]["note"] == "Same fact."
    assert alignments[0]["kind"] == "inference"
    assert alignments[1]["downgraded"] is True
    assert alignments[1]["wikipedia"] is None
    assert payload["coverage"][0]["topic"] == "Introduction"
    assert not any("claims" in note for note in payload["pending"])


def test_compare_404_for_unknown_query(tmp_path):
    work = make_artifacts(tmp_path)
    client = TestClient(create_app(work, make_scans(tmp_path)))
    response = client.get("/api/compare", params={"q": "zzz-nothing"})
    assert response.status_code == 404
    assert "Nothing in the index matches" in response.json()["detail"]


def test_fragment_entries_are_searchable(tmp_path):
    work = make_artifacts(tmp_path)
    client = TestClient(create_app(work, make_scans(tmp_path)))
    payload = client.get("/api/compare", params={"q": "aetna burns"}).json()
    assert payload["topic"]["label"].startswith("Fragment")
    assert payload["match"]["strength"] == "none"
    assert any("No accepted match" in note for note in payload["match"]["reasons"])


def test_scan_routes_serve_image_and_blocks(tmp_path):
    work = make_artifacts(tmp_path)
    scans = make_scans(tmp_path)
    client = TestClient(create_app(work, scans))
    image = client.get("/api/scans/page-0013-aaaaaaaaaaaa.jpg")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.content == (scans / ENTRY_MATCHED["filename"]).read_bytes()
    by_page_id = client.get(f"/api/scans/{ENTRY_MATCHED['page_id']}.jpg")
    assert by_page_id.status_code == 200
    blocks = client.get("/api/scans/page-0013-aaaaaaaaaaaa.json").json()
    assert blocks["pageHeader"] == "292 SHIP-BUILDING."
    assert blocks["blocks"][0]["bbox"] == [[0.06, 0.08], [0.53, 0.12]]
    assert client.get("/api/scans/page-9999-ffffffffffff.jpg").status_code == 404
    assert client.get("/api/scans/page-9999-ffffffffffff.json").status_code == 404


def test_meta_and_cases_shapes(tmp_path):
    work = make_artifacts(tmp_path)
    client = TestClient(create_app(work, make_scans(tmp_path), tmp_path / "db.lancedb"))
    meta = client.get("/api/meta").json()
    assert meta["sample"]["size"] == 100
    names = {row["name"] for row in meta["models"]}
    # B4: every row comes from a saved artifact; no mock list is copied.
    assert any("nemotron-3.5-parse" in name for name in names)
    assert any("embed-vl" in name for name in names)
    assert any("rerank-vl" in name for name in names)
    assert not any(name.startswith("LanceDB") for name in names)  # no lancedb-summary.json yet
    assert not any("Hermes Agent" in name for name in names)  # no agent report yet
    assert all(row.get("evidence") for row in meta["models"])
    assert meta["matchLogitThreshold"] == MATCH_LOGIT_THRESHOLD
    # Write a lancedb summary and the LanceDB row appears; meta stays truthful.
    (work / "lancedb-summary.json").write_text(json.dumps(
        {"tables": {"match_evidence": 2, "britannica_entries": 2}, "fts_indexes": True}), encoding="utf-8")
    meta = client.get("/api/meta").json()
    lancedb_rows = [row for row in meta["models"] if row["name"] == "LanceDB"]
    assert len(lancedb_rows) == 1
    assert lancedb_rows[0]["evidence"] == "artifacts/lancedb-summary.json"
    cases = client.get("/api/cases").json()
    assert cases["cases"] == []
    assert cases["pending"]


def test_chat_delegates_to_the_agent_runner(tmp_path, monkeypatch):
    work = make_artifacts(tmp_path)
    client = TestClient(create_app(work, make_scans(tmp_path)))
    calls = {}

    def fake_ask(question, *, topic="", adapter=None, timeout=600):
        calls["question"] = question
        calls["topic"] = topic
        return {"answer": "Answer with [B1].", "citations": [{"id": "B1", "source": "britannica",
                                                              "passageId": "B1", "rerankScore": -3.1}],
                "grounding": "supported", "trace": [{"step": "Write answer", "model": "stub", "detail": "", "ms": None}],
                "recorded": False}

    monkeypatch.setattr("nemotron_challenge.agent_runner.ask_agent", fake_ask)
    response = client.post("/api/chat", json={"topic": "ship-building", "question": "What changed?"})
    assert response.status_code == 200
    assert response.json()["grounding"] == "supported"
    assert calls == {"question": "What changed?", "topic": "ship-building"}
    assert client.post("/api/chat", json={"question": ""}).status_code == 422


def test_search_reads_the_lancedb_store(tmp_path):
    work = make_artifacts(tmp_path)
    db_path = tmp_path / "db.lancedb"
    from nemotron_challenge.lancedb_sync import connect, ensure_fts_indexes, ensure_tables

    db = connect(db_path)
    tables = ensure_tables(db)
    tables["britannica_entries"].add([{
        "entry_id": ENTRY_MATCHED["entry_id"], "page_id": ENTRY_MATCHED["page_id"],
        "heading": "SHIP-BUILDING", "fragment": False, "body": ENTRY_MATCHED["body"],
        "scan_sha256": "a" * 64, "vector": None}])
    tables["wiki_paragraphs"].add([{
        "page_id": "101", "revision_id": "777", "section": None, "paragraph_index": 0,
        "text": "Shipbuilding is the construction of ships.", "text_sha256": "d" * 64, "vector": None}])
    assert ensure_fts_indexes(db) is True

    client = TestClient(create_app(work, make_scans(tmp_path), db_path))
    payload = client.get("/api/search", params={"q": "ship"}).json()
    kinds = {row["kind"] for row in payload["results"]}
    assert kinds == {"entry", "paragraph"}
    entry_hits = [row for row in payload["results"] if row["kind"] == "entry"]
    assert entry_hits[0]["entry_id"] == ENTRY_MATCHED["entry_id"]


def test_search_without_a_store_returns_a_note(tmp_path):
    work = make_artifacts(tmp_path)
    client = TestClient(create_app(work, make_scans(tmp_path), tmp_path / "missing.lancedb"))
    payload = client.get("/api/search", params={"q": "ship"}).json()
    assert payload["results"] == []
    assert payload["note"]
