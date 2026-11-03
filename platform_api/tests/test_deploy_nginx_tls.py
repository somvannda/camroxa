"""A production deploy must never finish with nginx serving HTTP only.

Incident this pins: `deploy_production.py` bootstrapped a minimal HTTP-only
`camxora-production` site, then applied the uploaded HTTPS config only when both
`/tmp/nginx-camxora-production.conf` and the certificate existed. When that
condition was false the run printed nothing and exited 0 — production ended up
serving the wrong certificate for `api.` and `admin.`, so the API was healthy on
127.0.0.1:8100 but unreachable over HTTPS, while the deploy reported success.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

DEPLOY_DIR = Path(__file__).resolve().parents[2] / "scripts" / "deploy"


def _load(name: str):
    path = DEPLOY_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"deploy_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return _load("nginx_guard")


def test_committed_template_covers_every_required_host(guard) -> None:
    template = (DEPLOY_DIR / "nginx-camxora-production.conf").read_text(encoding="utf-8")
    assert guard.missing_tls_hosts(template) == []
    assert guard.missing_tls_error(template) is None


def test_http_only_bootstrap_config_is_rejected(guard) -> None:
    """The exact shape the remote script leaves behind when the apply is skipped."""
    bootstrap = (
        "server { listen 80; server_name api.camxora.com; location / { proxy_pass http://127.0.0.1:8100; } }\n"
        "server { listen 80; server_name camxora.com www.camxora.com; location / { proxy_pass http://127.0.0.1:3100; } }\n"
        "server { listen 80; server_name admin.camxora.com; location / { try_files $uri /index.html; } }\n"
        "server { listen 80; server_name music.camxora.com; location / { proxy_pass http://127.0.0.1:3102; } }\n"
    )

    missing = guard.missing_tls_hosts(bootstrap)
    assert "api.camxora.com" in missing
    assert "admin.camxora.com" in missing
    assert "app.camxora.com" in missing
    assert guard.missing_tls_error(bootstrap) is not None


def test_missing_app_vhost_is_reported(guard) -> None:
    """The bootstrap config also omits app.camxora.com entirely."""
    partial = (
        "server { listen 443 ssl; server_name api.camxora.com; "
        "ssl_certificate /etc/letsencrypt/live/api.camxora.com/fullchain.pem; }\n"
        "server { listen 443 ssl; server_name admin.camxora.com; "
        "ssl_certificate /etc/letsencrypt/live/api.camxora.com/fullchain.pem; }\n"
    )

    missing = guard.missing_tls_hosts(partial)
    assert "app.camxora.com" in missing
    assert "camxora.com" in missing


def test_https_without_certificate_line_is_not_enough(guard) -> None:
    """Listening on 443 without a certificate still serves the wrong cert."""
    no_cert = "server { listen 443; server_name api.camxora.com; }\n"

    assert "api.camxora.com" in guard.missing_tls_hosts(no_cert)


def test_custom_required_hosts_are_honoured(guard) -> None:
    conf = (
        "server { listen 443 ssl; server_name example.test; "
        "ssl_certificate /etc/letsencrypt/live/example.test/fullchain.pem; }\n"
    )

    assert guard.missing_tls_hosts(conf, ("example.test",)) == []
    assert guard.missing_tls_hosts(conf, ("example.test", "other.test")) == ["other.test"]
