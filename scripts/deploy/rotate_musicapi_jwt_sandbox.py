#!/usr/bin/env python3
"""Rotate the musicapi JWT_SECRET on the sandbox VPS (REQUIREMENTS 1.8).

A fresh 48-byte hex secret is generated *on the server* and written to both:

  * the durable source ``/opt/camxora/.deploy-secrets`` (``MUSICAPI_JWT_SECRET``)
    that camxora-musicapi-remote.sh reuses on every redeploy, and
  * the generated app env ``/opt/camxora/repo/musicapi/.env`` (``JWT_SECRET``).

Both files are backed up first, the secrets file is re-sourced to prove it still
parses, and ``camxora-musicapi`` is restarted.

Rotating ``JWT_SECRET`` only invalidates existing sessions and in-flight OAuth
state (see ``src/appAuth.ts``) — users simply log in again. ``COOKIE_ENCRYPTION_KEY``
is deliberately left untouched, so encrypted Suno cookies stay readable.

Usage:
    python scripts/deploy/rotate_musicapi_jwt_sandbox.py --check   # read-only
    python scripts/deploy/rotate_musicapi_jwt_sandbox.py           # rotate

Sandbox only: ``resolve_sandbox_ssh`` refuses production hosts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    ensure_paramiko,
    load_sandbox_secrets,
    resolve_sandbox_ssh,
    ssh_connect,
)

SECRETS_FILE = "/opt/camxora/.deploy-secrets"
ENV_FILE = "/opt/camxora/repo/musicapi/.env"
SERVICE = "camxora-musicapi"
HEALTH_URL = "http://127.0.0.1:4003/health"

CHECK_REMOTE = f"""
set -euo pipefail
SECRETS_FILE="{SECRETS_FILE}"
ENV_FILE="{ENV_FILE}"
for f in "$SECRETS_FILE" "$ENV_FILE"; do
  if [[ -f "$f" ]]; then
    echo "present: $f ($(stat -c '%a %U:%G' "$f"), $(wc -l <"$f") lines)"
  else
    echo "MISSING: $f"
  fi
done
echo "MUSICAPI_JWT_SECRET in secrets: $(grep -c '^MUSICAPI_JWT_SECRET=' "$SECRETS_FILE" || true)"
echo "JWT_SECRET in app env:         $(grep -c '^JWT_SECRET=' "$ENV_FILE" || true)"
echo "secrets keys: $(grep -oE '^[A-Z_]+=' "$SECRETS_FILE" | tr -d '=' | sort | tr '\\n' ' ')"
echo "service: $(systemctl is-active {SERVICE} || true)"
curl -s -o /dev/null -w 'core /health -> %{{http_code}}\\n' {HEALTH_URL} || echo 'core /health unreachable'
"""

ROTATE_REMOTE = f"""
set -euo pipefail
SECRETS_FILE="{SECRETS_FILE}"
ENV_FILE="{ENV_FILE}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

[[ -f "$SECRETS_FILE" && -f "$ENV_FILE" ]] || {{ echo "missing secrets/env file"; exit 1; }}

cp -a "$SECRETS_FILE" "$SECRETS_FILE.bak.$TS"
cp -a "$ENV_FILE" "$ENV_FILE.bak.$TS"
echo "backups: $SECRETS_FILE.bak.$TS , $ENV_FILE.bak.$TS"

NEW_SECRET="$(openssl rand -hex 48)"

python3 - "$SECRETS_FILE" "$NEW_SECRET" <<'PY'
import pathlib, sys
path, val = sys.argv[1], sys.argv[2]
p = pathlib.Path(path)
key = "MUSICAPI_JWT_SECRET="
lines = p.read_text().splitlines()
out = [key + val if ln.startswith(key) else ln for ln in lines]
if not any(ln.startswith(key) for ln in lines):
    out.append(key + val)
p.write_text("\\n".join(out) + "\\n")
PY

python3 - "$ENV_FILE" "$NEW_SECRET" <<'PY'
import pathlib, sys
path, val = sys.argv[1], sys.argv[2]
p = pathlib.Path(path)
key = "JWT_SECRET="
lines = p.read_text().splitlines()
out = [key + val if ln.startswith(key) else ln for ln in lines]
if not any(ln.startswith(key) for ln in lines):
    out.append(key + val)
p.write_text("\\n".join(out) + "\\n")
PY

chmod 600 "$ENV_FILE"; chown camxora:camxora "$ENV_FILE"
chmod 600 "$SECRETS_FILE"; chown root:root "$SECRETS_FILE" 2>/dev/null || true

if ! bash -c "set -e; source '$SECRETS_FILE'" >/dev/null 2>&1; then
  echo "VALIDATION FAILED: secrets file no longer parses - restoring backups"
  cp -a "$SECRETS_FILE.bak.$TS" "$SECRETS_FILE"
  cp -a "$ENV_FILE.bak.$TS" "$ENV_FILE"
  exit 1
fi
echo "secrets-source-ok"
grep -q '^MUSICAPI_JWT_SECRET=' "$SECRETS_FILE" && echo secrets-line-ok
grep -q '^JWT_SECRET=' "$ENV_FILE" && echo env-line-ok
echo "new secret hex length: $(awk -F= '/^MUSICAPI_JWT_SECRET=/{{print length($2)}}' "$SECRETS_FILE")"

systemctl restart {SERVICE}
for _ in $(seq 1 25); do
  if curl -sf -o /dev/null {HEALTH_URL}; then break; fi
  sleep 1
done
curl -s -o /dev/null -w 'core /health -> %{{http_code}}\\n' {HEALTH_URL}
echo "service: $(systemctl is-active {SERVICE} || true)"
echo JWT_ROTATED
"""


def run(client, remote: str) -> int:
    _, stdout, stderr = client.exec_command(remote)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    sys.stdout.write(out)
    if err.strip():
        sys.stderr.write(err)
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="Rotate the musicapi JWT_SECRET on the sandbox VPS")
    parser.add_argument("--check", action="store_true", help="Report current state only; make no changes")
    args = parser.parse_args()

    ensure_paramiko()
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Sandbox host: {user}@{host}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        if args.check:
            return run(client, CHECK_REMOTE)
        print("Rotating musicapi JWT_SECRET (backup -> rewrite both files -> restart)...")
        code = run(client, ROTATE_REMOTE)
    finally:
        client.close()

    if code == 0:
        print("\nDone. Existing sessions are now invalid; users must log in again.")
    else:
        print(f"\nRotation FAILED (exit {code}). Restore from {SECRETS_FILE}.bak.* / {ENV_FILE}.bak.*")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
