# No `from __future__ import annotations`: the SDK evaluates tool signatures at
# registration time, and the `limit` field description uses a local variable.

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from app.config import Settings
from app.database import Database
from app.security.data_restrictions import restrict_fields, validate_account_id, validate_limit
from app.tools import READ_ONLY, as_json, checked


def register(server: MCPServer, db: Database, settings: Settings) -> None:
    max_rows = settings.max_rows
    default_limit = min(20, max_rows)

    @server.tool(
        name="get_ledger_entries",
        title="Ledger lookup",
        description="List an account's most recent ledger entries with running balances, newest first.",
        annotations=READ_ONLY,
        structured_output=False,
    )
    def get_ledger_entries(
        account_id: Annotated[str, Field(description="Account ID, for example ACC-1001.")],
        limit: Annotated[
            int, Field(description=f"Maximum number of ledger entries to return (1 to {max_rows}).")
        ] = default_limit,
    ) -> str:
        account_id = checked(validate_account_id, account_id)
        limit = checked(validate_limit, limit, max_rows)
        if db.get_account(account_id) is None:
            raise ToolError(f"Account {account_id} not found.")
        rows = db.list_ledger_entries(account_id, limit)
        return as_json({
            "account_id": account_id,
            "count": len(rows),
            "ledger_entries": [restrict_fields("ledger_entry", row) for row in rows],
        })
