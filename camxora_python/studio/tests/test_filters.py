import numpy as np
import pytest

from studio.core.models import FILTER_IDS
from studio.render.filters import apply_filter


@pytest.fixture
def sample_frame() -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.integers(0, 255, size=(32, 32, 3), dtype=np.uint8)


def test_none_filter_is_passthrough(sample_frame: np.ndarray):
    out = apply_filter(sample_frame, "none")
    assert out is sample_frame


def test_unknown_filter_id_is_passthrough(sample_frame: np.ndarray):
    out = apply_filter(sample_frame, "does-not-exist")
    assert np.array_equal(out, sample_frame)


@pytest.mark.parametrize("filter_id", [f for f in FILTER_IDS if f != "none"])
def test_all_registered_filters_run_and_preserve_shape_dtype(filter_id: str, sample_frame: np.ndarray):
    out = apply_filter(sample_frame, filter_id)
    assert out.shape == sample_frame.shape
    assert out.dtype == np.uint8
    assert not np.array_equal(out, sample_frame)


def test_noir_output_is_grayscale(sample_frame: np.ndarray):
    out = apply_filter(sample_frame, "noir")
    assert np.all(out[..., 0] == out[..., 1])
    assert np.all(out[..., 1] == out[..., 2])


def test_warm_increases_red_relative_to_blue():
    frame = np.full((8, 8, 3), 128, dtype=np.uint8)
    out = apply_filter(frame, "warm")
    assert out[0, 0, 0] > out[0, 0, 2]  # R > B


def test_cool_increases_blue_relative_to_red():
    frame = np.full((8, 8, 3), 128, dtype=np.uint8)
    out = apply_filter(frame, "cool")
    assert out[0, 0, 2] > out[0, 0, 0]  # B > R


def test_mono_blue_maps_shadows_and_highlights():
    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    dark_out = apply_filter(frame, "mono-blue")
    bright_out = apply_filter(np.full((4, 4, 3), 255, dtype=np.uint8), "mono-blue")
    assert dark_out[0, 0, 2] < bright_out[0, 0, 2]  # highlights bluer/brighter than shadows
