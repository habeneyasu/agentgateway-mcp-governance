"""Read-only access to the synthetic SQLite database.

Read-only is enforced twice in this module, independently of the read-only
volume mount used at deploy time:

1. The file is opened with the SQLite URI flag ``mode=ro``, so the connection
   cannot write and will not create the file if it is missing.
2. ``PRAGMA query_only = ON`` makes SQLite reject any statement that would
   modify the database, even if the file were opened writable.

Every query uses bound parameters and selects explicit columns.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote

Row = dict[str, Any]

CUSTOMER_COLUMNS = (
    "customer_id", "full_name", "email", "phone", "national_id",
    "date_of_birth", "risk_rating", "created_at",
)
ACCOUNT_COLUMNS = (
    "account_id", "customer_id", "account_number", "account_type",
    "currency", "status", "opened_at",
)
TRANSACTION_COLUMNS = (
    "transaction_id", "account_id", "direction", "amount_cents", "currency",
    "counterparty", "description", "status", "posted_at",
)
LEDGER_COLUMNS = (
    "entry_id", "account_id", "transaction_id", "entry_type", "amount_cents",
    "balance_after_cents", "posted_at",
)


class DatabaseError(RuntimeError):
    """Raised when the database cannot be opened or queried."""


class Database:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        if not self._path.is_file():
            raise DatabaseError(f"database file not found: {self._path}")
        self._uri = f"file:{quote(str(self._path.resolve()))}?mode=ro"

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._uri, uri=True)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON")
            yield conn
        finally:
            conn.close()

    def _query(self, sql: str, params: Sequence[Any] = ()) -> list[Row]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def get_customer(self, customer_id: str) -> Row | None:
        rows = self._query(
            f"SELECT {', '.join(CUSTOMER_COLUMNS)} FROM customers WHERE customer_id = ?",
            (customer_id,),
        )
        return rows[0] if rows else None

    def get_account(self, account_id: str) -> Row | None:
        rows = self._query(
            f"SELECT {', '.join(ACCOUNT_COLUMNS)} FROM accounts WHERE account_id = ?",
            (account_id,),
        )
        return rows[0] if rows else None

    def list_accounts_for_customer(self, customer_id: str) -> list[Row]:
        return self._query(
            f"SELECT {', '.join(ACCOUNT_COLUMNS)} FROM accounts "
            "WHERE customer_id = ? ORDER BY account_id",
            (customer_id,),
        )

    def list_transactions(self, account_id: str, limit: int) -> list[Row]:
        return self._query(
            f"SELECT {', '.join(TRANSACTION_COLUMNS)} FROM transactions "
            "WHERE account_id = ? ORDER BY posted_at DESC LIMIT ?",
            (account_id, limit),
        )

    def list_ledger_entries(self, account_id: str, limit: int) -> list[Row]:
        return self._query(
            f"SELECT {', '.join(LEDGER_COLUMNS)} FROM ledger_entries "
            "WHERE account_id = ? ORDER BY posted_at DESC LIMIT ?",
            (account_id, limit),
        )


def build_database(seed_path: Path, db_path: Path) -> None:
    """Create the database file from seed SQL. Used only at image build time."""
    if db_path.exists():
        raise DatabaseError(f"refusing to overwrite existing database: {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(seed_path.read_text(encoding="utf-8"))
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise DatabaseError(f"seed data has foreign key violations: {violations}")
        conn.commit()
    finally:
        conn.close()
    os.chmod(db_path, 0o444)


def main() -> None:
    parser = argparse.ArgumentParser(description="Database utilities")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="build the database from seed SQL")
    build.add_argument("--seed", type=Path, required=True)
    build.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        build_database(args.seed, args.db)
        print(f"built {args.db} from {args.seed}")


if __name__ == "__main__":
    main()
