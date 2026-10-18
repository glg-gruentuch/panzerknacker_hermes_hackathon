"""Extraction blocks, segmentation, and continuation joining stay inspectable."""
import json
from pathlib import Path

from nemotron_challenge.config import PARSE_MODEL, Settings
from nemotron_challenge.extract import (
    clean_heading,
    flat_entry,
    image_data_url,
    join_continuations,
    page_header,
    parse_blocks,
    run_extract,
    running_head_key,
    segment,
    title_key,
)

SAMPLE_MARKDOWN = "\n\n".join(
    [
        "<x_0.05><y_0.04>292 SHIP-BUILDING.<x_0.65><y_0.05><class_Page-header>",
        "<x_0.06><y_0.06>Fractical Building<x_0.12><y_0.11><class_Section-header>",
        "<x_0.11><y_0.05>ends in close contact with the sides.<x_0.53><y_0.11><class_Text>",
        "<x_0.11><y_0.11>The beams are discussed below.<x_0.53><y_0.21><class_Text>",
        "<x_0.13><y_0.33>1. By chocks.<x_0.54><y_0.36><class_List-item>",
        "292",
        "",
        "<x_0.54><y_0.40>Fig. 2 exhibits a view.<x_0.94><y_0.44><class_Caption>",
    ]
)


def test_parse_blocks_reads_class_text_and_bbox():
    blocks = parse_blocks(SAMPLE_MARKDOWN)
    assert blocks[0]["class"] == "Page-header"
    assert blocks[0]["text"] == "292 SHIP-BUILDING."
    assert blocks[0]["bbox"] == [[0.05, 0.04], [0.65, 0.05]]
    assert blocks[-1]["class"] == "Caption"
    assert all(block["text"] for block in blocks)


def test_parse_blocks_tolerates_missing_tags():
    blocks = parse_blocks("<x_0.1><y_0.2>dangling text with only a prefix")
    assert blocks[0]["class"] is None
    assert blocks[0]["bbox"] is None
    assert blocks[0]["text"] == "dangling text with only a prefix"


def test_page_header_reads_the_running_head():
    assert page_header(parse_blocks(SAMPLE_MARKDOWN)) == "292 SHIP-BUILDING."


def test_segment_groups_text_under_headings_and_skips_running_head():
    entries, header = segment(SAMPLE_MARKDOWN)
    assert header == "292 SHIP-BUILDING."
    assert len(entries) == 1
    entry = entries[0]
    assert entry["heading"] == "Fractical Building"
    assert entry["heading_class"] == "Section-header"
    assert "The beams are discussed below." in entry["body"]
    assert "292 SHIP-BUILDING." not in entry["body"]
    assert [block["class"] for block in entry["blocks"]] == ["Text", "Text", "List-item", "Caption"]


def test_segment_starts_continuation_entry_from_running_head():
    markdown = "\n\n".join(
        [
            "<x_0.05><y_0.04>RES 752<x_0.65><y_0.05><class_Page-header>",
            "<x_0.07><y_0.07>Radiance curvature will be infinite.<x_0.50><y_0.15><class_Text>",
        ]
    )
    entries, _ = segment(markdown)
    assert len(entries) == 1
    assert entries[0]["heading_class"] == "Page-header"
    assert entries[0]["heading"] == "RES 752"


def test_join_continuations_joins_running_head_pages():
    page_a = ("britannica:rev:train:13", [
        {"heading": "Fractical Building", "heading_class": "Section-header", "page_header": "292 SHIP-BUILDING",
         "blocks": [], "body": "First part."},
    ])
    page_b = ("britannica:rev:train:14", [
        {"heading": "293 SHIP-BUILDING", "heading_class": "Page-header", "page_header": "293 SHIP-BUILDING",
         "blocks": [], "body": "Second part."},
    ])
    entries, joins = join_continuations([page_a, page_b])
    assert len(entries) == 1
    assert entries[0]["continued_on"] == "britannica:rev:train:14"
    assert "Second part." in entries[0]["body"]
    assert joins[0]["rule"] == "running-head"


