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

### Phase 4: Authentication

Files: `scripts/generate_credentials.sh`, gateway config

- `generate_credentials.sh` creates an RSA keypair and a JWKS file, and issues test JWTs for `analyst`, `auditor` and one with an invalid signature.
- A JWT auth policy rejects any request without a valid token.

**Done when:** `tests/integration/test_authentication.py` passes.

### Phase 5: Tool authorization

- MCP authorization rules written in CEL that check JWT claims. `analyst` can use customers and accounts; `auditor` can use all four tools.

**Done when:** `test_authorization.py` passes. Blocked tools don't appear in the tool list, and calling one is denied.

### Phase 6: Rate limiting

- A local token-bucket rate limit.

**Done when:** `test_rate_limits.py` passes. Going over the limit returns 429, and requests succeed again after the bucket refills.

### Phase 7: CEL response guardrails

- Masking or blocking of the sensitive fields from Phase 1, using the approach Phase 0 confirmed is supported.

**Done when:** `test_response_guardrails.py` passes.

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
- [ ] Phase 3: Network and gateway with no policies
- [ ] Phase 4: Authentication
- [ ] Phase 5: Tool authorization
- [ ] Phase 6: Rate limiting
- [ ] Phase 7: CEL response guardrails
- [ ] Phase 8: Observability
- [ ] Phase 9: Read-only proof and test harness
- [ ] Phase 10: Documentation
