"""Reset service — orchestrates backup, reset, and restore operations.

Coordinates between the ResetRepository (DB operations), filesystem (backup
JSON files), Redis (cache flush), and AuditService (audit logging) to provide
atomic user-data wipe with pre-wipe backup guarantee.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.6, 3.7, 3.8, 3.9, 3.10,
              4.1, 4.2, 4.3, 4.4, 5.3, 5.4, 5.5, 5.6, 5.7
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from redis.asyncio import Redis

from platform_api.exceptions import (
    BackupCreationError,
    ResetError,
    ResetExecutionError,
    RestoreExecutionError,
)
from platform_api.models.reset_models import (
    REDIS_FLUSH_PATTERNS,
    BackupMetadata,
    ResetResult,
    RestoreResult,
)
from platform_api.repositories.reset_repo import AsyncPGPool, ResetRepository
from platform_api.services.audit_service import AuditService

logger = logging.getLogger(__name__)

ADMIN_EMAIL = "admin@mgfaceless.com"


class ResetService:
    """Orchestrates user data backup, reset, and restore operations.

    Guarantees:
        - Backup is always created before any destructive operation.
        - All DB deletions happen in a single transaction (120s timeout).
        - Redis flush failure after DB commit is reported but does not raise.
        - Audit log entries are written for every completed operation.

    Args:
        pool: An asyncpg connection pool instance.
        redis: An async Redis client instance.
        audit_service: Service for recording audit log entries.
        backup_dir: Absolute path to the directory for backup JSON files.
    """

    def __init__(
        self,
        pool: AsyncPGPool,
        redis: Redis,  # type: ignore[type-arg]
        audit_service: AuditService,
        backup_dir: str,
    ) -> None:
        self._pool = pool
        self._redis = redis
        self._audit_service = audit_service
        self._backup_dir = backup_dir
        self._repo = ResetRepository(pool)

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    async def create_backup(self, admin_id: str) -> BackupMetadata:
        """Create a backup of all user data without performing a reset.

        Fetches all user data from the database, serializes to JSON, and
        writes to the backup directory with a timestamped filename.

        Args:
            admin_id: UUID string of the admin triggering the backup.

        Returns:
            BackupMetadata with filename, timestamp, size, and record info.

        Raises:
            BackupCreationError: If the backup file cannot be written.
        """
        # Fetch all user data
        data = await self._repo.fetch_all_user_data(
            exclude_admin_email=ADMIN_EMAIL
        )

        # Generate timestamped filename
        now = datetime.now(timezone.utc)
        timestamp_str = now.strftime("%Y-%m-%dT%H-%M-%S")
        filename = f"backup_{timestamp_str}Z.json"

        # Build JSON structure
        tables = [table for table, rows in data.items() if rows]
        total_records = sum(len(rows) for rows in data.values())

        backup_content = {
            "metadata": {
                "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "total_records": total_records,
                "tables": tables,
                "actor_id": admin_id,
                "version": 1,
            },
            "data": data,
        }

        # Write to filesystem
        filepath = Path(self._backup_dir) / filename
        try:
            os.makedirs(self._backup_dir, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(backup_content, f, default=_json_serializer)
        except (OSError, IOError, TypeError, ValueError) as exc:
            logger.error("Backup creation failed: %s", exc)
            raise BackupCreationError(
                "Backup creation failed, reset aborted.",
                details={"error": str(exc)},
            ) from exc

        file_size = filepath.stat().st_size

        logger.info(
            "Backup created: %s (%d records, %d bytes)",
            filename,
            total_records,
            file_size,
        )

        return BackupMetadata(
            filename=filename,
            created_at=now,
            file_size_bytes=file_size,
            total_records=total_records,
            tables=tables,
            actor_id=admin_id,
        )

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    async def execute_reset(self, admin_id: str) -> ResetResult:
        """Create backup then wipe all user data in a single transaction.

        Steps:
            1. Create backup (abort on failure).
            2. Open transaction with 120s statement timeout.
            3. Delete user data in FK order.
            4. Reset counters to 0.
            5. Commit.
            6. Flush Redis cache patterns (non-fatal on failure).
            7. Write audit log entry.

        Args:
            admin_id: UUID string of the admin performing the reset.

        Returns:
            ResetResult with backup filename, tables cleared, counts, and
            redis_flushed status.

        Raises:
            BackupCreationError: If backup write fails (reset aborted).
            ResetExecutionError: If any DB operation fails (rolled back).
        """
        # Step 1: Create backup — aborts on failure
        backup_meta = await self.create_backup(admin_id)

        # Steps 2-5: Transaction with deletions and counter resets
        delete_counts: dict[str, int] = {}
        counter_counts: dict[str, int] = {}

        try:
            async with self._pool.acquire() as conn:
                # Set statement timeout for this connection
                await conn.execute(
                    "SET statement_timeout = '120s'"
                )
                async with conn.transaction():
                    # Step 3: Delete user data in FK order
                    delete_counts = (
                        await self._repo.delete_user_data_in_transaction(
                            conn, ADMIN_EMAIL
                        )
                    )
                    # Step 4: Reset counters
                    counter_counts = (
                        await self._repo.reset_counters_in_transaction(conn)
                    )
        except (BackupCreationError, ResetExecutionError):
            raise
        except Exception as exc:
            logger.error("Reset transaction failed: %s", exc)
            raise ResetExecutionError(
                table="transaction",
                detail=str(exc),
            ) from exc

        # Build result data
        tables_cleared = [
            table for table, count in delete_counts.items() if count > 0
        ]
        total_deleted = sum(delete_counts.values())

        # Step 6: Flush Redis (non-fatal)
        redis_flushed = True
        redis_error: str | None = None
        try:
            await self._flush_redis()
        except Exception as exc:
            redis_flushed = False
            redis_error = str(exc)
            logger.warning(
                "Redis flush failed after successful DB reset: %s", exc
            )

        # Step 7: Write audit log
        all_counts = {**delete_counts, **counter_counts}
        await self._audit_service.log_event(
            actor_id=admin_id,
            action_type="user_data_reset",
            target_resource="all_user_data",
            metadata={
                "backup_filename": backup_meta.filename,
                "tables_cleared": tables_cleared,
                "record_counts": all_counts,
                "total_records_deleted": total_deleted,
                "redis_flushed": redis_flushed,
            },
        )

        return ResetResult(
            backup_filename=backup_meta.filename,
            tables_cleared=tables_cleared,
            record_counts=all_counts,
            total_records_deleted=total_deleted,
            redis_flushed=redis_flushed,
            redis_error=redis_error,
        )

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    async def execute_restore(
        self, backup_filename: str, admin_id: str
    ) -> RestoreResult:
        """Restore user data from a backup file.

        Reads the backup JSON, opens a transaction with 120s timeout, and
        inserts all records with ON CONFLICT DO NOTHING semantics.

        Args:
            backup_filename: Name of the backup JSON file.
            admin_id: UUID string of the admin performing the restore.

        Returns:
            RestoreResult with records_restored and records_skipped counts.

        Raises:
            FileNotFoundError: If backup file doesn't exist.
            RestoreExecutionError: If any insert fails (rolls back).
        """
        filepath = Path(self._backup_dir) / backup_filename

        if not filepath.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_filename}")

        # Read and parse backup
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                backup_content = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise RestoreExecutionError(
                table="file_read",
                detail=f"Failed to read backup file: {exc}",
            ) from exc

        data: dict[str, list[dict]] = backup_content.get("data", {})

        # Execute restore in a transaction
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("SET statement_timeout = '120s'")
                async with conn.transaction():
                    records_inserted, records_skipped = (
                        await self._repo.restore_data_in_transaction(conn, data)
                    )
        except RestoreExecutionError:
            raise
        except Exception as exc:
            logger.error("Restore transaction failed: %s", exc)
            raise RestoreExecutionError(
                table="transaction",
                detail=str(exc),
            ) from exc

        # Write audit log
        await self._audit_service.log_event(
            actor_id=admin_id,
            action_type="user_data_restore",
            target_resource=f"backup:{backup_filename}",
            metadata={
                "backup_filename": backup_filename,
                "records_restored": records_inserted,
                "records_skipped": records_skipped,
            },
        )

        return RestoreResult(
            backup_filename=backup_filename,
            records_restored=records_inserted,
            records_skipped=records_skipped,
        )

    # ------------------------------------------------------------------
    # List Backups
    # ------------------------------------------------------------------

    async def list_backups(self) -> list[BackupMetadata]:
        """List available backups sorted newest-first, max 100.

        Scans the backup directory for JSON files matching the backup
        naming pattern, reads their metadata headers, and returns them
        sorted by creation date descending.

        Returns:
            List of BackupMetadata, newest first, capped at 100 entries.

        Raises:
            ResetError: If the backup directory is inaccessible or any
                backup file's metadata cannot be read (Req 4.4).
        """
        backup_path = Path(self._backup_dir)

        # If the directory doesn't exist, no backups available (Req 4.3)
        if not backup_path.exists():
            return []

        # Verify the directory is accessible (Req 4.4)
        try:
            files = list(backup_path.glob("backup_*.json"))
        except OSError as exc:
            logger.error(
                "Backup storage directory inaccessible: %s", exc
            )
            raise ResetError(
                f"Backup storage access failure: {exc}",
                details={"error": str(exc)},
            ) from exc

        if not files:
            return []

        backups: list[BackupMetadata] = []

        for filepath in files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = json.load(f)

                metadata = content.get("metadata", {})
                created_at_str = metadata.get("created_at", "")
                created_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )

                backups.append(
                    BackupMetadata(
                        filename=filepath.name,
                        created_at=created_at,
                        file_size_bytes=filepath.stat().st_size,
                        total_records=metadata.get("total_records", 0),
                        tables=metadata.get("tables", []),
                        actor_id=metadata.get("actor_id"),
                    )
                )
            except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
                # Req 4.4: Do NOT return partial list — raise error
                logger.error(
                    "Failed to read backup file %s: %s",
                    filepath.name,
                    exc,
                )
                raise ResetError(
                    f"Failed to read backup file: {filepath.name}",
                    details={"filename": filepath.name, "error": str(exc)},
                ) from exc

        # Sort newest-first, cap at 100
        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups[:100]

    # ------------------------------------------------------------------
    # Redis Flush
    # ------------------------------------------------------------------

    async def _flush_redis(self) -> None:
        """Flush Redis keys matching the configured patterns.

        Uses SCAN + DELETE to avoid blocking Redis with large KEYS commands.
        Iterates REDIS_FLUSH_PATTERNS and deletes all matching keys.
        """
        total_deleted = 0

        for pattern in REDIS_FLUSH_PATTERNS:
            cursor: int | bytes = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    await self._redis.delete(*keys)
                    total_deleted += len(keys)
                if cursor == 0:
                    break

        logger.info("Redis flush complete: deleted %d keys", total_deleted)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for types not handled by stdlib json.

    Handles datetime, date, UUID, bytes, and set types.
    """
    from datetime import date
    from uuid import UUID

    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
