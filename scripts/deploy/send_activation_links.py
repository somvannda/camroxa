#!/usr/bin/env python3
"""Send the 24-hour activation-link email to unconfirmed music-web accounts.

Runs on the API host inside the platform venv (the driver uploads it):

    PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python \
        /tmp/send_activation_links.py            # dry run
    ... --apply                                  # send

Idempotent: successfully sent addresses are recorded in a JSON state file and
skipped on later runs unless ``--force`` is passed. Suspended and deleted
accounts are never emailed. Addresses with an undeliverable TLD are still
attempted (so the report shows the bounce) but flagged.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg

from platform_api.config import get_settings
from platform_api.services.email_link_tokens import build_email_verify_link
from platform_api.services.email_service import send_activation_email

STATE_PATH = Path.home() / ".camxora-activation-links-sent.json"
BAD_TLDS = {".con", ".ocm", ".cm"}

TARGETS_SQL = """
SELECT id, email, display_name, created_at
FROM users
WHERE email_confirmed = false
  AND deleted_at IS NULL
  AND status <> 'suspended'
ORDER BY created_at
"""


def load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def undeliverable(email: str) -> bool:
    lower = email.lower()
    return any(lower.endswith(tld) for tld in BAD_TLDS)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="actually send (default: dry run)")
    parser.add_argument("--only", action="append", default=[], help="email address to target")
    parser.add_argument("--force", action="store_true", help="re-send even if already sent")
    parser.add_argument("--limit", type=int, default=0, help="max recipients (0 = all)")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between sends")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.smtp_host or settings.smtp_host.strip().lower() in {"localhost", "127.0.0.1"}:
        raise SystemExit(
            "SMTP is not configured on this host (still localhost/MailHog); refusing to send."
        )

    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    try:
        rows = await pool.fetch(TARGETS_SQL)
    finally:
        await pool.close()

    only = {item.strip().lower() for item in args.only if item.strip()}
    if only:
        rows = [row for row in rows if str(row["email"]).lower() in only]
    if args.limit > 0:
        rows = rows[: args.limit]

    state = load_state()
    print(f"mode={'APPLY' if args.apply else 'DRY-RUN'} targets={len(rows)} "
          f"smtp={settings.smtp_host}:{settings.smtp_port}")

    sent = skipped = failed = 0
    failures: list[tuple[str, str]] = []
    for row in rows:
        email = str(row["email"])
        display_name = str(row["display_name"] or "there")
        prior = state.get(email) or {}
        if prior.get("ok") and not args.force:
            print(f"SKIP  {email} (already sent {prior.get('sent_at', '?')})")
            skipped += 1
            continue

        link = build_email_verify_link(str(row["id"]), email)
        flag = "  [UNDELIVERABLE TLD]" if undeliverable(email) else ""
        if undeliverable(email) and not args.force:
            print(f"SKIP  {email} (undeliverable TLD){flag}")
            skipped += 1
            continue
        if not args.apply:
            print(f"DRY   {email:<42} name={display_name!r} link_len={len(link)}{flag}")
            continue

        ok = send_activation_email(
            to_email=email,
            activation_link=link,
            display_name=display_name,
        )
        state[email] = {
            "ok": ok,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "display_name": display_name,
            "undeliverable_tld": undeliverable(email),
        }
        save_state(state)
        if ok:
            sent += 1
            print(f"SENT  {email}{flag}")
        else:
            failed += 1
            failures.append((email, "SMTP send failed"))
            print(f"FAIL  {email}{flag}")
        time.sleep(max(0.0, args.delay))

    print(f"ACTIVATION_CAMPAIGN_DONE sent={sent} skipped={skipped} failed={failed} "
          f"state={STATE_PATH}")
    for email, reason in failures:
        print(f"  FAILED {email}: {reason}")


if __name__ == "__main__":
    asyncio.run(main())
