"""Sandbox-only wallet audit API checks. Prints no secrets."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.sandbox.camxora.com"
ADMIN_EMAIL = os.environ.get("CAMXORA_ADMIN_EMAIL", "duke@camxora.com")
ADMIN_PASSWORD = os.environ["CAMXORA_ADMIN_PASSWORD"]

WATCH = (
    "kongsomvannda1987@gmail.com",
    "ksomvannda@gmail.com",
    "credits-cutover-test@sandbox.camxora.test",
)


def req(
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=45) as resp:
            raw = resp.read().decode("utf-8", "replace")
            payload = json.loads(raw) if raw else {}
            return resp.status, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw[:400]}
        return exc.code, payload


def unwrap(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def main() -> int:
    results: list[str] = []

    status, plans = req("GET", "/api/v1/plans/public")
    rows = unwrap(plans) if isinstance(unwrap(plans), list) else unwrap(plans).get("items") or unwrap(plans)
    if not isinstance(rows, list):
        rows = []
    prices = [int(r.get("price_cents") or 0) for r in rows if isinstance(r, dict)]
    names = [str(r.get("name") or r.get("slug") or "") for r in rows if isinstance(r, dict)]
    leak_79 = any(p == 7900 for p in prices)
    results.append(
        f"D09_public_v1 status={status} rows={len(rows)} leak79={leak_79} names={names}"
    )

    status, v3plans = req("GET", "/api/v3/plans/public")
    v3rows = unwrap(v3plans)
    if isinstance(v3rows, dict):
        v3rows = v3rows.get("items") or v3rows.get("plans") or []
    if not isinstance(v3rows, list):
        v3rows = []
    leak_79_v3 = any(int(r.get("price_cents") or 0) == 7900 for r in v3rows if isinstance(r, dict))
    free = next((r for r in v3rows if isinstance(r, dict) and int(r.get("price_cents") or 0) == 0), None)
    daily = None if free is None else free.get("daily_credits")
    music = None if free is None else free.get("music_credits")
    lyric = None if free is None else free.get("lyric_credits")
    results.append(
        f"D04_public_v3 status={status} rows={len(v3rows)} leak79={leak_79_v3} free_daily={daily} music={music} lyric={lyric}"
    )

    status, login = req(
        "POST",
        "/api/v1/auth/login",
        body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    login_data = unwrap(login) if isinstance(login, dict) else {}
    token = None
    if isinstance(login_data, dict):
        token = login_data.get("access_token") or login_data.get("token")
        if not token and isinstance(login_data.get("tokens"), dict):
            token = login_data["tokens"].get("access_token")
    if status != 200 or not token:
        print("LOGIN_FAIL", status)
        print(json.dumps(login, indent=2)[:800])
        return 1
    results.append(f"admin_login status={status}")

    status, flag = req("GET", "/api/v1/settings", token=token)
    settings = unwrap(flag)
    flag_val = None
    if isinstance(settings, dict):
        flag_val = settings.get("credits_only_v3_charge")
        if flag_val is None and isinstance(settings.get("settings"), dict):
            flag_val = settings["settings"].get("credits_only_v3_charge")
        if flag_val is None and isinstance(settings.get("items"), list):
            for item in settings["items"]:
                if isinstance(item, dict) and item.get("key") == "credits_only_v3_charge":
                    flag_val = item.get("value")
    results.append(f"flag credits_only_v3_charge={flag_val}")

    items: list[dict[str, Any]] = []
    page = 1
    while page <= 20:
        status, users = req("GET", f"/api/v1/users?page={page}&page_size=100", token=token)
        users_payload = unwrap(users)
        if not isinstance(users_payload, dict):
            results.append(f"C01_users_list_bad status={status} page={page}")
            break
        batch = users_payload.get("users") or users_payload.get("items") or []
        if not isinstance(batch, list):
            break
        items.extend([u for u in batch if isinstance(u, dict)])
        total = int(users_payload.get("total") or 0)
        if len(items) >= total or not batch:
            break
        page += 1
    tag_cols = 0
    for item in items:
        if item.get("tag") or item.get("user_tag"):
            tag_cols += 1
    watch_rows = [u for u in items if str(u.get("email") or "").lower() in {w.lower() for w in WATCH}]
    results.append(
        f"C01_users_list status={status} pages={page} count={len(items)} watch={len(watch_rows)} tag_fields={tag_cols}"
    )
    for user in watch_rows:
        results.append(
            "USER "
            + json.dumps(
                {
                    "email": user.get("email"),
                    "id": user.get("id"),
                    "plan_name": user.get("plan_name"),
                    "credit_balance": user.get("credit_balance"),
                    "music_credits_used": user.get("music_credits_used"),
                    "music_credits_limit": user.get("music_credits_limit"),
                    "music_credits_remaining": user.get("music_credits_remaining"),
                },
                default=str,
            )
        )

    for user in watch_rows:
        uid = user.get("id")
        email = user.get("email")
        st, detail = req("GET", f"/api/v1/users/{uid}/details", token=token)
        detail_data = unwrap(detail) if isinstance(detail, dict) else {}
        st3, v3 = req("GET", f"/api/v3/users/{uid}/credits", token=token)
        v3data = unwrap(v3) if isinstance(v3, dict) else {}
        results.append(
            "DETAIL "
            + json.dumps(
                {
                    "email": email,
                    "list_plan": user.get("plan_name"),
                    "detail_plan": detail_data.get("plan_name") if isinstance(detail_data, dict) else None,
                    "list_credits": user.get("credit_balance"),
                    "detail_status": st,
                    "detail_wallet": (
                        (detail_data.get("wallet") or {}).get("balance")
                        if isinstance(detail_data, dict) and isinstance(detail_data.get("wallet"), dict)
                        else detail_data.get("credit_balance") if isinstance(detail_data, dict) else None
                    ),
                    "v3_status": st3,
                    "v3_balance": v3data.get("balance") if isinstance(v3data, dict) else None,
                    "v3_lots": (
                        [
                            {
                                "tag": lot.get("tag") or lot.get("lot_type"),
                                "remaining": lot.get("remaining") or lot.get("remaining_units"),
                                "expires_at": lot.get("expires_at"),
                            }
                            for lot in (v3data.get("lots") or [])[:8]
                        ]
                        if isinstance(v3data, dict)
                        else None
                    ),
                },
                default=str,
            )
        )

    status, licenses = req("GET", "/api/v1/licenses?limit=200", token=token)
    lic_payload = unwrap(licenses)
    lic_items = lic_payload.get("items") if isinstance(lic_payload, dict) else lic_payload
    if not isinstance(lic_items, list):
        lic_items = []
    sources = {}
    for row in lic_items:
        if not isinstance(row, dict):
            continue
        sources[row.get("source") or "desktop"] = sources.get(row.get("source") or "desktop", 0) + 1
    watch_lic = [
        {
            "email": r.get("user_email"),
            "source": r.get("source"),
            "plan_name": r.get("plan_name"),
            "status": r.get("status"),
        }
        for r in lic_items
        if isinstance(r, dict)
        and str(r.get("user_email") or "").lower() in {w.lower() for w in WATCH}
    ]
    results.append(f"C04_licenses status={status} count={len(lic_items)} sources={sources}")
    results.append("LIC_WATCH " + json.dumps(watch_lic, default=str))

    status, usage = req("GET", "/api/v1/admin/usage?page=1&page_size=50", token=token)
    usage_data = unwrap(usage) if isinstance(usage, dict) else {}
    summary = usage_data.get("summary") if isinstance(usage_data, dict) else {}
    usage_items = usage_data.get("items") if isinstance(usage_data, dict) else []
    leftover_rows = []
    if isinstance(usage_items, list):
        leftover_rows = [
            {
                "reason": t.get("reason"),
                "label": t.get("label") or t.get("display_reason") or t.get("reason_label"),
                "email": t.get("user_email"),
                "amount": t.get("amount"),
            }
            for t in usage_items
            if isinstance(t, dict)
            and (
                t.get("reason") in {"v3_web_remaining", "v3_period_grant", "v3_daily_grant"}
                or "leftover" in str(t.get("label") or t.get("reason") or "").lower()
            )
        ]
    results.append(
        "C08_usage "
        + json.dumps(
            {
                "status": status,
                "total": usage_data.get("total") if isinstance(usage_data, dict) else None,
                "grant_issued": summary.get("grant_issued") if isinstance(summary, dict) else None,
                "grant_issued_events": summary.get("grant_issued_events") if isinstance(summary, dict) else None,
                "wallet_charged": summary.get("wallet_charged") if isinstance(summary, dict) else None,
                "leftover_on_page": leftover_rows[:8],
            },
            default=str,
        )
    )

    for user in watch_rows:
        uid = user.get("id")
        email = user.get("email")
        st, tx = req(
            "GET",
            f"/api/v1/admin/usage?page=1&page_size=50&user_id={uid}",
            token=token,
        )
        tx_data = unwrap(tx) if isinstance(tx, dict) else {}
        items_tx = tx_data.get("items") if isinstance(tx_data, dict) else []
        if not isinstance(items_tx, list):
            items_tx = []
        leftover = [
            {
                "reason": t.get("reason"),
                "label": t.get("label") or t.get("display_reason") or t.get("reason_label"),
                "amount": t.get("amount"),
                "direction": t.get("direction"),
            }
            for t in items_tx
            if isinstance(t, dict)
            and t.get("reason")
            in {"v3_web_remaining", "v3_period_grant", "v3_daily_grant", "v3_pack"}
        ]
        results.append(f"C07_tx {email} status={st} n={len(items_tx)} marks={leftover[:10]}")

    status, spent = req("GET", "/api/v1/admin/user-spend?page=1&page_size=20", token=token)
    spent_data = unwrap(spent) if isinstance(spent, dict) else {}
    if status >= 400:
        results.append("C09_user_spend_ERR " + json.dumps(spent, default=str)[:1200])
    else:
        spent_items = spent_data.get("items") if isinstance(spent_data, dict) else []
        results.append(
            "C09_user_spend "
            + json.dumps(
                {
                    "status": status,
                    "total": spent_data.get("total") if isinstance(spent_data, dict) else None,
                    "sample": [
                        {
                            "email": i.get("user_email") or i.get("email"),
                            "plan_name": i.get("plan_name"),
                            "wallet_charged": i.get("wallet_charged") or i.get("wallet_spent"),
                            "alerts": i.get("alerts"),
                        }
                        for i in (spent_items or [])[:6]
                        if isinstance(i, dict)
                    ],
                },
                default=str,
            )
        )

    status, v2 = req("GET", "/api/v1/v2/credits/balance", token=token)
    results.append(f"admin_v2_balance status={status} data={unwrap(v2) if status < 500 else 'err'}")

    print("WALLET_AUDIT_API")
    for line in results:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
