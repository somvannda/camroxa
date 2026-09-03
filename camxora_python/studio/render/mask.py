"""Feathered clip masks for compositor blits."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw

from studio.core.models import Clip
from studio.core.time_utils import clamp


def _rotate_mask(mask: np.ndarray, angle_deg: float) -> np.ndarray:
    if abs(angle_deg) < 0.01:
        return mask
    h, w = mask.shape[:2]
    center = (w / 2.0, h / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    return cv2.warpAffine(mask, matrix, (w, h), flags=cv2.INTER_LINEAR, borderValue=0.0)


def _draw_heart(draw: ImageDraw.ImageDraw, cx: float, cy: float, mw: float, mh: float) -> None:
    x1 = cx - mw / 2
    x2 = cx + mw / 2
    y1 = cy - mh / 2
    y2 = cy + mh / 2
    lobe_h = mh * 0.32
    draw.ellipse([x1, y1, cx, y1 + lobe_h * 2], fill=255)
    draw.ellipse([cx, y1, x2, y1 + lobe_h * 2], fill=255)
    draw.polygon([(x1, y1 + lobe_h), (x2, y1 + lobe_h), (cx, y2)], fill=255)


def _draw_star(draw: ImageDraw.ImageDraw, cx: float, cy: float, mw: float, mh: float) -> None:
    outer_r = min(mw, mh) * 0.5
    inner_r = outer_r * 0.42
    points: list[tuple[float, float]] = []
    for i in range(10):
        angle = np.deg2rad(-90 + i * 36)
        radius = outer_r if i % 2 == 0 else inner_r
        points.append((cx + radius * np.cos(angle), cy + radius * np.sin(angle)))
    draw.polygon(points, fill=255)


def build_clip_mask(clip: Clip, dst_w: int, dst_h: int) -> np.ndarray:
    """Return float32 HxW alpha mask in 0..1 for the resized clip tile."""
    if dst_w <= 0 or dst_h <= 0:
        return np.zeros((max(1, dst_h), max(1, dst_w)), dtype=np.float32)
    if not clip.mask_enabled:
        return np.ones((dst_h, dst_w), dtype=np.float32)

    cx = clamp(float(clip.mask_x), 0.0, 1.0) * dst_w
    cy = clamp(float(clip.mask_y), 0.0, 1.0) * dst_h
    mw = max(1.0, clamp(float(clip.mask_width), 0.05, 2.0) * dst_w)
    mh = max(1.0, clamp(float(clip.mask_height), 0.05, 2.0) * dst_h)
    shape = (clip.mask_shape or "rectangle").lower()

    x1 = int(round(cx - mw / 2))
    y1 = int(round(cy - mh / 2))
    x2 = int(round(cx + mw / 2))
    y2 = int(round(cy + mh / 2))

    mask = np.zeros((dst_h, dst_w), dtype=np.float32)

    if shape == "circle":
        cv2.ellipse(
            mask,
            (int(round(cx)), int(round(cy))),
            (int(round(mw / 2)), int(round(mh / 2))),
            0,
            0,
            360,
            1.0,
            -1,
        )
    elif shape == "split":
        pts = np.array([[x1, y1], [x2, y1], [x1, y2]], dtype=np.int32)
        cv2.fillPoly(mask, [pts], 1.0)
    elif shape == "filmstrip":
        bands = 5
        band_h = mh / bands
        for index in range(bands):
            if index % 2 == 0:
                by1 = int(round(cy - mh / 2 + index * band_h))
                by2 = int(round(cy - mh / 2 + (index + 1) * band_h))
                cv2.rectangle(mask, (x1, by1), (x2, by2), 1.0, -1)
    elif shape in ("heart", "stars"):
        pil = Image.new("L", (dst_w, dst_h), 0)
        draw = ImageDraw.Draw(pil)
        if shape == "heart":
            _draw_heart(draw, cx, cy, mw, mh)
        else:
            _draw_star(draw, cx, cy, mw, mh)
        mask = np.array(pil, dtype=np.float32) / 255.0
    else:
        radius = clamp(float(clip.mask_round_corners), 0.0, 100.0) / 100.0 * min(mw, mh) * 0.5
        if radius > 0.5:
            pil = Image.new("L", (dst_w, dst_h), 0)
            draw = ImageDraw.Draw(pil)
            draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=255)
            mask = np.array(pil, dtype=np.float32) / 255.0
        else:
            cv2.rectangle(mask, (x1, y1), (x2, y2), 1.0, -1)

    mask = _rotate_mask(mask, float(clip.mask_rotation or 0.0))

    feather_px = clamp(float(clip.mask_feather), 0.0, 100.0) / 100.0 * min(dst_w, dst_h) * 0.25
    if feather_px >= 0.5:
        k = int(max(3, round(feather_px * 2))) | 1
        mask = cv2.GaussianBlur(mask, (k, k), feather_px)

    if clip.mask_invert:
        mask = 1.0 - mask
    return np.clip(mask, 0.0, 1.0)


def apply_crop_alpha(alpha: np.ndarray, clip: Clip) -> np.ndarray:
    inset = clamp(float(clip.crop_inset or 0.0), 0.0, 0.45)
    if inset <= 0.0:
        return alpha
    src_h, src_w = alpha.shape[:2]
    dx = int(round(src_w * inset))
    dy = int(round(src_h * inset))
    x1, y1 = dx, dy
    x2, y2 = src_w - dx, src_h - dy
    if x2 <= x1 + 1 or y2 <= y1 + 1:
        return alpha
    return alpha[y1:y2, x1:x2]
