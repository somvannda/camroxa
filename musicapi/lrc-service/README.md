# musicapi LRC microservice

Localhost lyric-alignment service backing the timestamped-lyrics endpoints
(`/me/lyrics/:id`, `/v1/lyrics/:id`,
`POST /api/v1/generate/get-timestamped-lyrics`).

Suno's **direct** API (`studio-api-prod.suno.com`) returns lyric text but no
word/line timing — the legacy `platform_api` got timings from the sunoapi.org
reseller. This service removes that dependency: it transcribes the generated
track with **faster-whisper** (word timestamps) and snaps the recognised words
onto the known lyric lines, then emits LRC. Like `musicapi/midi-service`, it
runs as a persistent localhost service so the model loads once; the Node API
calls it per clip.

## Engine note

This is ASR + monotonic sequence-matching against the known lyrics, **not**
phoneme-level forced alignment. It is CPU-friendly (`int8`) and needs no GPU.
Quality is tunable via `LRC_MODEL` (`tiny`/`base`/`small`/`medium`/`large-v3`;
default `small`). If word-level karaoke precision becomes a requirement, swap in
WhisperX wav2vec2 alignment behind the same `/align` contract.

The Node side degrades gracefully: if the service is unreachable, the endpoints
fall back to plain lyrics with an empty alignment (the pre-alignment behaviour),
so a missing sidecar never fails generation.

## Endpoints

```bash
curl -s localhost:4011/health
# {"ok":true,"model":"small","loaded":true}

curl -s -X POST localhost:4011/align \
  -H 'content-type: application/json' \
  -d '{"url":"http://127.0.0.1:4003/...","lyrics":"[Verse]\nHello world\nWe sing along"}'
# {"ok":true,"lines":[{"text":"Hello world","startS":1.0,"endS":2.2}, ...],
#  "words":[{"word":"Hello","startS":1.0,"endS":1.3}, ...],
#  "lrc":"[00:01.00]Hello world\n[00:03.00]We sing along", ...}
```

`/align` accepts JSON `{"url","lyrics"}`, JSON `{"audio_b64","lyrics"}`, or raw
audio bytes with the lyrics base64 in the `x-lyrics-b64` header.

## Install (on the API host)

```bash
# uv manages a standalone CPython under /opt so the service user can read it
bash provision.sh
```

`provision.sh` installs Python 3.11, `faster-whisper`, and pre-downloads the
model into `/opt/camxora/lrc-service/models` (set `LRC_MODEL` to change it).

## Run

`systemd` unit `camxora-musicapi-lrc.service` starts `server.py` on
`127.0.0.1:${LRC_PORT:-4011}` as the `camxora` user.

## Environment

| var | default | meaning |
|---|---|---|
| `LRC_PORT` | `4011` | listen port |
| `LRC_MODEL` | `small` | faster-whisper model size |
| `LRC_DEVICE` | `cpu` | `cpu` or `cuda` |
| `LRC_COMPUTE_TYPE` | `int8` | CTranslate2 compute type |
| `LRC_LANGUAGE` | auto | force a language (e.g. `en`) |
| `LRC_VAD` | `1` | run voice-activity detection first |
| `HF_HOME` | (system) | set to the models dir by the unit |

## Tests

`python test_align.py` — pure `snap_to_lyrics` / `interpolate_nones` / LRC
checks, no model required.
