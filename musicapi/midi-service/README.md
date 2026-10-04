# musicapi MIDI microservice

Localhost Basic Pitch (Spotify) audio-to-MIDI service backing the `/api/v1/midi/*`
endpoints. Suno exposes no MIDI API — it is a Studio-only feature — so we
transcribe the separated stems ourselves, exactly like sunoapi.org serves its own
`midiData`.

## Why Python 3.10

`basic-pitch` supports Python ≤3.11. On Linux + Python < 3.11 it installs the
light `tflite-runtime` (no TensorFlow); on 3.11+ it pins an old TensorFlow that
has no 3.12 wheels. We therefore run it on a self-contained Python 3.10.

## Install (on the API host)

```bash
# uv manages a standalone CPython, installed under /opt so the service user can read it
export UV_PYTHON_INSTALL_DIR=/opt/camxora/midi-service/python
curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh
uv python install 3.10

apt-get install -y libsndfile1            # soundfile/librosa
mkdir -p /opt/camxora/midi-service
uv venv --python 3.10 /opt/camxora/midi-service/.venv
V=/opt/camxora/midi-service/.venv/bin
uv pip install --python "$V/python" basic-pitch "setuptools<81" "numpy<2"
chown -R camxora:camxora /opt/camxora/midi-service
```

Notes: `setuptools<81` is required (the pinned `resampy` imports `pkg_resources`);
`numpy<2` is required by `tflite-runtime` (`_ARRAY_API` ABI).

## Run

`systemd` unit `camxora-musicapi-midi.service` starts
`server.py` on `127.0.0.1:${MIDI_PORT:-4010}` as the `camxora` user.

```bash
curl -s localhost:4010/health
curl -s -X POST localhost:4010/transcribe \
  -H 'content-type: application/json' \
  -d '{"url":"http://127.0.0.1:4003/...","name":"Vocals"}'
```
