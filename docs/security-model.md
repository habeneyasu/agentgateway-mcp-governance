# Security Model

This document describes what the reference implementation protects, the threats it addresses, which layer enforces each control, and what remains out of scope. Each control has an integration test that proves it; see [testing.md](testing.md).

## What is protected

| Asset | Why it matters |
| --- | --- |
| Customer PII: national ID, email, phone | Exposure harms individuals and breaches privacy obligations |
| Account numbers | Enable fraud if disclosed |
| Financial records: transactions, ledger | Confidential; must not be altered |
| Gateway credentials: JWT signing key, session key | Whoever holds them can impersonate callers or tamper with sessions |

All data in this project is synthetic. The national IDs, account numbers, emails and phone numbers look real so that the controls have something meaningful to protect.

## Trust boundaries

```text
 Untrusted                     Policy enforcement             Trusted, isolated
┌─────────────┐  HTTP + JWT   ┌──────────────────┐  internal   ┌──────────────┐   ┌──────────┐
│ MCP client  │──────────────►│  agentgateway    │────────────►│  MCP server  │──►│  SQLite  │
│ / AI agent  │ 127.0.0.1 only│  authN · authZ   │  network    │  validation  │   │ read-only│
└─────────────┘               │  rate · mask ·   │  (no host,  │  allowlists  │   └──────────┘
                              │  logs · metrics  │  no egress) └──────────────┘
                              └──────────────────┘
```

1. **Client to gateway.** Callers are untrusted. Every request must carry a valid JWT, and all policy is enforced here.
2. **Gateway to MCP server.** The server trusts only traffic that arrives over the isolated internal network. It returns sensitive fields unmasked, so it must never be reachable any other way.
3. **Server to database.** The server can only read. The database is read-only in three independent ways.

## Threats and controls

| Threat | Control | Enforced by | Proven by |
| --- | --- | --- | --- |
| Anonymous or forged callers | RS256 JWT validation: signature, issuer, audience, expiry (`jwtAuth`, strict) | Gateway | `test_authentication.py` |
| Callers using tools beyond their role | Allow-only CEL rules on `jwt.role` (`mcpAuthorization`). Denied tools are hidden from `tools/list`; calls to them are rejected | Gateway | `test_authorization.py` |
| Discovering tools by probing names | A denied call returns the same error as a call to a nonexistent tool | Gateway | `test_authorization.py` |
| Excessive or runaway agent traffic | Per-user token bucket keyed on `jwt.sub` (`localRateLimit`) | Gateway | `test_rate_limits.py` |
| Sensitive data in tool responses | CEL masking of national ID, account number, email and phone, plus generic redaction (`mcpGuardrails`); fails closed | Gateway | `test_response_guardrails.py` |
| A second, unmasked copy of the data | Tools return one JSON text block, with no `structuredContent` or `outputSchema` | MCP server | `test_read_only_access.py` |
| Unattributed activity | JSON access logs with `user.id`, `user.role`, `mcp.tool`, status and reason; Prometheus counters | Gateway | `test_observability.py` |
| Bypassing the gateway | MCP server on an `internal`, host-`isolated` network with no published ports and no internet access | Docker Compose | `test_isolation.py` |
| Malformed or malicious input (e.g. SQL injection) | Strict ID formats, row limits, bound parameters | MCP server | `test_read_only_access.py` |
| Over-sharing fields | Per-record field allowlists; `date_of_birth` never leaves the server | MCP server | Phase 2 checks |
| Data modification | SQLite `mode=ro` and `PRAGMA query_only`; database file `root:root 0444`; read-only root filesystem | MCP server, image, Compose | `test_read_only_access.py` |
| Container compromise and escalation | Non-root users, `cap_drop: [ALL]`, `no-new-privileges`, read-only root filesystems | Docker Compose | `test_isolation.py` |
| Session tampering | MCP session IDs encrypted with an AES-256-GCM `SESSION_KEY` | Gateway | Gateway logs no "not encrypted" warning |
| Credential leakage | Only the public JWKS is mounted into the gateway, read-only; the signing key and tokens are git-ignored, mode 0600 | Repo, Compose | Review |

## Defense in depth

The gateway is the main enforcement point, but the server doesn't depend on it for everything:

- **Authorization at the gateway, validation in the server.** If a gateway rule is misconfigured, the server still rejects malformed IDs and caps result sizes.
- **Masking at the gateway, minimization in the server.** The server never returns fields no tool needs. The gateway masks the sensitive fields that tools do return.
- **Read-only in three places.** The SQLite connection, the file permissions and the container filesystem each block writes on their own.
- **Fail closed.** Authorization uses allow rules only, so an expression error grants nothing. A guardrail expression error rejects the response instead of returning raw data.

## How rejections appear to callers

| Event | HTTP status | Caller sees | Log `reason` |
| --- | --- | --- | --- |
| Missing or invalid JWT | 401 | Unauthorized | `JwtAuth` |
| Tool not allowed | 400 | JSON-RPC error `unknown resource` | `Authorization` |
| Over the rate limit | 200 | JSON-RPC error `-32003` `rate limit exceeded`, with `x-ratelimit-*` headers | `RateLimit` |
| Invalid tool input | 200 | Tool result with `isError: true` and a message | `Upstream` |

A rate-limited MCP request is **not** an HTTP 429. Clients and monitoring must check the JSON-RPC error code.

## Assumptions and residual risks

- **Demo credentials.** `generate_credentials.sh` creates a local signing key and long-lived (24h) tokens. In production, use an identity provider with short-lived tokens and a remote JWKS URL, and keep keys in a secrets manager.
- **Pattern-based masking.** Masking relies on field names and regular expressions. A new sensitive field, or a different format, needs a new rule. Prefer having the server leave out what callers don't need.
- **Local rate limits only.** Buckets live in one gateway instance. With several replicas, use `remoteRateLimit`.
- **No TLS.** The gateway is bound to `127.0.0.1` for local use. Any wider exposure needs TLS in front of or at the gateway.
- **Host administrators are trusted.** Anyone with root or Docker access on the host can exec into the containers and bypass every control.
- **Key rotation requires a restart.** After `make creds`, run `make restart`.
- **The admin UI is not published.** It listens only inside the gateway container.

## Out of scope

Real banking integrations, write operations, enterprise identity federation, multi-tenant isolation, LLM token budgeting, and production hardening such as TLS, secret management and high availability.
