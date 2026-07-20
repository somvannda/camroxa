"""REQ-2.7 — Golden frame parity: preview PNG vs export PNG at fixed timestamps.

Compares ``render_preview_png()`` against ``render_export_png()`` (single-frame
export path from ``run_gpu_render``) at t=1 s and t=30 s. Requires GPU + GLFW;
skipped automatically when unavailable.

Update stored baselines::

    set CAMXORA_GOLDEN_UPDATE=1
    pytest camxora_python/tests/test_export_golden_frames.py -v
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "golden_frames"
E2E_FIXTURE_DIR = PACKAGE_ROOT / ".dbg" / "export_e2e_test" / "assets"

EXPORT_FPS = 24
ANALYSIS_FPS = 60
TEST_WIDTH = 640
TEST_HEIGHT = 360
# Normalized RMSE on 0–255 RGBA; preview vs export still differ on particle draw path.
RMSE_THRESHOLD = 18.0
# Average-hash Hamming distance (0 = identical).
PHASH_THRESHOLD = 12

TEMPLATE_CASES = ("minimal",)
TIMESTAMP_SEC = (1.0, 30.0)

PARITY_GAP_NOTES = (
    "MSAA: preview defaults to 4x; export uses 0 (REQ-1.4). Tests pass msaa_samples=0.",
    "Spectrum CPU path: preview PNG uses inline bin mapping; export uses _spectrum_fast.",
    "Particles: preview PNG uses GL_POINTS; export uses styled quads when enabled.",
    "Camera/bg shake uses wall clock unless disabled in fixture (time.time jitter).",
    "Preview PNG integrates camera shake only on the target frame; export integrates every frame.",
)


def _require_gpu() -> None:
    try:
        import glfw
    except ImportError:
        pytest.skip("glfw not installed — GPU golden tests require optional gpu deps")
    if not glfw.init():
        pytest.skip("GLFW init failed — no GPU/display context (headless CI)")
    glfw.terminate()


def _ensure_tone(path: Path, *, duration_sec: float = 45.0) -> Path:
    if path.is_file():
        return path
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 44100
    samples = int(max(1.0, duration_sec) * sample_rate)
    t = np.linspace(0.0, duration_sec, samples, endpoint=False, dtype=np.float64)
    tone = (0.25 * np.sin(2.0 * np.pi * 440.0 * t)).astype(np.float32)
    sf.write(str(path), tone, sample_rate)
    return path


def _ensure_bg_png(path: Path, *, width: int = 640, height: int = 360) -> Path:
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        arr[y, :, 0] = int(20 + (y / max(1, height - 1)) * 40)
        arr[y, :, 1] = int(10 + (y / max(1, height - 1)) * 30)
        arr[y, :, 2] = int(60 + (y / max(1, height - 1)) * 80)
    Image.fromarray(arr, mode="RGB").save(path)
    return path


def _resolve_fixture_bundle(case_id: str, tmp_path: Path) -> dict[str, Path]:
    case_dir = FIXTURES_ROOT / case_id
    e2e_template = E2E_FIXTURE_DIR / "template.json"
    e2e_bg = E2E_FIXTURE_DIR / "bg.png"
    e2e_mp3 = E2E_FIXTURE_DIR / "test_export.mp3"

    template_path = case_dir / "template.json"
    if not template_path.is_file() and e2e_template.is_file():
        template_path = e2e_template

    bg_path = case_dir / "bg.png"
    if not bg_path.is_file() and e2e_bg.is_file():
        bg_path = e2e_bg
    bg_path = _ensure_bg_png(bg_path)

    mp3_path = case_dir / "test_tone.wav"
    if e2e_mp3.is_file():
        mp3_path = e2e_mp3
    else:
        mp3_path = _ensure_tone(mp3_path, duration_sec=45.0)

    if not template_path.is_file():
        pytest.skip(f"golden fixture template missing for case {case_id!r}")

    template_dict = json.loads(template_path.read_text(encoding="utf-8"))
    if isinstance(template_dict, dict):
        template_dict = dict(template_dict)
        template_dict["background"] = str(bg_path.resolve())
        patched = tmp_path / f"{case_id}_runtime_template.json"
        patched.write_text(json.dumps(template_dict), encoding="utf-8")
        template_path = patched

    return {
        "template": template_path,
        "background": bg_path,
        "mp3": mp3_path,
    }


def _frame_indices(time_sec: float, *, export_fps: int = EXPORT_FPS, analysis_fps: int = ANALYSIS_FPS) -> tuple[int, int]:
    export_frame = int(round(float(time_sec) * float(export_fps)))
    analysis_frame = int(round(float(time_sec) * float(analysis_fps)))
    return export_frame, analysis_frame


def _load_rgba(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.array(img.convert("RGBA"), dtype=np.uint8)


def _rmse(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        raise AssertionError(f"shape mismatch: {a.shape} vs {b.shape}")
    diff = a.astype(np.float64) - b.astype(np.float64)
    return float(np.sqrt(np.mean(diff * diff)))


def _average_hash(image: np.ndarray, *, hash_size: int = 8) -> np.ndarray:
    gray = image[..., :3].mean(axis=2)
    pil = Image.fromarray(gray.astype(np.uint8), mode="L")
    small = pil.resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    pixels = np.array(small, dtype=np.float64)
    return pixels >= pixels.mean()


def _hamming(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(a != b))


def _compare_images(preview_path: Path, export_path: Path) -> tuple[float, int]:
    preview = _load_rgba(preview_path)
    export = _load_rgba(export_path)
    rmse = _rmse(preview, export)
    phash_dist = _hamming(_average_hash(preview), _average_hash(export))
    return rmse, phash_dist


def _build_gpu_options(bundle: dict[str, Path], tmp_path: Path):
    from visualizer.gpu_render import GpuOptions

    return GpuOptions(
        mp3_path=str(bundle["mp3"]),
        background_path=str(bundle["background"]),
        output_dir=str(tmp_path / "out"),
        template_path=str(bundle["template"]),
        template_b64="",
        logo_path="",
        ffmpeg_path=shutil.which("ffmpeg") or "ffmpeg",
        fps=EXPORT_FPS,
        width=TEST_WIDTH,
        height=TEST_HEIGHT,
        speed_mode="fast",
    )


def _render_pair(
    opts,
    *,
    export_frame: int,
    analysis_frame: int,
    preview_png: Path,
    export_png: Path,
) -> None:
    from visualizer.gpu_render import render_export_png, render_preview_png

    render_preview_png(
        opts,
        str(preview_png),
        preview_frame=int(analysis_frame),
        msaa_samples=0,
        analysis_fps=ANALYSIS_FPS,
    )
    render_export_png(opts, str(export_png), export_frame=int(export_frame))


@pytest.fixture(scope="module", autouse=True)
def _gpu_gate() -> None:
    _require_gpu()


@pytest.mark.gpu
@pytest.mark.parametrize("case_id", TEMPLATE_CASES)
@pytest.mark.parametrize("time_sec", TIMESTAMP_SEC)
def test_preview_export_golden_parity(case_id: str, time_sec: float, tmp_path: Path) -> None:
    bundle = _resolve_fixture_bundle(case_id, tmp_path)
    export_frame, analysis_frame = _frame_indices(time_sec)
    opts = _build_gpu_options(bundle, tmp_path)

    work = tmp_path / f"{case_id}_t{int(time_sec)}s"
    work.mkdir(parents=True, exist_ok=True)
    preview_png = work / "preview.png"
    export_png = work / "export.png"

    _render_pair(
        opts,
        export_frame=export_frame,
        analysis_frame=analysis_frame,
        preview_png=preview_png,
        export_png=export_png,
    )

    baselines = FIXTURES_ROOT / case_id / "baselines"
    tag = f"t{int(time_sec)}s"
    baseline_preview = baselines / f"{tag}_preview.png"
    baseline_export = baselines / f"{tag}_export.png"
    baseline_diff = baselines / f"{tag}_parity.json"

    if os.environ.get("CAMXORA_GOLDEN_UPDATE") == "1":
        baselines.mkdir(parents=True, exist_ok=True)
        shutil.copy2(preview_png, baseline_preview)
        shutil.copy2(export_png, baseline_export)
        rmse, phash_dist = _compare_images(preview_png, export_png)
        baseline_diff.write_text(
            json.dumps({"rmse": rmse, "phash_hamming": phash_dist}, indent=2),
            encoding="utf-8",
        )

    rmse, phash_dist = _compare_images(preview_png, export_png)
    assert rmse <= RMSE_THRESHOLD, (
        f"preview vs export RMSE {rmse:.2f} > {RMSE_THRESHOLD} at t={time_sec}s "
        f"(known gaps: {'; '.join(PARITY_GAP_NOTES)})"
    )
    assert phash_dist <= PHASH_THRESHOLD, (
        f"preview vs export phash distance {phash_dist} > {PHASH_THRESHOLD} at t={time_sec}s"
    )


def test_golden_parity_skip_reasons_documented() -> None:
    """Non-GPU sanity check: parity gap notes stay in module for release review."""
    assert PARITY_GAP_NOTES
    assert any("MSAA" in note for note in PARITY_GAP_NOTES)
