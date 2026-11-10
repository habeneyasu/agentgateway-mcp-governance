# No `from __future__ import annotations`: the SDK evaluates tool signatures at
# registration time, and the `limit` field description uses a local variable.

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from app.config import Settings
from app.database import Database
from app.security.data_restrictions import restrict_fields, validate_customer_id
from app.tools import READ_ONLY, as_json, checked


def register(server: MCPServer, db: Database, settings: Settings) -> None:
    @server.tool(
        name="get_customer",
        title="Customer lookup",
        description="Look up a customer's profile and the IDs of their accounts.",
        annotations=READ_ONLY,
        structured_output=False,
    )
    def get_customer(
        customer_id: Annotated[str, Field(description="Customer ID, for example CUST-0001.")],
    ) -> str:
        customer_id = checked(validate_customer_id, customer_id)
        customer = db.get_customer(customer_id)
        if customer is None:
            raise ToolError(f"Customer {customer_id} not found.")
        accounts = db.list_accounts_for_customer(customer_id)
        return as_json({
            "customer": restrict_fields("customer", customer),
            "account_ids": [account["account_id"] for account in accounts],
        })
