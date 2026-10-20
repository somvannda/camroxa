"""Unit tests for AES-256-GCM audio packager and watermark."""

from uuid import uuid4

import pytest

from platform_api.services.audio_packager import (
    MAGIC_ORIGINAL,
    MAGIC_PACKAGE,
    ab_plaintext_variant,
    decrypt_chunk,
    decrypt_original,
    decrypt_package,
    derive_kek,
    encrypt_original,
    looks_like_camxora_audio,
    new_content_key,
    package_chunks,
    parse_package_header,
    unwrap_content_key,
    wrap_content_key,
)
from platform_api.services.forensic_watermark import (
    embed_lsb,
    payload_hash,
    watermark_audio_bytes,
    watermark_payload,
)


def test_package_round_trip_and_seek() -> None:
    key = new_content_key()
    plaintext = b"ID3" + b"\x00" * 200 + (b"mpeg-fake-audio-" * 20000)
    key_id = str(uuid4())
    blob = package_chunks(plaintext, key, key_id=key_id)
    assert blob.startswith(MAGIC_PACKAGE)
    assert looks_like_camxora_audio(blob)
    header, _ = parse_package_header(blob)
    assert header.key_id == key_id
    assert header.chunk_count >= 1
    assert decrypt_package(blob, key) == plaintext
    first = decrypt_chunk(blob, key, 0)
    assert plaintext.startswith(first)


def test_encrypted_original_covers_wav_and_lrc() -> None:
    key = new_content_key()
    wav = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"data" + b"\x00" * 64
    lrc = b"[00:00.00]hello\n[00:01.00]world\n"
    for plain in (wav, lrc):
        blob = encrypt_original(plain, key)
        assert looks_like_camxora_audio(blob)
        assert blob.startswith(MAGIC_ORIGINAL)
        assert not blob.startswith(plain[:4])
        assert decrypt_original(blob, key) == plain


def test_encrypted_original_is_not_mpeg() -> None:
    key = new_content_key()
    mp3 = b"ID3\x04\x00\x00" + b"\x00" * 20 + b"\xff\xfb" + b"frames" * 50
    blob = encrypt_original(mp3, key)
    assert blob.startswith(MAGIC_ORIGINAL)
    assert not blob.startswith(b"ID3")
    assert decrypt_original(blob, key) == mp3


def test_wrap_unwrap_content_key() -> None:
    kek = derive_kek("unit-test-secret")
    content = new_content_key()
    wrapped = wrap_content_key(kek, content)
    assert unwrap_content_key(kek, wrapped) == content


def test_ab_variant_differs() -> None:
    data = b"x" * 2048
    assert ab_plaintext_variant(data, lane="a") == data
    assert ab_plaintext_variant(data, lane="b") != data


def test_watermark_leaves_mp3_unchanged_and_hash_is_stable() -> None:
    mp3 = b"ID3\x04\x00\x00" + bytes([0, 0, 0, 30]) + b"\x00" * 30 + b"\x40" * 4000
    marked, digest = watermark_audio_bytes(
        mp3, user_id="user-1", export_id="export-1", secret="sekrit"
    )
    # MP3 is lossy: never modified. Ownership relies on server-side records.
    assert marked == mp3
    payload = watermark_payload(user_id="user-1", export_id="export-1", secret="sekrit")
    assert payload_hash(payload) == digest
    assert embed_lsb(mp3, payload) == marked


def test_watermark_changes_wav_bytes() -> None:
    samples = bytes(range(256)) * 40
    wav = (
        b"RIFF"
        + (36 + len(samples)).to_bytes(4, "little")
        + b"WAVE"
        + b"fmt "
        + (16).to_bytes(4, "little")
        + b"\x00" * 16
        + b"data"
        + len(samples).to_bytes(4, "little")
        + samples
    )
    marked, digest = watermark_audio_bytes(
        wav, user_id="user-1", export_id="export-1", secret="sekrit"
    )
    assert marked != wav
    assert len(marked) == len(wav)
    payload = watermark_payload(user_id="user-1", export_id="export-1", secret="sekrit")
    assert payload_hash(payload) == digest
    assert embed_lsb(wav, payload) == marked


@pytest.mark.asyncio
async def test_package_plaintext_skips_when_already_ready() -> None:
    from platform_api.services.audio_package_service import AudioPackageService

    class _Conn:
        async def execute(self, *_a, **_k):
            return None

        async def fetchrow(self, *_a, **_k):
            return {"package_status": "ready", "packaged_storage_key": "web-music/x/ok.cxa"}

        def transaction(self):
            class _Tx:
                async def __aenter__(self):
                    return None

                async def __aexit__(self, *_a):
                    return False

            return _Tx()

    class _Acquire:
        async def __aenter__(self):
            return _Conn()

        async def __aexit__(self, *_a):
            return False

    class _Pool:
        def acquire(self):
            return _Acquire()

    service = AudioPackageService(_Pool())
    result = await service.package_plaintext(
        b"ID3" + b"\x00" * 32,
        subject_type="suno_task",
        subject_id=uuid4(),
        variant="ok",
        base_key="web-music/x/ok",
        storage=object(),
    )
    assert result["status"] == "ready"
    assert result["skipped"] is True
