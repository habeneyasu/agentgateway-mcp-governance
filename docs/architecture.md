# Securing MCP Servers with agentgateway v1.7

**A Practical Reference Implementation for MCP Access Control, Runtime Guardrails, and Usage Governance**

## 1. Project Purpose

As AI agents increasingly interact with enterprise systems through the Model Context Protocol (MCP), controlling what agents can access becomes as important as what they can do.

Unrestricted tool access introduces risks such as unauthorized operations, sensitive data exposure, excessive requests, and limited visibility into agent activity.

This project demonstrates how agentgateway v1.7 can provide a centralized governance layer for MCP servers, applying security and runtime controls without requiring those gateway policies to be embedded in the underlying business application.

The goal is a small, reproducible, open-source reference implementation for developers building secure MCP-based systems.

## 2. Architecture

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

> **Execution principle:** Every client request passes through the gateway. The gateway governs access and applies runtime policies; the MCP server executes authorized tools using synthetic, read-only financial data.

## 3. Core Capabilities

| Capability         | Demonstration                                         |
| ------------------ | ----------------------------------------------------- |
| Authentication     | Reject unauthenticated clients                        |
| Tool authorization | Allow or deny specific MCP tools                      |
| Rate limiting      | Control excessive request traffic                     |
| CEL guardrails     | Protect sensitive fields in tool responses            |
| Observability      | Record gateway requests and tool activity             |
| Storage security   | Enforce read-only database access                     |
| Network isolation  | Keep the MCP server off the host-published interface  |

All security demonstrations use synthetic data and automated integration tests.

## 4. Project Structure

```text
agentgateway-mcp-governance/
│
├── mcp-client/                       # MCP client / AI agent entry point
│   ├── client.py
│   └── requirements.txt
│
├── gateway/                          # Centralized governance layer
│   ├── config/
│   │   └── agentgateway.yaml
│   └── policies/
│       └── README.md
│
├── mcp-server/                       # Business capabilities and data access
│   ├── app/
│   │   ├── server.py                 # MCP server entry point
│   │   ├── config.py                 # Application configuration
│   │   ├── database.py               # SQLite connection and queries
│   │   │
│   │   ├── tools/                    # Financial investigation tools
│   │   │   ├── customers.py
│   │   │   ├── accounts.py
│   │   │   ├── transactions.py
│   │   │   └── ledger.py
│   │   │
│   │   └── security/                 # Application-level restrictions
│   │       └── data_restrictions.py
│   │
│   ├── data/
│   │   └── seed.sql
│   │
│   ├── Dockerfile
│   └── requirements.txt
│
├── tests/                            # Automated verification
│   ├── integration/
│   │   ├── test_authentication.py
│   │   ├── test_authorization.py
│   │   ├── test_rate_limits.py
│   │   ├── test_response_guardrails.py
│   │   ├── test_observability.py
│   │   └── test_read_only_access.py
│   │
│   └── conftest.py
│
├── scripts/
│   └── generate_credentials.sh
│
├── docs/
│   ├── architecture.md
│   ├── implementation-plan.md
│   ├── security-model.md
│   └── testing.md
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
├── pytest.ini
├── LICENSE
└── README.md
```

### How the Layers Work

| Layer                          | Responsibility                                                                  | Location            |
| ------------------------------ | ------------------------------------------------------------------------------- | ------------------- |
| **1. MCP Client**              | Initiates requests and invokes MCP tools                                        | `mcp-client/`       |
| **2. Governance Gateway**      | agentgateway v1.7: Authentication · Authorization · Rate Limiting · CEL Guardrails · Observability | `gateway/`          |
| **3. MCP Server**              | Business logic · Tool execution · Input validation · Application security       | `mcp-server/`       |
| **4. Data Layer**              | Synthetic SQLite database · Read-only access                                    | `mcp-server/data/`  |

## 5. Technology Stack

- **Gateway:** agentgateway v1.7
- **MCP implementation:** Python MCP SDK
- **Database:** SQLite
- **Deployment:** Docker Compose
- **Security:** Gateway authentication, MCP authorization, CEL guardrails, and rate limiting
- **Verification:** Pytest and end-to-end integration tests

## 6. Implementation Scope

The first release includes:

- One agentgateway instance
- One Python MCP server
- Four read-only financial investigation tools
- One synthetic SQLite database
- Docker-based deployment
- Automated security and integration tests
- Reproducible configuration and documentation

**Out of scope:** Real banking integrations, financial write operations, custom AI agents, frontend dashboards, enterprise identity federation, and LLM token-cost budgeting.

LLM cost tracking can be explored separately when an actual model traffic path is included.

## 7. Expected Outcomes

- **For the AAIF community:** A reproducible example of integrating MCP servers with agentgateway governance capabilities.
- **For enterprise and FinTech teams:** A practical demonstration of centralized MCP access control, response protection, and usage governance.
- **For developers:** Reusable configurations, containerized deployment, and automated tests that demonstrate how these controls work together.

## 8. Guiding Principle

> Connecting an AI agent to an enterprise tool should never mean giving it unrestricted access.

Every interaction should be **authenticated, authorized, controlled, protected, and observable**.

This project demonstrates how agentgateway v1.7 can help establish that governance boundary around MCP-based systems.
