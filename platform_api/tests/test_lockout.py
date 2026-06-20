"""Tests for the account lockout service (platform_api.services.lockout)."""

from __future__ import annotations

import pytest

from platform_api.exceptions import AccountLockedError
from platform_api.services.lockout import (
    LOCKOUT_DURATION_SEC,
    LOCKOUT_THRESHOLD,
    AccountLockout,
)


# ---------------------------------------------------------------------------
# Fake async Redis for unit-testing without a real server
# ---------------------------------------------------------------------------


class FakeRedis:
    """Minimal async Redis stub supporting the subset used by AccountLockout."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def incr(self, key: str) -> int:
        current = int(self._store.get(key, "0"))
        current += 1
        self._store[key] = str(current)
        return current

    async def expire(self, key: str, seconds: int) -> bool:
        self._ttls[key] = seconds
        return True

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        self._store[key] = value
        self._ttls[key] = seconds
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                self._ttls.pop(key, None)
                count += 1
        return count


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def lockout(fake_redis: FakeRedis) -> AccountLockout:
    return AccountLockout(redis=fake_redis)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# check_lockout tests
# ---------------------------------------------------------------------------


class TestCheckLockout:
    """Tests for AccountLockout.check_lockout."""

    async def test_no_lockout_when_key_absent(self, lockout: AccountLockout) -> None:
        """Should not raise when no lockout key exists."""
        await lockout.check_lockout("user@example.com")  # should not raise

    async def test_raises_when_locked(
        self, lockout: AccountLockout, fake_redis: FakeRedis
    ) -> None:
        """Should raise AccountLockedError when lockout key exists."""
        fake_redis._store["auth:lockout:user@example.com"] = "1"
        with pytest.raises(AccountLockedError):
            await lockout.check_lockout("user@example.com")


# ---------------------------------------------------------------------------
# record_failed_attempt tests
# ---------------------------------------------------------------------------


class TestRecordFailedAttempt:
    """Tests for AccountLockout.record_failed_attempt."""

    async def test_increments_counter(
        self, lockout: AccountLockout, fake_redis: FakeRedis
    ) -> None:
        """Counter increments on each failed attempt."""
        await lockout.record_failed_attempt("user@example.com")
        assert fake_redis._store["auth:failures:user@example.com"] == "1"

        await lockout.record_failed_attempt("user@example.com")
        assert fake_redis._store["auth:failures:user@example.com"] == "2"

    async def test_sets_expiry_on_counter(
        self, lockout: AccountLockout, fake_redis: FakeRedis
    ) -> None:
        """Failure counter should have TTL equal to LOCKOUT_DURATION_SEC."""
        await lockout.record_failed_attempt("user@example.com")
        assert fake_redis._ttls.get("auth:failures:user@example.com") == LOCKOUT_DURATION_SEC

    async def test_locks_account_at_threshold(
        self, lockout: AccountLockout, fake_redis: FakeRedis
    ) -> None:
        """After LOCKOUT_THRESHOLD failures, lockout key is set."""
        for _ in range(LOCKOUT_THRESHOLD):
            await lockout.record_failed_attempt("user@example.com")

        # Lockout key must exist
        assert "auth:lockout:user@example.com" in fake_redis._store
        # Failure counter should be deleted
        assert "auth:failures:user@example.com" not in fake_redis._store

    async def test_lockout_key_has_correct_ttl(
        self, lockout: AccountLockout, fake_redis: FakeRedis
    ) -> None:
        """Lockout key TTL matches LOCKOUT_DURATION_SEC (15 minutes)."""
        for _ in range(LOCKOUT_THRESHOLD):
            await lockout.record_failed_attempt("user@example.com")

        assert fake_redis._ttls["auth:lockout:user@example.com"] == LOCKOUT_DURATION_SEC

    async def test_no_lockout_below_threshold(
        self, lockout: AccountLockout, fake_redis: FakeRedis
    ) -> None:
        """Fewer than LOCKOUT_THRESHOLD attempts must not trigger lockout."""
        for _ in range(LOCKOUT_THRESHOLD - 1):
            await lockout.record_failed_attempt("user@example.com")

        assert "auth:lockout:user@example.com" not in fake_redis._store

    async def test_separate_emails_tracked_independently(
        self, lockout: AccountLockout, fake_redis: FakeRedis
    ) -> None:
        """Failures for different emails do not cross-contaminate."""
        for _ in range(LOCKOUT_THRESHOLD - 1):
            await lockout.record_failed_attempt("alice@example.com")

        await lockout.record_failed_attempt("bob@example.com")

        # Neither should be locked
        assert "auth:lockout:alice@example.com" not in fake_redis._store
        assert "auth:lockout:bob@example.com" not in fake_redis._store


# ---------------------------------------------------------------------------
# reset_failures tests
# ---------------------------------------------------------------------------


class TestResetFailures:
    """Tests for AccountLockout.reset_failures."""

    async def test_clears_counter(
        self, lockout: AccountLockout, fake_redis: FakeRedis
    ) -> None:
        """Successful login clears the failure counter."""
        # Simulate 3 failures then a success
        for _ in range(3):
            await lockout.record_failed_attempt("user@example.com")

        await lockout.reset_failures("user@example.com")
        assert "auth:failures:user@example.com" not in fake_redis._store

    async def test_reset_is_idempotent(
        self, lockout: AccountLockout, fake_redis: FakeRedis
    ) -> None:
        """Resetting when no failures exist should not raise."""
        await lockout.reset_failures("user@example.com")  # should not raise


# ---------------------------------------------------------------------------
# Integration-style scenario tests
# ---------------------------------------------------------------------------


class TestLockoutScenarios:
    """End-to-end lockout scenarios."""

    async def test_locked_after_threshold_then_check_raises(
        self, lockout: AccountLockout
    ) -> None:
        """Full scenario: fail 5 times then verify lockout raises."""
        email = "target@example.com"
        for _ in range(LOCKOUT_THRESHOLD):
            await lockout.record_failed_attempt(email)

        with pytest.raises(AccountLockedError):
            await lockout.check_lockout(email)

    async def test_reset_before_threshold_prevents_lockout(
        self, lockout: AccountLockout, fake_redis: FakeRedis
    ) -> None:
        """A successful login between failures resets the counter."""
        email = "user@example.com"
        for _ in range(LOCKOUT_THRESHOLD - 1):
            await lockout.record_failed_attempt(email)

        await lockout.reset_failures(email)

        # Start failing again — should take another full set to lock
        for _ in range(LOCKOUT_THRESHOLD - 1):
            await lockout.record_failed_attempt(email)

        assert "auth:lockout:user@example.com" not in fake_redis._store
