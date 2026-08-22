"""AES-256-GCM packaging for Camxora audio (at-rest original + chunked stream)."""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC_PACKAGE = b"CXA1"
MAGIC_ORIGINAL = b"CXO1"
FORMAT_VERSION = 1
CHUNK_SIZE = 256 * 1024
NONCE_LEN = 12
TAG_LEN = 16
GCM_MIME = "application/vnd.camxora.audio"
CONTENT_KEY_LEN = 32


def derive_kek(secret: str, *, salt: bytes = b"camxora-content-audio-kek") -> bytes:
    """Derive a 256-bit KEK from the deploy secret."""
    material = (secret or "").encode("utf-8")
    if not material:
        raise ValueError("CONTENT_AUDIO_KEK is empty.")
    return HKDF(
        algorithm=SHA256(),
        length=32,
        salt=salt,
        info=b"camxora-audio-kek-v1",
    ).derive(material)


def new_content_key() -> bytes:
    return os.urandom(CONTENT_KEY_LEN)


def wrap_content_key(kek: bytes, content_key: bytes) -> bytes:
    """Wrap a 32-byte content key with AES-256-GCM. Blob: nonce + ct+tag."""
    if len(content_key) != CONTENT_KEY_LEN:
        raise ValueError("content_key must be 32 bytes.")
    nonce = os.urandom(NONCE_LEN)
    token = AESGCM(kek).encrypt(nonce, content_key, b"camxora-wrap-v1")
    return nonce + token


def unwrap_content_key(kek: bytes, blob: bytes) -> bytes:
    if len(blob) < NONCE_LEN + TAG_LEN + CONTENT_KEY_LEN:
        raise ValueError("wrapped key blob is too short.")
    nonce, token = blob[:NONCE_LEN], blob[NONCE_LEN:]
    return AESGCM(kek).decrypt(nonce, token, b"camxora-wrap-v1")


def encrypt_original(plaintext: bytes, content_key: bytes) -> bytes:
    """Single-blob encrypted original. Not a valid MP3."""
    nonce = os.urandom(NONCE_LEN)
    token = AESGCM(content_key).encrypt(nonce, plaintext, b"camxora-original-v1")
    return MAGIC_ORIGINAL + bytes([FORMAT_VERSION]) + nonce + struct.pack(">I", len(token)) + token


def decrypt_original(blob: bytes, content_key: bytes) -> bytes:
    if len(blob) < 9 + NONCE_LEN or not blob.startswith(MAGIC_ORIGINAL):
        raise ValueError("not a Camxora encrypted original.")
    if blob[4] != FORMAT_VERSION:
        raise ValueError("unsupported original version.")
    nonce = blob[5 : 5 + NONCE_LEN]
    (token_len,) = struct.unpack(">I", blob[5 + NONCE_LEN : 9 + NONCE_LEN])
    token = blob[9 + NONCE_LEN : 9 + NONCE_LEN + token_len]
    if len(token) != token_len:
        raise ValueError("truncated encrypted original.")
    return AESGCM(content_key).decrypt(nonce, token, b"camxora-original-v1")


@dataclass(frozen=True)
class PackageHeader:
    chunk_size: int
    chunk_count: int
    key_id: str


def package_chunks(plaintext: bytes, content_key: bytes, *, key_id: str) -> bytes:
    """Chunked seekable container. MIME application/vnd.camxora.audio."""
    key_id_bytes = key_id.encode("utf-8")
    if len(key_id_bytes) > 65535:
        raise ValueError("key_id too long.")
    chunks = [
        plaintext[i : i + CHUNK_SIZE] for i in range(0, max(len(plaintext), 1), CHUNK_SIZE)
    ] or [b""]
    header = (
        MAGIC_PACKAGE
        + bytes([FORMAT_VERSION])
        + struct.pack(">I", CHUNK_SIZE)
        + struct.pack(">I", len(chunks))
        + struct.pack(">H", len(key_id_bytes))
        + key_id_bytes
    )
    body = bytearray()
    aes = AESGCM(content_key)
    for index, chunk in enumerate(chunks):
        nonce = os.urandom(NONCE_LEN)
        aad = f"camxora-chunk-v1:{index}".encode("ascii")
        token = aes.encrypt(nonce, chunk, aad)
        body.extend(nonce)
        body.extend(struct.pack(">I", len(token)))
        body.extend(token)
    return bytes(header + body)


def parse_package_header(blob: bytes) -> tuple[PackageHeader, int]:
    if len(blob) < 15 or not blob.startswith(MAGIC_PACKAGE):
        raise ValueError("not a Camxora audio package.")
    if blob[4] != FORMAT_VERSION:
        raise ValueError("unsupported package version.")
    chunk_size, chunk_count, key_len = struct.unpack(">IIH", blob[5:15])
    key_id = blob[15 : 15 + key_len].decode("utf-8")
    offset = 15 + key_len
    return PackageHeader(chunk_size=chunk_size, chunk_count=chunk_count, key_id=key_id), offset


def decrypt_chunk(blob: bytes, content_key: bytes, index: int) -> bytes:
    header, offset = parse_package_header(blob)
    if index < 0 or index >= header.chunk_count:
        raise ValueError("chunk index out of range.")
    aes = AESGCM(content_key)
    cursor = offset
    for current in range(header.chunk_count):
        if cursor + NONCE_LEN + 4 > len(blob):
            raise ValueError("truncated package.")
        nonce = blob[cursor : cursor + NONCE_LEN]
        cursor += NONCE_LEN
        (token_len,) = struct.unpack(">I", blob[cursor : cursor + 4])
        cursor += 4
        token = blob[cursor : cursor + token_len]
        cursor += token_len
        if current != index:
            continue
        aad = f"camxora-chunk-v1:{index}".encode("ascii")
        return aes.decrypt(nonce, token, aad)
    raise ValueError("chunk not found.")


def iter_encrypted_chunks(blob: bytes) -> list[bytes]:
    """Return each on-disk chunk record (nonce + len + token) for ranged serving."""
    header, offset = parse_package_header(blob)
    records: list[bytes] = []
    cursor = offset
    for _ in range(header.chunk_count):
        start = cursor
        if cursor + NONCE_LEN + 4 > len(blob):
            raise ValueError("truncated package.")
        cursor += NONCE_LEN
        (token_len,) = struct.unpack(">I", blob[cursor : cursor + 4])
        cursor += 4 + token_len
        records.append(blob[start:cursor])
    return records


def decrypt_package(blob: bytes, content_key: bytes) -> bytes:
    header, _ = parse_package_header(blob)
    return b"".join(decrypt_chunk(blob, content_key, i) for i in range(header.chunk_count))


def looks_like_camxora_audio(blob: bytes) -> bool:
    return blob.startswith(MAGIC_PACKAGE) or blob.startswith(MAGIC_ORIGINAL)


def ab_plaintext_variant(plaintext: bytes, *, lane: str) -> bytes:
    """Lane B flips one payload byte so A/B forensic patterns differ after decrypt."""
    if lane != "b" or len(plaintext) < 1024:
        return plaintext
    buf = bytearray(plaintext)
    buf[1023] ^= 0x01
    return bytes(buf)
