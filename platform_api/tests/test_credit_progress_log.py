"""Credit progress log tests."""

from __future__ import annotations

import logging

from platform_api.services.credit_progress_log import log_deducted, log_refunded
from platform_api.services.credit_units import CREDIT_SCALE


def test_credit_progress_log_formats_display_amounts(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="platform_api.credits"):
        log_deducted(
            user_id="2be1d677-9c37-46e8-82dc-6d54e9bf8322",
            amount_units=3 * CREDIT_SCALE,
            reason="llm_draft",
            ref_id="song-ref-1",
            new_balance_units=100 * CREDIT_SCALE,
        )
        log_refunded(
            user_id="2be1d677-9c37-46e8-82dc-6d54e9bf8322",
            amount_units=3 * CREDIT_SCALE,
            reason="draft_generation_failed",
            ref_id="song-ref-1",
            new_balance_units=103 * CREDIT_SCALE,
        )
    assert "[credits] Deducted 3 credits" in caplog.text
    assert "[credits] Refunded 3 credits" in caplog.text
    assert "balance now 100 credits" in caplog.text
    assert "balance now 103 credits" in caplog.text
