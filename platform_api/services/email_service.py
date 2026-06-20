"""Email service for sending verification codes and notifications.

Dev mode: MailHog at localhost:1025 (no auth).
Production: configurable SMTP via platform settings.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from threading import Lock

from platform_api.config import get_settings

logger = logging.getLogger(__name__)

_lock = Lock()


def _build_verification_email(
    code: str,
    display_name: str,
    from_name: str,
    from_address: str,
) -> MIMEMultipart:
    """Build a minimal, clean HTML verification email."""
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ margin: 0; padding: 0; background: #ffffff; font-family: 'Segoe UI', system-ui, sans-serif; }}
  .container {{ max-width: 480px; margin: 0 auto; padding: 40px 24px; }}
  .header {{ text-align: center; margin-bottom: 32px; }}
  .logo {{ font-size: 28px; font-weight: 800; color: #7466F1; letter-spacing: 2px; }}
  .subtitle {{ color: #888; font-size: 14px; margin-top: 8px; }}
  .card {{ background: #0f1629; border-radius: 16px; padding: 32px; text-align: center; border: 1px solid rgba(116,102,241,0.15); }}
  .greeting {{ color: #eef4ff; font-size: 16px; margin-bottom: 24px; }}
  .code-label {{ color: rgba(255,255,255,0.5); font-size: 12px; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px; }}
  .code {{ color: #ffffff; font-size: 36px; font-weight: 800; letter-spacing: 8px; padding: 16px 0; }}
  .divider {{ height: 1px; background: rgba(255,255,255,0.08); margin: 24px 0; }}
  .note {{ color: rgba(255,255,255,0.45); font-size: 12px; line-height: 1.6; }}
  .footer {{ text-align: center; margin-top: 32px; color: #aaa; font-size: 11px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">CAMXORA</div>
    <div class="subtitle">Music Generation Studio</div>
  </div>
  <div class="card">
    <div class="greeting">Hey {display_name},</div>
    <div class="code-label">Your verification code</div>
    <div class="code">{code}</div>
    <div class="divider"></div>
    <div class="note">
      This code expires in 15 minutes.<br>
      If you didn't create an account, you can safely ignore this email.
    </div>
  </div>
  <div class="footer">
    &copy; 2026 CAMXORA. All rights reserved.
  </div>
</div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Verify your CAMXORA account — {code}"
    msg["From"] = f"{from_name} <{from_address}>"
    msg["To"] = ""  # Set by caller
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


def send_verification_email(
    to_email: str,
    code: str,
    display_name: str = "there",
) -> bool:
    """Send a verification code email via SMTP.

    Returns True on success, False on failure.
    Thread-safe — uses a lock around SMTP operations.
    """
    settings = get_settings()
    msg = _build_verification_email(
        code=code,
        display_name=display_name,
        from_name=settings.email_from_name,
        from_address=settings.email_from_address,
    )
    msg["To"] = to_email

    with _lock:
        try:
            if settings.smtp_use_tls:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
                server.starttls()
            else:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)

            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)

            server.sendmail(
                settings.email_from_address,
                [to_email],
                msg.as_string(),
            )
            server.quit()
            logger.info("Verification email sent to %s", to_email)
            return True
        except Exception as exc:
            logger.error("Failed to send verification email to %s: %s", to_email, exc)
            return False