def test_join_continuations_keeps_unrelated_pages_separate():
    page_a = ("britannica:rev:train:13", [
        {"heading": "SHIP-BUILDING", "heading_class": "Section-header", "page_header": "SHIP-BUILDING",
         "blocks": [], "body": "Text."},
    ])
    page_b = ("britannica:rev:train:14", [
        {"heading": "VOLCANOES", "heading_class": "Section-header", "page_header": "VOLCANOES",
         "blocks": [], "body": "Other text."},
    ])
    entries, joins = join_continuations([page_a, page_b])
    assert len(entries) == 2
    assert joins == []


def test_title_key_folds_case_and_punctuation():
    assert title_key("292 SHIP-BUILDING.") == "292 ship building"
    assert title_key("A B  C") == "a b c"


def test_running_head_key_drops_page_numbers():
    assert running_head_key("292 SHIP-BUILDING.") == "ship building"
    assert running_head_key("293 SHIP-BUILDING") == "ship building"
    assert running_head_key("R E S 752 T RES") == "r e s t res"


def test_clean_heading_drops_markdown_artifacts():
    assert clean_heading("## 2. Eyes placed thus, :") == "2. Eyes placed thus"
    assert clean_heading("_1. Eyes placed thus_, :") == "1. Eyes placed thus"
    assert clean_heading("_Eyes eight._") == "Eyes eight"


def test_join_continuations_keeps_numbered_headings_separate():
    page = ("britannica:rev:train:261", [
        {"heading": "1. Eyes placed thus", "heading_class": "Section-header", "page_header": "ENTOMOLOGY",
         "blocks": [], "body": "a"},
        {"heading": "2. Eyes placed thus", "heading_class": "Section-header", "page_header": "ENTOMOLOGY",
         "blocks": [], "body": "b"},
    ])
    entries, joins = join_continuations([page])
    assert len(entries) == 2
    assert joins == []


def test_join_continuations_only_joins_the_first_entry_of_a_page():
    page_a = ("a", [{"heading": "SHIP BUILDING", "heading_class": "Section-header", "page_header": "SHIP",
                     "blocks": [], "body": "x"}])
    page_b = ("b", [
        {"heading": "FIRST", "heading_class": "Section-header", "page_header": "SHIP", "blocks": [], "body": "y"},
        {"heading": "SHIP BUILDING", "heading_class": "Section-header", "page_header": "SHIP", "blocks": [], "body": "z"},
    ])
    entries, joins = join_continuations([page_a, page_b])
    assert len(entries) == 3
    assert joins == []


def test_image_data_url_encodes_and_rejects_bad_input(tmp_path):
    scan = tmp_path / "page.jpg"
    scan.write_bytes(b"\xff\xd8\xff\xe0tiny")
    assert image_data_url(scan).startswith("data:image/jpeg;base64,")
    big = tmp_path / "big.jpg"
    big.write_bytes(b"\xff" + b"0" * (9 * 1024 * 1024))
    try:
        image_data_url(big)
    except ValueError as exc:
        assert "8 MiB" in str(exc)
    else:
        raise AssertionError("oversized scan was accepted")


def test_flat_entry_drops_blocks():
    entry = {"entry_id": "e1", "page_id": "p", "filename": "f.jpg", "heading": "H",
             "heading_class": "Section-header", "page_header": "P", "continued": False,
             "continued_on": None, "blocks": [{"class": "Text", "text": "x", "bbox": None}], "body": "x"}
    flat = flat_entry(entry)
    assert "blocks" not in flat and flat["n_blocks"] == 1 and flat["body"] == "x"


def _fake_reply(markdown: str) -> dict:
    return {
        "model": PARSE_MODEL,
        "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": markdown}}],
    }


class _FakeParseClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def parse(self, image_data_url: str, **kwargs):
        return _fake_reply(SAMPLE_MARKDOWN)


class _BudgetRetryParseClient(_FakeParseClient):
    budgets: list[int] = []

    def parse(self, image_data_url: str, **kwargs):
        from nemotron_challenge.clients import ProtocolError

        budget = kwargs.get("max_tokens", 8744)
        type(self).budgets.append(budget)
        if budget < 16000:
            raise ProtocolError("chat response is incomplete; inspect the token budget and finish_reason")
        return _fake_reply(SAMPLE_MARKDOWN)


class _AlwaysIncompleteParseClient(_FakeParseClient):
    def parse(self, image_data_url: str, **kwargs):
        from nemotron_challenge.clients import ProtocolError

        raise ProtocolError("chat response is incomplete; inspect the token budget and finish_reason")


