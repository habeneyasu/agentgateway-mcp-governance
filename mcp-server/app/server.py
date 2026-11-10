"""MCP server entry point: ``python -m app.server``."""

from __future__ import annotations

import logging

from mcp.server.mcpserver import MCPServer

from app.config import Settings, load_settings
from app.database import Database
from app.tools import accounts, customers, ledger, transactions

SERVER_NAME = "agentgateway-mcp-governance-server"
SERVER_VERSION = "0.1.0"


def create_server(settings: Settings) -> MCPServer:
    db = Database(settings.db_path)
    server = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions=(
            "Read-only governance tools over synthetic financial data: "
            "customers, accounts, transactions and ledger entries."
        ),
    )
    for module in (customers, accounts, transactions, ledger):
        module.register(server, db, settings)
    return server


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    server = create_server(settings)
    # Stateless JSON responses: the gateway owns client sessions, and each
    # tool call is an independent, read-only query.
    server.run(
        "streamable-http",
        host=settings.host,
        port=settings.port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
