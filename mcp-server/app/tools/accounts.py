# No `from __future__ import annotations`: the SDK evaluates tool signatures at
# registration time, and the `limit` field description uses a local variable.

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from app.config import Settings
from app.database import Database
from app.security.data_restrictions import restrict_fields, validate_account_id
from app.tools import READ_ONLY, as_json, checked


def register(server: MCPServer, db: Database, settings: Settings) -> None:
    @server.tool(
        name="get_account",
        title="Account lookup",
        description="Look up an account's details, including its owner and status.",
        annotations=READ_ONLY,
        structured_output=False,
    )
    def get_account(
        account_id: Annotated[str, Field(description="Account ID, for example ACC-1001.")],
    ) -> str:
        account_id = checked(validate_account_id, account_id)
        account = db.get_account(account_id)
        if account is None:
            raise ToolError(f"Account {account_id} not found.")
        return as_json({"account": restrict_fields("account", account)})
