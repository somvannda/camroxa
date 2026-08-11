"""Quarantined legacy composition adapters (pre engine split).

These modules remain importable for older unit tests during cutover but are
**not** the render authority for Studio. Video uses Video-local ``composition_*``
catalogs; Studio uses ``visualizer_studio.scene`` / ``visualizer_studio.presets``.
"""

LEGACY_ADAPTER_NOTICE = (
    "Engine split: Video catalogs live under features.video.lib.composition_*; "
    "Studio uses visualizer_studio.scene / visualizer_studio.presets."
)
