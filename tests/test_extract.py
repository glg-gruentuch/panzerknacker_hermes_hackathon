"""Extraction blocks, segmentation, and continuation joining stay inspectable."""
import json

from nemotron_challenge.config import PARSE_MODEL, Settings
from nemotron_challenge.extract import (
    clean_heading,
    clean_headword,
    flat_entry,
    headword_of,
    image_data_url,
    join_continuations,
    page_header,
    parse_blocks,
    run_derive,
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


def test_headword_of_detects_inline_headwords_and_rejects_the_rest():
    assert headword_of("ETNA, or Mount Etna, a volcano of Sicily.") == "ETNA"
    assert headword_of("SHIP-BUILDING, the art of constructing vessels.") == "SHIP-BUILDING"
    assert headword_of("A TEMO GUISTO, in multic, figurities to flag.") == "A TEMO GUISTO"
    assert headword_of("SILEX. See FlANT.") == "SILEX"
    assert headword_of("Ataraxy, a term ufed by the floes.") is None
    assert headword_of("ends in close contact with, and cooked or dowelled.") is None
    assert headword_of("292 SHIP-BUILDING.") is None
    assert headword_of("A T reads—timber is then introduced.") is None


def test_clean_headword_drops_markdown_noise():
    assert clean_headword("**ETNA**") == "ETNA"
    assert clean_headword("_SHIP-BUILDING_") == "SHIP-BUILDING"
    assert clean_headword("A  TEMO   GUISTO") == "A TEMO GUISTO"


SEGMENT_HEADWORD = "\n\n".join(
    [
        "<x_0.05><y_0.04>A S T [ 852] A S T<x_0.65><y_0.05><class_Page-header>",
        "<x_0.06><y_0.07>ATE, the goddels of mithief; in the Pagan tho-ology.<x_0.53><y_0.10><class_Text>",
        "<x_0.06><y_0.11>ATEGUA, or ATEGUA, an ancient town of Spain.<x_0.53><y_0.14><class_Text>",
    ]
)

SEGMENT_RUNNING_HEAD = "\n\n".join(
    [
        "<x_0.05><y_0.04>292 SHIP-BUILDING.<x_0.65><y_0.05><class_Page-header>",
        "<x_0.06><y_0.06>Fractical Building<x_0.12><y_0.11><class_Section-header>",
        "<x_0.11><y_0.05>ends in close contact with, and cooked or dowelled to, the sides.<x_0.53><y_0.11><class_Text>",
    ]
)


def test_segment_starts_entries_at_inline_headwords():
    entries, header = segment(SEGMENT_HEADWORD)
    assert header == "A S T [ 852] A S T"
    assert [entry["heading"] for entry in entries] == ["ATE", "ATEGUA"]
    assert all(entry["fragment"] is False for entry in entries)
    assert entries[0]["heading_class"] == "Text"
    assert entries[0]["body"].startswith("ATE, the goddels of mithief")


def test_segment_ignores_the_running_head_as_a_heading():
    entries, header = segment(SEGMENT_RUNNING_HEAD)
    assert header == "292 SHIP-BUILDING."
    assert len(entries) == 1
    entry = entries[0]
    assert entry["heading"] is None
    assert entry["fragment"] is True
    assert entry["page_header"] == "292 SHIP-BUILDING."
    assert "SHIP-BUILDING" not in (entry["heading"] or "")
    assert entry["body"].startswith("ends in close contact")


def test_segment_merges_subsection_headings_into_the_parent_entry():
    markdown = "\n\n".join(
        [
            "<x_0.05><y_0.04>Chap. VI.<x_0.65><y_0.05><class_Page-header>",
            "<x_0.05><y_0.06>CHAP. VI. OF THE SENSES, AND THEIR ORGANS.<x_0.65><y_0.07><class_Section-header>",
            "<x_0.05><y_0.08>Sect. I. _Of Touch._<x_0.65><y_0.09><class_Section-header>",
            "<x_0.05><y_0.10>1. Eyes placed thus<x_0.65><y_0.11><class_Section-header>",
            "<x_0.05><y_0.12>TOUCH is one of the external senses.<x_0.65><y_0.13><class_Text>",
        ]
    )
    entries, _ = segment(markdown)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["heading"] is None
    assert entry["fragment"] is True
    assert entry["subsections"] == [
        "CHAP. VI. OF THE SENSES, AND THEIR ORGANS",
        "Sect. I. Of Touch",
        "1. Eyes placed thus",
    ]


def test_segment_collects_text_before_the_first_headword_as_a_fragment():
    markdown = "\n\n".join(
        [
            "<x_0.06><y_0.06>astronomers are obliged to enlighten the crois-hairs.<x_0.53><y_0.09><class_Text>",
            "<x_0.06><y_0.10>ERANARCHIA, a public officer among the ancient Greeks.<x_0.53><y_0.13><class_Text>",
        ]
    )
    entries, _ = segment(markdown)
    assert [entry["fragment"] for entry in entries] == [True, False]
    assert entries[0]["heading"] is None
    assert entries[0]["body"].startswith("astronomers are obliged")
    assert entries[1]["heading"] == "ERANARCHIA"
    assert entries[1]["body"].startswith("ERANARCHIA, a public officer")


def test_segment_drops_entries_without_content_blocks():
    markdown = "\n\n".join(
        [
            "<x_0.05><y_0.06>ACT [ 97] ACT<x_0.65><y_0.07><class_Section-header>",
            "<x_0.06><y_0.10>ACT, in general, denotes the exertion of powers.<x_0.53><y_0.13><class_Text>",
        ]
    )
    entries, _ = segment(markdown)
    assert len(entries) == 1
    assert entries[0]["heading"] == "ACT"


# Fixtures for B1, taken from real raw replies. page-0257 is a paragraph of
# running text with no headword; 0374 is a full-page picture with no text.
TEXT_ONLY_PAGE = "\n\n".join(
    [
        "<x_0.04><y_0.0375>_Swift_ in his power to provide him indarwify. Swift that person (10/3) in different, having previously taken his matter's degree at Oxford.<x_0.53><y_0.11><class_Text>",
        "<x_0.0986><y_0.1992>This day is generally believed to have been the daughter of Sir William Temple flower, whom he never, a Mrs Hierans, met.<x_0.53><y_0.26><class_Text>",
    ]
)
PICTURE_ONLY_PAGE = "<x_0.0><y_0.0><x_0.998><y_0.9984><class_Picture>"


def test_segment_gives_a_text_only_page_exactly_one_fragment():
    entries, header = segment(TEXT_ONLY_PAGE)
    assert header == ""
    assert len(entries) == 1
    assert entries[0]["fragment"] is True
    assert entries[0]["heading"] is None
    assert entries[0]["body"].startswith("_Swift_ in his power")
    assert "Sir William Temple" in entries[0]["body"]


def test_segment_gives_a_picture_only_page_one_empty_fragment():
    entries, header = segment(PICTURE_ONLY_PAGE)
    assert header == ""
    assert len(entries) == 1
    assert entries[0]["fragment"] is True
    assert entries[0]["heading"] is None
    assert entries[0]["body"] == ""
    assert entries[0]["continued"] is True


def test_segment_keeps_subsection_only_pages_as_a_fragment():
    entries, _ = segment("<x_0.05><y_0.06>3. Eyes placed thus<x_0.65><y_0.07><class_Section-header>")
    assert len(entries) == 1
    assert entries[0]["fragment"] is True
    assert entries[0]["subsections"] == ["3. Eyes placed thus"]
    assert entries[0]["body"] == ""


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
             "heading_class": "Text", "page_header": "P", "continued": False,
             "continued_on": None, "blocks": [{"class": "Text", "text": "x", "bbox": None}], "body": "x"}
    flat = flat_entry(entry)
    assert "blocks" not in flat and flat["n_blocks"] == 1 and flat["body"] == "x"
    assert flat["fragment"] is False and flat["subsections"] == []


