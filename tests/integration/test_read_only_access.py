"""Phase 9: read-only access is enforced at every layer, and the server invariants hold.

Invariant 1: one JSON text block per tool response, no outputSchema/structuredContent.
Invariant 2: app-level validation stays in place behind the gateway.
Invariant 3: non-root, read-only runtime.
"""

import json

import pytest

from conftest import container_python, requires_docker, run_mcp

SAMPLE_ARGS = {
    "get_customer": {"customer_id": "CUST-0001"},
    "get_account": {"account_id": "ACC-1001"},
    "list_transactions": {"account_id": "ACC-1001", "limit": 2},
    "get_ledger_entries": {"account_id": "ACC-1001", "limit": 2},
}
INJECTIONS = [
    "CUST-0001'; DROP TABLE customers;--",
    "CUST-0001' OR '1'='1",
    "CUST-0001; DELETE FROM ledger_entries",
]


@pytest.fixture(scope="module")
def auditor_view(gateway_url, token):
    async def action(session):
        tools = (await session.list_tools()).tools
        results = {name: await session.call_tool(name, args) for name, args in SAMPLE_ARGS.items()}
        injections = [await session.call_tool("get_customer", {"customer_id": value}) for value in INJECTIONS]
        after = await session.call_tool("get_customer", {"customer_id": "CUST-0001"})
        return tools, results, injections, after
    return run_mcp(gateway_url, token("auditor"), action)


# --- Through the gateway -----------------------------------------------------

def test_every_tool_is_read_only_with_no_output_schema(auditor_view):
    tools, *_ = auditor_view
    assert len(tools) == 4
    for tool in tools:
        assert tool.annotations.read_only_hint is True, tool.name
        assert tool.annotations.destructive_hint is False, tool.name
        assert tool.output_schema is None, tool.name


def test_every_response_is_a_single_json_text_block(auditor_view):
    _, results, *_ = auditor_view
    for name, result in results.items():
        assert not result.is_error, name
        assert result.structured_content is None, name
        assert len(result.content) == 1 and result.content[0].type == "text", name
        json.loads(result.content[0].text)


def test_sql_injection_is_rejected_by_app_validation_and_data_survives(auditor_view):
    *_, injections, after = auditor_view
    for result in injections:
        assert result.is_error and "Invalid customer_id" in result.content[0].text
    assert not after.is_error
    assert json.loads(after.content[0].text)["customer"]["customer_id"] == "CUST-0001"


# --- Inside the MCP server container ------------------------------------------

WRITE_PROBE = r"""
import json, os, sqlite3, stat
from pathlib import Path
from app.database import Database

def attempt(fn):
    try:
        fn()
        return "ALLOWED"
    except Exception as exc:
        return type(exc).__name__

def via_app():
    with Database(Path("/data/finance.db"))._connect() as conn:
        conn.execute("DELETE FROM customers")

def via_query_only_on_writable_handle():
    conn = sqlite3.connect("file:/data/finance.db?mode=rw", uri=True)
    conn.execute("PRAGMA query_only = ON")
    conn.execute("DELETE FROM customers")

def via_plain_sqlite():
    conn = sqlite3.connect("/data/finance.db")
    conn.execute("DELETE FROM customers")
    conn.commit()

db, data = os.stat("/data/finance.db"), os.stat("/data")
print(json.dumps({
    "uid": os.getuid(),
    "db_owner": [db.st_uid, db.st_gid], "db_mode": oct(stat.S_IMODE(db.st_mode)),
    "dir_owner": [data.st_uid, data.st_gid], "dir_mode": oct(stat.S_IMODE(data.st_mode)),
    "app_connection": attempt(via_app),
    "query_only": attempt(via_query_only_on_writable_handle),
    "plain_sqlite": attempt(via_plain_sqlite),
    "append_db_file": attempt(lambda: open("/data/finance.db", "ab").close()),
    "create_in_data": attempt(lambda: open("/data/new.db", "w").close()),
    "write_root_fs": attempt(lambda: open("/srv/new.txt", "w").close()),
}))
"""


@pytest.fixture(scope="module")
def write_probe():
    return json.loads(container_python("mcp-server", WRITE_PROBE))


@requires_docker
def test_server_runs_as_non_root(write_probe):
    assert write_probe["uid"] == 10001


@requires_docker
def test_database_file_is_root_owned_and_read_only(write_probe):
    assert write_probe["db_owner"] == [0, 0] and write_probe["db_mode"] == "0o444"
    assert write_probe["dir_owner"] == [0, 0] and write_probe["dir_mode"] == "0o755"


@requires_docker
@pytest.mark.parametrize("attempt", [
    "app_connection",   # mode=ro + query_only, as the server uses it
    "query_only",       # read-write open + query_only (the 0444 file refuses the open)
    "plain_sqlite",     # an ordinary connection, as if the app code were bypassed
    "append_db_file",   # raw file write
    "create_in_data",   # new file next to the database
    "write_root_fs",    # anywhere on the root filesystem
])
def test_write_attempt_is_blocked(write_probe, attempt):
    assert write_probe[attempt] != "ALLOWED", f"{attempt} was allowed"
