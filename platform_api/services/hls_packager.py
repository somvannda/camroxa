"""AES-128 HLS packaging for iOS Safari native playback."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

HLS_SEGMENT_SECONDS = 6
HLS_KEY_PLACEHOLDER = "https://camxora.invalid/hls-key"
_M3U8_KEY_RE = re.compile(r'URI="([^"]*)"')
_SEGMENT_LINE_RE = re.compile(r"^[A-Za-z0-9._-]+\.(?:ts|m4s)$")


class HlsPackagerError(RuntimeError):
    """HLS packaging failed."""


@dataclass(frozen=True)
class HlsPackageArtifacts:
    files: dict[str, bytes]
    segment_names: tuple[str, ...]


def derive_hls_aes_key(content_key: bytes) -> bytes:
    if len(content_key) != 32:
        raise ValueError("content_key must be 32 bytes.")
    return HKDF(
        algorithm=SHA256(),
        length=16,
        salt=b"camxora-hls-aes128",
        info=b"v1",
    ).derive(content_key)


def derive_hls_iv(content_key: bytes) -> bytes:
    if len(content_key) != 32:
        raise ValueError("content_key must be 32 bytes.")
    return HKDF(
        algorithm=SHA256(),
        length=16,
        salt=b"camxora-hls-iv",
        info=b"v1",
    ).derive(content_key)


def rewrite_hls_playlist(
    manifest: str,
    *,
    key_url: str,
    segment_url_prefix: str,
) -> str:
    out: list[str] = []
    prefix = segment_url_prefix.rstrip("/")
    for raw in manifest.splitlines():
        line = raw.strip("\ufeff")
        if not line:
            continue
        if line.startswith("#EXT-X-KEY"):
            iv_match = re.search(r"IV=0x([0-9A-Fa-f]+)", line)
            iv_part = f",IV=0x{iv_match.group(1)}" if iv_match else ""
            out.append(f'#EXT-X-KEY:METHOD=AES-128,URI="{key_url}"{iv_part}')
            continue
        if _SEGMENT_LINE_RE.match(line):
            out.append(f"{prefix}/{line}")
            continue
        out.append(line)
    if out and not out[-1].startswith("#"):
        pass
    return "\n".join(out) + "\n"


def _ffmpeg_bin() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise HlsPackagerError("ffmpeg is not installed on this host.")
    return path


def package_hls_aes128(mp3_bytes: bytes, content_key: bytes) -> HlsPackageArtifacts:
    """Build an AES-128 HLS VOD package (AAC in MPEG-TS) from MP3 bytes."""
    if not mp3_bytes:
        raise HlsPackagerError("empty audio input.")
    aes_key = derive_hls_aes_key(content_key)
    iv = derive_hls_iv(content_key)
    iv_hex = iv.hex()

    with tempfile.TemporaryDirectory(prefix="camxora-hls-") as tmp:
        work = Path(tmp)
        input_path = work / "input.mp3"
        input_path.write_bytes(mp3_bytes)
        key_path = work / "hls.key"
        key_path.write_bytes(aes_key)
        keyinfo_path = work / "keyinfo.txt"
        keyinfo_path.write_text(
            f"{HLS_KEY_PLACEHOLDER}\n{key_path}\n{iv_hex}\n",
            encoding="utf-8",
        )
        out_m3u8 = work / "index.m3u8"
        segment_pattern = str(work / "seg%03d.ts")
        cmd = [
            _ffmpeg_bin(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-f",
            "hls",
            "-hls_time",
            str(HLS_SEGMENT_SECONDS),
            "-hls_playlist_type",
            "vod",
            "-hls_segment_filename",
            segment_pattern,
            "-hls_key_info_file",
            str(keyinfo_path),
            str(out_m3u8),
        ]
        proc = subprocess.run(cmd, capture_output=True, check=False)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace").strip()
            raise HlsPackagerError(detail or "ffmpeg HLS packaging failed.")
        if not out_m3u8.is_file():
            raise HlsPackagerError("ffmpeg did not produce index.m3u8.")

        files: dict[str, bytes] = {"index.m3u8": out_m3u8.read_bytes()}
        segment_names: list[str] = []
        for seg in sorted(work.glob("seg*.ts")):
            name = seg.name
            files[name] = seg.read_bytes()
            segment_names.append(name)
        if not segment_names:
            raise HlsPackagerError("ffmpeg produced no HLS segments.")
        return HlsPackageArtifacts(files=files, segment_names=tuple(segment_names))
