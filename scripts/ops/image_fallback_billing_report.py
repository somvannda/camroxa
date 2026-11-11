#!/usr/bin/env python3
"""Read-only report: image charges vs the provider that actually ran.

The v3 image charge is quoted from the AI Routing assignment. When SLAI fails
and the job falls back to kie (or any other model), the debit and the executed
provider differ. This report shows, per day:

  charges/refunds   image debits and failure refunds in the wallet ledger
  jobs by provider  image_jobs rows grouped by the provider that succeeded
  fair credits      sum of the persisted pricing row for the executed provider
  delta             net charged minus fair (negative = undercharged)

Pricing rows are averaged per provider/operation when a provider has several
models, because image_jobs does not store the executed sub-model.

Read-only: no ledger or job rows are modified.

Usage:
    python scripts/ops/image_fallback_billing_report.py --days 14
    python scripts/ops/image_fallback_billing_report.py --days 30 --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date, timedelta

import asyncpg

UNITS_PER_CREDIT = 10_000

SQL = """
WITH span AS (
    SELECT $1::date AS start_date, $2::date AS end_date
), prices AS (
    SELECT ai_service, operation_type, avg(credits_per_operation)::numeric AS units
    FROM credit_pricing
    WHERE operation_type IN ('background_image', 'thumbnail_image')
    GROUP BY 1, 2
), jobs AS (
    SELECT j.created_at::date AS d,
           j.provider,
           j.kind,
           count(*)::bigint AS n
    FROM image_jobs j
    WHERE j.created_at::date BETWEEN (SELECT start_date FROM span)
                                 AND (SELECT end_date FROM span)
    GROUP BY j.created_at::date, j.provider, j.kind
), job_totals AS (
    SELECT d,
           sum(n)::bigint AS jobs,
           sum(n) FILTER (WHERE provider = 'slai')::bigint AS slai,
           sum(n) FILTER (WHERE provider = 'kie')::bigint AS kie,
           sum(n) FILTER (WHERE provider NOT IN ('slai', 'kie'))::bigint AS other,
           sum(coalesce(p.units, 0) * n)::numeric AS fair_units
    FROM jobs j
    LEFT JOIN prices p
      ON p.ai_service = j.provider
     AND p.operation_type = CASE j.kind
           WHEN 'thumbnail' THEN 'thumbnail_image'
           ELSE 'background_image'
         END
    GROUP BY d
), ledger AS (
    SELECT created_at::date AS d,
           count(*) FILTER (WHERE reason = 'v3_image')::bigint AS charges,
           coalesce(sum(amount) FILTER (WHERE reason = 'v3_image'), 0)::bigint AS charged_units,
           count(*) FILTER (
               WHERE reason = 'image_generation_failed' AND direction = 'refund'
           )::bigint AS refunds,
           coalesce(sum(amount) FILTER (
               WHERE reason = 'image_generation_failed' AND direction = 'refund'
           ), 0)::bigint AS refund_units,
           count(*) FILTER (
               WHERE reason = 'v3_image' AND metadata ? 'provider'
           )::bigint AS attributed_charges
    FROM credit_transactions
    WHERE created_at::date BETWEEN (SELECT start_date FROM span)
                               AND (SELECT end_date FROM span)
      AND reason IN ('v3_image', 'image_generation_failed')
    GROUP BY created_at::date
)
SELECT to_char(days.d, 'YYYY-MM-DD') AS day,
       coalesce(l.charges, 0) AS charges,
       coalesce(l.refunds, 0) AS refunds,
       coalesce(l.charged_units, 0) AS charged_units,
       coalesce(l.refund_units, 0) AS refund_units,
       coalesce(l.attributed_charges, 0) AS attributed_charges,
       coalesce(j.jobs, 0) AS jobs,
       coalesce(j.slai, 0) AS slai,
       coalesce(j.kie, 0) AS kie,
       coalesce(j.other, 0) AS other,
       coalesce(j.fair_units, 0) AS fair_units
FROM generate_series(
         (SELECT start_date FROM span), (SELECT end_date FROM span), '1 day'
     ) AS days(d)
LEFT JOIN ledger l ON l.d = days.d
LEFT JOIN job_totals j ON j.d = days.d
ORDER BY days.d
"""


def _credits(units: int | float) -> float:
    return round(float(units) / UNITS_PER_CREDIT, 4)


async def run(dsn: str, days: int, as_json: bool) -> int:
    end = date.today()
    start = end - timedelta(days=max(1, days) - 1)
    conn = await asyncpg.connect(dsn=dsn)
    try:
        rows = await conn.fetch(SQL, start, end)
    finally:
        await conn.close()

    out: list[dict] = []
    for r in rows:
        charged = int(r["charged_units"] or 0) - int(r["refund_units"] or 0)
        fair = int(r["fair_units"] or 0)
        out.append(
            {
                "day": r["day"],
                "charges": int(r["charges"] or 0),
                "refunds": int(r["refunds"] or 0),
                "net_charged_credits": _credits(charged),
                "jobs": int(r["jobs"] or 0),
                "slai": int(r["slai"] or 0),
                "kie": int(r["kie"] or 0),
                "other": int(r["other"] or 0),
                "fair_credits": _credits(fair),
                "delta_credits": _credits(charged - fair),
                "attributed_charges": int(r["attributed_charges"] or 0),
            }
        )

    if as_json:
        print(json.dumps({"start": str(start), "end": str(end), "days": out}, indent=2))
        return 0

    print(f"image billing: {start} .. {end} (read-only)")
    print(
        "day         chg rfd  net_chg   jobs slai  kie other  fair  delta  attr"
    )
    for d in out:
        print(
            f"{d['day']}  {d['charges']:>4} {d['refunds']:>3} "
            f"{d['net_charged_credits']:>8.2f} {d['jobs']:>6} "
            f"{d['slai']:>4} {d['kie']:>4} {d['other']:>5} "
            f"{d['fair_credits']:>6.2f} {d['delta_credits']:>+7.2f} "
            f"{d['attributed_charges']:>5}"
        )
    total_net = sum(int(r["net_charged_credits"] * UNITS_PER_CREDIT) for r in out)
    total_fair = sum(int(r["fair_credits"] * UNITS_PER_CREDIT) for r in out)
    print(
        f"total net {_credits(total_net):.2f} credits, "
        f"fair {_credits(total_fair):.2f}, "
        f"delta {_credits(total_net - total_fair):+.2f} credits"
    )
    print(
        "note: historical rows without metadata.provider cannot be rewritten "
        "safely (charges carry no job id); this report is estimate-only."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("PLATFORM_DATABASE_URL"),
        help="platform DB DSN (default: $PLATFORM_DATABASE_URL)",
    )
    parser.add_argument("--days", type=int, default=14, help="window size in days")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()
    if not args.dsn:
        print("error: no DSN; pass --dsn or set PLATFORM_DATABASE_URL", file=sys.stderr)
        return 2
    dsn = str(args.dsn).replace("postgresql+asyncpg://", "postgresql://")
    try:
        return asyncio.run(run(dsn, args.days, args.json))
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
