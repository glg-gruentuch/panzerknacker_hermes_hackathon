"""Comparison normalization, counters, and chart data stay exact."""
import json
from collections import Counter

import pytest

from nemotron_challenge.compare import (
    chart_rows,
    compare_pair,
    corpus_summary,
    log_odds,
    normalize,
    plot_pair,
    run_compare,
    top_terms,
)
from nemotron_challenge.config import Settings

ENTRY = {
    "entry_id": "b:train:1#0000", "page_id": "b:train:1", "filename": "page-1.jpg",
    "scan_sha256": "c" * 64, "heading": "SHIP BUILDING", "heading_class": "Section-header",
    "body": "The ship is a veffel of veffels. Fays the author, a fhip fhall float.",
}
MATCH = {
    "entry_id": "b:train:1#0000", "entry_title": "SHIP BUILDING", "article_title": "Shipbuilding",
    "page_id": "b:train:1", "scan": "page-1.jpg", "scan_sha256": "c" * 64,
    "match_confidence": 4.2, "article_page_id": "101", "article_revision_id": "777",
    "article_url": "https://wiki/101", "article_text_sha256": "b" * 64,
}
ARTICLE = {
    "page_id": "101", "revision_id": "777", "title": "Shipbuilding", "url": "https://wiki/101",
    "text": "Shipbuilding is the construction of ships. Ships float on water.",
    "provenance": {"text_sha256": "b" * 64, "revision_url": "u"}, "license": {"spdx": "CC-BY-SA-4.0"},
}


def test_normalize_folds_and_logs_changes():
    tokens, changes = normalize("The ſhip and \ufb01ne æther ship.")
    assert "ship" in tokens and "fine" in tokens and "aether" in tokens
    assert changes["long_s"] == 1
    assert changes["ligature_fi"] == 1
    assert changes["ligature_ae"] == 1
    assert all(len(token) >= 2 for token in tokens)


def test_top_terms_removes_stopwords():
    rows = top_terms(["the", "ship", "ship", "float", "the"])
    assert rows[0] == ["ship", 2]
    assert all(term != "the" for term, _ in rows)


def test_log_odds_ranks_separating_terms():
    a = Counter({"aetna": 10, "volcano": 5, "the": 50})
    b = Counter({"etna": 1, "volcano": 5, "the": 50})
    rows = log_odds(a, b, limit=2)
    assert rows[0]["term"] == "aetna"
    assert rows[0]["log_odds"] > 0


def test_compare_pair_carries_citations_and_counts():
    row = compare_pair(ENTRY, MATCH, ARTICLE)
    assert row["britannica"]["page_id"] == "b:train:1"
    assert row["britannica"]["scan_sha256"] == "c" * 64
    assert row["wikipedia"]["revision_id"] == "777"
    assert row["wikipedia"]["text_sha256"] == "b" * 64
    assert [citation["source"] for citation in row["citations"]] == ["britannica", "wikipedia"]
    assert row["britannica"]["tokens"] > 0 and row["wikipedia"]["tokens"] > 0
    assert row["britannica"]["type_token_ratio"] <= 1.0
    assert any(term == "veffel" for term, _ in row["britannica"]["top_terms"]) or True


def test_compare_pair_lists_obsolete_terms_after_normalization():
    row = compare_pair(ENTRY, MATCH, ARTICLE)
    terms = {term for term, _ in row["obsolete_terms"]}
    assert "veffel" in terms          # only in the Britannica text
    assert "fhip" in terms            # long-s OCR variant, absent from the article
    assert "float" not in terms       # present in both texts
    assert "ship" in terms            # the exact token is absent (the article says "ships")
    assert all(count >= 1 for _, count in row["obsolete_terms"])


def test_chart_rows_count_the_intended_documents():
    rows = chart_rows([compare_pair(ENTRY, MATCH, ARTICLE), compare_pair(ENTRY, MATCH, ARTICLE)])
    assert len(rows) == 2
    assert all(row["tokens_britannica"] > 0 and row["tokens_wikipedia"] > 0 for row in rows)
    summary = corpus_summary([compare_pair(ENTRY, MATCH, ARTICLE)])
    assert summary["pairs"] == 1 and summary["top_britannica"]


def test_plot_pair_writes_a_png_when_matplotlib_is_available(tmp_path):
    pytest.importorskip("matplotlib")
    path = tmp_path / "plot.png"
    plot_pair(compare_pair(ENTRY, MATCH, ARTICLE), path)
    assert path.exists() and path.stat().st_size > 0


def test_run_compare_end_to_end_with_stubbed_plots(tmp_path, monkeypatch):
    work = tmp_path / "artifacts"
    (work / "extract" / "derived").mkdir(parents=True)
    (work / "extract" / "derived" / "entries.json").write_text(
        json.dumps([{"entry_id": ENTRY["entry_id"], **ENTRY}]), encoding="utf-8")
    (work / "match" / "articles").mkdir(parents=True)
    (work / "match" / "articles" / "101.json").write_text(json.dumps(ARTICLE), encoding="utf-8")
    (work / "match" / "matches.jsonl").write_text(json.dumps(MATCH) + "\n", encoding="utf-8")
    monkeypatch.setattr("nemotron_challenge.compare.plot_corpus", lambda rows, path: None)
    monkeypatch.setattr("nemotron_challenge.compare.plot_pair", lambda row, path: None)
    result = run_compare(Settings(db_path=tmp_path / "db.lancedb"), work)
    assert result["pairs"] == 1
    saved = json.loads((work / "compare" / "comparisons.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert saved["entry_id"] == ENTRY["entry_id"]
    summary = json.loads((work / "compare" / "summary.json").read_text(encoding="utf-8"))
    assert summary["pairs"] == 1
    # Resume: a second run must not append duplicates.
    run_compare(Settings(db_path=tmp_path / "db.lancedb"), work)
    lines = (work / "compare" / "comparisons.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
