"""The static export writes one compare file per entry and the name-rule map (B10)."""
import json
from pathlib import Path

from nemotron_challenge.config import Settings
from nemotron_challenge.site_export import entry_filename, run_export

ENTRY_A = {
    "entry_id": "britannica:rev:train:13#0000", "page_id": "britannica:rev:train:13",
    "filename": "page-0013-a.jpg", "scan_sha256": "a" * 64, "heading": "SHIP-BUILDING",
    "heading_class": "Text", "fragment": False, "subsections": [], "page_header": "292 SHIP-BUILDING.",
    "continued": False, "continued_on": None, "n_blocks": 1,
    "body": "SHIP-BUILDING is the art of constructing vessels.",
}
ENTRY_B = {
    "entry_id": "britannica:rev:train:14#0000", "page_id": "britannica:rev:train:14",
    "filename": "page-0014-b.jpg", "scan_sha256": "b" * 64, "heading": None,
    "heading_class": None, "fragment": True, "subsections": [], "page_header": "VOLCANOES.",
    "continued": True, "continued_on": None, "n_blocks": 1,
    "body": "Aetna burns in Sicily.",
}
MATCH_ROW = {"entry_id": ENTRY_A["entry_id"], "entry_title": "SHIP-BUILDING", "heading_class": "Text",
             "fragment": False, "page_id": ENTRY_A["page_id"], "scan": ENTRY_A["filename"],
             "scan_sha256": "a" * 64, "match_confidence": -3.1, "bm25_rank": 1, "similarity": 0.7,
             "embed_rank": 1, "rerank_rank": 1, "article_page_id": "101", "article_title": "Shipbuilding",
             "article_revision_id": "777", "article_url": "https://en.wikipedia.org/wiki/Shipbuilding",
             "article_text_sha256": "d" * 64}
ARTICLE = {"page_id": "101", "revision_id": "777", "title": "Shipbuilding",
           "url": "https://en.wikipedia.org/wiki/Shipbuilding",
           "provenance": {"text_sha256": "d" * 64}, "license": {"spdx": "CC-BY-SA-4.0"},
           "text": "Shipbuilding is the construction of ships.\n\nIt happens in shipyards."}
COMPARISON = {"entry_id": ENTRY_A["entry_id"], "entry_title": "SHIP-BUILDING", "article_title": "Shipbuilding",
              "match_confidence": -3.1, "method": "test", "britannica": {"excerpt": "SHIP-BUILDING"},
              "wikipedia": {"excerpt": "Shipbuilding"}, "distinctive": {"britannica": [], "wikipedia": []},
              "normalization": {"britannica": {}, "wikipedia": {}}, "citations": []}


def _fixture(tmp_path: Path) -> Path:
    work = tmp_path / "artifacts"
    (work / "extract" / "derived").mkdir(parents=True)
    (work / "extract" / "derived" / "entries.json").write_text(
        json.dumps([ENTRY_A, ENTRY_B]), encoding="utf-8")
    (work / "match" / "articles").mkdir(parents=True)
    (work / "match" / "matches.jsonl").write_text(json.dumps(MATCH_ROW) + "\n", encoding="utf-8")
    (work / "match" / "articles" / "101.json").write_text(json.dumps(ARTICLE), encoding="utf-8")
    (work / "compare").mkdir()
    (work / "compare" / "comparisons.jsonl").write_text(json.dumps(COMPARISON) + "\n", encoding="utf-8")
    run_dir = work / "agent" / "runs" / "scan-check-1"
    run_dir.mkdir(parents=True)
    (run_dir / "command.json").write_text(json.dumps({"question": "Check the scan."}), encoding="utf-8")
    (run_dir / "answer.txt").write_text("The scan says otherwise [B1].", encoding="utf-8")
    (run_dir / "trace.json").write_text(json.dumps({"steps": [{"step": "Tool call", "ms": 12}]}), encoding="utf-8")
    return work


def test_entry_filename_replaces_special_characters():
    assert entry_filename("britannica:309f:train:257#0000") == "britannica_309f_train_257_0000.json"
    assert entry_filename("weird id/with*chars") == "weird_id_with_chars.json"


def test_export_writes_one_compare_file_per_entry(tmp_path):
    work = _fixture(tmp_path)
    out = tmp_path / "app" / "data"
    result = run_export(Settings(db_path=tmp_path / "db"), work, out)

    assert result["entries"] == 2
    for name in ("topics.json", "meta.json", "cases.json", "chat-recorded.json", "compare/index.json"):
        assert (out / name).exists(), name
    index = json.loads((out / "compare" / "index.json").read_text(encoding="utf-8"))
    assert index[ENTRY_A["entry_id"]] == "britannica_rev_train_13_0000.json"
    assert index[ENTRY_B["entry_id"]] == "britannica_rev_train_14_0000.json"
    assert len(index) == len([ENTRY_A, ENTRY_B])
    payload = json.loads((out / "compare" / index[ENTRY_A["entry_id"]]).read_text(encoding="utf-8"))
    assert payload["topic"]["headword"] == "SHIP-BUILDING"
    fragment = json.loads((out / "compare" / index[ENTRY_B["entry_id"]]).read_text(encoding="utf-8"))
    assert fragment["pending"]
    chat = json.loads((out / "chat-recorded.json").read_text(encoding="utf-8"))
    assert chat[0]["recorded"] is True
    assert chat[0]["question"] == "Check the scan."
    assert chat[0]["runDir"].endswith("scan-check-1")
