#!/usr/bin/env bash
# Platform-wide health probe with Telegram alerting.
#
# Driven by camxora-platform-healthcheck.timer (every 5 minutes). Unlike the
# musicapi-only probe, this covers the whole stack used by music.camxora.com:
# systemd units, public endpoints, database/Redis, SMTP login, recent email
# failures, disk and TLS. Alerts only on a state CHANGE (plus a daily
# "all systems OK" digest) so a long outage pages once, not every 5 minutes.
#
# Run standalone:      bash scripts/deploy/platform-healthcheck.sh
# Send today's digest: bash scripts/deploy/platform-healthcheck.sh --digest-now
set -uo pipefail

REPO="${REPO:-/opt/camxora/repo}"
ENV_FILE="${ENV_FILE:-${REPO}/platform_api/.env}"
STATE_FILE="${STATE_FILE:-/opt/camxora/.platform-health.state}"
DIGEST_FILE="${DIGEST_FILE:-/opt/camxora/.platform-health.digest}"
HEALTHCHECK_STATE="${HEALTHCHECK_STATE:-/opt/camxora/.musicapi-health.state}"

log() { echo "[platform-health] $*"; }

env_key() {
  local key="$1"
  [[ -f "${ENV_FILE}" ]] || return 0
  grep -E "^${key}=" "${ENV_FILE}" 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '"'
}

TELEGRAM_BOT_TOKEN="$(env_key PLATFORM_TELEGRAM_BOT_TOKEN)"
TELEGRAM_CHAT_ID="$(env_key PLATFORM_TELEGRAM_CHAT_ID)"
DEPLOY_ENV="$(env_key PLATFORM_ENVIRONMENT)"
DEPLOY_ENV="$(printf '%s' "${DEPLOY_ENV}" | tr '[:upper:]' '[:lower:]')"

send_alert() {
  local text="$1"
  log "ALERT: ${text}"
  if [[ "${DEPLOY_ENV}" != "production" && "${DEPLOY_ENV}" != "prod" ]]; then
    log "non-production environment (${DEPLOY_ENV:-unknown}); alert not delivered"
    return 0
  fi
  if [[ -z "${TELEGRAM_BOT_TOKEN}" || -z "${TELEGRAM_CHAT_ID}" ]]; then
    log "no Telegram creds configured; alert not delivered"
    return 0
  fi
  if curl -fsS -m 15 -X POST \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${text}" \
    --data-urlencode "parse_mode=HTML" \
    --data-urlencode "disable_web_page_preview=true" >/dev/null; then
    log "alert delivered"
  else
    log "WARN: Telegram send failed"
  fi
}

failures=()
add_failure() { failures+=("$1"); }

# --- systemd units ----------------------------------------------------------
UNITS=(camxora-api camxora-music camxora-website nginx postgresql redis-server
       camxora-musicapi camxora-musicapi-web-user camxora-musicapi-web-admin)
for unit in "${UNITS[@]}"; do
  systemctl is-active --quiet "${unit}" || add_failure "unit ${unit} is not active"
done

# --- public endpoints -------------------------------------------------------
check_url() {
  local url="$1" name="$2" code
  code="$(curl -sS -o /dev/null -w '%{http_code}' -m 20 "${url}" 2>/dev/null || true)"
  [[ "${code}" == "200" ]] || add_failure "${name} returned HTTP ${code:-no response} (${url})"
}
check_url "https://api.camxora.com/health" "api health"
check_url "https://music.camxora.com/" "music web"
check_url "https://admin.camxora.com/" "admin"
check_url "https://camxora.com/" "website"
check_url "https://musicapi.camxora.com/health" "musicapi health"

# --- database / redis -------------------------------------------------------
if command -v pg_isready >/dev/null 2>&1; then
  pg_isready -q || add_failure "postgres is not accepting connections"
fi
if command -v redis-cli >/dev/null 2>&1; then
  [[ "$(redis-cli ping 2>/dev/null)" == "PONG" ]] || add_failure "redis did not answer PONG"
fi

# --- SMTP login (the check that would have caught the Oct 15 outage) --------
SMTP_OUT="$(
  cd "${REPO}" && PYTHONPATH="${REPO}" "${REPO}/platform_api/.venv/bin/python" - <<'PY' 2>&1
import smtplib, ssl, sys
from platform_api.config import get_settings
s = get_settings()
host = (s.smtp_host or "").strip()
if not host or host.lower() in {"localhost", "127.0.0.1"}:
    print("SMTP_NOT_CONFIGURED"); sys.exit(2)
