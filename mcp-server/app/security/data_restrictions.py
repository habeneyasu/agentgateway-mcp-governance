"""Application-level restrictions applied by the MCP server itself.

These rules belong to the business application, not the gateway:

- Input validation: identifiers must match their exact format before any
  query runs.
- Result limits: list tools return between 1 and ``MCP_MAX_ROWS`` rows.
- Field allowlists: a tool returns only the fields listed for its record type.
  Fields no tool needs (such as ``date_of_birth``) never leave the server.

Masking of sensitive fields that tools *do* return (national ID, account
number, email, phone) is deliberately left to the gateway's CEL response
guardrails, so data protection policy is enforced centrally.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal

RecordType = Literal["customer", "account", "transaction", "ledger_entry"]

_CUSTOMER_ID = re.compile(r"CUST-[0-9]{4}")
_ACCOUNT_ID = re.compile(r"ACC-[0-9]{4}")

ALLOWED_FIELDS: dict[RecordType, tuple[str, ...]] = {
    "customer": (
        "customer_id", "full_name", "email", "phone", "national_id",
        "risk_rating", "created_at",
    ),
    "account": (
        "account_id", "customer_id", "account_number", "account_type",
        "currency", "status", "opened_at",
    ),
    "transaction": (
        "transaction_id", "account_id", "direction", "amount_cents", "currency",
        "counterparty", "description", "status", "posted_at",
    ),
    "ledger_entry": (
        "entry_id", "account_id", "transaction_id", "entry_type", "amount_cents",
        "balance_after_cents", "posted_at",
    ),
}


class RestrictionError(ValueError):
    """An input or output violates an application-level restriction."""


def validate_customer_id(value: str) -> str:
    if not isinstance(value, str) or not _CUSTOMER_ID.fullmatch(value):
        raise RestrictionError("Invalid customer_id: expected the format CUST-0000.")
    return value


def validate_account_id(value: str) -> str:
    if not isinstance(value, str) or not _ACCOUNT_ID.fullmatch(value):
        raise RestrictionError("Invalid account_id: expected the format ACC-0000.")
    return value


def validate_limit(value: int, max_rows: int) -> int:
    # bool is a subclass of int; reject it explicitly.
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= max_rows:
        raise RestrictionError(f"Invalid limit: must be an integer from 1 to {max_rows}.")
    return value


def restrict_fields(record_type: RecordType, row: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the allowlisted fields for this record type."""
    return {field: row[field] for field in ALLOWED_FIELDS[record_type] if field in row}
