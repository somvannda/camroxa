"""Render the CAMXORA auth emails to reviewable HTML files.

Run from the repository root:

    python scripts/preview-auth-emails.py

The output goes to camxora.com/email-templates/. The previews are generated
from the same render functions used by the API, so layout changes cannot drift
between the preview and the real message.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from platform_api.services.email_templates import (  # noqa: E402
    render_password_reset_email,
    render_verification_email,
)

OUT_DIR = ROOT / "camxora.com" / "email-templates"
BASE_URL = os.environ.get("CAMXORA_EMAIL_PREVIEW_BASE_URL", "http://localhost:3103")
LOGO_URL = os.environ.get(
    "CAMXORA_EMAIL_PREVIEW_LOGO_URL",
    f"{BASE_URL}/email/camxora-logo.png",
)
SAMPLE_EMAIL = "somvannda1@gmail.com"
SAMPLE_NAME = "Somvannda"
SAMPLE_CODE = "482913"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    reset_url = f"{BASE_URL}/reset-password?email={quote(SAMPLE_EMAIL)}"
    verify_url = f"{BASE_URL}/verify-email?email={quote(SAMPLE_EMAIL)}"

    reset_html = render_password_reset_email(
        code=SAMPLE_CODE,
        display_name=SAMPLE_NAME,
        reset_url=reset_url,
        account_email=SAMPLE_EMAIL,
        logo_url=LOGO_URL,
    )
    verify_html = render_verification_email(
        code="731204",
        display_name=SAMPLE_NAME,
        verify_url=verify_url,
        account_email=SAMPLE_EMAIL,
        logo_url=LOGO_URL,
    )

    (OUT_DIR / "password-reset.html").write_text(reset_html, encoding="utf-8")
    (OUT_DIR / "verify-email.html").write_text(verify_html, encoding="utf-8")

    print(f"Wrote {OUT_DIR / 'password-reset.html'}")
    print(f"Wrote {OUT_DIR / 'verify-email.html'}")
    print(f"Preview base URL: {BASE_URL}")


if __name__ == "__main__":
    main()
