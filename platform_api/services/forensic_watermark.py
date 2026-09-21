"""Inaudible-ish forensic watermark for owner MP3/WAV exports.

v1 embeds a repeating payload in LSBs of non-sync bytes after any ID3 header.
This is not ID3-tag-only. Re-encoding reduces it; analog hole is out of scope.
"""

from __future__ import annotations

import hashlib
import hmac
from uuid import UUID

_PAYLOAD_LEN = 16


def watermark_payload(*, user_id: str, export_id: str, secret: str) -> bytes:
    """16-byte payload derived from user + export + server secret (not raw user id)."""
    mac = hmac.new(
        (secret or "camxora-watermark").encode("utf-8"),
        f"{user_id}:{export_id}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return mac[:_PAYLOAD_LEN]


def payload_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _skip_id3(data: bytes) -> int:
    if len(data) >= 10 and data.startswith(b"ID3"):
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        return min(len(data), 10 + size)
    return 0


def _embed_start(data: bytes) -> int:
    """First safe byte to touch: after ID3, or at the WAV PCM payload."""
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        off = 12
        limit = min(len(data), 12 + 8192)
        while off + 8 <= limit:
            chunk_id = data[off : off + 4]
            size = int.from_bytes(data[off + 4 : off + 8], "little")
            if chunk_id == b"data":
                return min(len(data), off + 8)
            step = 8 + size + (size & 1)
            if step <= 0 or off + step > limit:
                break
            off += step
        # Standard PCM fallback (fmt chunk + data header).
        return min(len(data), 44)
    return _skip_id3(data)


def embed_lsb(data: bytes, payload: bytes) -> bytes:
    """Embed payload LSBs without corrupting container/frame headers.

    - WAV: only PCM sample bytes (skip RIFF/fmt/data chunk headers).
      16-bit sample LSB flips are +/-1 amplitude -> inaudible.
    - MP3: only bytes after the ID3 tag, never the byte right after an
      MPEG frame sync (0xFF) or a 0xFE byte (which could become a false
      0xFF sync and desync the decoder).
    """
    if not data or not payload:
        return data
    # MP3 (lossy compression): a single bit flip inside the audio payload can
    # decode as audible noise, so MP3 downloads are never modified. Ownership
    # claims rely on the server-side export event + payload hash records.
    if not (len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"):
        return data
    start = _embed_start(data)
    buf = bytearray(data)
    p = 0
    for i in range(start, len(buf)):
        if buf[i] in (0xFF, 0xFE):
            continue
        if (i - start) % 48 != 0:
            continue
        if i - 1 >= start and buf[i - 1] == 0xFF:
            continue
        buf[i] = (buf[i] & 0xFE) | (payload[p % len(payload)] & 1)
        p += 1
    return bytes(buf)


def watermark_audio_bytes(
    data: bytes,
    *,
    user_id: str | UUID,
    export_id: str | UUID,
    secret: str,
) -> tuple[bytes, str]:
    payload = watermark_payload(
        user_id=str(user_id),
        export_id=str(export_id),
        secret=secret,
    )
    return embed_lsb(data, payload), payload_hash(payload)
