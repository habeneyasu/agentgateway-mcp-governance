"""Phase 4: the gateway rejects every request without a valid JWT."""

import json

import pytest

from conftest import INITIALIZE, raw_post, run_mcp

EXPECTED_TOOLS = {"get_customer", "get_account", "list_transactions", "get_ledger_entries"}


def test_request_without_token_is_rejected(gateway_url):
    response = raw_post(gateway_url, INITIALIZE)
    assert response.status_code == 401


def test_malformed_token_is_rejected(gateway_url):
    response = raw_post(gateway_url, INITIALIZE, {"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_non_bearer_scheme_is_rejected(gateway_url, token):
    response = raw_post(gateway_url, INITIALIZE, {"Authorization": f"Basic {token('analyst')}"})
    assert response.status_code == 401


@pytest.mark.parametrize("name", ["bad-signature", "expired", "wrong-issuer", "wrong-audience"])
def test_invalid_token_is_rejected(gateway_url, token, name):
    response = raw_post(gateway_url, INITIALIZE, {"Authorization": f"Bearer {token(name)}"})
    assert response.status_code == 401, f"{name} token was not rejected"


def test_rejected_tool_call_never_reaches_the_server(gateway_url, token):
    call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "get_customer", "arguments": {"customer_id": "CUST-0001"}}}
    response = raw_post(gateway_url, call, {"Authorization": f"Bearer {token('expired')}"})
    assert response.status_code == 401
    assert "900-12-3401" not in response.text


@pytest.mark.parametrize("name", ["analyst", "auditor"])
def test_valid_token_can_use_mcp(gateway_url, token, name):
    async def action(session):
        tools = {tool.name for tool in (await session.list_tools()).tools}
        result = await session.call_tool("get_account", {"account_id": "ACC-1001"})
        return tools, result

    tools, result = run_mcp(gateway_url, token(name), action)
    assert tools == EXPECTED_TOOLS
    assert not result.is_error
    assert json.loads(result.content[0].text)["account"]["account_id"] == "ACC-1001"
