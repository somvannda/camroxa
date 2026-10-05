#!/usr/bin/env python3
"""Apply CutLuy credentials on sandbox via admin API (no direct DB)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SECRETS = REPO / ".deploy" / "secrets.env"
API = "https://api.sandbox.camxora.com/api/v1"


def load_env() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in SECRETS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        data[k.strip()] = v.strip()
    return data


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    env = load_env()
    secret = env.get("PLATFORM_CUTLUY_SECRET_KEY", "").strip()
    if not secret:
        print("ERROR: PLATFORM_CUTLUY_SECRET_KEY missing in .deploy/secrets.env")
        return 1

    admin_email = env.get("CAMXORA_ADMIN_EMAIL", "duke@camxora.com").strip()
    admin_password = env.get("CAMXORA_ADMIN_PASSWORD", "").strip()
    if not admin_password:
        print("ERROR: CAMXORA_ADMIN_PASSWORD missing in .deploy/secrets.env")
        return 1

    try:
        tokens = request(
            "POST",
            "/auth/login",
            {"email": admin_email, "password": admin_password},
        )
    except urllib.error.HTTPError as exc:
        print(f"Login failed ({exc.code}): {exc.read().decode()}")
        return 1

    token = tokens["access_token"]
    cutluy = request(
        "PUT",
        "/admin/billing/cutluy-config",
        {
            "api_base_url": "https://cutluy.com",
            "payment_link_id": env.get("PLATFORM_CUTLUY_PAYMENT_LINK_ID", "").strip(),
            "secret_key": secret,
            "webhook_secret": env.get("PLATFORM_CUTLUY_WEBHOOK_SECRET", "").strip() or None,
        },
        token=token,
    )
    print("CutLuy config:", json.dumps({k: cutluy[k] for k in cutluy if "masked" in k or k.endswith("_configured") or k in ("secret_source", "api_base_url")}))

    for key, value in [
        ("billing.provider.cutluy.enabled", "true"),
        ("billing.active_provider", "cutluy"),
    ]:
        request(
            "PUT",
            "/admin/system-settings",
            {"key": key, "value": value, "value_type": "string"},
            token=token,
        )
        print(f"Set {key}={value}")

    providers = request("GET", "/billing/providers")
    print(
        "Providers:",
        json.dumps(
            {
                "active_provider": providers.get("active_provider"),
                "paid_checkout_available": providers.get("paid_checkout_available"),
                "cutluy_secret_configured": providers.get("cutluy_secret_configured"),
                "cutluy_available": next(
                    (p.get("available") for p in providers.get("providers", []) if p.get("id") == "cutluy"),
                    None,
                ),
            }
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
