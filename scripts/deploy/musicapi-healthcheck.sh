#!/usr/bin/env bash
# Health probe for the CamXora Music API stack, with Telegram alerting.
#
# Driven by camxora-musicapi-healthcheck.timer (every 5 minutes). Checks the
# three systemd units and the core `/health` endpoint, and alerts only on a
# state CHANGE (healthy -> unhealthy, and the recovery) so a long outage pages
# once instead of every run. The `/health` probe retries for a while because the
# remote installer starts this unit right after restarting the stack, so a
# booting API must not read as an outage. No Telegram creds configured => the
# probe still runs and still exits non-zero on failure; it just cannot alert
# anyone.
#
# Run standalone to test:  bash scripts/deploy/musicapi-healthcheck.sh
# Force an alert path:     PORT=1 bash scripts/deploy/musicapi-healthcheck.sh
#
# Alert creds are resolved first-non-empty-wins from:
#   1. ALERT_TELEGRAM_BOT_TOKEN / ALERT_TELEGRAM_CHAT_ID   (musicapi/.env)
#   2. PLATFORM_TELEGRAM_BOT_TOKEN / PLATFORM_TELEGRAM_CHAT_ID (platform_api/.env)
#
# Delivery is production-only: sandbox shares the same bot/chat, so a non-prod
# host records state and exits non-zero on failure but never pages. The target is
# `MUSICAPI_ENV` (musicapi/.env) with `PLATFORM_ENVIRONMENT` (platform_api/.env)
# as the fallback already present on both hosts.
set -uo pipefail

log() { echo "[musicapi-health] $*"; }

PORT="${PORT:-${MUSICAPI_PORT:-4003}}"
HEALTH_URL="http://127.0.0.1:${PORT}/health"
STATE_FILE="${STATE_FILE:-/opt/camxora/.musicapi-health.state}"
UNITS=(camxora-musicapi camxora-musicapi-web-user camxora-musicapi-web-admin)

env_key() {
  local file="$1" key="$2"
  [[ -f "${file}" ]] || return 0
  grep -E "^${key}=" "${file}" 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '"'
}

TELEGRAM_BOT_TOKEN="${ALERT_TELEGRAM_BOT_TOKEN:-$(env_key /opt/camxora/repo/musicapi/.env ALERT_TELEGRAM_BOT_TOKEN)}"
TELEGRAM_CHAT_ID="${ALERT_TELEGRAM_CHAT_ID:-$(env_key /opt/camxora/repo/musicapi/.env ALERT_TELEGRAM_CHAT_ID)}"
[[ -n "${TELEGRAM_BOT_TOKEN}" ]] || TELEGRAM_BOT_TOKEN="$(env_key /opt/camxora/repo/platform_api/.env PLATFORM_TELEGRAM_BOT_TOKEN)"
[[ -n "${TELEGRAM_CHAT_ID}" ]] || TELEGRAM_CHAT_ID="$(env_key /opt/camxora/repo/platform_api/.env PLATFORM_TELEGRAM_CHAT_ID)"

DEPLOY_ENV="${MUSICAPI_ENV:-$(env_key /opt/camxora/repo/musicapi/.env MUSICAPI_ENV)}"
[[ -n "${DEPLOY_ENV}" ]] || DEPLOY_ENV="$(env_key /opt/camxora/repo/platform_api/.env PLATFORM_ENVIRONMENT)"
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
    --data-urlencode "disable_web_page_preview=true" >/dev/null; then
    log "alert delivered"
  else
    log "WARN: Telegram send failed"
  fi
}

# /health retry budget. The remote installer starts this unit immediately after
# a restart (camxora-musicapi-remote.sh), so give the API time to bind :4003
# before declaring it down; a genuine outage still exhausts every attempt.
HEALTH_RETRIES="${HEALTH_RETRIES:-6}"
HEALTH_RETRY_DELAY="${HEALTH_RETRY_DELAY:-5}"
[[ "${HEALTH_RETRIES}" -ge 1 ]] 2>/dev/null || HEALTH_RETRIES=1

# Probe /health, retrying transient boot failures. On success prints the body
# and returns 0; once attempts are exhausted prints a human-readable reason
# (distinguishing "no HTTP response" from a non-200 / bad body) and returns 1.
probe_health() {
  local attempt code body tmp
  tmp="$(mktemp)"
  for ((attempt = 1; attempt <= HEALTH_RETRIES; attempt++)); do
    code="$(curl -sS -m 10 -o "${tmp}" -w '%{http_code}' "${HEALTH_URL}" 2>/dev/null || true)"
    body="$(cat "${tmp}" 2>/dev/null || true)"
    if [[ "${code}" == "200" && "${body}" == *'"ok":true'* ]]; then
      rm -f "${tmp}"
      printf '%s' "${body}"
      return 0
    fi
    [[ "${attempt}" -lt "${HEALTH_RETRIES}" ]] && sleep "${HEALTH_RETRY_DELAY}"
  done
  rm -f "${tmp}"
  if [[ -z "${code}" || "${code}" == "000" ]]; then
    printf '%s did not answer after %s attempts' "${HEALTH_URL}" "${HEALTH_RETRIES}"
  else
    printf '%s returned HTTP %s: %s' "${HEALTH_URL}" "${code}" "${body:-<empty>}"
  fi
  return 1
}

# Persist the last state. Writes a sibling temp file and renames it into place:
# rename only needs write access to the directory, so a stale root-owned state
# file (the "cannot write ..." WARN) gets replaced instead of blocking the
# alert dedupe forever.
write_state() {
  local tmp="${STATE_FILE}.$$"
  if printf '%s\n' "$1" >"${tmp}" 2>/dev/null && mv -f "${tmp}" "${STATE_FILE}" 2>/dev/null; then
    return 0
  fi
  rm -f "${tmp}" 2>/dev/null || true
  return 1
}

failures=()
for unit in "${UNITS[@]}"; do
  systemctl is-active --quiet "${unit}" || failures+=("unit ${unit} is not active")
done

health=""
if ! health="$(probe_health)"; then
  failures+=("${health}")
fi

prev="$(cat "${STATE_FILE}" 2>/dev/null || echo unknown)"
if [[ "${#failures[@]}" -eq 0 ]]; then
  state="ok"
  log "healthy (${HEALTH_URL}, all units active)"
else
  state="down"
  for failure in "${failures[@]}"; do log "FAIL: ${failure}"; done
fi

if [[ "${state}" != "${prev}" ]]; then
  joined="$(printf '%s; ' "${failures[@]}")"
  if [[ "${state}" == "down" ]]; then
    send_alert "$(hostname) musicapi UNHEALTHY: ${joined}"
  elif [[ "${prev}" == "down" ]]; then
    send_alert "$(hostname) musicapi RECOVERED: health OK, all units active."
  fi
  write_state "${state}" || log "WARN: cannot write ${STATE_FILE}"
fi

[[ "${state}" == "ok" ]]
