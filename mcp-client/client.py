"""Scripted MCP client that talks to the MCP server through agentgateway.

Usage:
    python client.py demo                      # list tools, then call each one
    python client.py list                      # list the tools this caller can see
    python client.py call get_customer '{"customer_id": "CUST-0001"}'

Options and environment:
    --url    / MCP_GATEWAY_URL   default http://127.0.0.1:13000/mcp
    --token  / MCP_TOKEN         bearer token sent as `Authorization: Bearer ...`
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any

import httpx2
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_URL = "http://127.0.0.1:13000/mcp"


class _IgnoreAcceptedTermination(logging.Filter):
    """agentgateway answers the session-closing DELETE with 202 Accepted, which
    mcp 2.3.0 logs as a failure (it expects 200 or 204). The session is closed;
    drop only that one message."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage() != "Session termination failed: 202"


logging.getLogger("mcp.client.streamable_http").addFilter(_IgnoreAcceptedTermination())

DEMO_CALLS: list[tuple[str, dict[str, Any]]] = [
    ("get_customer", {"customer_id": "CUST-0001"}),
    ("get_account", {"account_id": "ACC-1001"}),
    ("list_transactions", {"account_id": "ACC-1001", "limit": 3}),
    ("get_ledger_entries", {"account_id": "ACC-1001", "limit": 3}),
]


def _text(result: Any) -> str:
    return "".join(block.text for block in result.content if block.type == "text")


def _pretty(text: str) -> str:
    try:
        return json.dumps(json.loads(text), indent=2)
    except ValueError:
        return text


async def _with_session(url: str, token: str | None, action):
    headers = {"Authorization": f"Bearer {token}"} if token else None
    timeout = httpx2.Timeout(30.0, read=300.0)
    async with httpx2.AsyncClient(headers=headers, timeout=timeout) as http:
        async with streamable_http_client(url, http_client=http) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                return await action(session)


async def list_tools(session: ClientSession) -> int:
    tools = (await session.list_tools()).tools
    print(f"{len(tools)} tool(s) available:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")
    return 0


async def call_tool(session: ClientSession, name: str, arguments: dict[str, Any]) -> int:
    result = await session.call_tool(name, arguments)
    status = "ERROR" if result.is_error else "OK"
    print(f"{name}({json.dumps(arguments)}) -> {status}")
    print(_pretty(_text(result)))
    return 1 if result.is_error else 0


async def demo(session: ClientSession) -> int:
    rc = await list_tools(session)
    for name, arguments in DEMO_CALLS:
        print()
        rc |= await call_tool(session, name, arguments)
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP client for the agentgateway governance demo")
    parser.add_argument("--url", default=os.environ.get("MCP_GATEWAY_URL", DEFAULT_URL))
    parser.add_argument("--token", default=os.environ.get("MCP_TOKEN"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="list tools, then call each one with sample arguments")
    sub.add_parser("list", help="list the tools this caller can see")
    call = sub.add_parser("call", help="call one tool")
    call.add_argument("tool")
    call.add_argument("arguments", nargs="?", default="{}", help="tool arguments as a JSON object")
    args = parser.parse_args()

    if args.command == "demo":
        action = demo
    elif args.command == "list":
        action = list_tools
    else:
        try:
            arguments = json.loads(args.arguments)
        except ValueError as exc:
            parser.error(f"arguments must be a JSON object: {exc}")
        if not isinstance(arguments, dict):
            parser.error("arguments must be a JSON object")
        action = lambda session: call_tool(session, args.tool, arguments)  # noqa: E731

    try:
        return asyncio.run(_with_session(args.url, args.token, action))
    except Exception as exc:  # connection failures arrive wrapped in an ExceptionGroup
        root = exc
        while isinstance(root, BaseExceptionGroup) and root.exceptions:
            root = root.exceptions[0]
        print(f"error: could not complete the request to {args.url}: {type(root).__name__}: {root}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
