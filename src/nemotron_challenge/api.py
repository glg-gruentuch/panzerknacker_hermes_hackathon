"""FastAPI backend for the web UI.

Reads the saved artifacts through :class:`~nemotron_challenge.web_adapter.WebAdapter`.
No model call happens at request time except ``POST /api/chat``, which runs the
challenge Hermes profile through ``agent_runner.ask_agent``.

Run it with::

    uv run uvicorn nemotron_challenge.api:app

Environment:
- ``PANZERKNACKER_ARTIFACTS``: artifacts directory (default ``artifacts``)
- ``CHALLENGE_SCAN_DIR``: scan images directory (default ``data/raw/britannica``)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .web_adapter import WebAdapter

DEFAULT_WORK_DIR = Path(os.environ.get("PANZERKNACKER_ARTIFACTS", "artifacts"))
DEFAULT_SCAN_DIR = Path(os.environ.get("CHALLENGE_SCAN_DIR", "data/raw/britannica"))
DEFAULT_DB_PATH = Path(os.environ.get("CHALLENGE_DB_PATH", "data/team.lancedb"))


class ChatRequest(BaseModel):
    topic: str = ""
    question: str = Field(min_length=1, max_length=2000)
    history: list[dict[str, Any]] = Field(default_factory=list)


def create_app(work_dir: Path | str | None = None, scan_dir: Path | str | None = None,
               db_path: Path | str | None = None) -> FastAPI:
    """Build the app over one artifacts directory. Tests pass small fixtures."""
    app = FastAPI(title="Panzerknacker Britannica-Wikipedia API", version="1.0")
    adapter = WebAdapter(work_dir or DEFAULT_WORK_DIR, scan_dir or DEFAULT_SCAN_DIR,
                         db_path if db_path is not None else DEFAULT_DB_PATH)
    app.state.adapter = adapter

    @app.get("/api/topics")
    def topics() -> dict[str, Any]:
        return adapter.topics()

    @app.get("/api/search")
    def search(q: str = "") -> dict[str, Any]:
        return adapter.search(q)

    @app.get("/api/compare")
    def compare(q: str = "") -> dict[str, Any]:
        result = adapter.compare(q)
        if result is None:
            raise HTTPException(status_code=404,
                                detail=f"Nothing in the index matches {q!r}. Try a Britannica headword.")
        return result

    @app.get("/api/cases")
    def cases() -> dict[str, Any]:
        return adapter.cases()

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        return adapter.meta()

    @app.get("/api/scans/{name}.jpg")
    def scan(name: str) -> FileResponse:
        path = adapter.scan_path(name)
        if path is None:
            raise HTTPException(status_code=404, detail=f"No scan named {name!r} is stored.")
        return FileResponse(path, media_type="image/jpeg", filename=path.name)

    @app.get("/api/scans/{name}.json")
    def scan_blocks(name: str) -> dict[str, Any]:
        payload = adapter.page_blocks(name)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"No Parse blocks for {name!r} are stored.")
        return payload

    @app.post("/api/chat")
    def chat(request: ChatRequest) -> dict[str, Any]:
        from .agent_runner import ask_agent

        return ask_agent(request.question, topic=request.topic, adapter=adapter)

    return app


app = create_app()
