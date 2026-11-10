"""Phase 5: per-tool access by JWT role (mcpAuthorization)."""

import pytest
from mcp.shared.exceptions import MCPError

from conftest import run_mcp

ALL_TOOLS = {"get_customer", "get_account", "list_transactions", "get_ledger_entries"}
ANALYST_TOOLS = {"get_customer", "get_account"}
SAMPLE_ARGS = {
    "get_customer": {"customer_id": "CUST-0001"},
    "get_account": {"account_id": "ACC-1001"},
    "list_transactions": {"account_id": "ACC-1001", "limit": 1},
    "get_ledger_entries": {"account_id": "ACC-1001", "limit": 1},
}


def list_tools(url, bearer):
    async def action(session):
        return {tool.name for tool in (await session.list_tools()).tools}
    return run_mcp(url, bearer, action)


def call(url, bearer, tool, arguments):
    """Return the tool result, or the MCPError the gateway raised instead."""
    async def action(session):
        try:
            return await session.call_tool(tool, arguments)
        except MCPError as exc:
            return exc
    return run_mcp(url, bearer, action)


@pytest.mark.parametrize("role, expected", [
    ("auditor", ALL_TOOLS),
    ("analyst", ANALYST_TOOLS),
    ("guest", set()),
])
def test_tool_list_is_filtered_by_role(gateway_url, token, role, expected):
    assert list_tools(gateway_url, token(role)) == expected


@pytest.mark.parametrize("role, tool", [
    *[("auditor", tool) for tool in sorted(ALL_TOOLS)],
    *[("analyst", tool) for tool in sorted(ANALYST_TOOLS)],
])
def test_allowed_calls_succeed(gateway_url, token, role, tool):
    result = call(gateway_url, token(role), tool, SAMPLE_ARGS[tool])
    assert not isinstance(result, MCPError), f"{role} was denied {tool}: {result}"
    assert not result.is_error


@pytest.mark.parametrize("role, tool", [
    *[("analyst", tool) for tool in sorted(ALL_TOOLS - ANALYST_TOOLS)],
    *[("guest", tool) for tool in sorted(ALL_TOOLS)],
])
def test_denied_calls_are_rejected_even_when_the_name_is_known(gateway_url, token, role, tool):
    result = call(gateway_url, token(role), tool, SAMPLE_ARGS[tool])
    assert isinstance(result, MCPError), f"{role} was allowed {tool}"
    assert "ACC-1001" not in str(result)


def test_denied_tool_is_indistinguishable_from_a_missing_tool(gateway_url, token):
    denied = call(gateway_url, token("analyst"), "list_transactions", SAMPLE_ARGS["list_transactions"])
    missing = call(gateway_url, token("analyst"), "no_such_tool", {})
    assert isinstance(denied, MCPError) and isinstance(missing, MCPError)
    assert str(denied) == str(missing)
