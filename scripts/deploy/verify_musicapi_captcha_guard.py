#!/usr/bin/env python3
"""Verify the musicapi guards are live in production.

Read-only: never restarts a service, never touches the database, and never
submits a Suno generation (so no user credits are spent and no song rows are
created).

Checks:
  1. musicapi /health answers 200
  2. camxora-musicapi is active
  3. deployed dist/ carries the solve gate and the capacity classifier
  4. TWOCAPTCHA_* knobs resolve (defaults 2 / 2000ms are fine)
  5. media storage (B2) is configured - finished songs need a durable URL
  6. --solve: run ONE real 2Captcha Turnstile solve on the VPS, using the
     effective key the running service resolves (app_settings over .env).
     Costs roughly $0.003 of 2Captcha balance - never user credits.

Usage:
    python scripts/deploy/verify_musicapi_captcha_guard.py
    python scripts/deploy/verify_musicapi_captcha_guard.py --solve
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

HEALTH_URL = "https://musicapi.camxora.com/health"
REMOTE_REPO = "/opt/camxora/repo/musicapi"
REMOTE_ENV = f"{REMOTE_REPO}/.env"

# Runs inside the deployed tree so it resolves the SAME key the service uses
# (runtime settings / app_settings win over .env). Prints one line, never the key.
SOLVE_PROBE_JS = """
const {loadRuntimeSettings} = require("./dist/runtimeSettings.js");
const {config} = require("./dist/config.js");
const {Solver} = require("@2captcha/captcha-solver");
(async () => {
  await loadRuntimeSettings();
  const key = config.twoCaptchaKey || "";
  if (!key) { console.log("NO_KEY"); process.exit(3); }
  try {
    const solver = new Solver(key);
    const res = await solver.cloudflareTurnstile({
      sitekey: config.turnstileSitekey,
      pageurl: config.turnstilePageUrl,
    });
    const token = res && res.data;
    if (!token) { console.log("NO_TOKEN"); process.exit(4); }
    console.log("OK len=" + token.length);
  } catch (e) {
    console.log("ERR " + ((e && (e.err || e.message)) || e));
    process.exit(5);
  }
})();
"""


class CheckFailed(Exception):
    """A verification step failed; the message is the reported reason."""


def _ssh_client(env: str):
    secrets = load_secrets(env)  # type: ignore[arg-type]
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets.get("VPS_HOST", "")
    user = secrets.get("PRODUCTION_VPS_USER") or secrets.get("VPS_USER", "root")
    custom_key = secrets.get("PRODUCTION_VPS_SSH_KEY") or secrets.get("VPS_SSH_KEY")
    if not host:
        raise CheckFailed("PRODUCTION_VPS_HOST/VPS_HOST missing from deploy secrets")
    key_path = Path(custom_key) if custom_key else ensure_deploy_key()
    return ssh_connect(host, user, key_path, secrets.get("VPS_PASSWORD") or None), host


def _run(client, command: str, timeout: float = 60.0) -> str:
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return out or err


def check_health() -> str:
    try:
        with urllib.request.urlopen(  # noqa: S310 - fixed host
            urllib.request.Request(
                HEALTH_URL, headers={"User-Agent": "camxora-captcha-guard-verify/1.0"}
            ),
            timeout=20,
        ) as response:
            status = response.status
            body = response.read(500).decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise CheckFailed(f"{HEALTH_URL} unreachable: {exc}") from exc
    if status != 200:
        raise CheckFailed(f"{HEALTH_URL} returned HTTP {status}")
    return f"HTTP {status} {body[:120]}"


def check_service(client) -> str:
    state = _run(client, "systemctl is-active camxora-musicapi")
    if state != "active":
        raise CheckFailed(f"camxora-musicapi is '{state or 'unknown'}', expected 'active'")
    since = _run(client, "systemctl show camxora-musicapi -p ActiveEnterTimestamp --value")
    return f"active since {since}"


def check_build_markers(client) -> str:
    markers = {
        "CaptchaUnavailableError": f"grep -c CaptchaUnavailableError {REMOTE_REPO}/dist/captcha.js",
        "SolveSemaphore": f"grep -c SolveSemaphore {REMOTE_REPO}/dist/captcha.js",
        "isCaptchaUnavailableError": f"grep -c isCaptchaUnavailableError {REMOTE_REPO}/dist/sunoError.js",
        "captcha_capacity": f"grep -c 'no captcha solver' {REMOTE_REPO}/dist/sunoError.js",
    }
    counts: dict[str, int] = {}
    for label, command in markers.items():
        raw = _run(client, f"{command} || true")
        try:
            counts[label] = int(raw or "0")
        except ValueError:
            counts[label] = 0
    missing = [label for label, count in counts.items() if count <= 0]
    if missing:
        raise CheckFailed(
            "deployed dist/ lacks the captcha guard markers: "
            + ", ".join(missing)
            + " - musicapi was not redeployed after the fix"
        )
    return ", ".join(f"{label}x{count}" for label, count in counts.items())


def check_storage(client) -> str:
    """Durable media storage must be configured, or finished songs have no URL."""
    command = (
        f"cd {REMOTE_REPO} && node --env-file=.env -e "
        "'const{loadRuntimeSettings}=require(\"./dist/runtimeSettings.js\");"
        "const{config}=require(\"./dist/config.js\");"
        "(async()=>{await loadRuntimeSettings();"
        "console.log(JSON.stringify({bucket:(config.storage.bucket||\"\").length,"
        "keyId:(config.storage.keyId||\"\").length,"
        "applicationKey:(config.storage.applicationKey||\"\").length}));})()'"
    )
    raw = _run(client, command)
    try:
        sizes = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CheckFailed(f"storage probe returned unparsable output: {raw[:120]}") from exc
    empty = [name for name, size in sizes.items() if int(size) <= 0]
    if empty:
        raise CheckFailed(
            "media storage is not configured (empty: "
            + ", ".join(empty)
            + ") - finished songs will fail with media_storage_not_configured"
        )
    return "bucket/keyId/applicationKey all present"


def check_knobs(client) -> str:
    raw = _run(
        client,
        f"grep -E '^TWOCAPTCHA_(MAX_CONCURRENT|NOSLOT_RETRY_DELAY_MS)=' {REMOTE_ENV} || true",
    )
    values = {}
    for line in raw.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    concurrency = values.get("TWOCAPTCHA_MAX_CONCURRENT", "2 (default)")
    delay = values.get("TWOCAPTCHA_NOSLOT_RETRY_DELAY_MS", "2000 (default)")
    return f"maxConcurrent={concurrency}, noSlotRetryDelayMs={delay}"


def check_live_solve(client) -> str:
    """One real Turnstile solve using the service's effective key."""
    payload = base64.b64encode(SOLVE_PROBE_JS.encode()).decode()
    # Write the probe inside the deployed tree so relative requires and
    # node_modules resolve exactly as they do for the service.
    probe = f"{REMOTE_REPO}/camxora_captcha_probe.cjs"
    command = (
        f"printf '%s' '{payload}' | base64 -d > {probe} && "
        f"cd {REMOTE_REPO} && node --env-file=.env camxora_captcha_probe.cjs; "
        f"rc=$?; rm -f {probe}; exit $rc"
    )
    out = _run(client, command, timeout=240)
    if out.startswith("OK "):
        return f"2Captcha solved a Turnstile ({out[3:]})"
    if out.strip() == "NO_KEY":
        raise CheckFailed(
            "the service resolves no 2Captcha key (TWOCAPTCHA_KEY empty and the stored "
            "app_settings value does not decrypt) - generation will fail when Suno's gate is up"
        )
    if out.startswith("ERR "):
        reason = out[4:]
        if "NO_SLOT_AVAILABLE" in reason or "maximum capacity" in reason.lower():
            raise CheckFailed(
                "2Captcha has no free solve slot (external queue pressure, not the deploy)"
            )
        raise CheckFailed(f"2Captcha solve failed: {reason[:160]}")
    raise CheckFailed(f"unexpected probe output: {out[:160]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the musicapi 2Captcha guard")
    parser.add_argument(
        "--env",
        choices=("production", "sandbox"),
        default="production",
        help="which VPS to inspect (default: production)",
    )
    parser.add_argument(
        "--solve",
        action="store_true",
        help="also run one real 2Captcha Turnstile solve (~$0.003 of 2Captcha balance)",
    )
    args = parser.parse_args()

    client, host = _ssh_client(args.env)
    failures = 0
    try:
        steps = [
            ("health", lambda: check_health()),
            ("service", lambda: check_service(client)),
            ("deployed code", lambda: check_build_markers(client)),
            ("captcha knobs", lambda: check_knobs(client)),
            ("media storage", lambda: check_storage(client)),
        ]
        if args.solve:
            steps.append(("live solve", lambda: check_live_solve(client)))

        print(f"musicapi captcha guard verification - {args.env} ({host})")
        for name, step in steps:
            try:
                detail = step()
            except CheckFailed as exc:
                failures += 1
                print(f"  FAIL  {name}: {exc}")
            except Exception as exc:  # noqa: BLE001 - report, never crash the run
                failures += 1
                print(f"  FAIL  {name}: unexpected {exc.__class__.__name__}: {exc}")
            else:
                print(f"  PASS  {name}: {detail}")
    finally:
        client.close()

    if failures:
        print(f"FAILED: {failures} check(s)")
        return 1
    print("OK: captcha guard verified" + (" (including a live solve)" if args.solve else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
