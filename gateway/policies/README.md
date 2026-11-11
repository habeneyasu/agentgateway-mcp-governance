# Gateway Policies

All gateway policy lives in [`../config/agentgateway.yaml`](../config/agentgateway.yaml), on the single MCP route. This guide explains each policy and how to change it safely.

## Request flow

```text
request ─► jwtAuth ─► localRateLimit ─► mcpAuthorization ─► MCP server ─► mcpGuardrails ─► response
              │              │                 │                                  │
             401      JSON-RPC -32003   unknown resource                 masked / [REDACTED]
```

Every request is also written to the JSON access log and counted in Prometheus metrics.

## Policies

### `jwtAuth`: who is calling

```yaml
jwtAuth:
  mode: strict
  issuer: agentgateway-mcp-governance
  audiences: [mcp-gateway]
  jwks:
    file: /credentials/jwks.json
```

- `strict` rejects any request without a valid token.
- The JWKS file holds only the public key and is mounted read-only from `gateway/credentials/`.
- After rotating keys (`make creds`), run `make restart`.
- For an identity provider, replace `jwks.file` with `jwks.url` and set its issuer and audience.

### `mcpAuthorization`: what they may call

```yaml
mcpAuthorization:
  rules:
  - 'jwt.role == "auditor"'
  - 'jwt.role == "analyst" && mcp.tool.name in ["get_customer", "get_account"]'
```

- Rules are CEL expressions combined with OR. Anything not allowed is denied, so a new role gets nothing until you add a rule for it.
- Use **allow rules only**. A `deny` rule whose expression errors fails open.
- Useful variables: `jwt.<claim>`, `mcp.tool.name`, `mcp.tool.arguments`.

### `localRateLimit`: how often

```yaml
localRateLimit:
- type: requests
  key: jwt.sub
  maxTokens: 100
  tokensPerFill: 20
  fillInterval: 1s
```

- Each `jwt.sub` gets its own bucket. One MCP session uses about 5 HTTP requests.
- A limited request gets HTTP 200 with JSON-RPC error `-32003`, not 429.
- For different limits per role, use the `conditional:` form with `condition: 'jwt.role == "..."'`.

### `mcpGuardrails`: what they may see

A CEL `transform` on every `tools/call` response rewrites `content[].text`:

| Pattern | Result |
| --- | --- |
| `"national_id":"900-12-3401"` | `***-**-3401` |
| `"account_number":"400034651979"` | `********1979` |
| `"email":"amara.okafor@example.com"` | `***@example.com` |
| `"phone":"+1-555-0101"` | `***-0101` |
| any other `ddd-dd-dddd` or email | `[REDACTED]` |

To mask a new field, add a `.regexReplaceAll(r'("field":\s*")...', '$$1...')` step before the generic patterns. If an expression errors, the call is rejected rather than returned unmasked.

### Logging and metrics

```yaml
config:
  statsAddr: 0.0.0.0:15020
  logging:
    format: json
    fields:
      add:
        user.id: jwt.sub
        user.role: jwt.role
        mcp.tool: mcp.tool.name
```

Follow the logs with `make logs`, and see per-tool counts with `make metrics` (`agentgateway_mcp_requests_total`).

## Editing the config safely

1. **Write a literal `$` as `$$`.** agentgateway expands environment variables anywhere in the file, **including comments**. Regex group `$1` must be written `$$1`; a bare dollar sign followed by a name stops the gateway from starting.
2. **Validate before restarting:**
   ```bash
   docker run --rm -v "$PWD/gateway/config:/config:ro" \
     -v "$PWD/gateway/credentials/jwks.json:/credentials/jwks.json:ro" \
     cr.agentgateway.dev/agentgateway:v1.7.0 -f /config/agentgateway.yaml --validate-only
   ```
3. **Apply and test:** `make restart && make test`.

Reference: the agentgateway v1.7 config schema, [`schema/config.md`](https://github.com/agentgateway/agentgateway/blob/v1.7.0/schema/config.md), and CEL variables, [`schema/cel.md`](https://github.com/agentgateway/agentgateway/blob/v1.7.0/schema/cel.md).
