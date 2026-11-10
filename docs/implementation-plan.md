# Implementation Plan

This document defines the build order for the reference implementation described in [architecture.md](architecture.md).

**Approach:** build from the bottom layer up, and get the gateway working with no policies before adding any. Then add one security control per phase, with its integration test in the same phase. When a test fails, it can only be the control just added. Each phase is one commit, so every control can be reviewed and rolled back on its own.

## Decisions

| Topic        | Decision                                                                                  |
| ------------ | ----------------------------------------------------------------------------------------- |
| Roles        | `analyst` (limited tools) and `auditor` (all four tools)                                  |
| Test harness | Tests assume the stack is already running (`make up`, then `make test`)                   |
| Python       | 3.12                                                                                      |
| Tools        | Four: customers, accounts, transactions, ledger                                           |
| Gateway      | agentgateway v1.7, with the config format checked against official docs before use        |

## Invariants

Later phases must keep these decisions. Phase 9's tests check each one.

1. **One JSON text block per tool response.** Tools never return `structuredContent` or an `outputSchema`, so the gateway's response masking has a single field to cover.
2. **Defense in depth.** App-level input validation, row limits, field allowlists and read-only database access stay in place after gateway authorization is added. Gateway controls are added on top; they never replace these.
3. **Non-root, read-only runtime.** The MCP server runs as uid 10001. The database is `root:root 0444` under a `root:root 0755` `/data`.

### Access rule until gateway enforcement is verified

The MCP server returns sensitive fields unmasked, and masking is enforced only at the gateway (Phase 7). Until Phases 4–7 are configured and their tests pass:

- **The MCP server is never published to the host.** No `ports:` entry in Compose; it sits only on the `internal: true` network. Running it directly is allowed only for local checks, bound to `127.0.0.1`.
- **The gateway port is published on `127.0.0.1` only.** In Phase 3 the gateway has no policies, so anything that can reach its port can read raw data. Binding to loopback keeps that baseline local to the developer's machine.
- **`127.0.0.1` stays the default after Phase 7.** Exposing the gateway more widely is an explicit, documented opt-in, not the default.

## Phases

### Phase 0: Check the agentgateway v1.7 docs

Before writing any gateway config, check the v1.7 config format against the official docs and examples:

- JWT authentication
- MCP authorization rules
- Local rate limiting
- CEL response handling
- Access logs and metrics

**Risk:** CEL response guardrails are the least certain capability. If v1.7 can't change or block response bodies with CEL, choose and document a fallback before Phase 7.

#### Findings (checked against the `v1.7.0` tag: `schema/config.md`, `schema/cel.md`, `examples/`)

v1.7.0 was released on 27 Oct 2026. Every planned control is supported natively, so no fallback is needed.

| Area | Confirmed v1.7 config | Notes |
| ---- | --------------------- | ----- |
| Image | `cr.agentgateway.dev/agentgateway:v1.7.0` | Manifest confirmed in the registry |
| Authentication | `policies.jwtAuth`: `mode: strict`, `issuer`, `audiences`, `jwks.file` | A multi-issuer `providers[]` form also exists. `jwks.file` is relative to the gateway's working directory, not the config file |
| Tool authorization | `policies.mcpAuthorization.rules`: a list of CEL strings, or `{allow \| require \| deny}` objects | Rules are OR-ed. Denied tools are removed from `tools/list`, and calls to them are rejected. Avoid `deny`, because an expression error fails open |
| Rate limiting | `policies.localRateLimit[]`: `type: requests`, `maxTokens`, `tokensPerFill`, `fillInterval`, `key` | `key: jwt.sub` gives each user their own bucket. The status code isn't documented; confirm it in Phase 6 (expected 429) |
| Response guardrails | `policies.mcpGuardrails.processors[]` with `kind: expression`, `methods: {"tools/call": response}`, `condition`, plus one of `transform` or `reject` | `transform` rewrites `mcp.result` (e.g. `regexReplaceAll` over `content[].text`). Processors run in order, and an expression error fails closed |
| CEL variables | `jwt.sub`, `jwt.<claim>`, `mcp.tool.name`, `mcp.tool.arguments`, `mcp.methodName`, `mcp.params`, `mcp.result` | `mcp.params` and `mcp.result` are only available inside guardrails |
| Logging | `config.logging.format: json`, `config.logging.fields.add: {name: <CEL>}` | Used to add `jwt.sub` and `mcp.tool.name` to access logs |
| Metrics | Enabled by default at `:15020/metrics` (`config.statsAddr`) | Includes `tool_calls_total{server,name}`, `list_calls_total` and `agentgateway_requests_total{status}` |
| Tracing | `frontendPolicies.tracing.host` (OTLP) | Optional; not in the first release |

