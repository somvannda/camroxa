"""Studio mirror internal token is wired through both production deploys."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_platform_deploy_forwards_and_writes_the_studio_token() -> None:
    platform_deploy = _read("scripts", "deploy", "deploy_production.py")
    platform_remote = _read("scripts", "deploy", "camxora-production-remote.sh")
    assert '"STUDIO_INTERNAL_TOKEN"' in platform_deploy
    assert "PLATFORM_STUDIO_INTERNAL_TOKEN=${STUDIO_INTERNAL_TOKEN:-}" in platform_remote


def test_musicapi_deploy_forwards_and_writes_the_studio_token() -> None:
    musicapi_deploy = _read("scripts", "deploy", "sync_musicapi_sandbox.py")
    musicapi_remote = _read("scripts", "deploy", "camxora-musicapi-remote.sh")
    assert 'export_env["STUDIO_INTERNAL_TOKEN"]' in musicapi_deploy
    assert "STUDIO_INTERNAL_TOKEN=${STUDIO_INTERNAL_TOKEN:-}" in musicapi_remote


def test_the_secrets_example_documents_the_token() -> None:
    example = _read(".deploy", "secrets.production.env.example")
    assert "STUDIO_INTERNAL_TOKEN=" in example
