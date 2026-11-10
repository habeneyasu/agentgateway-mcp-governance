# Testing

The integration tests run against the live stack and check each control from the outside, the way a real client would see it. There are 69 tests, and the suite takes about 10 seconds.

## Running the tests

Prerequisites: Docker 28+ with Docker Compose, Python 3.12, openssl, make.

```bash
make venv     # .venv with mcp==2.3.0 and pytest
make up       # generate credentials if missing, build, start, wait until healthy
make test     # run the suite
make down
```

Without make:

```bash
scripts/generate_credentials.sh
docker compose up -d --build --wait
pip install -r tests/requirements.txt
pytest
```

The tests **assume the stack is already running**; they don't start or stop it. Override the endpoints with `MCP_GATEWAY_URL` (default `http://127.0.0.1:13000/mcp`) and `METRICS_URL` (default `http://127.0.0.1:15020/metrics`).

## What each file proves

| File | Tests | Proves |
| --- | --- | --- |
| `test_authentication.py` | 10 | Missing, malformed, non-Bearer, badly signed, expired, wrong-issuer and wrong-audience tokens get 401; a rejected call returns no data; valid tokens work |
| `test_authorization.py` | 16 | Tool lists are filtered by role (auditor 4, analyst 2, guest 0); allowed calls succeed; denied calls fail even when the tool name is known; a denial looks like a missing tool |
| `test_rate_limits.py` | 5 | A 100-request burst passes and later requests are limited; the limited response is JSON-RPC `-32003` with `x-ratelimit-*` headers; other users are unaffected; the bucket refills |
| `test_response_guardrails.py` | 16 | Every customer's national ID, email and phone and every account number is masked; no raw value appears in any response; other data and error messages are unchanged |
| `test_observability.py` | 5 | Metrics are served; per-tool, 401 and authorization-denial counters go up; log lines carry `user.id`, `user.role` and `mcp.tool` |
| `test_read_only_access.py` | 11 | Tools are read-only with one JSON text block per response; SQL injection is rejected; inside the container every write path is blocked and the database is root-owned and read-only |
| `test_isolation.py` | 6 | The MCP server has no published ports, can't be reached from the host and has no internet access; gateway ports are loopback-only; containers are hardened |

## Test design

- **One token per purpose.** `generate_credentials.sh` writes tokens for `analyst`, `auditor` and `guest` (no tools), a `ratelimit` token with its own rate-limit bucket, and four invalid tokens (`expired`, `wrong-issuer`, `wrong-audience`, `bad-signature`).
- **Rate-limit isolation.** The rate-limit tests use only the `ratelimit` token, so draining its bucket never affects other tests. Other tests stay well under the 100-request burst.
- **Raw HTTP where status matters.** `raw_post()` in `conftest.py` sends a single JSON-RPC message to inspect status codes and headers; `run_mcp()` opens a full MCP session.
- **Before-and-after metrics.** The observability tests read a counter, act, and check that it went up by exactly 1, so earlier traffic doesn't matter.
- **Docker-dependent tests** (`test_isolation.py`, the container half of `test_read_only_access.py`, and the log test) use `requires_docker` and are skipped if the docker CLI is unavailable.
- **Known SDK noise.** agentgateway closes sessions with `202 Accepted`, which mcp 2.3.0 logs as "Session termination failed: 202". `conftest.py` filters out only that message.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Many tests fail with 401 | Tokens expired (24h) or credentials regenerated without restarting the gateway | `make creds && make restart` |
| `missing ... .jwt; run scripts/generate_credentials.sh` | No credentials yet | `make creds` |
| Connection refused | Stack not running, or a different port | `make up`; check `GATEWAY_PORT` / `MCP_GATEWAY_URL` |
| Gateway restarts with "environment variable not found" | A bare `$` in `agentgateway.yaml` (even in a comment) | Write a literal `$` as `$$`; see [gateway/policies/README.md](../gateway/policies/README.md) |
| Rate-limit tests fail right after another run | The `ratelimit` bucket hasn't refilled | Wait a second and rerun (the fixture already waits 1.5s) |
| `test_isolation.py` fails on the container IP | Docker older than 28 (no `isolated` gateway mode) | Upgrade Docker |

## Adding a test

1. Use the fixtures in `tests/conftest.py`: `gateway_url`, `token(name)`, `raw_post()`, `run_mcp()`, `compose()`, `container_python()`.
2. Need a new identity? Add a token in `scripts/generate_credentials.sh` rather than reusing one whose rate-limit bucket other tests depend on.
3. Test from the outside, through the gateway, unless the property only exists inside a container.
