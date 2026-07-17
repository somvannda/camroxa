#!/usr/bin/env python3
"""Diagnose onboarding 401 draft + billing 502 on sandbox."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

APP_API = "https://app.sandbox.camxora.com/api/v1"
DIRECT_API = "https://api.sandbox.camxora.com/api/v1"


def cookie_request(
    base: str,
    path: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    jar: CookieJar,
) -> tuple[int, str, dict[str, str]]:
    url = f"{base}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Portal-Context": "user"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    try:
        with opener.open(req, timeout=30) as resp:
            set_cookie = resp.headers.get("Set-Cookie", "")
            return resp.status, resp.read(2000).decode("utf-8", errors="replace"), {"set-cookie": set_cookie}
    except urllib.error.HTTPError as exc:
        set_cookie = exc.headers.get("Set-Cookie", "")
        return exc.code, exc.read(2000).decode("utf-8", errors="replace"), {"set-cookie": set_cookie}


def main() -> int:
    print("=== SSH: portal env + logs ===")
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    ssh_cmd = """
echo '--- user_portal .env.production ---'
cat /opt/camxora/repo/user_portal/.env.production 2>/dev/null || echo missing
echo '--- portal systemd env ---'
systemctl show camxora-portal -p Environment --no-pager
echo '--- billing provider public ---'
curl -sf https://api.sandbox.camxora.com/api/v1/billing/providers | head -c 800; echo
echo '--- recent api journal (billing/cutluy/draft) ---'
journalctl -u camxora-api -n 120 --no-pager | grep -iE 'cutluy|billing|draft|ExternalService|401' | tail -30
"""
    _, stdout, stderr = client.exec_command(ssh_cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("SSH stderr:", err)
    client.close()

    print("\n=== Cookie auth: app same-origin API ===")
    jar_app = CookieJar()
    code, body, meta = cookie_request(
        APP_API,
        "/auth/login",
        method="POST",
        body={"email": "somvannda@gmail.com", "password": "wrong-password-probe"},
        jar=jar_app,
    )
    print(f"login (wrong pw) app: {code} {body[:200]}")

    # Use admin for successful auth test
    jar_ok = CookieJar()
    for label, base in [("app", APP_API), ("api", DIRECT_API)]:
        code, body, meta = cookie_request(
            base,
            "/auth/login",
            method="POST",
            body={"email": "duke@camxora.com", "password": "Iamduke168!!@@##$$"},
            jar=jar_ok if label == "app" else CookieJar(),
        )
        jar = jar_ok if label == "app" else CookieJar()
        if label == "api":
            jar = CookieJar()
            code, body, meta = cookie_request(
                base,
                "/auth/login",
                method="POST",
                body={"email": "duke@camxora.com", "password": "Iamduke168!!@@##$$"},
                jar=jar,
            )
        print(f"\nlogin {label}: {code}")
        if code != 200:
            print(body[:300])
            continue
        me_code, me_body, _ = cookie_request(base, "/users/me", jar=jar)
        draft_code, draft_body, _ = cookie_request(base, "/channel-setup/draft", jar=jar)
        print(f"  users/me: {me_code}")
        print(f"  channel-setup/draft: {draft_code} {draft_body[:200]}")

        plans_code, plans_body, _ = cookie_request(base, "/plans/public", jar=jar)
        if plans_code == 200:
            plans = json.loads(plans_body)
            paid = [p for p in plans if p.get("effective_price_cents", 0) > 0]
            if paid:
                plan_id = paid[0]["id"]
                pay_code, pay_body, _ = cookie_request(
                    base,
                    "/billing/payments",
                    method="POST",
                    body={"plan_id": plan_id},
                    jar=jar,
                )
                print(f"  billing/payments ({paid[0].get('name')}): {pay_code}")
                print(f"    {pay_body[:400]}")
        else:
            print(f"  plans/public failed: {plans_code}")

    print("\n=== Cross-origin cookie bleed test ===")
    jar_api = CookieJar()
    cookie_request(
        DIRECT_API,
        "/auth/login",
        method="POST",
        body={"email": "duke@camxora.com", "password": "Iamduke168!!@@##$$"},
        jar=jar_api,
    )
    code_app_draft, body_app_draft, _ = cookie_request(APP_API, "/channel-setup/draft", jar=jar_api)
    print(f"login api.sandbox, draft app.sandbox: {code_app_draft} (expect 401 if cookie domain mismatch)")
    print(body_app_draft[:200])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