**Design consequence for Phase 2 and Phase 7:** the response guardrail rewrites `content[].text`. Python MCP SDK tools that return structured output also send `structuredContent`, which a text-only mask would leave untouched. Either turn off structured output on the tools, or have the guardrail also rewrite or drop `structuredContent`. Phase 7's test must check both fields.

### Phase 1: Data layer

Files: `mcp-server/data/seed.sql`, `mcp-server/app/database.py`

- `seed.sql`: four tables (`customers`, `accounts`, `transactions`, `ledger_entries`) filled with synthetic data. Some fields are deliberately sensitive (national ID, full account number, email, phone) so the guardrails have something to protect.
- The database file is built from `seed.sql` when the image is built.
- `database.py` opens the file in read-only mode (`mode=ro`) and turns on `PRAGMA query_only`. All queries use parameters.
- The file is also mounted read-only in Compose, which gives two separate layers of read-only protection.

### Phase 2: MCP server

Files: `server.py`, `config.py`, `tools/*.py`, `security/data_restrictions.py`, `Dockerfile`, `requirements.txt`

- A FastMCP server over Streamable HTTP with four tools, one per module: `get_customer`, `get_account`, `list_transactions`, `get_ledger_entries`.
- `data_restrictions.py` holds the app-level rules: input validation (ID format), a cap on rows returned, and a list of allowed columns.
- The Dockerfile runs the server as a non-root user.

#### Notes from the build

- **MCP SDK 2.x (`mcp==2.3.0`):** `FastMCP` is now `mcp.server.mcpserver.MCPServer`. Anticipated failures (bad input, not found) are raised as `ToolError`, so the caller gets `isError: true` with the message, and other exceptions reach the caller only as a generic error.
- **One output field:** every tool is registered with `structured_output=False` and returns one JSON text block. No `outputSchema` or `structuredContent` is sent, so Phase 7 has a single field to mask.
- **Masking split:** the app drops fields no tool needs (`date_of_birth`) through a per-record field allowlist. It returns the sensitive fields tools do need (national ID, account number, email, phone) unmasked; the gateway masks them in Phase 7. Calling the server directly therefore shows raw data, and Phase 3's network isolation is what prevents that.
- **Transport:** Streamable HTTP at `/mcp`, stateless, with JSON responses. The gateway owns client sessions.
- **Image:** `finance.db` is built during the image build and copied in as `root:root 0444` under a `root:root 0755` `/data`. The server runs as uid 10001. Inside the container, SQLite writes, appending to the file, and creating new files in `/data` are all denied.
- **Tool modules** don't use `from __future__ import annotations`. The SDK evaluates tool signatures when the tool is registered, and the `limit` description refers to a local variable.

### Phase 3: Network and gateway with no policies

Files: `docker-compose.yml`, `gateway/config/agentgateway.yaml`, `mcp-client/client.py`

- Two networks. The MCP server sits only on an `internal: true` network with no published ports. The gateway sits on both networks and publishes one port, bound to `127.0.0.1` (see the access rule under Invariants).
- The gateway just routes `/mcp` to the MCP server.
- `client.py` is a scripted client that lists the tools and calls each one through the gateway.

**Done when:** the client works through the gateway, and the MCP server can't be reached from the host.

#### Notes from the build

