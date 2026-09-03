"""Per-clip filter pixel transforms (numpy/OpenCV), keyed by the ids in
`core/registries.py`. Port of the reference app's CSS `filter:` presets,
reimplemented as direct pixel operations since there's no browser canvas
filter pipeline here.
"""

from __future__ import annotations

from typing import Callable

import cv2
import numpy as np


def _saturation(frame: np.ndarray, mult: float) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * mult, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)


def _contrast_brightness(frame: np.ndarray, contrast: float = 1.0, brightness: float = 0.0) -> np.ndarray:
    out = frame.astype(np.float32) * contrast + brightness
    return np.clip(out, 0, 255).astype(np.uint8)


def _channel_tint(frame: np.ndarray, r: float, g: float, b: float, add: tuple[float, float, float] = (0, 0, 0)) -> np.ndarray:
    out = frame.astype(np.float32)
    out[..., 0] = out[..., 0] * r + add[0]
    out[..., 1] = out[..., 1] * g + add[1]
    out[..., 2] = out[..., 2] * b + add[2]
    return np.clip(out, 0, 255).astype(np.uint8)


def _vivid(frame: np.ndarray) -> np.ndarray:
    return _contrast_brightness(_saturation(frame, 1.55), contrast=1.15, brightness=5)


def _noir(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    gray_rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    return _contrast_brightness(gray_rgb, contrast=1.3, brightness=-12)


def _warm(frame: np.ndarray) -> np.ndarray:
    return _channel_tint(frame, 1.12, 1.02, 0.90, add=(8, 0, 0))


def _cool(frame: np.ndarray) -> np.ndarray:
    return _channel_tint(frame, 0.90, 0.98, 1.18, add=(0, 0, 6))


def _fade(frame: np.ndarray) -> np.ndarray:
    desaturated = _saturation(frame, 0.55).astype(np.float32)
    lifted = desaturated * 0.82 + 26
    return np.clip(lifted, 0, 255).astype(np.uint8)


def _dream(frame: np.ndarray) -> np.ndarray:
    soft = cv2.GaussianBlur(frame, (0, 0), sigmaX=3.2)
    blended = cv2.addWeighted(frame, 0.6, soft, 0.4, 0)
    desaturated = _saturation(blended, 0.85)
    return _contrast_brightness(desaturated, contrast=1.0, brightness=14)


def _mono_blue(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    shadow = np.array([8.0, 20.0, 42.0], dtype=np.float32)
    highlight = np.array([150.0, 215.0, 255.0], dtype=np.float32)
    out = shadow[None, None, :] + gray[..., None] * (highlight - shadow)[None, None, :]
    return np.clip(out, 0, 255).astype(np.uint8)


def _sepia(frame: np.ndarray) -> np.ndarray:
    out = frame.astype(np.float32)
    r = out[..., 0] * 0.393 + out[..., 1] * 0.769 + out[..., 2] * 0.189
    g = out[..., 0] * 0.349 + out[..., 1] * 0.686 + out[..., 2] * 0.168
    b = out[..., 0] * 0.272 + out[..., 1] * 0.534 + out[..., 2] * 0.131
    return np.clip(np.stack([r, g, b], axis=-1), 0, 255).astype(np.uint8)


def _vintage(frame: np.ndarray) -> np.ndarray:
    tinted = _channel_tint(frame, 1.08, 0.95, 0.82, add=(12, 8, 0))
    return _contrast_brightness(_saturation(tinted, 0.75), contrast=0.92, brightness=8)


def _punch(frame: np.ndarray) -> np.ndarray:
    return _contrast_brightness(_saturation(frame, 1.45), contrast=1.25, brightness=4)


def _emerald(frame: np.ndarray) -> np.ndarray:
    return _channel_tint(frame, 0.85, 1.15, 0.92, add=(0, 10, 0))


def _rose(frame: np.ndarray) -> np.ndarray:
    return _channel_tint(frame, 1.14, 0.88, 0.96, add=(10, 0, 8))


def _golden(frame: np.ndarray) -> np.ndarray:
    return _channel_tint(frame, 1.18, 1.08, 0.78, add=(12, 8, 0))


def _arctic(frame: np.ndarray) -> np.ndarray:
    cooled = _channel_tint(frame, 0.92, 0.98, 1.12, add=(8, 12, 18))
    return _contrast_brightness(cooled, contrast=1.05, brightness=16)


def _sunset(frame: np.ndarray) -> np.ndarray:
    return _channel_tint(frame, 1.22, 0.92, 1.08, add=(18, 4, 0))


def _neon(frame: np.ndarray) -> np.ndarray:
    boosted = _saturation(frame, 1.8)
    return _contrast_brightness(boosted, contrast=1.2, brightness=6)


def _matte(frame: np.ndarray) -> np.ndarray:
    return _contrast_brightness(_saturation(frame, 0.45), contrast=0.88, brightness=10)


def _bleach(frame: np.ndarray) -> np.ndarray:
    return _contrast_brightness(frame, contrast=0.75, brightness=42)


def _charcoal(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    gray_rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    return _contrast_brightness(gray_rgb, contrast=1.1, brightness=-28)


def _lavender(frame: np.ndarray) -> np.ndarray:
    return _channel_tint(frame, 1.05, 0.92, 1.14, add=(8, 0, 14))


def _citrus(frame: np.ndarray) -> np.ndarray:
    return _channel_tint(frame, 1.08, 1.18, 0.82, add=(6, 12, 0))


def _crimson(frame: np.ndarray) -> np.ndarray:
    return _channel_tint(frame, 1.28, 0.82, 0.86, add=(16, 0, 0))


def _teal(frame: np.ndarray) -> np.ndarray:
    return _channel_tint(frame, 0.82, 1.08, 1.12, add=(0, 8, 12))


def _silver(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    gray_rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    return _contrast_brightness(gray_rgb, contrast=0.95, brightness=22)


def _ink(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    shadow = np.array([12.0, 10.0, 28.0], dtype=np.float32)
    highlight = np.array([120.0, 110.0, 180.0], dtype=np.float32)
    out = shadow[None, None, :] + gray[..., None] * (highlight - shadow)[None, None, :]
    return np.clip(out, 0, 255).astype(np.uint8)


def _copper(frame: np.ndarray) -> np.ndarray:
    return _channel_tint(frame, 1.16, 0.88, 0.72, add=(14, 6, 0))


def _mist(frame: np.ndarray) -> np.ndarray:
    soft = cv2.GaussianBlur(frame, (0, 0), sigmaX=2.0)
    blended = cv2.addWeighted(frame, 0.55, soft, 0.45, 0)
    return _contrast_brightness(_saturation(blended, 0.65), contrast=0.9, brightness=18)


_IMPLEMENTATIONS: dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "vivid": _vivid,
    "noir": _noir,
    "warm": _warm,
    "cool": _cool,
    "fade": _fade,
    "dream": _dream,
    "mono-blue": _mono_blue,
    "sepia": _sepia,
    "vintage": _vintage,
    "punch": _punch,
    "emerald": _emerald,
    "rose": _rose,
    "golden": _golden,
    "arctic": _arctic,
    "sunset": _sunset,
    "neon": _neon,
    "matte": _matte,
    "bleach": _bleach,
    "charcoal": _charcoal,
    "lavender": _lavender,
    "citrus": _citrus,
    "crimson": _crimson,
    "teal": _teal,
    "silver": _silver,
    "ink": _ink,
    "copper": _copper,
    "mist": _mist,
}


def apply_filter(frame: np.ndarray, filter_id: str) -> np.ndarray:
    """Return `frame` (HxWx3 uint8 RGB) with `filter_id` applied."""
    if filter_id == "none" or filter_id not in _IMPLEMENTATIONS:
        return frame
    return _IMPLEMENTATIONS[filter_id](frame)
