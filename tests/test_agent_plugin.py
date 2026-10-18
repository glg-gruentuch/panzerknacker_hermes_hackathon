"""The Hermes plugin answers from stored artifacts and admits missing evidence."""
import importlib.util
import json
from pathlib import Path

PLUGIN_PATH = Path(__file__).resolve().parents[1] / "integrations" / "hermes" / "nemotron-challenge" / "__init__.py"

ROW = {
    "entry_id": "britannica:rev:train:13#0000",
    "entry_title": "SHIP BUILDING",
    "article_title": "Shipbuilding",
    "match_confidence": 4.2,
    "method": "test method",
    "britannica": {"page_id": "britannica:rev:train:13", "scan": "page-0013.jpg", "excerpt": "The ship..."},
    "wikipedia": {"page_id": "101", "revision_id": "777", "url": "https://wiki/101", "excerpt": "Shipbuilding..."},
    "distinctive": {"britannica": [{"term": "aetna", "log_odds": 2.1, "count_a": 4, "count_b": 0}]},
    "citations": [{"source": "britannica", "page_id": "britannica:rev:train:13"},
                  {"source": "wikipedia", "page_id": "101", "revision_id": "777"}],
}


CLAIMS_ROW = {
    "entry_id": "britannica:rev:train:13#0000",
    "page_id": "britannica:rev:train:13",
    "article_page_id": "101",
    "article_revision_id": "777",
    "article_title": "Shipbuilding",
    "claims": [
        {"quote": "The ship...", "type": "definition", "verdict": "agrees",
         "wikipedia_quote": "Shipbuilding...", "explanation": {"kind": "inference", "text": "Both agree."},
         "downgraded": False},
    ],
    "claims_dropped": 1,
    "section_coverage": [],
}

MATCH_ROW = {"entry_id": "britannica:rev:train:13#0000", "entry_title": "SHIP BUILDING",
             "article_url": "https://wiki/101"}