- **Gateway config:** `binds` → `listeners` → `routes` → `backends.mcp.targets`, with one target named `finance` at `http://mcp-server:8000/mcp`. With one target, tool names are not prefixed. Policies for Phases 4–8 go on the route (`routes[].policies`). Validate with `agentgateway -f <file> --validate-only`.
- **Host port:** the gateway is published at `127.0.0.1:${GATEWAY_PORT:-13000}`. 13000 avoids common clashes on 3000 and 8000.
- **Host access to the internal network:** on Linux, `internal: true` alone still lets processes on the Docker host reach the MCP server's container IP directly, bypassing the gateway. Setting `com.docker.network.bridge.gateway_mode_ipv4/ipv6: isolated` (Docker 28+) on the `backend` network gives the bridge no host address and closes that path. Verified: before the change, `172.27.0.2:8000` was reachable from the host; after it, the container IP is unreachable and the bridge has no host address.
- **Container hardening:** both containers run with a read-only root filesystem, `cap_drop: [ALL]` and `no-new-privileges`. The database is read-only through the root filesystem as well as through its file mode. The gateway runs as uid 65532 and the MCP server as uid 10001.
- **Session close:** agentgateway answers the session-closing `DELETE` with `202 Accepted`. mcp 2.3.0 logs that as "Session termination failed: 202" because it expects 200 or 204. The session is closed, so the client filters out only that message.

**Verified:**
- All 27 server checks pass through the gateway.
- The MCP server has no host port mapping, and its container IP can't be reached from the host.
- The gateway listens only on `127.0.0.1:13000` and refuses connections on the LAN address.
- The MCP server has no outbound network access (no route, no DNS).

### Phase 4: Authentication

Files: `scripts/generate_credentials.sh`, gateway config

- `generate_credentials.sh` creates an RSA keypair and a JWKS file, and issues test JWTs for `analyst`, `auditor` and one with an invalid signature.
- A JWT auth policy rejects any request without a valid token.

**Done when:** `tests/integration/test_authentication.py` passes.

#### Notes from the build

- **Credentials:** `generate_credentials.sh` uses only bash, openssl, basenc and xxd. It writes `gateway/credentials/` (git-ignored), containing an RS256 signing key, `jwks.json` (`kid: mcp-governance-demo-1`), `analyst.jwt` and `auditor.jwt` (24h; set `TOKEN_TTL_SECONDS` to change), and four negative-test tokens: expired, wrong issuer, wrong audience, untrusted key.
- **Claims:** `iss: agentgateway-mcp-governance`, `aud: mcp-gateway`, `sub` (`analyst-1` / `auditor-1`), `role` (`analyst` / `auditor`). Phase 5 authorizes on `jwt.role`.
- **Only the public key reaches the gateway:** Compose mounts `jwks.json` alone, read-only, at `/credentials/jwks.json`. The signing key stays on the host.
- **Policy:** `jwtAuth` in `mode: strict` on the route. Regenerating credentials needs `docker compose restart agentgateway`.
- **Test harness started early:** `pytest.ini`, `tests/requirements.txt` and `tests/conftest.py` (gateway URL, a token loader, a raw-HTTP helper for status codes, an MCP session helper). Phase 9 adds to them.

**Verified (10 tests):**
- Missing tokens, malformed tokens, `Basic` instead of `Bearer`, bad signatures, expired tokens, wrong issuer and wrong audience all get **401**.
- A rejected `tools/call` returns no data.
- Valid analyst and auditor tokens can list and call tools.

### Phase 5: Tool authorization

- MCP authorization rules written in CEL that check JWT claims. `analyst` can use customers and accounts; `auditor` can use all four tools.

**Done when:** `test_authorization.py` passes. Blocked tools don't appear in the tool list, and calling one is denied.

#### Notes from the build

- **Rules** (allow-only, OR-ed): `jwt.role == "auditor"` gets all tools; `jwt.role == "analyst" && mcp.tool.name in ["get_customer", "get_account"]`. Any other role gets nothing.
- **New `guest.jwt`** (valid signature, `role: guest`) shows that an authenticated but unlisted role sees and can call no tools.
- **Denied calls** return the JSON-RPC error `unknown resource`, identical to calling a tool that doesn't exist. A denial doesn't reveal that the tool exists.
- **Test harness:** `conftest.py` filters out the harmless "Session termination failed: 202" message. In `test_authentication.py`, the valid-token test now checks access, not the exact tool set.

**Verified (16 tests, 26 in the suite):**
- Tool lists per role: auditor 4, analyst 2, guest 0.
- Every allowed call succeeds.
- Every denied call is rejected, even when the caller knows the tool name, and returns no data.
- A denied call is indistinguishable from a call to a missing tool.

### Phase 6: Rate limiting

- A local token-bucket rate limit.

**Done when:** `test_rate_limits.py` passes. Going over the limit is rejected, and requests succeed again after the bucket refills.

#### Notes from the build

