"""Gateway contract tests use a stub upstream and a real loopback HTTP server."""
import json
import threading

import httpx
import pytest

from nemotron_challenge.clients import RetrievalClient, ServiceError
from nemotron_challenge.config import (
    EMBED_DIMENSIONS,
    EMBED_MODEL,
    EMBED_REVISION,
    RERANK_MODEL,
    RERANK_REVISION,
)
from nemotron_challenge.nim_gateway import Gateway, GatewayError, NimBackend, make_server

VECTOR = [1.0] + [0.0] * (EMBED_DIMENSIONS - 1)


def backend(handler, key="test-key"):
    return NimBackend(key, client=httpx.Client(transport=httpx.MockTransport(handler)))


def embed_reply(vectors):
    return httpx.Response(200, json={
        "model": EMBED_MODEL,
        "data": [{"index": index, "embedding": vector} for index, vector in enumerate(vectors)],
    })


def test_embedding_maps_document_to_passage_and_returns_contract():
    seen = {}

    def handle(request):
        seen["path"] = request.url.path
        seen["auth"] = request.headers["Authorization"]
        seen["payload"] = json.loads(request.content)
        return embed_reply([VECTOR, VECTOR])

    gateway = Gateway(backend(handle))
    status, body = gateway.handle("POST", "/v1/embeddings", {
        "model": EMBED_MODEL, "input": ["first", "second"], "input_type": "document",
    })

    assert status == 200
    assert seen["payload"] == {"model": EMBED_MODEL, "input_type": "passage", "input": ["first", "second"]}
    assert seen["auth"] == "Bearer test-key"
    assert body["model"] == EMBED_MODEL and body["model_revision"] == EMBED_REVISION
    assert body["dimensions"] == EMBED_DIMENSIONS and body["normalized"] is True
    assert [row["index"] for row in body["data"]] == [0, 1]


def test_embedding_restores_input_order_and_query_type():
    def handle(request):
        assert json.loads(request.content)["input_type"] == "query"
        return httpx.Response(200, json={
            "data": [{"index": 1, "embedding": [0.0, 1.0] + [0.0] * 2046},
                     {"index": 0, "embedding": VECTOR}],
        })

    status, body = Gateway(backend(handle)).handle(
        "POST", "/v1/embeddings", {"model": EMBED_MODEL, "input": ["one", "two"], "input_type": "query"}
    )
    assert status == 200
    assert body["data"][0]["embedding"] == VECTOR
    assert body["data"][1]["embedding"][1] == 1.0


def test_rerank_maps_passages_and_sorts_raw_logits():
    seen = {}

    def handle(request):
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"rankings": [
            {"index": 0, "logit": -3.5}, {"index": 2, "logit": -1.25}, {"index": 1, "logit": -2.0},
        ]})

    gateway = Gateway(backend(handle))
    status, body = gateway.handle("POST", "/v1/rerank", {
        "model": RERANK_MODEL, "query": "telephone",
        "documents": ["one", "two", "three"], "top_n": 2,
    })

    assert status == 200
    assert seen["payload"] == {
        "model": RERANK_MODEL,
        "query": {"text": "telephone"},
        "passages": [{"text": "one"}, {"text": "two"}, {"text": "three"}],
    }
    assert body["score_type"] == "raw_logit" and body["model_revision"] == RERANK_REVISION
    assert body["results"] == [{"index": 2, "relevance_score": -1.25},
                               {"index": 1, "relevance_score": -2.0}]


@pytest.mark.parametrize("payload,detail", [
    ({"model": EMBED_MODEL, "input": [{"text": "scan", "image": "data:image/png;base64,AA=="}], "input_type": "document"},
     "image records are not supported"),
    ({"model": EMBED_MODEL, "input": ["a"] * 17, "input_type": "document"}, "1 to 16 items"),
    ({"model": EMBED_MODEL, "input": ["<image>"], "input_type": "document"}, "reserved image control tokens"),
    ({"model": "other/model", "input": ["a"], "input_type": "document"}, "model ID differs"),
    ({"model": EMBED_MODEL, "input": ["a"], "input_type": "passage"}, "input_type must be query or document"),
])
def test_bad_requests_fail_before_upstream(payload, detail):
    calls = []

    def handle(request):
        calls.append(request.url.path)
        return embed_reply([VECTOR])

    with pytest.raises(GatewayError) as error:
        Gateway(backend(handle)).handle("POST", "/v1/embeddings", payload)
    assert error.value.status == 422 and detail in error.value.detail
    assert calls == []


