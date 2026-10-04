#!/usr/bin/env bash
# Provision the Basic Pitch venv for the MIDI microservice. Idempotent: skips
# the heavy install when the venv already exists (see README.md for why Python
# 3.10 + tflite-runtime, and the setuptools/numpy pins).
#
# Usage (as root):  bash provision.sh
set -euo pipefail

log() { echo "[midi-provision] $*"; }

export DEBIAN_FRONTEND=noninteractive
export PATH="/usr/local/bin:$PATH"
export UV_PYTHON_INSTALL_DIR=/opt/camxora/midi-service/python

MIDI_DIR=/opt/camxora/midi-service
VENV_PY="${MIDI_DIR}/.venv/bin/python"

if [[ -x "${VENV_PY}" ]]; then
  log "venv already present at ${VENV_PY}; nothing to do."
  exit 0
fi

mkdir -p "${MIDI_DIR}"

if ! command -v uv >/dev/null 2>&1; then
  log "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh
fi

log "Installing libsndfile1 (soundfile/librosa)..."
apt-get install -y -qq libsndfile1 >/dev/null 2>&1 || true

log "Installing Python 3.10 under ${MIDI_DIR}..."
uv python install 3.10
uv venv --python 3.10 "${MIDI_DIR}/.venv"

log "Installing basic-pitch (tflite-runtime; ~550MB)..."
uv pip install --python "${VENV_PY}" basic-pitch "setuptools<81" "numpy<2"

chown -R camxora:camxora "${MIDI_DIR}"
log "Verifying import as camxora..."
sudo -u camxora "${VENV_PY}" -c "from basic_pitch.inference import predict; print('basic_pitch OK')"
log "Done."