try:
    srv = smtplib.SMTP(host, s.smtp_port, timeout=12)
    if s.smtp_use_tls:
        srv.starttls(context=ssl.create_default_context())
    if s.smtp_user and s.smtp_password:
        srv.login(s.smtp_user, s.smtp_password)
    srv.quit()
    print("SMTP_OK")
except Exception as exc:
    print(f"SMTP_FAIL {type(exc).__name__}: {exc}"); sys.exit(1)
PY
)"
[[ "${SMTP_OUT}" == "SMTP_OK" ]] || add_failure "email delivery broken: ${SMTP_OUT}"

# A few transient failures are normal (typo/invalid recipients). Three or more
# in ten minutes means real breakage, not one bad address.
JOURNAL_OK=0
if journalctl -u camxora-api -n 1 --no-pager >/dev/null 2>&1; then
  JOURNAL_OK=1
fi
if [[ "${JOURNAL_OK}" == "1" ]]; then
  EMAIL_FAILS="$(journalctl -u camxora-api --since '10 min ago' --no-pager 2>/dev/null | grep -c 'Failed to send email' || true)"
  [[ "${EMAIL_FAILS:-0}" -ge 3 ]] && add_failure "${EMAIL_FAILS} email send failures in the last 10 minutes"
fi

# --- maintenance heartbeat --------------------------------------------------
if [[ -f "${HEALTHCHECK_STATE}" ]]; then
  grep -q '^ok$' "${HEALTHCHECK_STATE}" 2>/dev/null || add_failure "musicapi healthcheck state is not ok"
fi
if [[ "${JOURNAL_OK}" == "1" ]]; then
  if ! journalctl -u camxora-api --since '2 hours ago' --no-pager 2>/dev/null | grep -q 'Credit grant maintenance'; then
    add_failure "credit grant maintenance has not logged in 2 hours"
  fi
fi

# --- disk / TLS -------------------------------------------------------------
DISK_PCT="$(df -P / | awk 'NR==2 {gsub("%","",$5); print $5}')"
[[ "${DISK_PCT:-0}" -ge 90 ]] && add_failure "disk ${DISK_PCT}% used"

for host in api.camxora.com music.camxora.com admin.camxora.com musicapi.camxora.com; do
  end="$(echo | timeout 10 openssl s_client -servername "${host}" -connect "${host}:443" 2>/dev/null \
    | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
  if [[ -n "${end}" ]]; then
    days=$(( ( $(date -d "${end}" +%s) - $(date +%s) ) / 86400 ))
    [[ "${days}" -lt 14 ]] && add_failure "TLS for ${host} expires in ${days} days"
  else
    add_failure "could not read TLS expiry for ${host}"
  fi
done

# --- state + alerting -------------------------------------------------------
if [[ "${#failures[@]}" -eq 0 ]]; then
  state="ok"
  detail=""
else
  state="down"
  detail="$(printf '%s; ' "${failures[@]}")"
  for failure in "${failures[@]}"; do log "FAIL: ${failure}"; done
fi

if [[ "${state}" == "ok" ]]; then
  log "healthy: units, endpoints, DB, Redis, SMTP, email, grants, disk ${DISK_PCT}%, TLS"
fi

prev="$(cat "${STATE_FILE}" 2>/dev/null || echo unknown)"
if [[ "${state}" != "${prev}" ]]; then
  if [[ "${state}" == "down" ]]; then
    send_alert "🔴 <b>$(hostname) platform UNHEALTHY</b>"$'\n'"${detail}"
  elif [[ "${prev}" == "down" ]]; then
    send_alert "🟢 <b>$(hostname) platform RECOVERED</b>"$'\n'"All platform checks are passing."
  fi
  printf '%s\n' "${state}" >"${STATE_FILE}" 2>/dev/null || log "WARN: cannot write ${STATE_FILE}"
fi

# --- daily digest -----------------------------------------------------------
today="$(TZ='Asia/Phnom_Penh' date +%F)"
sent_day="$(cat "${DIGEST_FILE}" 2>/dev/null || true)"
if [[ "${1:-}" == "--digest-now" || "${sent_day}" != "${today}" && "$(TZ='Asia/Phnom_Penh' date +%H)" == "09" ]]; then
  if [[ "${state}" == "ok" ]]; then
    send_alert "🟢 <b>$(hostname) daily health</b>"$'\n'"All checks passing: units, public endpoints, DB, Redis, SMTP, email, grants, disk (${DISK_PCT}%), TLS."
  else
    send_alert "🟠 <b>$(hostname) daily health</b>"$'\n'"${detail}"
  fi
  printf '%s\n' "${today}" >"${DIGEST_FILE}" 2>/dev/null || true
fi

[[ "${state}" == "ok" ]]
