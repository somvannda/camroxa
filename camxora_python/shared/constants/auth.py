"""Authentication feature flags for the desktop app."""

from __future__ import annotations

import os

# Public self-service registration is disabled by default. Set CAMXORA_ALLOW_REGISTRATION=true to re-enable.
REGISTRATION_ENABLED = os.environ.get("CAMXORA_ALLOW_REGISTRATION", "false").strip().lower() in {
    "1",
    "true",
    "yes",
}
