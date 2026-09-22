# Fix music preflight 500 on fractional wallet balance

## Summary

Desktop Music → Automation showed a yellow **"An unexpected error occurred."** and the **Generate** button stayed disabled. The desktop was rendering the API's generic 500 message from `POST /api/v3/batches/preflight`; `GET /api/v3/credits/quota-status` failed the same way.

Captured production error body:

```
1 validation error for MusicPlanPreflightResponse
wallet_balance
  Input should be a valid integer, got a number with a fractional part
  [type=int_from_float, input_value=1970.4442, input_type=float]
```

## Root cause

`units_to_credits()` (`platform_api/services/credit_units.py`) returns a **float** of display credits, but two response models declared `wallet_balance: int`:

- `platform_api/models/schemas.py` → `MusicPlanPreflightResponse.wallet_balance`
- `platform_api/models/schemas.py` → `QuotaStatusResponse.wallet_balance`

Pydantic v2 rejects a fractional float for an `int` field, so any account whose balance converts to a non-whole number (e.g. `1970.4442`) got an unhandled 500. Whole-number balances passed, which is why it was account-specific. `/licenses` and admin user responses already used `float`.

## Fix

- `platform_api/models/schemas.py`: both `wallet_balance` fields `int` → `float`.
- `camxora_python/shared/models/platform.py`: `MusicPlanPreflightResponse.wallet_balance` `int` → `float` so the client accepts the corrected payload.
- Regression test: `platform_api/tests/test_wallet_balance_response_types.py`.

## Deploy / compatibility

- Server fix is required; whole-number-balance accounts keep working either way.
- Fractional-balance accounts also need the desktop model change shipped (next desktop build); the current 1.3.2 client still types the field as `int`.
