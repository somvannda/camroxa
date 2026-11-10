# Creator Program: publish, earn, get paid

## Summary

Ships the Camxora Creator Program end to end: a creator publishes a finished
generation in one call, plays count, royalties accrue into a ledger, and money
leaves through a maker-checked payout with tax withheld. Identity documents are
encrypted at rest and every money action is recorded in an append-only trail.

There is **no application step**. The artist profile is created on first publish.

## Product impact

- **Publishing** — `/creator/releases` has one primary action, **Publish**. The
  title defaults to the generation title; genre and rights are the only inputs.
  Drafts remain available as a secondary action.
- **Public pages** — `/creators/[handle]` lists real published releases with
  track counts, not a placeholder.
- **Artist page** — avatar and banner are cropped in the browser (1:1 → 512×512,
  3:1 → 1500×500) before upload.
- **Earnings and payouts** — holdback earnings release hourly; payouts settle in
  **KHR or USD** with the rate recorded; KYC is required for money only.
- **Tax** — 30% US royalty withholding applies (Cambodia has no treaty). A
  statement is generated per tax year and can be printed.
- **Admin** — payout verification, payouts with maker-checker, releases,
  royalty periods, reconciliation, annual statements, and a money audit console.
- The word "program" is gone from creator screens: `Creator Studio` is now
  `Your music`.

## Technical impact

- Migrations **186–196**: `valid_streams`, `royalty_ledger`, `royalty_policies`,
  `royalty_periods`, `creator_profiles`, `creator_releases`,
  `creator_earning_eligibility`, `creator_earnings`, `creator_kyc`,
  `creator_payouts`, `creator_payout_accounts`, `creator_tax_statements`,
  `creator_money_audit`.
- **Money correctness**
  - Payouts carry `gross_micros`, `withheld_micros`, `fx_rate`,
    `payout_amount_minor`; the ledger stays in USD micros.
  - Reconciliation compares earnings against payout **gross**, so withholding is
    not counted as drift.
  - Maker-checker: creator/approver cannot double-act on one payout.
  - `creator_money_audit` has a trigger that rejects UPDATE and DELETE.
- **Document security** — `DocumentCipher` derives a key from the master secret
  with a purpose-specific salt; KYC objects are stored as ciphertext and are only
  decrypted by an authenticated admin endpoint with `Cache-Control: no-store`.
- **Scheduled jobs** — creator eligibility (hourly), earnings holdback release
  (hourly), reserve release after 90 days (daily). All are idempotent.

## Files touched

`platform_api/` (services, routers, 11 migrations, tests), `camxora.com/`
(CreatorUI kit, creator screens, public creator page), `admin_portal/` (creator
consoles, sidebar, page header), `docs/creator-program/`, `scripts/creator-program/`.

## Migration/deploy

- 11 forward migrations, single head `196`.
- Backfill needed in environments that stored KYC documents before encryption:
  `python scripts/creator-program/encrypt_existing_kyc_documents.py --dry-run`,
  then without `--dry-run`.
- Optional demo catalog: `python scripts/creator-program/seed_sample_releases.py`
  (never in production).

## Tests

- 76 creator/royalty tests pass; both frontends typecheck.
- Verified against real storage and a real database: KHR payout conversion
  ($30.00 → $9.00 withheld → $21.00 → 86,100 ៛) through CSV, reconciliation, UI
  and statement; KYC object ciphertext with a matching decrypted hash; reserve
  release split 60/40 netting to zero and refusing a second release; audit rows
  written by real actions.

## Follow-ups

- The KHR rate is operator-entered (bounded 3,500–5,000). It needs a dated rate
  source before volume.
- Tax statements are printable pages, not signed PDFs.
- Audit trail has no export yet.
