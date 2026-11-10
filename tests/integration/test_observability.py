"""Phase 8: gateway metrics and structured access logs record who called what."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import httpx2
import pytest
from mcp.shared.exceptions import MCPError

from conftest import INITIALIZE, raw_post, run_mcp

METRICS_URL = os.environ.get("METRICS_URL", "http://127.0.0.1:15020/metrics")
ROOT = Path(__file__).resolve().parents[2]


def metric(name, **labels):
    """Sum a Prometheus counter over series whose labels include `labels`."""
    text = httpx2.get(METRICS_URL, timeout=5).text
    total = 0.0
    for line in text.splitlines():
        match = re.match(rf"^{name}\{{(.*)\}} (\S+)$", line)
        if match and all(f'{k}="{v}"' in match.group(1) for k, v in labels.items()):
            total += float(match.group(2))
    return total


def call(url, bearer, tool, arguments):
    async def action(session):
        try:
            return await session.call_tool(tool, arguments)
        except MCPError as exc:
            return exc
    return run_mcp(url, bearer, action)


def test_metrics_endpoint_is_served():
    response = httpx2.get(METRICS_URL, timeout=5)
    assert response.status_code == 200
    assert "agentgateway_requests_total" in response.text


def test_tool_calls_are_counted_per_tool(gateway_url, token):
    labels = {"method": "tools/call", "resource": "get_ledger_entries"}
    before = metric("agentgateway_mcp_requests_total", **labels)
    call(gateway_url, token("auditor"), "get_ledger_entries", {"account_id": "ACC-1002", "limit": 1})
    assert metric("agentgateway_mcp_requests_total", **labels) == before + 1


def test_authentication_failures_are_counted(gateway_url):
    labels = {"status": "401", "reason": "JwtAuth"}
    before = metric("agentgateway_requests_total", **labels)
    raw_post(gateway_url, INITIALIZE)
    assert metric("agentgateway_requests_total", **labels) == before + 1


def test_authorization_denials_are_counted(gateway_url, token):
    labels = {"reason": "Authorization"}
    before = metric("agentgateway_requests_total", **labels)
    result = call(gateway_url, token("analyst"), "get_ledger_entries", {"account_id": "ACC-1001"})
    assert isinstance(result, MCPError)
    assert metric("agentgateway_requests_total", **labels) == before + 1


@pytest.mark.skipif(shutil.which("docker") is None, reason="needs the docker CLI to read gateway logs")
def test_access_log_records_caller_role_and_tool(gateway_url, token):
    call(gateway_url, token("auditor"), "get_account", {"account_id": "ACC-1007"})
    logs = subprocess.run(
        ["docker", "compose", "logs", "--no-log-prefix", "--since", "60s", "agentgateway"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    entries = [json.loads(line) for line in logs.splitlines() if line.startswith("{")]
    calls = [e for e in entries if e.get("mcp.method.name") == "tools/call" and e.get("mcp.tool") == "get_account"
             and e.get("user.id") == "auditor-1"]
    assert calls, "no structured log line for the auditor's get_account call"
    entry = calls[-1]
    assert entry["user.role"] == "auditor"
    assert entry["http.status"] == 200
