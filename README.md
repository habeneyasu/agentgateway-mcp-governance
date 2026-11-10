# agentgateway MCP Governance

**A reference implementation for securing MCP servers with [agentgateway](https://agentgateway.dev) v1.7: access control, runtime guardrails and usage governance.**

AI agents increasingly reach enterprise systems through the Model Context Protocol (MCP). Unrestricted tool access brings risks: unauthorized operations, sensitive data exposure, excessive request traffic, and little visibility into what agents do.

This project shows how agentgateway can act as a central governance layer in front of an MCP server. Authentication, tool authorization, rate limiting, response masking and observability are enforced at the gateway, not built into the business application. The goal is a small, reproducible example that developers can run, read and adapt.

> [!NOTE]
> **Work in progress.** The data layer and the MCP server are built and verified. The gateway, client, Docker Compose setup and integration tests are next. See [Status](#status).

## Architecture

```text
┌──────────────────────────────────────┐
│       MCP Client / AI Agent          │
└──────────────────┬───────────────────┘
                   │ Streamable HTTP
                   ▼
┌──────────────────────────────────────┐
│          agentgateway v1.7           │
│                                      │
│  • Authentication                    │
│  • MCP Tool Authorization            │
│  • Request Rate Limiting             │
│  • CEL Response Guardrails           │
│  • Usage Observability               │
└──────────────────┬───────────────────┘
                   │ Internal Network
                   ▼
┌──────────────────────────────────────┐
│          Python MCP Server           │
│                                      │
│  • Customer Lookup                   │
│  • Account Lookup                    │
│  • Transaction Lookup                │
│  • Ledger Lookup                     │
│  • Application-Level Restrictions    │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│       Synthetic SQLite Database      │
│             Read-Only                │
└──────────────────────────────────────┘
```

Every client request passes through the gateway. The gateway decides who may call which tool, how often, and what the caller may see in the response. The MCP server runs authorized tools against synthetic, read-only financial data.

See [docs/architecture.md](docs/architecture.md) for the full design.

## Security controls

| Control | Enforced by | How |
| --- | --- | --- |
| Authentication | Gateway | JWT validation (`jwtAuth`, strict mode) |
| Tool authorization | Gateway | CEL rules on JWT claims (`mcpAuthorization`); blocked tools are hidden from the tool list |
| Rate limiting | Gateway | Per-user token bucket (`localRateLimit`, keyed by `jwt.sub`) |
| Response guardrails | Gateway | CEL masking of sensitive fields in tool responses (`mcpGuardrails`) |
| Observability | Gateway | JSON access logs with caller identity and tool name; Prometheus metrics |
| Input validation and limits | MCP server | Strict ID formats, row caps, per-record field allowlists |
| Read-only storage | MCP server | SQLite `mode=ro` and `PRAGMA query_only`; database file `0444`, owned by root |
| Network isolation | Docker Compose | MCP server only on an internal network; gateway published on `127.0.0.1` |

The gateway controls are added on top of the server's own protections, not in place of them.

## The MCP tools

All four tools are read-only and return one JSON text block.

| Tool | Input | Returns |
| --- | --- | --- |
| `get_customer` | `customer_id` (e.g. `CUST-0001`) | Customer profile and the IDs of their accounts |
| `get_account` | `account_id` (e.g. `ACC-1001`) | Account details, owner and status |
| `list_transactions` | `account_id`, `limit` (1–50, default 20) | Most recent transactions, newest first |
| `get_ledger_entries` | `account_id`, `limit` (1–50, default 20) | Ledger entries with running balances, newest first |

The data is entirely synthetic: 5 customers, 7 accounts and 43 transactions. Sensitive-looking values are deliberately fake: national IDs use the never-issued 900 range, phone numbers use the reserved 555-01xx range, and emails use `example.com`.

## Status

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Confirm the agentgateway v1.7 configuration | ✅ Done |
| 1 | Data layer: schema, seed data, read-only access | ✅ Done |
| 2 | MCP server: four tools, app-level restrictions, container | ✅ Done |
| 3 | Network isolation and gateway with no policies | Next |
| 4 | Authentication | Planned |
| 5 | Tool authorization | Planned |
| 6 | Rate limiting | Planned |
| 7 | CEL response guardrails | Planned |
| 8 | Observability | Planned |
| 9 | Integration test suite | Planned |
| 10 | Documentation | Planned |

The build order, design decisions and verification notes for each phase are in [docs/implementation-plan.md](docs/implementation-plan.md).

## Running the MCP server (development only)

> [!WARNING]
> The MCP server returns sensitive fields unmasked; masking is the gateway's job. Until the gateway phases are complete, run the server only on `127.0.0.1` for local checks, and never publish its port more widely.

Requirements: Docker.

```bash
docker build -t agentgateway-mcp-governance/mcp-server:dev mcp-server
docker run --rm -p 127.0.0.1:8000:8000 agentgateway-mcp-governance/mcp-server:dev
```

The server listens for Streamable HTTP at `http://127.0.0.1:8000/mcp`. Point any MCP client at it, for example the [MCP Inspector](https://github.com/modelcontextprotocol/inspector).

If port 8000 is already in use, change the host side of the mapping, e.g. `-p 127.0.0.1:18000:8000`, and connect to `http://127.0.0.1:18000/mcp`.

Configuration is read from environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MCP_DB_PATH` | `/data/finance.db` | Path to the SQLite database |
| `MCP_HOST` | `0.0.0.0` (in the container) | Address to listen on |
| `MCP_PORT` | `8000` | Port to listen on |
| `MCP_MAX_ROWS` | `50` | Largest `limit` the list tools accept (1–500) |

## Project structure

```text
agentgateway-mcp-governance/
├── mcp-client/      # MCP client / AI agent entry point
├── gateway/         # agentgateway configuration and policies
├── mcp-server/      # Python MCP server, tools, restrictions, seed data, Dockerfile
├── tests/           # Integration tests for each control
├── scripts/         # Credential generation
└── docs/            # Architecture and implementation plan
```

## Technology

- [agentgateway](https://github.com/agentgateway/agentgateway) v1.7.0
- [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk) 2.3.0 on Python 3.12
- SQLite
- Docker and Docker Compose
- Pytest

## Scope

**Out of scope:** real banking integrations, financial write operations, custom AI agents, frontend dashboards, enterprise identity federation, and LLM token-cost budgeting.

## License

[Apache License 2.0](LICENSE)
