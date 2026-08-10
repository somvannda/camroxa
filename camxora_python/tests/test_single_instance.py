"""Tests for single-instance guard."""

from __future__ import annotations

import sys

import pytest
from PySide6.QtWidgets import QApplication

from shared.lib.single_instance import (
    SingleInstanceGuard,
    single_instance_server_name,
)


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def test_production_keeps_stable_server_name() -> None:
    assert single_instance_server_name("production") == (
        "Camxora.DesktopStudio.SingleInstance.v1"
    )
    assert single_instance_server_name("development") == (
        "Camxora.DesktopStudio.SingleInstance.v1"
    )


def test_sandbox_uses_distinct_server_name() -> None:
    assert single_instance_server_name("sandbox") == (
        "Camxora.DesktopStudio.SingleInstance.v1.sandbox"
    )


def test_second_guard_cannot_become_primary(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAMXORA_BUILD_ENV", "production")
    monkeypatch.setattr(
        "shared.lib.single_instance.single_instance_server_name",
        lambda build_env=None: "Camxora.DesktopStudio.SingleInstance.v1.test-primary",
    )

    first = SingleInstanceGuard(qapp)
    assert first.try_become_primary() is True

    activated = {"count": 0}

    def _on_activate() -> None:
        activated["count"] += 1

    first.set_activate_handler(_on_activate)

    second = SingleInstanceGuard(qapp)
    assert second.try_become_primary() is False

    # Local-socket signals are delivered via the Qt event loop.
    for _ in range(20):
        qapp.processEvents()
        if activated["count"] >= 1:
            break
    assert activated["count"] >= 1


def test_sandbox_and_production_can_both_be_primary(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    names = iter(
        [
            "Camxora.DesktopStudio.SingleInstance.v1.test-prod",
            "Camxora.DesktopStudio.SingleInstance.v1.test-sandbox",
        ]
    )
    monkeypatch.setattr(
        "shared.lib.single_instance.single_instance_server_name",
        lambda build_env=None: next(names),
    )

    production = SingleInstanceGuard(qapp)
    assert production.try_become_primary() is True

    sandbox = SingleInstanceGuard(qapp)
    assert sandbox.try_become_primary() is True