def test_run_extract_uses_stub_client_and_writes_artifacts(tmp_path, monkeypatch):
    scan_dir = tmp_path / "scans"
    scan_dir.mkdir()
    pages = []
    for index, name in enumerate(["page-0001-aaaaaaaaaaaa.jpg", "page-0002-bbbbbbbbbbbb.jpg"]):
        (scan_dir / name).write_bytes(b"\xff\xd8\xff\xe0tiny")
        pages.append({"page_id": f"britannica:rev:train:{index}", "row_index": index, "volume_id": "1",
                      "filename": name, "image_sha256": "a" * 64, "image_bytes": 4})
    manifest = {"dataset": "NationalLibraryOfScotland/encyclopaedia_britannica_illustrated",
                "revision": "309f765b1ecc83e0a7f7762e44b4a927a7555443", "source_url": "https://example.com",
                "license": "CC0-1.0", "pages": pages}

    monkeypatch.setattr("nemotron_challenge.extract.load_manifest", lambda: manifest)
    monkeypatch.setattr("nemotron_challenge.extract.ParseClient", _FakeParseClient)

    work_dir = tmp_path / "artifacts"
    settings = Settings(db_path=tmp_path / "team.lancedb")
    result = run_extract(settings, work_dir, scan_dir=scan_dir)

    assert result["pages_ok"] == 2
    assert result["pages_failed"] == 0
    assert result["entries"] >= 1
    derived = json.loads((work_dir / "extract" / "derived" / "entries.json").read_text(encoding="utf-8"))
    assert derived and all("body" in row for row in derived)
    assert all(row["scan_sha256"] == "a" * 64 for row in derived)
    page_file = json.loads((work_dir / "extract" / "derived" / "page-0001-aaaaaaaaaaaa.jpg.json").read_text(encoding="utf-8"))
    assert page_file["entries"][0]["blocks"]
    assert page_file["entries"][0]["entry_id"].startswith("britannica:rev:train:0#")
    coverage = json.loads((work_dir / "extract" / "coverage.json").read_text(encoding="utf-8"))
    assert coverage["pages_total"] == 2


def _scan_setup(tmp_path):
    scan_dir = tmp_path / "scans"
    scan_dir.mkdir()
    pages = []
    for index, name in enumerate(["page-0001-aaaaaaaaaaaa.jpg", "page-0002-bbbbbbbbbbbb.jpg"]):
        (scan_dir / name).write_bytes(b"\xff\xd8\xff\xe0tiny")
        pages.append({"page_id": f"britannica:rev:train:{index}", "row_index": index, "volume_id": "1",
                      "filename": name, "image_sha256": "a" * 64, "image_bytes": 4})
    manifest = {"dataset": "NationalLibraryOfScotland/encyclopaedia_britannica_illustrated",
                "revision": "309f765b1ecc83e0a7f7762e44b4a927a7555443", "source_url": "https://example.com",
                "license": "CC0-1.0", "pages": pages}
    return scan_dir, manifest


def test_run_extract_retries_with_a_larger_token_budget(tmp_path, monkeypatch):
    scan_dir, manifest = _scan_setup(tmp_path)
    _BudgetRetryParseClient.budgets = []
    monkeypatch.setattr("nemotron_challenge.extract.load_manifest", lambda: manifest)
    monkeypatch.setattr("nemotron_challenge.extract.ParseClient", _BudgetRetryParseClient)
    result = run_extract(Settings(db_path=tmp_path / "db.lancedb"), tmp_path / "artifacts", scan_dir=scan_dir)
    assert result["pages_ok"] == 2
    assert result["pages_failed"] == 0
    assert 8744 in _BudgetRetryParseClient.budgets and 16000 in _BudgetRetryParseClient.budgets


def test_run_extract_records_a_degenerate_reply_as_failure(tmp_path, monkeypatch):
    scan_dir, manifest = _scan_setup(tmp_path)
    monkeypatch.setattr("nemotron_challenge.extract.load_manifest", lambda: manifest)
    monkeypatch.setattr("nemotron_challenge.extract.ParseClient", _AlwaysIncompleteParseClient)
    result = run_extract(Settings(db_path=tmp_path / "db.lancedb"), tmp_path / "artifacts", scan_dir=scan_dir)
    assert result["pages_ok"] == 0
    assert result["pages_failed"] == 2
    assert all("ProtocolError" in failure["error"] for failure in result["failures"])
