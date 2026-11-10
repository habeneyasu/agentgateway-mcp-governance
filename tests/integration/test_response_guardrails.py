"""Phase 7: the gateway masks sensitive fields in tool responses (mcpGuardrails)."""

import json
import re

import pytest

from conftest import run_mcp

CUSTOMERS = [f"CUST-000{i}" for i in range(1, 6)]
ACCOUNTS = [f"ACC-100{i}" for i in range(1, 8)]

# Raw formats of the synthetic sensitive values; none may appear in any response.
RAW_PATTERNS = {
    "national_id": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "account_number": re.compile(r"\b\d{12}\b"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@example\.com"),
    "phone": re.compile(r"555-01\d{2}"),
}


@pytest.fixture(scope="module")
def responses(gateway_url, token):
    """Call every lookup once as the auditor and keep the raw response text."""
    async def action(session):
        out = {}
        for cid in CUSTOMERS:
            out[cid] = await session.call_tool("get_customer", {"customer_id": cid})
        for aid in ACCOUNTS:
            out[aid] = await session.call_tool("get_account", {"account_id": aid})
        out["transactions"] = await session.call_tool("list_transactions", {"account_id": "ACC-1001", "limit": 50})
        out["ledger"] = await session.call_tool("get_ledger_entries", {"account_id": "ACC-1001", "limit": 50})
        out["error"] = await session.call_tool("get_account", {"account_id": "bad-id"})
        return out
    return run_mcp(gateway_url, token("auditor"), action)


def text(result):
    return "".join(block.text for block in result.content if block.type == "text")


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_customer_pii_is_masked(responses, cid):
    customer = json.loads(text(responses[cid]))["customer"]
    assert re.fullmatch(r"\*\*\*-\*\*-\d{4}", customer["national_id"])
    assert re.fullmatch(r"\*\*\*@example\.com", customer["email"])
    assert re.fullmatch(r"\*\*\*-\d{4}", customer["phone"])
    assert customer["customer_id"] == cid and customer["full_name"]


@pytest.mark.parametrize("aid", ACCOUNTS)
def test_account_number_is_masked(responses, aid):
    account = json.loads(text(responses[aid]))["account"]
    assert re.fullmatch(r"\*{8}\d{4}", account["account_number"])
    assert account["account_id"] == aid


def test_no_raw_sensitive_value_appears_in_any_response(responses):
    for name, result in responses.items():
        body = text(result)
        for field, pattern in RAW_PATTERNS.items():
            assert not pattern.search(body), f"raw {field} in {name} response: {pattern.search(body).group()}"


def test_non_sensitive_data_is_unchanged(responses):
    transactions = json.loads(text(responses["transactions"]))
    ledger = json.loads(text(responses["ledger"]))
    assert transactions["count"] == len(transactions["transactions"]) == 5
    assert ledger["count"] == len(ledger["ledger_entries"]) == 5
    assert all(isinstance(t["amount_cents"], int) for t in transactions["transactions"])
    assert ledger["ledger_entries"][0]["balance_after_cents"] > 0


def test_tool_errors_still_reach_the_caller(responses):
    assert responses["error"].is_error
    assert "Invalid account_id" in text(responses["error"])


def test_responses_have_no_structured_content(responses):
    assert all(result.structured_content is None for result in responses.values())
