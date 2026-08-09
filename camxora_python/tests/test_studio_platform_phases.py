"""P1–P7 Studio platform phase smoke tests."""

from __future__ import annotations

from pathlib import Path

from features.studio.lib.scene_document import apply_axis_patch, blank_studio_document
from features.studio.lib.schema_validate import validate_composition_document, validate_project_document
from features.studio.plugins.loader import discover_plugins, plugin_catalog_entries
from features.studio.services.ai_designer import AiDesignerEngine
from features.studio.services.marketplace_cloud import MarketplaceCloudService
from features.studio.services.template_library import StudioTemplateLibrary
from features.studio.lib.schema_bridge import composition_to_project
from visualizer.composition_effects.camera_gpu import camera_view_offset_px
from visualizer.composition_renderer import document_to_renderer_dict


def test_p1_camera_and_overlay_bridge() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionCameraBehavior": "orbit",
            "compositionOverlayEnabled": True,
            "overlayStyle": "vhs",
            "albumEnabled": True,
            "albumManualText": "Neon Nights",
            "compositionLightingEffect": "god_rays",
        },
    )
    rendered = document_to_renderer_dict(doc, time_sec=1.5, audio_level=0.7)
    cam = rendered.get("cameraSettings") or {}
    ox, oy, zoom = camera_view_offset_px(cam, width=1920, height=1080)
    assert cam.get("behaviorId") == "orbit"
    assert abs(ox) > 0 or abs(oy) > 0 or zoom != 1.0
    assert rendered["effects"]["rgb_split"]["enabled"] is True
    assert rendered["textOverlays"]
    assert rendered["effects"]["bloom"]["enabled"] is True


def test_p3_template_library_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.studio.services.template_library.get_studio_templates_dir",
        lambda _user_id=None: tmp_path / "templates",
    )
    lib = StudioTemplateLibrary()
    doc = apply_axis_patch(blank_studio_document(name="Pack"), {"compositionSpectrumShape": "circle"})
    saved = lib.save_template(doc, name="Pack")
    loaded = lib.load_template(str(saved["templateId"]))
    assert loaded is not None
    assert loaded["composition"]["spectrum"]["shape"] == "circle"
    dup = lib.duplicate(str(saved["templateId"]))
    assert dup is not None


def test_p3_schema_validate() -> None:
    doc = blank_studio_document()
    assert validate_composition_document(doc) == []
    project = composition_to_project(doc)
    assert validate_project_document(project) == []
    assert validate_composition_document(None)


def test_p5_ai_designer_generate() -> None:
    engine = AiDesignerEngine()
    result = engine.generate("cyberpunk purple EDM festival lightning")
    assert result.document["composition"]["spectrum"]["material"] in {"neon", "carbon", "glass", "ice"}
    assert result.document["composition"]["lighting"]["effect"]
    assert "Palette=" in result.explanation
    improved = engine.improve(result.document)
    assert improved.mode == "improve"


def test_p6_plugin_discovery() -> None:
    plugins_dir = Path(__file__).resolve().parents[1] / "features" / "studio" / "plugins"
    plugins = discover_plugins(plugins_dir)
    assert any(p.id.endswith("sample-neon-spectrum") for p in plugins)
    entries = plugin_catalog_entries(plugins)
    assert any("neon" in str(e.get("name") or "").lower() or "sample" in str(e.get("id") or "") for e in entries)


def test_p7_marketplace_cloud_stub() -> None:
    svc = MarketplaceCloudService()
    listings = svc.list_marketplace()
    assert listings
    job = svc.enqueue_cloud_render(project_id="abc12345")
    assert job.status == "done"
    assert "roles" in svc.enterprise_roles()
