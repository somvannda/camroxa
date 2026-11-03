# Backfill: refund orphaned `v3_music` charges

Status: **draft, awaiting approval.** No production writes have been made.

## Why

A `v3_music` debit is written before the `suno_tasks` row exists. Until the
cancellation fix in `platform_api/services/web_music_service.py`, a request that
was cancelled between the charge and the enqueue left a paid song with no task,
no `job_queue` row and no refund.

The fix stops new cases. This document reverses the existing ones.

## Scope (read-only audit, 2026-11-03)

7-day lookback, `v3_music` debits with no task, no job and no refund:

| User | Charges | Credits |
|---|---|---|
| pengpheakdey02@gmail.com | 6 | 60 |
| netvichet0102@gmail.com | 4 | 40 |
| sommakara84@gmail.com | 3 | 30 |
| sompheaktra777@gmail.com | 3 | 30 |
| pengchun.pc@gmail.com | 2 | 20 |
| **Total** | **18** | **180** |

Not in scope: `keochanleakna@gmail.com` (40 credits, retries of never-terminal
pending tasks). That needs the stale-pending sweeper; refunding it here would
double-count once the sweeper exists.

## Step 1 - dry run (safe, read-only)

```bash
# on the VPS, as the camxora user
cd /opt/camxora/repo
set -a; . platform_api/.env; set +a
python scripts/ops/audit_orphan_music_charges.py --days 7
```

Expected: the table above, exit code `1`. Machine-readable:

```bash
python scripts/ops/audit_orphan_music_charges.py --days 7 --json > /tmp/orphans.json
```

Re-check immediately before applying; the number must not have grown from a new
leak.

## Step 2 - approval

The amount, the user list and the refund reason must be signed off before any
write. Recommended reason string: `orphaned_music_charge` (distinguishable from
`suno_generation_failed`).

## Step 3 - apply (reviewed one-off, not raw SQL)

Refunds must go through the billing service so the wallet, `credit_wallets` and
`credit_transactions` move together. A raw `INSERT` into `credit_transactions`
leaves the wallet out of sync - exactly the drift already present on 4 accounts.

Requirements for the apply run:

- one refund per **debit row id**, so a re-run is a no-op;
- `direction = 'credit'`, `ref_id` = the original debit's `ref_id`;
- wallet balance increased by the same unit amount;
- every refunded debit id written to an audit log line.

The apply script is intentionally **not** written yet: it must be reviewed
against the current `CreditsOnlyBillingService.refund` signature before it can
touch production, and it should reuse that service rather than reimplement it.

## Step 4 - verify

```bash
# must return 0 rows / exit 0
python scripts/ops/audit_orphan_music_charges.py --days 7
```

Then confirm per-user balances moved by exactly the refunded amount:

```sql
SELECT u.email,
       w.balance / 10000.0 AS balance_now,
       round(coalesce(sum(ct.amount) FILTER (WHERE ct.reason = 'orphaned_music_charge'), 0) / 10000.0, 2) AS refunded
FROM users u
JOIN credit_wallets w ON w.user_id = u.id
LEFT JOIN credit_transactions ct ON ct.user_id = u.id
WHERE u.email IN (
  'pengpheakdey02@gmail.com', 'netvichet0102@gmail.com', 'sommakara84@gmail.com',
  'sompheaktra777@gmail.com', 'pengchun.pc@gmail.com')
GROUP BY u.email, w.balance;
```

## Rollback

None required - refunds are credits. If a refund is wrong, post a compensating
debit through the same service and record the reason.

## Follow-ups

1. Stale-pending sweeper for tasks that never reach a terminal state.
2. Schedule this audit (systemd timer or the ops-alert run) and page on
   `orphaned_charges > 0`.
3. Investigate the 4 existing wallet/ledger drifts before any other backfill.
