"""Claim alignment: substring checks, downgrades, failures, and cache hits.

All model clients are mocks; no network call happens here.
"""
import json
import time

from nemotron_challenge.claims import (
    EXTRACT_SYSTEM,
    judged_claim,
    run_claims,
    valid_claims,
)
from nemotron_challenge.clients import ServiceError
from nemotron_challenge.config import SUPER_MODEL, Settings

ENTRY = {
    "entry_id": "britannica:rev:train:13#0000",
    "page_id": "britannica:rev:train:13",
    "filename": "page-0013-aaaaaaaaaaaa.jpg",
    "scan_sha256": "a" * 64,
    "heading": "SHIP-BUILDING",
    "body": "The ship is long. The ship is made of oak.",
}

MATCH = {
    "entry_id": ENTRY["entry_id"],
    "article_page_id": "101",
    "article_revision_id": "777",
    "article_text_sha256": "c" * 64,
    "article_title": "Shipbuilding",
    "article_url": "https://en.wikipedia.org/wiki/Shipbuilding",
    "match_confidence": -3.1,
}

ARTICLE_TEXT = ("Shipbuilding is the construction of ships.\n\n"
                "Ships are made of oak and steel.")
ARTICLE = {"page_id": "101", "revision_id": "777", "title": "Shipbuilding",
           "url": "https://en.wikipedia.org/wiki/Shipbuilding",
           "provenance": {"text_sha256": "c" * 64}, "license": {"spdx": "CC-BY-SA-4.0"},
           "text": ARTICLE_TEXT}

GOOD_QUOTE = "The ship is long."
OAK_QUOTE = "The ship is made of oak."


def make_work(tmp_path):
    work = tmp_path / "artifacts"
    derived = work / "extract" / "derived"
    derived.mkdir(parents=True)
    (derived / "entries.json").write_text(json.dumps([ENTRY]), encoding="utf-8")
    match_dir = work / "match"
    (match_dir / "articles").mkdir(parents=True)
    (match_dir / "matches.jsonl").write_text(json.dumps(MATCH) + "\n", encoding="utf-8")
    (match_dir / "articles" / "101.json").write_text(json.dumps(ARTICLE), encoding="utf-8")
    return work


def make_settings(tmp_path):
    return Settings(wikipedia_api_url="http://stub", retrieval_base_url="http://stub",
                    db_path=tmp_path / "db.lancedb")


class FakeChat:
    calls = 0
    extract_reply = json.dumps({"claims": [
        {"quote": GOOD_QUOTE, "type": "definition"},
        {"quote": "This quote is not in the text.", "type": "definition"},
        {"quote": OAK_QUOTE, "type": "mystery-type"},
    ]})
    judge_reply = json.dumps({"verdict": "agrees",
                              "wikipedia_quote": "the construction of ships",
                              "explanation": "Both describe shipbuilding."})

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def complete(self, messages, max_tokens=4096, extra_body=None):
        type(self).calls += 1
        content = self.extract_reply if messages[0]["content"] == EXTRACT_SYSTEM else self.judge_reply
        return {"model": SUPER_MODEL,
                "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": content}}]}


class FakeRetrieval:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def embed(self, inputs, input_type):
        return [[1.0, 0.0] for _ in inputs]

    def rerank(self, query, documents, top_n=None):
        return [{"index": index, "relevance_score": 1.0 - index * 0.1} for index in range(len(documents))]


def install_stubs(monkeypatch, chat=FakeChat, retrieval=FakeRetrieval):
    monkeypatch.setattr("nemotron_challenge.claims.ChatClient", chat)
    monkeypatch.setattr("nemotron_challenge.claims.RetrievalClient", retrieval)


def test_valid_claims_drops_bad_quotes_and_types():
    claims, drops = valid_claims({"claims": [
        {"quote": GOOD_QUOTE, "type": "definition"},
        {"quote": "not in the body", "type": "definition"},
        {"quote": OAK_QUOTE, "type": "not-a-type"},
        {"quote": OAK_QUOTE, "type": "quantity", "value": 12.5, "unit": "feet"},
    ]}, ENTRY["body"])
    assert [claim["quote"] for claim in claims] == [GOOD_QUOTE, OAK_QUOTE]
    assert claims[1]["value"] == 12.5 and claims[1]["unit"] == "feet"
    assert drops == {"malformed": 0, "quote_not_found": 1, "invalid_type": 1, "over_limit": 0}
    empty, zero_drops = valid_claims(None, ENTRY["body"])
    assert empty == [] and all(count == 0 for count in zero_drops.values())


