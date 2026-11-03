"""Keep a production deploy from ending with nginx serving HTTP only.

Incident: `deploy_production.py` bootstraps nginx with a minimal HTTP-only
`camxora-production` site, then conditionally applies the uploaded HTTPS config
only if `/tmp/nginx-camxora-production.conf` and the cert both exist. When that
condition was false the script printed nothing, exited 0, and left production
serving the wrong certificate for `api.` / `admin.` — the API was healthy on
127.0.0.1:8100 but unreachable over HTTPS, and the deploy reported success.

These helpers are pure text checks so the same rule can be asserted in a unit
test, in `deploy_production.py` before it reports success, and in
`apply_nginx.py` after it reloads.
"""

from __future__ import annotations

import re

# Every host the canonical production template must serve over TLS. `app.` is
# included because the bootstrap config omits it entirely.
REQUIRED_TLS_HOSTS: tuple[str, ...] = (
    "api.camxora.com",
    "camxora.com",
    "admin.camxora.com",
    "music.camxora.com",
    "app.camxora.com",
)

_SERVER_BLOCK = re.compile(r"server\s*\{")


def _blocks(conf_text: str) -> list[str]:
    """Top-level ``server { ... }`` bodies, brace-balanced.

    A regex cannot do this: the blocks contain nested ``location`` braces, and
    commented-out ``server {`` examples appear in the template.
    """
    blocks: list[str] = []
    for match in _SERVER_BLOCK.finditer(conf_text):
        start = match.end()
        depth = 1
        for index in range(start, len(conf_text)):
            char = conf_text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(conf_text[start:index])
                    break
    return blocks


def _names(body: str) -> list[str]:
    match = re.search(r"server_name\s+([^;]+);", body)
    if match is None:
        return []
    return [name.strip() for name in match.group(1).split() if name.strip()]


def missing_tls_hosts(
    conf_text: str,
    required: tuple[str, ...] = REQUIRED_TLS_HOSTS,
) -> list[str]:
    """Hosts in ``required`` with no ``listen 443`` + certificate block.

    Returns an empty list when every required host is served over TLS.
    """
    tls_hosts: set[str] = set()
    for body in _blocks(conf_text):
        if "ssl_certificate" not in body or "443" not in body:
            continue
        tls_hosts.update(_names(body))
    return [host for host in required if host not in tls_hosts]


def missing_tls_error(conf_text: str, required: tuple[str, ...] = REQUIRED_TLS_HOSTS) -> str | None:
    """Human-readable failure, or None when the config is fine."""
    missing = missing_tls_hosts(conf_text, required)
    if not missing:
        return None
    return (
        "nginx would ship without TLS for: "
        + ", ".join(missing)
        + " — refusing to finish (production would serve the wrong certificate)"
    )
