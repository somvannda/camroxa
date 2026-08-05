"""Quarantined legacy composition adapters (pre engine-v1).

These modules remain importable for older unit tests during cutover but are
**not** the render authority. Prefer ``visualizer.scene`` + ``visualizer.presets``.
"""

LEGACY_ADAPTER_NOTICE = (
    "Engine v1 hard cut: use visualizer.scene / visualizer.presets. "
    "features.video.lib.composition_* apply helpers are legacy adapters."
)