def test_judged_claim_downgrades_a_bad_wikipedia_quote():
    kept = ["Ships are made of oak and steel."]
    payload = {"verdict": "agrees", "wikipedia_quote": "Ships are made of platinum",
               "explanation": "Same idea."}
    judged = judged_claim({"quote": OAK_QUOTE, "type": "definition"}, payload, kept)
    assert judged["verdict"] == "not_in_wikipedia"
    assert judged["downgraded"] is True
    assert judged["wikipedia_quote"] is None
    assert judged["rejected_wikipedia_quote"] == "Ships are made of platinum"
    assert judged["explanation"]["kind"] == "inference"


def test_judged_claim_rejects_unknown_verdicts():
    payload = {"verdict": "maybe", "wikipedia_quote": "Ships are made of oak and steel.", "explanation": ""}
    judged = judged_claim({"quote": OAK_QUOTE, "type": "definition"}, payload,
                          ["Ships are made of oak and steel."])
    assert judged["verdict"] == "not_in_wikipedia" and judged["downgraded"] is True


def test_run_claims_records_a_pair_with_funnel_evidence(tmp_path, monkeypatch):
    work = make_work(tmp_path)
    FakeChat.calls = 0
    install_stubs(monkeypatch)
    result = run_claims(make_settings(tmp_path), work)

    assert result["entries_done"] == 1 and result["failures"] == 0
    record = json.loads((work / "claims" / "claims.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert record["entry_id"] == ENTRY["entry_id"]
    assert record["page_id"] == ENTRY["page_id"]
    assert record["scan_sha256"] == "a" * 64
    assert record["article_page_id"] == "101"
    assert record["article_revision_id"] == "777"
    assert record["article_text_sha256"] == "c" * 64
    assert record["claims_dropped"] == 2
    assert len(record["claims"]) == 1
    claim = record["claims"][0]
    assert claim["verdict"] == "agrees"
    assert claim["quote"] in ENTRY["body"]
    assert claim["wikipedia_quote"] in ARTICLE_TEXT
    assert claim["explanation"]["kind"] == "inference"
    assert claim["evidence"] and all("embed_similarity" in row and "rerank_logit" in row
                                     for row in claim["evidence"])
    assert record["section_coverage"][0]["covered"] is True
    summary = json.loads((work / "claims" / "summary.json").read_text(encoding="utf-8"))
    assert summary["note"] == "claims for 1 of 1 matches"
    assert summary["verdict_counts"]["agrees"] == 1


def test_run_claims_writes_failures_and_keeps_going(tmp_path, monkeypatch):
    work = make_work(tmp_path)

    class FailingChat(FakeChat):
        def complete(self, messages, max_tokens=4096, extra_body=None):
            raise ServiceError("service returned HTTP 500", status_code=500)

    install_stubs(monkeypatch, chat=FailingChat)
    result = run_claims(make_settings(tmp_path), work)
    assert result["entries_done"] == 0 and result["entries_failed"] == 1
    failures = (work / "claims" / "failures.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(failures) == 1
    row = json.loads(failures[0])
    assert row["entry_id"] == ENTRY["entry_id"] and "ServiceError" in row["error"]
    summary = json.loads((work / "claims" / "summary.json").read_text(encoding="utf-8"))
    assert summary["failures"] == 1 and summary["note"] == "claims for 0 of 1 matches"


def test_cache_hit_skips_the_model_call(tmp_path, monkeypatch):
    work = make_work(tmp_path)
    FakeChat.calls = 0
    install_stubs(monkeypatch)
    run_claims(make_settings(tmp_path), work)
    first_calls = FakeChat.calls
    assert first_calls >= 2  # one extract, one judge

    # Remove the records but keep the cache: a re-run must not call the model.
    (work / "claims" / "claims.jsonl").unlink()
    FakeChat.calls = 0
    run_claims(make_settings(tmp_path), work)
    assert FakeChat.calls == 0


def test_time_cap_skips_and_reports_without_filling(tmp_path, monkeypatch):
    work = make_work(tmp_path)
    install_stubs(monkeypatch)
    result = run_claims(make_settings(tmp_path), work, deadline=time.time() - 1)
    assert result["entries_done"] == 0
    summary = json.loads((work / "claims" / "summary.json").read_text(encoding="utf-8"))
    assert summary["time_cap_reached"] is True
    assert summary["entries_skipped_by_time_cap"] == 1
    assert summary["note"] == "claims for 0 of 1 matches"
    assert not (work / "claims" / "claims.jsonl").exists()
