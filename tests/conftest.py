"""Shared fixtures for the integration tests.

The tests assume the stack is already running (`docker compose up -d`) and
credentials exist (`scripts/generate_credentials.sh`).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx2
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
TOKENS_DIR = ROOT / "gateway" / "credentials" / "tokens"
GATEWAY_URL = os.environ.get("MCP_GATEWAY_URL", "http://127.0.0.1:13000/mcp")

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "integration-tests", "version": "0"},
    },
}


@pytest.fixture(scope="session")
def gateway_url() -> str:
    return GATEWAY_URL


@pytest.fixture(scope="session")
def token():
    """Return a function that loads a token by name, e.g. token("analyst")."""
    def load(name: str) -> str:
        path = TOKENS_DIR / f"{name}.jwt"
        if not path.is_file():
            pytest.fail(f"missing {path}; run scripts/generate_credentials.sh")
        return path.read_text().strip()
    return load


def raw_post(url: str, body: dict[str, Any], headers: dict[str, str] | None = None) -> httpx2.Response:
    """POST one JSON-RPC message without the MCP client, to inspect HTTP status codes."""
    all_headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    all_headers.update(headers or {})
    with httpx2.Client(timeout=10) as client:
        return client.post(url, content=json.dumps(body), headers=all_headers)


def run_mcp(url: str, bearer: str | None, action):
    """Open an MCP session through the gateway and run `action(session)`."""
    async def go():
        headers = {"Authorization": f"Bearer {bearer}"} if bearer else None
        async with httpx2.AsyncClient(headers=headers, timeout=httpx2.Timeout(30, read=60)) as http:
            async with streamable_http_client(url, http_client=http) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    return await action(session)
    return asyncio.run(go())
