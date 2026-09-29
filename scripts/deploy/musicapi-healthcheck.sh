#!/usr/bin/env bash
# Health probe for the CamXora Music API stack, with Telegram alerting.
#
# Driven by camxora-musicapi-healthcheck.timer (every 5 minutes). Checks the
# three systemd units and the core `/health` endpoint, and alerts only on a
# state CHANGE (healthy -> unhealthy, and the recovery) so a long outage pages
# once instead of every run. No Telegram creds configured => the probe still
# runs and still exits non-zero on failure; it just cannot alert anyone.
#
# Run standalone to test:  bash scripts/deploy/musicapi-healthcheck.sh
# Force an alert path:     PORT=1 bash scripts/deploy/musicapi-healthcheck.sh
#
# Alert creds are resolved first-non-empty-wins from:
#   1. ALERT_TELEGRAM_BOT_TOKEN / ALERT_TELEGRAM_CHAT_ID   (musicapi/.env)
#   2. PLATFORM_TELEGRAM_BOT_TOKEN / PLATFORM_TELEGRAM_CHAT_ID (platform_api/.env)
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

send_alert() {
  local text="$1"
  log "ALERT: ${text}"
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

failures=()
for unit in "${UNITS[@]}"; do
  systemctl is-active --quiet "${unit}" || failures+=("unit ${unit} is not active")
done

health="$(curl -fsS -m 10 "${HEALTH_URL}" 2>/dev/null || true)"
if [[ -z "${health}" ]]; then
  failures+=("${HEALTH_URL} did not answer")
elif [[ "${health}" != *'"ok":true'* ]]; then
  failures+=("${HEALTH_URL} returned: ${health}")
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
  echo "${state}" >"${STATE_FILE}" 2>/dev/null || log "WARN: cannot write ${STATE_FILE}"
fi

[[ "${state}" == "ok" ]]