- **Policy:** `localRateLimit` with `type: requests` and `key: jwt.sub`: bursts of 100 HTTP requests per subject, refilled at 20 per second. One MCP session uses about 5 HTTP requests, so this allows about 20 quick sessions per user.
- **Not a 429:** on MCP routes a limited request gets **HTTP 200 with a JSON-RPC error** `{"code": -32003, "message": "rate limit exceeded"}`, plus `x-ratelimit-limit`, `x-ratelimit-remaining` and `x-ratelimit-reset` headers. The gateway logs it with `reason=RateLimit`. Clients must check the JSON-RPC error, not the HTTP status.
- **Dedicated test user:** `ratelimit.jwt` (`sub: rate-limit-test`) has its own bucket, so the rate-limit tests never drain other users' buckets.
- **Session key (security fix):** agentgateway logged "no session key configured; MCP session IDs are not encrypted". It tries to write a generated key into its config file, which is mounted read-only. `generate_credentials.sh` now writes `SESSION_KEY` (32 random bytes, hex) to `gateway/credentials/gateway.env` (mode 0600). Compose loads it with `env_file` (`required: true`), and the warning no longer appears.

**Verified (5 tests, 31 in the suite):**
- The first 100 requests in a burst are allowed, and later ones are limited.
- The limited response is a JSON-RPC error with rate-limit headers and no result.
- Other users are unaffected.
- The bucket refills within about 1 second.

### Phase 7: CEL response guardrails

- Masking or blocking of the sensitive fields from Phase 1, using the approach Phase 0 confirmed is supported.

**Done when:** `test_response_guardrails.py` passes.

#### Notes from the build

- **Processor:** one `mcpGuardrails` processor (`kind: expression`, `methods: {"tools/call": response}`) rewrites `content[].text` with `regexReplaceAll`. Field-anchored masks keep the last 4 characters: national ID `***-**-3401`, account number `********1979`, email `***@example.com` (domain kept), phone `***-0101`. Generic national-ID and email patterns then replace any value left in other fields with `[REDACTED]`.
- **`$` must be written `$$`:** agentgateway expands environment variables anywhere in the config file, **including comments**. Regex group references are therefore written `$$1`, and a comment containing a bare `$NAME` stops the gateway from starting ("environment variable not found"). `\$` does not escape it.
- **Raw strings:** the CEL regexes use raw strings (`r'...'`), so backslashes need no double escaping.
- **Fails closed:** an expression error, or a transform that produces an invalid MCP body, rejects the call instead of returning unmasked data.
- **Masking happens only at the gateway:** the MCP server still returns raw values, so network isolation (Phase 3) remains essential.

**Verified (16 tests, 47 in the suite):**
- All 5 customers have national ID, email and phone masked; all 7 accounts have the account number masked.
- No raw national ID, 12-digit account number, `@example.com` address or 555-01xx phone appears in any response.
- Transactions and ledger entries are unchanged.
- Tool error messages still reach the caller.
- No response carries `structuredContent`.

### Phase 8: Observability

- Structured access logs that include the caller's identity and the MCP tool name, plus the metrics endpoint.

**Done when:** a test checks the logs or metrics, and the docs explain how to read them.

### Phase 9: Read-only proof and test harness

Files: `tests/conftest.py`, `tests/integration/test_read_only_access.py`, `Makefile`, `pytest.ini`

- `test_read_only_access.py`: write attempts fail at the app layer and at the SQLite layer.
- `conftest.py` provides fixtures for the gateway URL, the tokens per role, and an MCP session helper.
- `Makefile` targets: `creds`, `up`, `down`, `test`, `logs`, `clean`.

### Phase 10: Documentation

Files: `docs/security-model.md`, `docs/testing.md`, `README.md`, `.env.example`, `gateway/policies/README.md`

- `security-model.md`: threats and the control for each.
- `testing.md`: how to run and read the tests.
- `README.md`: quick start.

## Progress

- [x] Phase 0: Check the agentgateway v1.7 docs
- [x] Phase 1: Data layer
- [x] Phase 2: MCP server
- [x] Phase 3: Network and gateway with no policies
- [x] Phase 4: Authentication
- [x] Phase 5: Tool authorization
- [x] Phase 6: Rate limiting
- [x] Phase 7: CEL response guardrails
- [ ] Phase 8: Observability
- [ ] Phase 9: Read-only proof and test harness
- [ ] Phase 10: Documentation
