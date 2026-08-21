"""Cache CXA1 ciphertext so chunk fetches do not re-download the whole object."""

from __future__ import annotations

import pytest

from platform_api.services.audio_packager import encrypted_chunk_record, new_content_key, package_chunks
from platform_api.services.encrypted_package_cache import (
    clear_packaged_blob_cache,
    get_packaged_blob,
    packaged_blob_cache_stats,
)


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    clear_packaged_blob_cache()
    yield
    clear_packaged_blob_cache()


@pytest.mark.asyncio
async def test_packaged_blob_loader_runs_once() -> None:
    calls = {"n": 0}

    async def loader() -> bytes:
        calls["n"] += 1
        return b"CXA1-cipher"

    first = await get_packaged_blob("pkg/a", loader)
    second = await get_packaged_blob("pkg/a", loader)
    assert first == second == b"CXA1-cipher"
    assert calls["n"] == 1
    assert packaged_blob_cache_stats()["size"] == 1


def test_encrypted_chunk_record_matches_iter_index() -> None:
    key = new_content_key()
    blob = package_chunks(b"x" * 300_000, key, key_id="k")
    rec0 = encrypted_chunk_record(blob, 0)
    rec1 = encrypted_chunk_record(blob, 1)
    assert rec0 and rec1
    assert rec0 != rec1
    with pytest.raises(IndexError):
        encrypted_chunk_record(blob, 99)
