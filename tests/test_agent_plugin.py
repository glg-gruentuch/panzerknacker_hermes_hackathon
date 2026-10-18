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


def load_plugin():
    spec = importlib.util.spec_from_file_location("challenge_plugin", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_artifacts(tmp_path) -> None:
    compare = tmp_path / "compare"
    compare.mkdir(parents=True)
    (compare / "comparisons.jsonl").write_text(json.dumps(ROW) + "\n", encoding="utf-8")


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


def test_register_installs_both_tools():
    plugin = load_plugin()
    registered = {}

    class FakeContext:
        def register_tool(self, name, toolset, schema, handler):
            registered[name] = {"toolset": toolset, "schema": schema, "handler": handler}

    plugin.register(FakeContext())
    assert set(registered) == {"challenge_search", "challenge_compare"}
    assert all(entry["toolset"] == "nemotron_challenge" for entry in registered.values())
    assert registered["challenge_compare"]["schema"]["name"] == "challenge_compare"
