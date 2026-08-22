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


def embed_lsb(data: bytes, payload: bytes) -> bytes:
    """XOR payload cycling into LSB of bytes that are not 0xFF (keeps MP3 sync)."""
    if not data or not payload:
        return data
    start = _skip_id3(data)
    buf = bytearray(data)
    p = 0
    for i in range(start, len(buf)):
        if buf[i] == 0xFF:
            continue
        if (i - start) % 48 != 0:
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
