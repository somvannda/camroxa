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
)

log "Installing unit files into ${UNIT_DST}..."
for unit in "${UNITS[@]}"; do
  install -m 644 "${UNIT_SRC}/${unit}" "${UNIT_DST}/${unit}"
done

if [[ ! -f "${REPO_DIR}/musicapi/dist/serve.js" ]]; then
  log "WARN: ${REPO_DIR}/musicapi/dist/serve.js missing - run 'npm ci && npm run build' in ${REPO_DIR}/musicapi"
fi

systemctl daemon-reload
log "Enabling units (start on boot + start now)..."
systemctl enable --now camxora-musicapi camxora-musicapi-web-user camxora-musicapi-web-admin

log "Status:"
systemctl --no-pager --full status \
  camxora-musicapi camxora-musicapi-web-user camxora-musicapi-web-admin || true

log "Done. Verify after a reboot with: systemctl is-enabled camxora-musicapi camxora-musicapi-web-user camxora-musicapi-web-admin"
