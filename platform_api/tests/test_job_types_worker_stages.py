"""Unit tests for job_types helpers and claim filtering."""

from __future__ import annotations

import pytest

from platform_api.services.job_types import (
    JOB_DRAFT,
    JOB_EXECUTE_BATCH,
    JOB_RUN_IMAGE_JOBS,
    JOB_SUNO_SUBMIT,
    PRI_EXECUTE_BATCH,
    STAGE_DRAFT_TYPES,
    STAGE_IMAGES_TYPES,
    STAGE_SUNO_TYPES,
    draft_priority_for_index,
    resolve_worker_job_types,
)


def test_execute_batch_outranks_draft_and_suno() -> None:
    assert PRI_EXECUTE_BATCH > 20
    assert PRI_EXECUTE_BATCH > draft_priority_for_index(0)
    assert PRI_EXECUTE_BATCH > 18


def test_draft_priority_tiers() -> None:
    assert draft_priority_for_index(0) == 20
    assert draft_priority_for_index(5) == 15
    assert draft_priority_for_index(15) == 5
    assert draft_priority_for_index(99) == 5


def test_resolve_worker_job_types_presets() -> None:
    assert resolve_worker_job_types("draft") == STAGE_DRAFT_TYPES
    assert resolve_worker_job_types("suno") == STAGE_SUNO_TYPES
    assert resolve_worker_job_types("images") == STAGE_IMAGES_TYPES
    assert JOB_EXECUTE_BATCH in resolve_worker_job_types("draft")
    assert JOB_DRAFT in resolve_worker_job_types("draft")
    assert JOB_SUNO_SUBMIT in resolve_worker_job_types("suno")
    assert JOB_RUN_IMAGE_JOBS in resolve_worker_job_types("images")


def test_resolve_worker_job_types_csv() -> None:
    types = resolve_worker_job_types("draft,suno_submit")
    assert types == frozenset({JOB_DRAFT, JOB_SUNO_SUBMIT})


def test_resolve_worker_job_types_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        resolve_worker_job_types("not_a_real_job")
