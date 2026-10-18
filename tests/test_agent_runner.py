"""Agent runner: the Hermes binary lookup and the strict citation check (B5)."""
import pytest

from nemotron_challenge.agent_runner import check_answer, hermes_bin
from nemotron_challenge.config import ConfigurationError

ENTRY = "britannica:" + "a" * 40 + ":train:107#0000"
URL = "https://en.wikipedia.org/w/index.php?title=Ship&oldid=1234567"


def _session(*tool_texts):
    return {"messages": [{"role": "tool", "content": text} for text in tool_texts]}


def test_hermes_bin_prefers_the_environment(tmp_path, monkeypatch):
    fake = tmp_path / "hermes"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_BIN", str(fake))
    assert hermes_bin() == fake


def test_hermes_bin_falls_back_to_path(monkeypatch):
    monkeypatch.delenv("HERMES_BIN", raising=False)
    monkeypatch.setattr("nemotron_challenge.agent_runner.dotenv_values", lambda _: {})
    monkeypatch.setattr("nemotron_challenge.agent_runner.shutil.which", lambda name: "/usr/local/bin/hermes")
    assert str(hermes_bin()) == "/usr/local/bin/hermes"


def test_hermes_bin_fails_with_a_clear_message(monkeypatch):
    monkeypatch.delenv("HERMES_BIN", raising=False)
    monkeypatch.setattr("nemotron_challenge.agent_runner.dotenv_values", lambda _: {})
    monkeypatch.setattr("nemotron_challenge.agent_runner.shutil.which", lambda name: None)
    with pytest.raises(ConfigurationError, match="HERMES_BIN"):
        hermes_bin()


def test_check_answer_accepts_fully_supported_citations():
    answer = f"Compare [{ENTRY}] with [{URL}]."
    checks = check_answer(answer, _session(f'{{"entry_id": "{ENTRY}"}}', f'{{"url": "{URL}"}}'))
    assert checks["has_citation"] is True
    assert checks["unsupported_ids"] == []
    assert checks["citations_verified"] is True
    assert checks["cited_ids"] == [ENTRY, URL]


def test_check_answer_rejects_an_unsupported_citation():
    answer = f"Compare [{ENTRY}] with [{URL}]."
    checks = check_answer(answer, _session(f'{{"entry_id": "{ENTRY}"}}'))
    assert checks["has_citation"] is False
    assert checks["unsupported_ids"] == [URL]


def test_check_answer_requires_both_sources():
    only_entry = check_answer(f"Only [{ENTRY}].", _session(ENTRY))
    assert only_entry["has_citation"] is False
    assert only_entry["has_wiki_citation"] is False
    only_wiki = check_answer(f"Only [{URL}].", _session(URL))
    assert only_wiki["has_citation"] is False
    assert only_wiki["has_entry_citation"] is False


def test_check_answer_without_a_session_falls_back_to_presence():
    answer = f"Compare [{ENTRY}] with [{URL}]."
    checks = check_answer(answer)
    assert checks["has_citation"] is True
    assert checks["citations_verified"] is False


def test_check_answer_reads_a_wikipedia_revision_number():
    answer = f"See [{ENTRY}] and the Wikipedia article, revision_id: 1234567."
    checks = check_answer(answer, _session(ENTRY, "revision_id: 1234567"))
    assert checks["has_wiki_citation"] is True
    assert checks["has_citation"] is True
    assert checks["unsupported_ids"] == []
