"""Shared pytest fixtures: tiny synthetic media files for import/decode tests."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
import soundfile as sf
from PIL import Image


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    path = tmp_path / "sample.mp4"
    fps = 10
    size = (64, 48)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for i in range(fps * 2):  # 2 seconds
        frame = np.full((size[1], size[0], 3), (i * 4) % 255, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return path


@pytest.fixture
def sample_audio(tmp_path: Path) -> Path:
    path = tmp_path / "sample.wav"
    sr = 22050
    t = np.linspace(0, 1.5, int(sr * 1.5), endpoint=False)
    data = 0.2 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
    sf.write(str(path), data, sr)
    return path


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    path = tmp_path / "sample.png"
    img = Image.new("RGB", (200, 100), color=(120, 80, 200))
    img.save(path)
    return path