def test_flat_entry_carries_fragment_and_subsections():
    entry = {"entry_id": "e2", "page_id": "p", "filename": "f.jpg", "heading": None,
             "heading_class": None, "page_header": "P", "fragment": True,
             "subsections": ["Sect. I. Land", "1. Eyes placed thus"],
             "blocks": [{"class": "Text", "text": "x", "bbox": None}], "body": "x"}
    flat = flat_entry(entry)
    assert flat["heading"] is None
    assert flat["fragment"] is True
    assert flat["subsections"] == ["Sect. I. Land", "1. Eyes placed thus"]


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
    summary = json.loads((work_dir / "extract" / "segment-summary.json").read_text(encoding="utf-8"))
    assert summary["entries"] == coverage["entries"]
    assert summary["headings_matching_running_head_pattern"] == 0


def test_run_derive_keeps_v1_and_writes_the_segment_summary(tmp_path, monkeypatch):
    work_dir = tmp_path / "artifacts"
    raw_dir = work_dir / "extract" / "raw"
    derived_dir = work_dir / "extract" / "derived"
    raw_dir.mkdir(parents=True)
    derived_dir.mkdir(parents=True)
    (derived_dir / "entries.json").write_text('[{"entry_id": "old"}]', encoding="utf-8")
    markdown = "\n\n".join(
        [
            "<x_0.05><y_0.04>292 SHIP-BUILDING.<x_0.65><y_0.05><class_Page-header>",
            "<x_0.11><y_0.05>ends in close contact with the sides.<x_0.53><y_0.11><class_Text>",
        ]
    )
    reply = {"model": PARSE_MODEL, "choices": [{"finish_reason": "stop",
                                                "message": {"role": "assistant", "content": markdown}}]}
    (raw_dir / "page-0001-aaaaaaaaaaaa.jpg.json").write_text(json.dumps(reply), encoding="utf-8")
    (work_dir / "extract" / "coverage.json").write_text(json.dumps({
        "pages_total": 2, "pages_ok": 1, "pages_failed": 1,
        "failures": [{"page_id": "britannica:rev:train:1", "error": "ProtocolError: incomplete"}],
    }), encoding="utf-8")
    pages = [
        {"page_id": "britannica:rev:train:0", "row_index": 0, "volume_id": "1",
         "filename": "page-0001-aaaaaaaaaaaa.jpg", "image_sha256": "a" * 64, "image_bytes": 4},
        {"page_id": "britannica:rev:train:1", "row_index": 1, "volume_id": "1",
         "filename": "page-0002-bbbbbbbbbbbb.jpg", "image_sha256": "b" * 64, "image_bytes": 4},
    ]
    manifest = {"dataset": "NationalLibraryOfScotland/encyclopaedia_britannica_illustrated",
                "revision": "309f765b1ecc83e0a7f7762e44b4a927a7555443", "source_url": "https://example.com",
                "license": "CC0-1.0", "pages": pages}
    monkeypatch.setattr("nemotron_challenge.extract.load_manifest", lambda: manifest)

    result = run_derive(work_dir)

    assert (derived_dir / "entries.v1.json").read_text(encoding="utf-8") == '[{"entry_id": "old"}]'
    entries = json.loads((derived_dir / "entries.json").read_text(encoding="utf-8"))
    assert len(entries) == 1 and entries[0]["fragment"] is True
    summary = json.loads((work_dir / "extract" / "segment-summary.json").read_text(encoding="utf-8"))
    assert summary["entries"] == 1 and summary["fragments"] == 1 and summary["headwords"] == 0
    assert summary["pages_derived"] == 1 and summary["pages_failed"] == 1
    assert summary["pages_with_entries"] == 1
    assert summary["pages_without_entries"] == []
    assert summary["failures"][0]["page_id"] == "britannica:rev:train:1"
    coverage = json.loads((work_dir / "extract" / "coverage.json").read_text(encoding="utf-8"))
    assert coverage["entries"] == 1 and coverage["pages_ok"] == 1
    assert coverage["failures"][0]["error"] == "ProtocolError: incomplete"
    assert "refreshed_by" in coverage
    assert result["stage"] == "derive"


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
