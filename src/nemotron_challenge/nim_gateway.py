"""Serve the challenge retrieval contract on top of NVIDIA hosted NIM.

The team's ``RetrievalClient`` expects the container contract in
``docs/model-service.md``: ``GET /v1/models``, ``POST /v1/embeddings`` and
``POST /v1/rerank``. NVIDIA hosts the same two models, but with other request
and reply shapes. This module is a loopback gateway that translates between the
two contracts. The client and the evidence rules stay unchanged.

Differences that the gateway hides:

* The hosted embedder uses ``input_type: passage`` for documents.
* The hosted reranker takes ``query: {text}`` and ``passages: [{text}]``, and
  returns ``rankings`` with ``logit`` values in place of ``results`` with
  ``relevance_score`` values.
* The hosted API accepts text only. It does not decode image records.

The hosted API does not report a model snapshot. The gateway reports the
challenge pin in the catalog with ``revision_verified: false``. Read
``docs/nim-gateway.md`` before you cite a hosted run as evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx
from dotenv import load_dotenv

from .config import (
    ConfigurationError,
    EMBED_DIMENSIONS,
    EMBED_MODEL,
    EMBED_REVISION,
    RERANK_MODEL,
    RERANK_REVISION,
    endpoint,
)

DEFAULT_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
DEFAULT_RERANK_URL = (
    "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-vl-1b-v2/reranking"
)
MAX_BODY_BYTES = 24 * 1024 * 1024
MAX_QUERY_CHARS = 2000
MAX_DOCUMENT_CHARS = 32000
MAX_EMBED_ITEMS = 16
MAX_RERANK_DOCUMENTS = 32
QUEUE_WAIT_SECONDS = 1.0
RESERVED_MARKERS = ("<image>", "<img>", "</img>", "<IMG_CONTEXT>")

# The hosted API reports no snapshot. Keep the pin in the catalog so the strict
# client can verify the model IDs and the vector size, and mark the pin as
# declared rather than verified.
CATALOG = {
    "object": "list",
    "data": [
        {
            "id": EMBED_MODEL,
            "object": "model",
            "revision": EMBED_REVISION,
            "revision_verified": False,
            "dimensions": EMBED_DIMENSIONS,
            "backend": "nvidia-hosted-nim",
        },
        {
            "id": RERANK_MODEL,
            "object": "model",
            "revision": RERANK_REVISION,
            "revision_verified": False,
            "backend": "nvidia-hosted-nim",
        },
    ],
}


class GatewayError(Exception):
    """An error that maps to one HTTP status and a JSON error body."""

    def __init__(self, status: int, detail: str, *, retry_after: str | None = None):
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.retry_after = retry_after

    def body(self) -> dict[str, Any]:
        return {"error": self.detail}


def _text(value: Any, limit: int, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise GatewayError(422, f"{name} must contain 1 to {limit} characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise GatewayError(422, f"{name} must be valid UTF-8") from None
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise GatewayError(422, f"{name} contains an unsupported control character")
    if any(marker in value for marker in RESERVED_MARKERS):
        raise GatewayError(422, f"{name} contains reserved image control tokens")
    return value


def _texts(items: Any, limit: int, limit_chars: int, name: str) -> list[str]:
    if not isinstance(items, list) or not 1 <= len(items) <= limit:
        raise GatewayError(422, f"{name} must contain 1 to {limit} items")
    texts: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise GatewayError(422, "the hosted endpoint accepts text only; image records are not supported")
        texts.append(_text(item, limit_chars, name))
    return texts


def _vector(value: Any) -> list[float]:
    if (
        not isinstance(value, list)
        or len(value) != EMBED_DIMENSIONS
        or any(type(item) not in {int, float} for item in value)
    ):
        raise GatewayError(503, "upstream embedding vector has an invalid size or value")
    return [float(item) for item in value]


class NimBackend:
    """Translate retrieval calls into NVIDIA hosted NIM calls."""

    def __init__(
        self,
        api_key: str,
        *,
        embed_url: str = DEFAULT_EMBED_URL,
        rerank_url: str = DEFAULT_RERANK_URL,
        client: httpx.Client | None = None,
        timeout: float = 120.0,
    ):
        if not api_key:
            raise ConfigurationError("set NVIDIA_API_KEY for the hosted NIM endpoints")
        self._api_key = api_key
        self.embed_url = embed_url
        self.rerank_url = rerank_url
        self._owned = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout, connect=10, pool=10),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
            follow_redirects=False,
        )

    def close(self) -> None:
        if self._owned:
            self._client.close()

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        body = json.dumps(payload, ensure_ascii=True, allow_nan=False).encode()
        try:
            response = self._client.post(url, content=body, headers=headers)
        except httpx.TimeoutException:
            raise GatewayError(503, "upstream_timeout", retry_after="2") from None
        except httpx.HTTPError:
            raise GatewayError(503, "upstream_connection_failed", retry_after="2") from None
        if response.status_code == 429:
            raise GatewayError(429, "upstream_rate_limited", retry_after=response.headers.get("Retry-After") or "5")
        if response.status_code >= 500:
            raise GatewayError(503, f"upstream_http_{response.status_code}", retry_after="2")
        if response.status_code >= 400:
            raise GatewayError(422, "upstream_rejected_the_input")
        try:
            result = response.json()
        except ValueError:
            raise GatewayError(503, "upstream_reply_is_not_json", retry_after="2") from None
        if not isinstance(result, dict):
            raise GatewayError(503, "upstream_reply_is_not_an_object", retry_after="2")
        return result

    def embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        """Send one embed request. Map the challenge document type to passage."""
        hosted_type = "query" if input_type == "query" else "passage"
        result = self._post(self.embed_url, {"model": EMBED_MODEL, "input_type": hosted_type, "input": texts})
        rows = result.get("data")
        if not isinstance(rows, list) or len(rows) != len(texts):
            raise GatewayError(503, "upstream embedding count differs")
        by_index: dict[int, list[float]] = {}
        for row in rows:
            if not isinstance(row, dict) or type(row.get("index")) is not int:
                raise GatewayError(503, "upstream embedding index is invalid")
            index = row["index"]
            if not 0 <= index < len(texts) or index in by_index:
                raise GatewayError(503, "upstream embedding index is repeated or out of range")
            by_index[index] = _vector(row.get("embedding"))
        return [by_index[index] for index in range(len(texts))]

    def rerank(self, query: str, documents: list[str]) -> list[dict[str, Any]]:
        """Send one rerank request and return rows sorted by raw logit, high first."""
        result = self._post(
            self.rerank_url,
            {
                "model": RERANK_MODEL,
                "query": {"text": query},
                "passages": [{"text": document} for document in documents],
            },
        )
        rows = result.get("rankings")
        if not isinstance(rows, list) or len(rows) != len(documents):
            raise GatewayError(503, "upstream ranking count differs")
        seen: set[int] = set()
        scored: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict) or type(row.get("index")) is not int:
                raise GatewayError(503, "upstream ranking index is invalid")
            index, score = row["index"], row.get("logit")
            if not 0 <= index < len(documents) or index in seen:
                raise GatewayError(503, "upstream ranking index is repeated or out of range")
            if not isinstance(score, (int, float)) or isinstance(score, bool):
                raise GatewayError(503, "upstream ranking score is not a number")
            value = float(score)
            if value != value or value in {float("inf"), float("-inf")}:
                raise GatewayError(503, "upstream ranking score is not finite")
            seen.add(index)
            scored.append({"index": index, "relevance_score": value})
        return sorted(scored, key=lambda item: (-item["relevance_score"], item["index"]))


class Gateway:
    """Validate challenge requests, then call the hosted backend."""

    def __init__(self, backend: NimBackend, *, token: str = ""):
        self.backend = backend
        self.token = token
        self._slot = threading.Lock()

    def models(self) -> dict[str, Any]:
        return CATALOG

    def _enter(self) -> None:
        if self._slot.acquire(timeout=QUEUE_WAIT_SECONDS):
            return
        raise GatewayError(429, "the gateway queue is full", retry_after="1")

    def embeddings(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("model") != EMBED_MODEL:
            raise GatewayError(422, "model ID differs")
        input_type = payload.get("input_type")
        if input_type not in {"query", "document"}:
            raise GatewayError(422, "input_type must be query or document")
        limit = MAX_QUERY_CHARS if input_type == "query" else MAX_DOCUMENT_CHARS
        texts = _texts(payload.get("input"), MAX_EMBED_ITEMS, limit, "input")
        self._enter()
        try:
            vectors = self.backend.embed(texts, input_type)
        finally:
            self._slot.release()
        return {
            "object": "list",
            "model": EMBED_MODEL,
            "model_revision": EMBED_REVISION,
            "dimensions": EMBED_DIMENSIONS,
            "normalized": True,
            "data": [
                {"object": "embedding", "index": index, "embedding": vector}
                for index, vector in enumerate(vectors)
            ],
            "backend": "nvidia-hosted-nim",
        }

    def rerank(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("model") != RERANK_MODEL:
            raise GatewayError(422, "model ID differs")
        query = _text(payload.get("query"), MAX_QUERY_CHARS, "query")
        documents = _texts(payload.get("documents"), MAX_RERANK_DOCUMENTS, MAX_DOCUMENT_CHARS, "documents")
        top_n = payload.get("top_n")
        if top_n is not None and (type(top_n) is not int or not 1 <= top_n <= len(documents)):
            raise GatewayError(422, "top_n must be 1 to the document count")
        self._enter()
        try:
            rows = self.backend.rerank(query, documents)
        finally:
            self._slot.release()
        if top_n is not None:
            rows = rows[:top_n]
        return {
            "model": RERANK_MODEL,
            "model_revision": RERANK_REVISION,
            "score_type": "raw_logit",
            "results": rows,
            "backend": "nvidia-hosted-nim",
        }

    def handle(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        path = path.rstrip("/") or "/"
        if method == "GET" and path in {"/health", "/ready"}:
            return 200, {"status": "ok" if path == "/health" else "ready", "backend": "nvidia-hosted-nim"}
        if method == "GET" and path in {"/models", "/v1/models"}:
            return 200, self.models()
        if method == "POST" and path in {"/embeddings", "/v1/embeddings"}:
            return 200, self.embeddings(payload or {})
        if method == "POST" and path in {"/rerank", "/v1/rerank"}:
            return 200, self.rerank(payload or {})
        raise GatewayError(404, "unknown route")


class GatewayHandler(BaseHTTPRequestHandler):
    gateway: Gateway
    server_version = "nim-gateway/0.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Silence the default access log. The gateway logs one line per request."""

    def _send(self, status: int, body: dict[str, Any], *, retry_after: str | None = None) -> None:
        data = json.dumps(body, ensure_ascii=True, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        if retry_after:
            self.send_header("Retry-After", retry_after)
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        if not self.gateway.token:
            return True
        return self.headers.get("Authorization") == f"Bearer {self.gateway.token}"

    def _dispatch(self, method: str) -> None:
        started = time.monotonic()
        status = 200
        try:
            if not self._authorized():
                raise GatewayError(401, "authorization header differs")
            payload = None
            if method == "POST":
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY_BYTES:
                    raise GatewayError(413, "request exceeds the 24 MiB limit")
                raw = self.rfile.read(length) if length else b""
                try:
                    payload = json.loads(raw or b"{}")
                except ValueError:
                    raise GatewayError(422, "request body is not valid JSON") from None
                if not isinstance(payload, dict):
                    raise GatewayError(422, "request body must be a JSON object")
            status, body = self.gateway.handle(method, self.path.split("?", 1)[0], payload)
        except GatewayError as exc:
            status, body = exc.status, exc.body()
            self._send(status, body, retry_after=exc.retry_after)
        except (ValueError, OSError):
            status, body = 500, {"error": "gateway failure"}
            self._send(status, body)
        else:
            self._send(status, body)
        print(f"[nim-gateway] {method} {self.path.split('?', 1)[0]} {status} {time.monotonic() - started:.2f}s",
              file=sys.stderr, flush=True)

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")


def make_server(gateway: Gateway, host: str = "127.0.0.1", port: int = 8001) -> ThreadingHTTPServer:
    """Bind a threaded server. Port 0 asks the operating system for a free port."""
    handler = type("BoundGatewayHandler", (GatewayHandler,), {"gateway": gateway})
    return ThreadingHTTPServer((host, port), handler)


def backend_from_env() -> NimBackend:
    """Read the key and the upstream routes from .env or the environment."""
    load_dotenv(".env", override=False)
    key = os.environ.get("NVIDIA_API_KEY", "").strip() or os.environ.get("NIM_API_KEY", "").strip()
    embed_url = endpoint(os.environ.get("NIM_EMBED_URL", DEFAULT_EMBED_URL), "NIM_EMBED_URL")
    rerank_url = endpoint(os.environ.get("NIM_RERANK_URL", DEFAULT_RERANK_URL), "NIM_RERANK_URL")
    return NimBackend(key, embed_url=embed_url, rerank_url=rerank_url)


def serve_from_env(host: str = "127.0.0.1", port: int = 8001) -> None:
    """Run the gateway until the process stops."""
    backend = backend_from_env()
    gateway = Gateway(backend, token=os.environ.get("NIM_GATEWAY_TOKEN", "").strip())
    server = make_server(gateway, host, port)
    print(f"[nim-gateway] listening on http://{host}:{port}/v1", file=sys.stderr, flush=True)
    print(f"[nim-gateway] embed  -> {backend.embed_url} ({EMBED_MODEL})", file=sys.stderr, flush=True)
    print(f"[nim-gateway] rerank -> {backend.rerank_url} ({RERANK_MODEL})", file=sys.stderr, flush=True)
    print("[nim-gateway] hosted pin is declared, not verified; see docs/nim-gateway.md", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        backend.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nim-gateway", description="Serve the retrieval contract from hosted NIM")
    parser.add_argument("--host", default=os.environ.get("NIM_GATEWAY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("NIM_GATEWAY_PORT", "8001")))
    args = parser.parse_args(argv)
    try:
        serve_from_env(args.host, args.port)
    except ConfigurationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
