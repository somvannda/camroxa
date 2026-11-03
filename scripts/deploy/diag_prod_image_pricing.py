#!/usr/bin/env python3
"""Read-only production check: what a v3 ``image`` charge resolves to.

Prints the image pricing rows, the image routing assignments, and the recent
``v3_image`` debits for one user, then shows which row the **old** resolver
(first ``background_image``/``thumbnail_image``/``image`` row in ``get_all()``
order) would have charged versus the routed row.

Usage:
    python scripts/deploy/diag_prod_image_pricing.py
    python scripts/deploy/diag_prod_image_pricing.py <user-uuid>
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"
DEFAULT_USER_ID = "2baeaae8-0121-4d98-872d-eff832237f46"
IMAGE_ALIASES = ("background_image", "thumbnail_image", "image")

CMD_TEMPLATE = r"""
set +e
echo '=== alembic ==='
sudo -u postgres psql -d camxora_platform -Atc "SELECT version_num FROM alembic_version ORDER BY 1;"
echo '=== image pricing rows ==='
sudo -u postgres psql -d camxora_platform -AtF '|' -c "SELECT ai_service, operation_type, COALESCE(sub_model,''), credits_per_operation, COALESCE(external_cost_cents,0) FROM credit_pricing WHERE operation_type IN ('background_image','thumbnail_image','image') ORDER BY ai_service, operation_type, sub_model;"
echo '=== image routing assignments ==='
sudo -u postgres psql -d camxora_platform -Atc "SELECT COALESCE(value::text,'') FROM system_settings WHERE key = 'ai_routing_assignments';"
echo '=== image fallback chain ==='
sudo -u postgres psql -d camxora_platform -Atc "SELECT COALESCE(value::text,'') FROM system_settings WHERE key = 'ai_routing_image_fallback_chain';"
echo '=== recent v3_image debits ==='
sudo -u postgres psql -d camxora_platform -AtF '|' -c "SELECT created_at, direction, amount, reason, COALESCE(ref_id,''), COALESCE(metadata::text,'') FROM credit_transactions WHERE user_id = '{user_id}' AND reason IN ('v3_image','v3_refund_image') ORDER BY created_at DESC LIMIT 30;"
echo DIAG_IMAGE_PRICING_DONE
"""


def run_cmd(client, cmd: str, timeout: int = 45) -> str:
    chan = client.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out = b""
    started = time.time()
    while True:
        if chan.recv_ready():
            chunk = chan.recv(65535)
            if not chunk:
                break
            out += chunk
        if chan.exit_status_ready():
            while chan.recv_ready():
                out += chan.recv(65535)
            break
        if time.time() - started > timeout:
            out += b"\nTIMEOUT\n"
            break
        time.sleep(0.1)
    return out.decode("utf-8", errors="replace")


def _split_sections(output: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw in output.splitlines():
        line = raw.strip()
        if line.startswith("===") and line.endswith("==="):
            current = line.strip("= ").strip()
            sections[current] = []
            continue
        if current and line and line != "DIAG_IMAGE_PRICING_DONE":
            sections[current].append(line)
    return sections


def _credits(units: str | int) -> str:
    try:
        return f"{int(units) / 10_000:g}"
    except (TypeError, ValueError):
        return str(units)


def _parse_rows(lines: list[str]) -> list[dict]:
    rows: list[dict] = []
    for line in lines:
        parts = line.split("|")
        if len(parts) < 4:
            continue
        rows.append(
            {
                "ai_service": parts[0].strip(),
                "operation_type": parts[1].strip(),
                "sub_model": parts[2].strip(),
                "units": int(parts[3]),
            }
        )
    return rows


def _routed(assignments: dict, operation: str) -> tuple[str, str]:
    entry = assignments.get(operation) or {}
    provider = str(entry.get("provider") or "").strip()
    sub_model = str(entry.get("sub_model") or "").strip()
    return provider, sub_model


def _old_resolver_pick(rows: list[dict]) -> dict | None:
    """First image alias row in ``get_all()`` order — what the bug charged."""
    for row in rows:
        if row["operation_type"] in IMAGE_ALIASES:
            return row
    return None


def _new_resolver_pick(rows: list[dict], provider: str, sub_model: str, operation: str) -> dict | None:
    """Routed provider/model first, then provider defaults, then the scan."""
    chain = []
    if provider:
        chain.extend(
            [
                (provider, operation, sub_model),
                (provider, operation, ""),
                (provider, "background_image", sub_model),
                (provider, "thumbnail_image", sub_model),
                (provider, "background_image", ""),
                (provider, "thumbnail_image", ""),
            ]
        )
    for service, op in (("fal", "background_image"), ("openai", "background_image")):
        chain.append((service, op, ""))
    seen: set[tuple[str, str, str]] = set()
    for service, op, model in chain:
        key = (service, op, model)
        if key in seen:
            continue
        seen.add(key)
        for row in rows:
            if (
                row["ai_service"] == service
                and row["operation_type"] == op
                and row["sub_model"] == model
            ):
                return row
    for row in rows:
        if provider and row["ai_service"] != provider:
            continue
        if row["operation_type"] in (operation, *IMAGE_ALIASES):
            return row
    return _old_resolver_pick(rows)


def main(argv: list[str]) -> int:
    user_id = str(UUID(argv[1] if len(argv) > 1 else DEFAULT_USER_ID))

    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Read-only check on {user}@{host} for user {user_id}", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    print("SSH connected", flush=True)
    try:
        output = run_cmd(client, CMD_TEMPLATE.format(user_id=user_id), timeout=40)
    finally:
        client.close()

    print(output, flush=True)

    sections = _split_sections(output)
    rows = _parse_rows(sections.get("image pricing rows", []))

    assignments: dict = {}
    for line in sections.get("image routing assignments", []):
        try:
            assignments = json.loads(line)
            break
        except json.JSONDecodeError:
            continue

    print("=== resolved price (new code) ===")
    for operation in ("background_image", "thumbnail_image"):
        provider, sub_model = _routed(assignments, operation)
        pick = _new_resolver_pick(rows, provider, sub_model, operation)
        if pick is None:
            print(f"{operation}: NO PRICING ROW")
            continue
        print(
            f"{operation}: routed {provider or '?'}/{sub_model or 'default'} "
            f"-> {pick['ai_service']}/{pick['operation_type']}/"
            f"{pick['sub_model'] or 'default'} = {_credits(pick['units'])} credits"
        )

    print("=== what the old resolver charged (first alias row) ===")
    old = _old_resolver_pick(rows)
    if old is None:
        print("no image pricing rows")
    else:
        print(
            f"{old['ai_service']}/{old['operation_type']}/"
            f"{old['sub_model'] or 'default'} = {_credits(old['units'])} credits"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
