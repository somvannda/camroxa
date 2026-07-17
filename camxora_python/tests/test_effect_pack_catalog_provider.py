"""Tests for effect pack catalog provider protocol."""

from __future__ import annotations

from pathlib import Path

from features.video.services.effect_pack_catalog_provider import (
    EffectPackCatalogProvider,
    LocalRegistryCatalogProvider,
)
from features.video.services.effect_pack_service import EffectPackService


def test_local_registry_catalog_provider_lists_empty_registry(tmp_path: Path) -> None:
    provider = LocalRegistryCatalogProvider(registry_root=tmp_path)
    catalog = provider.list_catalog()
    assert catalog == {"items": []}
    assert provider.get_download_url("pack", "1.0.0") is None


def test_effect_pack_service_uses_catalog_provider(tmp_path: Path) -> None:
    provider = LocalRegistryCatalogProvider(registry_root=tmp_path)
    service = EffectPackService(registry_root=tmp_path, catalog_provider=provider)
    assert isinstance(service.catalog_provider, EffectPackCatalogProvider)
    assert service.list_catalog() == {"items": []}
