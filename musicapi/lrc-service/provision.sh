#!/usr/bin/env bash
# Provision the faster-whisper venv for the LRC (lyric alignment) microservice.
# Idempotent: skips the heavy install when the venv already exists.
#
# Usage (as root):  bash provision.sh
set -euo pipefail

log() { echo "[lrc-provision] $*"; }

export DEBIAN_FRONTEND=noninteractive
export PATH="/usr/local/bin:$PATH"
export UV_PYTHON_INSTALL_DIR=/opt/camxora/lrc-service/python

LRC_DIR=/opt/camxora/lrc-service
VENV_PY="${LRC_DIR}/.venv/bin/python"
MODEL="${LRC_MODEL:-small}"

if [[ -x "${VENV_PY}" ]]; then
  log "venv already present at ${VENV_PY}; nothing to do."
  exit 0
fi

mkdir -p "${LRC_DIR}"

if ! command -v uv >/dev/null 2>&1; then
  log "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh
fi

log "Installing Python 3.11 under ${LRC_DIR}..."
uv python install 3.11
uv venv --python 3.11 "${LRC_DIR}/.venv"

# faster-whisper ships PyAV (bundled FFmpeg), so no system ffmpeg is required.
log "Installing faster-whisper (CTranslate2 backend, ~200MB)..."
uv pip install --python "${VENV_PY}" faster-whisper

log "Pre-downloading the '${MODEL}' model into ${LRC_DIR}/models..."
mkdir -p "${LRC_DIR}/models"
HF_HOME="${LRC_DIR}/models" "${VENV_PY}" -c \
  "from faster_whisper import WhisperModel; WhisperModel('${MODEL}', device='cpu', compute_type='int8'); print('model OK')"

chown -R camxora:camxora "${LRC_DIR}"
log "Verifying import as camxora..."
sudo -u camxora "${VENV_PY}" -c "from faster_whisper import WhisperModel; print('faster_whisper OK')"
log "Done."
