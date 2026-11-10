"""Financial investigation tools.

Every tool is read-only and returns its result as a single JSON text block
(``structured_output=False``), so the response has exactly one place for the
gateway's response guardrails to inspect.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from app.security.data_restrictions import RestrictionError

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


def as_json(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"))


def checked(func, *args: Any) -> Any:
    """Run a restriction check, reporting violations to the caller as a tool error."""
    try:
        return func(*args)
    except RestrictionError as exc:
        raise ToolError(str(exc)) from exc
