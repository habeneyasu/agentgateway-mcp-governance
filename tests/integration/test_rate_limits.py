"""Phase 6: per-user request rate limiting (localRateLimit keyed by jwt.sub).

The gateway allows bursts of 100 HTTP requests per JWT subject, refilled at
20 per second. On MCP routes a limited request gets HTTP 200 with a JSON-RPC
error (code -32003) and x-ratelimit-* headers, not HTTP 429.

These tests use the dedicated `ratelimit` token (sub: rate-limit-test) so they
never drain the buckets other tests rely on.
"""

import json
import time

import httpx2
import pytest

from conftest import INITIALIZE

BURST = 100
RATE_LIMITED = -32003


def post(client, url, bearer):
    return client.post(url, content=json.dumps(INITIALIZE), headers={
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    })


def is_limited(response):
    try:
        return response.json().get("error", {}).get("code") == RATE_LIMITED
    except ValueError:
        return False


@pytest.fixture(scope="module")
def burst(gateway_url, token):
    """Send 150 requests as fast as possible as the rate-limit test user."""
    time.sleep(1.5)  # start from a full bucket
    with httpx2.Client(timeout=10) as client:
        return [post(client, gateway_url, token("ratelimit")) for _ in range(150)]


def test_requests_within_the_burst_are_allowed(burst):
    assert not any(is_limited(r) for r in burst[:BURST])


def test_requests_beyond_the_burst_are_limited(burst):
    assert sum(is_limited(r) for r in burst[BURST:]) > 0


def test_limited_response_is_a_jsonrpc_error_with_rate_limit_headers(burst):
    limited = next(r for r in burst if is_limited(r))
    body = limited.json()
    assert limited.status_code == 200
    assert body["error"]["message"] == "rate limit exceeded"
    assert "result" not in body
    assert limited.headers["x-ratelimit-limit"] == str(BURST)
    assert limited.headers["x-ratelimit-remaining"] == "0"


def test_other_users_are_not_affected(burst, gateway_url, token):
    with httpx2.Client(timeout=10) as client:
        assert not is_limited(post(client, gateway_url, token("analyst")))


def test_bucket_refills(burst, gateway_url, token):
    time.sleep(1.1)
    with httpx2.Client(timeout=10) as client:
        assert not is_limited(post(client, gateway_url, token("ratelimit")))
