"""Regression: wallet_balance is fractional display credits, not an int.

`units_to_credits()` returns a float (e.g. 1970.4442). When the response
models declared ``wallet_balance: int``, Pydantic v2 rejected the fractional
value and the API returned a generic 500 for accounts whose balance was not a
whole number — which surfaced on the desktop Music page as a yellow
"An unexpected error occurred." under Automation and a disabled Generate.
"""

from __future__ import annotations

from platform_api.models.schemas import (
    MusicPlanPreflightResponse,
    QuotaStatusResponse,
)


def test_preflight_accepts_fractional_wallet_balance() -> None:
    response = MusicPlanPreflightResponse(can_generate=True, wallet_balance=1970.4442)
    assert response.wallet_balance == 1970.4442
    assert response.model_dump()["wallet_balance"] == 1970.4442


def test_quota_status_accepts_fractional_wallet_balance() -> None:
    response = QuotaStatusResponse(wallet_balance=1970.4442)
    assert response.wallet_balance == 1970.4442
    assert response.model_dump()["wallet_balance"] == 1970.4442


def test_wallet_balance_fields_are_float() -> None:
    for model in (MusicPlanPreflightResponse, QuotaStatusResponse):
        assert model.model_fields["wallet_balance"].annotation is float
