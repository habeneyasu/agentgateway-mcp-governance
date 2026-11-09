"""Application configuration, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path
    host: str
    port: int
    max_rows: int


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def load_settings() -> Settings:
    max_rows = _int_env("MCP_MAX_ROWS", 50)
    if not 1 <= max_rows <= 500:
        raise ValueError(f"MCP_MAX_ROWS must be between 1 and 500, got {max_rows}")
    return Settings(
        db_path=Path(os.environ.get("MCP_DB_PATH", "/data/finance.db")),
        host=os.environ.get("MCP_HOST", "0.0.0.0"),
        port=_int_env("MCP_PORT", 8000),
        max_rows=max_rows,
    )
