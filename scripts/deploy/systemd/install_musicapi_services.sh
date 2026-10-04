#!/usr/bin/env bash
# Install + enable the CamXora Music API systemd units (survives reboot).
#
# Prerequisite: the musicapi tree must already be deployed and built at
# ${REPO_DIR}/musicapi (core: `npm run build` -> dist/serve.js; web-user and
# web-admin: `npm run build` -> .next). Building/deploying the tree is handled
# by the musicapi deploy scripts, not by this installer.
#
# Usage (as root):  bash scripts/deploy/systemd/install_musicapi_services.sh
set -euo pipefail

log() { echo "[musicapi-systemd] $*"; }
need_root() { if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then log "Run as root (or via sudo)"; exit 1; fi; }
need_root

REPO_DIR="${REPO_DIR:-/opt/camxora/repo}"
UNIT_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DST="/etc/systemd/system"

UNITS=(
  camxora-musicapi.service
  camxora-musicapi-web-user.service
  camxora-musicapi-web-admin.service
  camxora-musicapi-midi.service
  camxora-musicapi-backup.service
  camxora-musicapi-backup.timer
  camxora-musicapi-healthcheck.service
  camxora-musicapi-healthcheck.timer
)

# Long-running services vs. scheduled timers need different enable targets.
SERVICES=(camxora-musicapi camxora-musicapi-web-user camxora-musicapi-web-admin)
TIMERS=(camxora-musicapi-backup.timer camxora-musicapi-healthcheck.timer)

log "Installing unit files into ${UNIT_DST}..."
for unit in "${UNITS[@]}"; do
  install -m 644 "${UNIT_SRC}/${unit}" "${UNIT_DST}/${unit}"
done

if [[ ! -f "${REPO_DIR}/musicapi/dist/serve.js" ]]; then
  log "WARN: ${REPO_DIR}/musicapi/dist/serve.js missing - run 'npm ci && npm run build' in ${REPO_DIR}/musicapi"
fi

systemctl daemon-reload
# `enable --now` is a no-op on an already-running unit, so a redeploy would
# silently keep serving the previous dist/serve.js. Enable for boot, then
# restart unconditionally so the new build is always the one running.
log "Enabling services (start on boot)..."
systemctl enable "${SERVICES[@]}"

# MIDI microservice is best-effort: it needs the Basic Pitch venv (provisioned
# by the deploy script). Start it when present; warn but never fail the deploy.
log "Enabling MIDI microservice..."
systemctl enable camxora-musicapi-midi.service >/dev/null 2>&1 || true
systemctl restart camxora-musicapi-midi.service 2>/dev/null \
  || log "WARN: camxora-musicapi-midi did not start (Basic Pitch venv missing?)"

log "Restarting services so the freshly built tree is what actually runs..."
systemctl restart "${SERVICES[@]}"

log "Enabling timers (backup nightly, health probe every 5 min)..."
systemctl enable --now "${TIMERS[@]}"

log "Verifying the restart picked up the current build..."
for svc in "${SERVICES[@]}"; do
  state="$(systemctl is-active "${svc}" || true)"
  if [[ "${state}" != "active" ]]; then
    log "FAIL: ${svc} is '${state}' after restart"
    exit 1
  fi
done

# Catches the exact footgun above: a process that started *before* the build
# means the deployed code is stale even though the unit reports "active".
if [[ -f "${REPO_DIR}/musicapi/dist/serve.js" ]]; then
  build_epoch="$(stat -c %Y "${REPO_DIR}/musicapi/dist/serve.js")"
  started_raw="$(systemctl show -p ActiveEnterTimestamp --value camxora-musicapi)"
  started_epoch="$(date -d "${started_raw}" +%s 2>/dev/null || echo 0)"
  if [[ "${started_epoch}" -gt 0 && "${started_epoch}" -lt "${build_epoch}" ]]; then
    log "FAIL: camxora-musicapi started at ${started_raw}, which precedes dist/serve.js (built $(date -d "@${build_epoch}" -u +%Y-%m-%dT%H:%M:%SZ)) - it is running stale code"
    exit 1
  fi
fi

log "Status:"
systemctl --no-pager --full status "${SERVICES[@]}" || true
systemctl --no-pager --full list-timers "${TIMERS[@]}" || true

log "Done. Verify after a reboot with: systemctl is-enabled ${SERVICES[*]} ${TIMERS[*]}"
