"""HLS packaging with AES-128 encryption for iOS Safari playback.

Creates AAC TS segments encrypted with AES-128-CBC (HLS standard).
Key is derived from the content key using HKDF.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

HLS_SEGMENT_DURATION = 10  # seconds
HLS_TARGET_BITRATE = "128k"


def derive_hls_key(content_key: bytes) -> bytes:
    """Derive a 128-bit AES key for HLS from the 256-bit content key."""
    if len(content_key) != 32:
        raise ValueError("content_key must be 32 bytes")
    return HKDF(
        algorithm=SHA256(),
        length=16,  # AES-128 requires 16-byte key
        salt=b"camxora-hls-aes128",
        info=b"hls-segment-key-v1",
    ).derive(content_key)


def generate_hls_iv(segment_number: int) -> bytes:
    """Generate initialization vector for HLS segment.
    
    HLS spec: IV is usually the segment sequence number as a 128-bit big-endian integer.
    """
    return struct.pack(">QQ", 0, segment_number)


@dataclass(frozen=True)
class HlsPackageResult:
    """Result of HLS packaging operation."""
    prefix: str  # Storage key prefix for segments (e.g., "hls/uuid/")
    segment_count: int
    total_bytes: int
    duration_seconds: float


async def package_audio_to_hls(
    mp3_bytes: bytes,
    content_key: bytes,
    *,
    storage_prefix: str,
    upload_fn: Any,
) -> HlsPackageResult:
    """Package MP3 audio into HLS AAC TS segments with AES-128 encryption.
    
    Args:
        mp3_bytes: Raw MP3 audio data
        content_key: 32-byte content key
        storage_prefix: Storage path prefix (e.g., "hls/task-uuid/ok/")
        upload_fn: Async function(key: str, data: bytes) -> None for uploading segments
    
    Returns:
        HlsPackageResult with prefix and metadata
    
    The master playlist (index.m3u8) is generated dynamically per session,
    so we only upload the TS segments here.
    """
    hls_key = derive_hls_key(content_key)
    
    with tempfile.TemporaryDirectory(prefix="camxora-hls-") as tmpdir:
        tmp_path = Path(tmpdir)
        input_mp3 = tmp_path / "input.mp3"
        key_file = tmp_path / "key.bin"
        key_info = tmp_path / "keyinfo.txt"
        output_pattern = tmp_path / "segment%d.ts"
        
        # Write input MP3
        input_mp3.write_bytes(mp3_bytes)
        
        # Write AES-128 key
        key_file.write_bytes(hls_key)
        
        # Write key info file for ffmpeg
        # Format: key_url\nkey_file_path\niv_hex
        # We'll use a placeholder URL since the actual URL is session-bound
        key_info.write_text(
            f"https://placeholder.key\n"
            f"{key_file}\n"
            f"{generate_hls_iv(0).hex()}\n"
        )
        
        # Run ffmpeg to create HLS segments
        cmd = [
            "ffmpeg",
            "-i", str(input_mp3),
            "-c:a", "aac",
            "-b:a", HLS_TARGET_BITRATE,
            "-f", "hls",
            "-hls_time", str(HLS_SEGMENT_DURATION),
            "-hls_list_size", "0",  # Keep all segments in playlist
            "-hls_segment_type", "mpegts",
            "-hls_key_info_file", str(key_info),
            "-hls_segment_filename", str(output_pattern),
            "-hls_playlist_type", "vod",
            "-y",  # Overwrite output
            str(tmp_path / "playlist.m3u8"),
        ]
        
        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")[:1000]
                raise RuntimeError(f"ffmpeg failed: {error_msg}")
                
        except FileNotFoundError:
            raise RuntimeError("ffmpeg not found. Install ffmpeg for HLS packaging.")
        
        # Read the generated playlist to get metadata
        playlist_path = tmp_path / "playlist.m3u8"
        if not playlist_path.exists():
            raise RuntimeError("ffmpeg did not generate playlist.m3u8")
        
        playlist_content = playlist_path.read_text()
        
        # Parse segment count and duration from playlist
        segment_count = 0
        total_duration = 0.0
        for line in playlist_content.splitlines():
            if line.startswith("#EXTINF:"):
                # Extract duration from #EXTINF:10.0,
                parts = line.split(":", 1)[1].split(",", 1)
                duration = float(parts[0])
                total_duration += duration
                segment_count += 1
        
        if segment_count == 0:
            raise RuntimeError("No segments generated by ffmpeg")
        
        # Upload segments to storage
        total_bytes = 0
        for i in range(segment_count):
            segment_file = tmp_path / f"segment{i}.ts"
            if not segment_file.exists():
                raise RuntimeError(f"Segment {i} not found")
            
            segment_data = segment_file.read_bytes()
            total_bytes += len(segment_data)
            
            # Upload segment
            storage_key = f"{storage_prefix}segment{i}.ts"
            await upload_fn(storage_key, segment_data)
            
            logger.info(
                "Uploaded HLS segment %d: %s (%d bytes)",
                i,
                storage_key,
                len(segment_data),
            )
        
        return HlsPackageResult(
            prefix=storage_prefix,
            segment_count=segment_count,
            total_bytes=total_bytes,
            duration_seconds=total_duration,
        )


def generate_session_m3u8(
    *,
    segment_count: int,
    segment_duration: float,
    key_url: str,
    segment_url_template: str,
) -> str:
    """Generate session-bound HLS master playlist.
    
    Args:
        segment_count: Number of TS segments
        segment_duration: Duration of each segment in seconds
        key_url: Session-bound key URL (e.g., /api/v1/web-music/licenses/hls-key/{token})
        segment_url_template: URL template for segments (e.g., /api/.../hls/{token}/segment{}.ts)
    
    Returns:
        M3U8 playlist content
    """
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        "#EXT-X-TARGETDURATION:{}".format(int(segment_duration) + 1),
        "#EXT-X-MEDIA-SEQUENCE:0",
        "#EXT-X-PLAYLIST-TYPE:VOD",
        f"#EXT-X-KEY:METHOD=AES-128,URI=\"{key_url}\",IV=0x{generate_hls_iv(0).hex()}",
    ]
    
    for i in range(segment_count):
        lines.append(f"#EXTINF:{segment_duration:.1f},")
        lines.append(segment_url_template.format(i))
    
    lines.append("#EXT-X-ENDLIST")
    return "\n".join(lines) + "\n"


async def test_hls_packaging():
    """Test HLS packaging with a small MP3."""
    # This is a minimal MP3 frame for testing
    test_mp3 = (
        b"\xff\xfb\x90\x00"  # MPEG sync + frame header
        + b"\x00" * 100  # Padding
    )
    test_key = os.urandom(32)
    
    uploaded = {}
    
    async def mock_upload(key: str, data: bytes) -> None:
        uploaded[key] = data
    
    result = await package_audio_to_hls(
        test_mp3,
        test_key,
        storage_prefix="test/hls/",
        upload_fn=mock_upload,
    )
    
    print(f"Packaged {result.segment_count} segments")
    print(f"Total: {result.total_bytes} bytes, {result.duration_seconds:.1f}s")
    print(f"Uploaded keys: {list(uploaded.keys())}")


if __name__ == "__main__":
    asyncio.run(test_hls_packaging())
