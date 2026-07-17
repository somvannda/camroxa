"""Repository for bulk user data operations: fetch, delete, reset counters, and restore.

Handles raw SQL operations for the admin user data reset feature.
All transaction-aware methods receive an existing connection and do NOT manage
their own transactions — the caller (ResetService) is responsible for transaction
boundaries.

Requirements: 2.2, 3.1, 3.2, 3.3, 3.4, 3.5, 5.3
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from platform_api.models.reset_models import DELETION_ORDER

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


class AsyncPGPool(Protocol):
    """Minimal protocol for an asyncpg connection pool."""

    async def acquire(self) -> Any: ...
    async def fetch(self, query: str, *args: Any) -> list[Any]: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...
    async def execute(self, query: str, *args: Any) -> str: ...


class Connection(Protocol):
    """Minimal protocol for an asyncpg connection within a transaction."""

    async def execute(self, query: str, *args: Any) -> str: ...
    async def fetch(self, query: str, *args: Any) -> list[Any]: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class ResetRepository:
    """Low-level database operations for user data reset and restore.

    All methods that accept a ``conn`` parameter operate within an existing
    transaction managed by the caller. The ``fetch_all_user_data`` method
    acquires its own connection from the pool (read-only, no transaction needed).

    Args:
        pool: An asyncpg connection pool instance.
    """

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    async def fetch_all_user_data(
        self, exclude_admin_email: str
    ) -> dict[str, list[dict]]:
        """Fetch all rows from user data tables for backup.

        Queries each table listed in DELETION_ORDER, plus user-owned rows
        from music_descriptions and music_structures. The admin account row
        (identified by email) is excluded from the users table.

        Args:
            exclude_admin_email: Email of the admin account to exclude.

        Returns:
            Dict mapping table_name → list of row dicts (JSON-serializable).
        """
        data: dict[str, list[dict]] = {}

        async with self._pool.acquire() as conn:
            for table in DELETION_ORDER:
                if table == "users":
                    rows = await conn.fetch(
                        f"SELECT * FROM {table} WHERE email != $1",
                        exclude_admin_email,
                    )
                else:
                    rows = await conn.fetch(f"SELECT * FROM {table}")

                data[table] = [dict(row) for row in rows]

            # Conditional: user-owned music_descriptions
            rows = await conn.fetch(
                "SELECT * FROM music_descriptions WHERE user_id IS NOT NULL"
            )
            data["music_descriptions"] = [dict(row) for row in rows]

            # Conditional: user-owned music_structures
            rows = await conn.fetch(
                "SELECT * FROM music_structures WHERE user_id IS NOT NULL"
            )
            data["music_structures"] = [dict(row) for row in rows]

        logger.info(
            "Fetched user data from %d tables for backup",
            len(data),
        )
        return data

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_user_data_in_transaction(
        self, conn: Connection, exclude_admin_email: str
    ) -> dict[str, int]:
        """Delete all user data rows in FK dependency order within an existing transaction.

        Iterates DELETION_ORDER and deletes all rows from each table.
        Special cases:
        - ``users`` table: excludes the admin account row.
        - ``music_descriptions``: deletes user-owned rows (user_id IS NOT NULL).
        - ``music_structures``: deletes user-owned rows (user_id IS NOT NULL).

        Args:
            conn: An asyncpg connection within an active transaction.
            exclude_admin_email: Email of the admin account to preserve.

        Returns:
            Dict mapping table_name → number of deleted rows.
        """
        counts: dict[str, int] = {}

        for table in DELETION_ORDER:
            if table == "users":
                result = await conn.execute(
                    f"DELETE FROM {table} WHERE email != $1",
                    exclude_admin_email,
                )
            else:
                result = await conn.execute(f"DELETE FROM {table}")

            # asyncpg execute returns status like "DELETE 42"
            count = self._parse_row_count(result)
            counts[table] = count
            logger.debug("Deleted %d rows from %s", count, table)

        # Conditional deletes for user-owned rows
        result = await conn.execute(
            "DELETE FROM music_descriptions WHERE user_id IS NOT NULL"
        )
        counts["music_descriptions"] = self._parse_row_count(result)

        result = await conn.execute(
            "DELETE FROM music_structures WHERE user_id IS NOT NULL"
        )
        counts["music_structures"] = self._parse_row_count(result)

        total = sum(counts.values())
        logger.info("Deleted %d total rows across %d tables", total, len(counts))
        return counts

    # ------------------------------------------------------------------
    # Reset counters
    # ------------------------------------------------------------------

    async def reset_counters_in_transaction(
        self, conn: Connection
    ) -> dict[str, int]:
        """Reset redeem_codes.current_redemptions and invitation_codes.current_uses to 0.

        Args:
            conn: An asyncpg connection within an active transaction.

        Returns:
            Dict mapping table_name → number of updated rows.
        """
        counts: dict[str, int] = {}

        result = await conn.execute(
            "UPDATE redeem_codes SET current_redemptions = 0"
        )
        counts["redeem_codes"] = self._parse_row_count(result)

        result = await conn.execute(
            "UPDATE invitation_codes SET current_uses = 0"
        )
        counts["invitation_codes"] = self._parse_row_count(result)

        logger.info(
            "Reset counters: redeem_codes=%d, invitation_codes=%d",
            counts["redeem_codes"],
            counts["invitation_codes"],
        )
        return counts

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    async def restore_data_in_transaction(
        self, conn: Connection, data: dict[str, list[dict]]
    ) -> tuple[int, int]:
        """Insert backup data into tables, skipping PK conflicts.

        For each table in the provided data dict, generates an INSERT ... ON
        CONFLICT DO NOTHING statement and tracks how many rows were actually
        inserted vs skipped.

        Args:
            conn: An asyncpg connection within an active transaction.
            data: Dict mapping table_name → list of row dicts to insert.

        Returns:
            Tuple of (records_inserted, records_skipped).
        """
        total_inserted = 0
        total_attempted = 0

        for table, rows in data.items():
            if not rows:
                continue

            total_attempted += len(rows)

            # Use the columns from the first row as the schema
            columns = list(rows[0].keys())
            col_names = ", ".join(columns)
            placeholders = ", ".join(
                f"${i + 1}" for i in range(len(columns))
            )

            insert_sql = (
                f"INSERT INTO {table} ({col_names}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT DO NOTHING"
            )

            inserted_for_table = 0
            for row in rows:
                values = [
                    self._serialize_value(row.get(col)) for col in columns
                ]
                result = await conn.execute(insert_sql, *values)
                count = self._parse_row_count(result)
                inserted_for_table += count

            total_inserted += inserted_for_table
            logger.debug(
                "Restored %d/%d rows into %s",
                inserted_for_table,
                len(rows),
                table,
            )

        total_skipped = total_attempted - total_inserted
        logger.info(
            "Restore complete: %d inserted, %d skipped",
            total_inserted,
            total_skipped,
        )
        return total_inserted, total_skipped

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_row_count(status: str) -> int:
        """Parse the affected row count from an asyncpg execute status string.

        asyncpg returns strings like "DELETE 42", "UPDATE 10", "INSERT 0 1".
        The row count is always the last numeric token.

        Args:
            status: The status string returned by asyncpg execute.

        Returns:
            The number of affected rows.
        """
        try:
            return int(status.split()[-1])
        except (ValueError, IndexError):
            return 0

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """Serialize a value for asyncpg insertion.

        Converts dicts/lists to JSON strings for jsonb columns.
        All other types are passed through unchanged.

        Args:
            value: The value to serialize.

        Returns:
            The serialized value suitable for asyncpg.
        """
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value