def test_rerank_rejects_documents_above_the_limit_before_upstream():
    gateway = Gateway(backend(lambda request: pytest.fail("upstream called")))
    with pytest.raises(GatewayError) as error:
        gateway.handle("POST", "/v1/rerank", {"model": RERANK_MODEL, "query": "q", "documents": ["d"] * 33})
    assert error.value.status == 422


def test_upstream_rate_limit_is_forwarded_with_retry_after():
    def handle(request):
        return httpx.Response(429, headers={"Retry-After": "7"}, json={"error": "slow down"})

    with pytest.raises(GatewayError) as error:
        Gateway(backend(handle)).handle(
            "POST", "/v1/embeddings", {"model": EMBED_MODEL, "input": ["a"], "input_type": "document"}
        )
    assert (error.value.status, error.value.retry_after) == (429, "7")


@pytest.mark.parametrize("status", [500, 503])
def test_upstream_server_errors_become_retryable_503(status):
    with pytest.raises(GatewayError) as error:
        Gateway(backend(lambda request: httpx.Response(status, json={"error": "boom"}))).handle(
            "POST", "/v1/embeddings", {"model": EMBED_MODEL, "input": ["a"], "input_type": "document"}
        )
    assert error.value.status == 503 and error.value.retry_after == "2"


def test_upstream_bad_vector_shape_stops_the_reply():
    def handle(request):
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]})

    with pytest.raises(GatewayError) as error:
        Gateway(backend(handle)).handle(
            "POST", "/v1/embeddings", {"model": EMBED_MODEL, "input": ["a"], "input_type": "document"}
        )
    assert error.value.status == 503


def test_missing_key_is_a_configuration_error():
    with pytest.raises(Exception) as error:
        NimBackend("")
    assert "NVIDIA_API_KEY" in str(error.value)


@pytest.fixture()
def served():
    """Run the gateway on a free port with a stub upstream, then stop it."""
    def handle(request):
        if request.url.path.endswith("/embeddings"):
            payload = json.loads(request.content)
            return embed_reply([
                [1.0 if position == index else 0.0 for position in range(EMBED_DIMENSIONS)]
                for index in range(len(payload["input"]))
            ])
        return httpx.Response(200, json={"rankings": [
            {"index": index, "logit": -1.0 - index / 10} for index in range(len(json.loads(request.content)["passages"]))
        ]})

    server = make_server(Gateway(backend(handle)), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}/v1"
    try:
        yield base, server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_real_client_accepts_the_gateway_contract(served):
    base, _ = served
    with RetrievalClient(base) as client:
        rows = client.verify_models()
        assert rows[EMBED_MODEL]["dimensions"] == EMBED_DIMENSIONS
        vectors = client.embed(["entry text", "candidate text"], "document")
        assert len(vectors) == 2 and len(vectors[0]) == EMBED_DIMENSIONS
        results = client.rerank("entry text", ["first", "second"], top_n=2)
    assert [row["index"] for row in results] == [0, 1]
    assert results[0]["relevance_score"] >= results[1]["relevance_score"]


def test_http_errors_carry_the_gateway_detail(served):
    base, _ = served
    with httpx.Client(base_url=base) as http:
        assert http.get("/models").json()["data"][0]["revision_verified"] is False
        response = http.post("/embeddings", json={"model": EMBED_MODEL, "input": ["<img>"], "input_type": "document"})
    assert response.status_code == 422
    assert "reserved image control tokens" in response.json()["error"]


def test_optional_token_guards_the_routes(served):
    base, _ = served
    server = make_server(Gateway(backend(lambda request: embed_reply([VECTOR])), token="local-token"), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/v1/models"
    try:
        assert httpx.get(url).status_code == 401
        assert httpx.get(url, headers={"Authorization": "Bearer local-token"}).status_code == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
