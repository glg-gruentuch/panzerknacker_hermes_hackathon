"""Transport helpers retry bounded errors and keep files atomic."""
import json

import pytest

from nemotron_challenge.clients import ServiceError
from nemotron_challenge.pipeline import append_jsonl, read_jsonl, retry_call, write_json


def test_retry_call_retries_429_then_succeeds(monkeypatch):
    sleeps = []
    monkeypatch.setattr("nemotron_challenge.pipeline.time.sleep", lambda seconds: sleeps.append(seconds))
    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ServiceError("busy", status_code=429, retry_after="0.1")
        return "ok"

    assert retry_call(flaky) == "ok"
    assert attempts["count"] == 3
    assert sleeps == [0.1, 0.1]


def test_retry_call_does_not_retry_other_statuses(monkeypatch):
    monkeypatch.setattr("nemotron_challenge.pipeline.time.sleep", lambda seconds: pytest.fail("slept"))

    def broken():
        raise ServiceError("bad input", status_code=422)

    with pytest.raises(ServiceError):
        retry_call(broken)


def test_retry_call_raises_after_limit(monkeypatch):
    monkeypatch.setattr("nemotron_challenge.pipeline.time.sleep", lambda seconds: None)

    def always_busy():
        raise ServiceError("busy", status_code=503)

    with pytest.raises(ServiceError):
        retry_call(always_busy, attempts=2)


def test_retry_call_ignores_a_bad_retry_after(monkeypatch):
    sleeps = []
    monkeypatch.setattr("nemotron_challenge.pipeline.time.sleep", lambda seconds: sleeps.append(seconds))
    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ServiceError("busy", status_code=503, retry_after="soon")
        return "ok"

    assert retry_call(flaky) == "ok"
    assert sleeps == [1.0]


def test_write_json_is_atomic(tmp_path):
    target = tmp_path / "nested" / "value.json"
    write_json(target, {"a": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    assert list(target.parent.glob("*.tmp")) == []


def test_jsonl_round_trip(tmp_path):
    path = tmp_path / "rows.jsonl"
    append_jsonl(path, [{"id": 1}, {"id": 2}])
    append_jsonl(path, [{"id": 3}])
    assert [row["id"] for row in read_jsonl(path)] == [1, 2, 3]
    assert read_jsonl(tmp_path / "missing.jsonl") == []