def load_plugin():
    spec = importlib.util.spec_from_file_location("challenge_plugin", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_artifacts(tmp_path) -> None:
    compare = tmp_path / "compare"
    compare.mkdir(parents=True)
    (compare / "comparisons.jsonl").write_text(json.dumps(ROW) + "\n", encoding="utf-8")
    match = tmp_path / "match"
    match.mkdir(parents=True)
    (match / "matches.jsonl").write_text(json.dumps(MATCH_ROW) + "\n", encoding="utf-8")
    claims = tmp_path / "claims"
    claims.mkdir(parents=True)
    (claims / "claims.jsonl").write_text(json.dumps(CLAIMS_ROW) + "\n", encoding="utf-8")


def _write_scan_page(tmp_path, *, filename="page-9999-aaaaaaaaaaaa.jpg", page_id="britannica:rev:train:9999"):
    """A small real JPEG plus a derived page file with one text block."""
    from PIL import Image

    scans = tmp_path / "scans"
    scans.mkdir()
    Image.new("RGB", (320, 120), "white").save(scans / filename, format="JPEG")
    derived = tmp_path / "artifacts" / "extract" / "derived"
    derived.mkdir(parents=True)
    (derived / f"{filename}.json").write_text(json.dumps({
        "page_id": page_id, "filename": filename, "page_header": "",
        "entries": [{"blocks": [
            {"class": "Text", "text": "Fractical Building here", "bbox": [[0.1, 0.1], [0.5, 0.3]]},
        ]}],
    }), encoding="utf-8")
    return scans, page_id


def test_search_returns_stored_matches(tmp_path, monkeypatch):
    _write_artifacts(tmp_path)
    monkeypatch.setenv("PANZERKNACKER_ARTIFACTS", str(tmp_path))
    plugin = load_plugin()
    result = json.loads(plugin.handle_search({"query": "ship building"}))
    assert result["status"] == "ok"
    assert result["matches"][0]["entry_id"] == ROW["entry_id"]


def test_search_reports_missing_evidence(tmp_path, monkeypatch):
    _write_artifacts(tmp_path)
    monkeypatch.setenv("PANZERKNACKER_ARTIFACTS", str(tmp_path))
    plugin = load_plugin()
    result = json.loads(plugin.handle_search({"query": "unfindable topic"}))
    assert result["status"] == "insufficient_evidence"


def test_compare_returns_citations(tmp_path, monkeypatch):
    _write_artifacts(tmp_path)
    monkeypatch.setenv("PANZERKNACKER_ARTIFACTS", str(tmp_path))
    plugin = load_plugin()
    result = json.loads(plugin.handle_compare({"entry_id": ROW["entry_id"]}))
    assert result["status"] == "ok"
    assert [citation["source"] for citation in result["citations"]] == ["britannica", "wikipedia"]
    assert result["britannica"]["page_id"] == "britannica:rev:train:13"


def test_compare_rejects_unknown_entry(tmp_path, monkeypatch):
    _write_artifacts(tmp_path)
    monkeypatch.setenv("PANZERKNACKER_ARTIFACTS", str(tmp_path))
    plugin = load_plugin()
    result = json.loads(plugin.handle_compare({"entry_id": "britannica:rev:train:999#0000"}))
    assert result["status"] == "insufficient_evidence"
    assert "Do not guess" in result["detail"]


def test_compare_without_artifact_file(tmp_path, monkeypatch):
    monkeypatch.setenv("PANZERKNACKER_ARTIFACTS", str(tmp_path / "empty"))
    plugin = load_plugin()
    result = json.loads(plugin.handle_compare({"entry_id": ROW["entry_id"]}))
    assert result["status"] == "insufficient_evidence"


def test_register_installs_all_tools():
    plugin = load_plugin()
    registered = {}

    class FakeContext:
        def register_tool(self, name, toolset, schema, handler):
            registered[name] = {"toolset": toolset, "schema": schema, "handler": handler}

    plugin.register(FakeContext())
    assert set(registered) == {"challenge_search", "challenge_compare", "challenge_claims", "challenge_scan_check"}
    assert all(entry["toolset"] == "nemotron_challenge" for entry in registered.values())
    assert registered["challenge_compare"]["schema"]["name"] == "challenge_compare"
    assert registered["challenge_scan_check"]["schema"]["name"] == "challenge_scan_check"


def test_claims_returns_verdicts_and_citations(tmp_path, monkeypatch):
    _write_artifacts(tmp_path)
    monkeypatch.setenv("PANZERKNACKER_ARTIFACTS", str(tmp_path))
    plugin = load_plugin()
    result = json.loads(plugin.handle_claims({"entry_id": ROW["entry_id"]}))
    assert result["status"] == "ok"
    assert result["claims"][0]["verdict"] == "agrees"
    assert result["claims"][0]["explanation"]["kind"] == "inference"
    assert [citation["source"] for citation in result["citations"]] == ["britannica", "wikipedia"]
    assert result["article_url"] == "https://wiki/101"


def test_claims_reports_missing_evidence(tmp_path, monkeypatch):
    _write_artifacts(tmp_path)
    monkeypatch.setenv("PANZERKNACKER_ARTIFACTS", str(tmp_path))
    plugin = load_plugin()
    result = json.loads(plugin.handle_claims({"entry_id": "britannica:rev:train:999#0000"}))
    assert result["status"] == "insufficient_evidence"


def test_scan_check_crops_and_returns_the_vision_verdict(tmp_path, monkeypatch):
    scans, page_id = _write_scan_page(tmp_path)
    monkeypatch.setenv("PANZERKNACKER_ARTIFACTS", str(tmp_path / "artifacts"))
    monkeypatch.setenv("PANZERKNACKER_SCANS", str(scans))
    plugin = load_plugin()
    seen = {}

    def fake_vision(image_url, quote):
        seen["image_url"] = image_url
        seen["quote"] = quote
        return 'Here you go: {"result": "mismatch", "reason": "The image reads Practical Building."}'

    monkeypatch.setattr(plugin, "_vision_check", fake_vision)
    result = json.loads(plugin.handle_scan_check({"page_id": page_id, "quote": "Fractical Building"}))
    assert result["status"] == "ok"
    assert result["result"] == "mismatch"
    assert result["bbox"] == [[0.1, 0.1], [0.5, 0.3]]
    assert seen["image_url"].startswith("data:image/png;base64,")
    assert seen["quote"] == "Fractical Building"


def test_scan_check_reports_match(tmp_path, monkeypatch):
    scans, page_id = _write_scan_page(tmp_path)
    monkeypatch.setenv("PANZERKNACKER_ARTIFACTS", str(tmp_path / "artifacts"))
    monkeypatch.setenv("PANZERKNACKER_SCANS", str(scans))
    plugin = load_plugin()
    monkeypatch.setattr(plugin, "_vision_check",
                        lambda image_url, quote: '{"result": "match", "reason": "The words are printed."}')
    result = json.loads(plugin.handle_scan_check({"page_id": page_id, "quote": "Fractical"}))
    assert result["result"] == "match"


def test_scan_check_unknown_quote_is_not_found(tmp_path, monkeypatch):
    scans, page_id = _write_scan_page(tmp_path)
    monkeypatch.setenv("PANZERKNACKER_ARTIFACTS", str(tmp_path / "artifacts"))
    monkeypatch.setenv("PANZERKNACKER_SCANS", str(scans))
    plugin = load_plugin()
    result = json.loads(plugin.handle_scan_check({"page_id": page_id, "quote": "not on this page"}))
    assert result["status"] == "not_found"


def test_scan_check_unknown_page_is_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("PANZERKNACKER_ARTIFACTS", str(tmp_path / "artifacts"))
    plugin = load_plugin()
    result = json.loads(plugin.handle_scan_check({"page_id": "britannica:rev:train:404", "quote": "x"}))
    assert result["status"] == "not_found"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_search_uses_the_backend_when_it_answers(tmp_path, monkeypatch):
    monkeypatch.setenv("PANZERKNACKER_ARTIFACTS", str(tmp_path))
    monkeypatch.setenv("CHALLENGE_API_URL", "http://api.test")
    plugin = load_plugin()
    payload = {"results": [{"entry_id": "britannica:rev:train:13#0000", "heading": "SHIP BUILDING", "score": 3.2}]}
    monkeypatch.setattr(plugin.urllib.request, "urlopen",
                        lambda request, timeout=None: _FakeResponse(payload))
    result = json.loads(plugin.handle_search({"query": "ship"}))
    assert result["status"] == "ok"
    assert result["search"] == "lance"
    assert result["matches"][0]["heading"] == "SHIP BUILDING"


def test_search_falls_back_when_the_backend_fails(tmp_path, monkeypatch):
    _write_artifacts(tmp_path)
    monkeypatch.setenv("PANZERKNACKER_ARTIFACTS", str(tmp_path))
    monkeypatch.setenv("CHALLENGE_API_URL", "http://api.test")

    def boom(request, timeout=None):
        raise OSError("connection refused")

    plugin = load_plugin()
    monkeypatch.setattr(plugin.urllib.request, "urlopen", boom)
    result = json.loads(plugin.handle_search({"query": "ship building"}))
    assert result["status"] == "ok"
    assert result["search"] == "fallback"
    assert result["matches"][0]["entry_id"] == ROW["entry_id"]
