# agentgateway MCP governance: common tasks.
# Run `make help` to list targets.

PYTHON ?= .venv/bin/python
CREDS  := gateway/credentials

.DEFAULT_GOAL := help
.PHONY: help venv creds up down restart test demo logs metrics clean

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-9s %s\n", $$1, $$2}'

venv: ## Create .venv with the client and test dependencies
	python3 -m venv .venv
	.venv/bin/pip install -q -r mcp-client/requirements.txt -r tests/requirements.txt

creds: ## Generate (or rotate) keys, session key and demo tokens
	scripts/generate_credentials.sh

up: ## Build and start the stack (generates credentials if missing)
	@test -f $(CREDS)/gateway.env || scripts/generate_credentials.sh
	docker compose up -d --build --wait

down: ## Stop the stack
	docker compose down

restart: ## Restart the gateway (after editing its config or rotating credentials)
	docker compose restart agentgateway

test: ## Run the integration tests (stack must be up)
	$(PYTHON) -m pytest

demo: ## Run the client demo as the auditor
	MCP_TOKEN="$$(cat $(CREDS)/tokens/auditor.jwt)" $(PYTHON) mcp-client/client.py demo

logs: ## Follow the gateway's JSON access logs
	docker compose logs -f --no-log-prefix agentgateway

metrics: ## Show per-tool MCP request counts
	@curl -s 127.0.0.1:$${METRICS_PORT:-15020}/metrics | grep '^agentgateway_mcp_requests_total'

clean: ## Stop the stack and remove built images, credentials and .venv
	docker compose down --rmi local
	rm -rf $(CREDS) .venv
