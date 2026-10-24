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
from urllib.parse import quote

from platform_api.config import get_settings
from platform_api.services.email_templates import render_password_reset_email

logger = logging.getLogger(__name__)

_lock = Lock()


def _build_verification_email(
    code: str,
    display_name: str,
    from_name: str,
    from_address: str,
    activation_link: str | None = None,
) -> MIMEMultipart:
    """Build a clean verification email with an optional 24-hour link."""
    import html as _html

    safe_name = _html.escape(display_name or "there")
    link_block = ""
    if activation_link:
        safe_link = _html.escape(activation_link, quote=True)
        link_block = f"""
    <div style="margin: 24px 0 8px;">
      <a href="{safe_link}"
         style="display:inline-block;background:linear-gradient(90deg,#7466F1,#A259FF);
                color:#ffffff;text-decoration:none;padding:14px 32px;border-radius:10px;
                font-weight:700;font-size:15px;">
        Activate my account
      </a>
    </div>
    <div class="note" style="margin-top:12px;">
      This button is valid for 24 hours. You can also enter the code below.
    </div>
    """

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
  .greeting {{ color: #eef4ff; font-size: 16px; margin-bottom: 16px; }}
  .code-label {{ color: rgba(255,255,255,0.5); font-size: 12px; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px; }}
  .code {{ color: #ffffff; font-size: 34px; font-weight: 800; letter-spacing: 8px; padding: 12px 0; }}
  .divider {{ height: 1px; background: rgba(255,255,255,0.08); margin: 24px 0; }}
  .note {{ color: rgba(255,255,255,0.45); font-size: 12px; line-height: 1.6; }}
  .footer {{ text-align: center; margin-top: 32px; color: #aaa; font-size: 11px; line-height: 1.7; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">CAMXORA</div>
    <div class="subtitle">Music Generation Studio</div>
  </div>
  <div class="card">
    <div class="greeting">Hey {safe_name},</div>
    <div style="color:#c7d2fe;font-size:14px;line-height:1.6;margin-bottom:8px;">
      Thanks for joining CAMXORA Music. Confirm this email address to activate your account.
    </div>
    {link_block}
    <div class="divider"></div>
    <div class="code-label">Or use this verification code</div>
    <div class="code">{code}</div>
    <div class="note">
      The code expires in 15 minutes.<br>
      If you didn't create an account, you can safely ignore this email.
    </div>
  </div>
  <div class="footer">
    &copy; 2026 CAMXORA. All rights reserved.<br>
    Need help? Contact support@camxora.com
  </div>
</div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Activate your CAMXORA Music account"
    msg["From"] = f"{from_name} <{from_address}>"
    msg["To"] = ""  # Set by caller
    plain_link = (
        f"\nOr activate with one click (valid 24 hours):\n{activation_link}\n"
        if activation_link
        else ""
    )
    plain = (
        f"Hey {display_name},\n\n"
        "Thanks for joining CAMXORA Music. Confirm this email address to activate your account.\n"
        f"{plain_link}\n"
        f"Your verification code is: {code}\n"
        "The code expires in 15 minutes.\n\n"
        "If you didn't create an account, you can ignore this email.\n"
        "Need help? Contact support@camxora.com\n"
    )
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


def _build_activation_email(
    display_name: str,
    activation_link: str,
    from_name: str,
    from_address: str,
) -> MIMEMultipart:
    """Professional one-click activation email for the recovery campaign."""
    import html as _html

    safe_name = _html.escape(display_name or "there")
    safe_link = _html.escape(activation_link, quote=True)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ margin: 0; padding: 0; background: #ffffff; font-family: 'Segoe UI', system-ui, sans-serif; }}
  .container {{ max-width: 520px; margin: 0 auto; padding: 40px 24px; }}
  .header {{ text-align: center; margin-bottom: 28px; }}
  .logo {{ font-size: 28px; font-weight: 800; color: #7466F1; letter-spacing: 2px; }}
  .subtitle {{ color: #888; font-size: 13px; margin-top: 8px; }}
  .card {{ background: #0f1629; border-radius: 18px; padding: 36px 32px; border: 1px solid rgba(116,102,241,0.18); }}
  h1 {{ color: #ffffff; font-size: 22px; line-height: 1.3; margin: 0 0 16px; }}
  p {{ color: #c7d2fe; font-size: 14px; line-height: 1.7; margin: 0 0 16px; }}
  .button {{ display:inline-block;background:linear-gradient(90deg,#7466F1,#A259FF);
             color:#ffffff;text-decoration:none;padding:14px 34px;border-radius:10px;
             font-weight:700;font-size:15px;margin:8px 0 20px; }}
  .muted {{ color: rgba(255,255,255,0.45); font-size: 12px; line-height: 1.7; }}
  .footer {{ text-align: center; margin-top: 28px; color: #999; font-size: 11px; line-height: 1.7; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">CAMXORA</div>
    <div class="subtitle">Music Generation Studio</div>
  </div>
  <div class="card">
    <h1>Activate your CAMXORA Music account</h1>
    <p>Hi {safe_name},</p>
    <p>
      Thanks for signing up for CAMXORA Music. We noticed our verification email
      didn&rsquo;t reach you, so here is a fresh activation link.
    </p>
    <div style="text-align:center;">
      <a class="button" href="{safe_link}">Activate my account</a>
    </div>
    <p>
      This link is valid for <strong style="color:#ffffff;">24 hours</strong>. Once
      activated, sign in and start creating &mdash; your Free plan includes
      <strong style="color:#ffffff;">50 credits every month</strong>.
    </p>
    <p class="muted">
      If the button doesn&rsquo;t work, copy this link into your browser:<br>
      <span style="color:#a5b4fc;word-break:break-all;">{safe_link}</span>
    </p>
    <p class="muted">
      If you didn&rsquo;t create a CAMXORA account, you can safely ignore this email.
    </p>
  </div>
  <div class="footer">
    &copy; 2026 CAMXORA. All rights reserved.<br>
    Questions? Contact support@camxora.com
  </div>
</div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Activate your CAMXORA Music account — 50 free credits inside"
    msg["From"] = f"{from_name} <{from_address}>"
    msg["To"] = ""  # Set by caller
    plain = (
        f"Hi {display_name},\n\n"
        "Thanks for signing up for CAMXORA Music. We noticed our verification email "
        "didn't reach you, so here is a fresh activation link.\n\n"
        f"Activate your account (valid 24 hours):\n{activation_link}\n\n"
        "Your Free plan includes 50 credits every month.\n\n"
        "If you didn't create a CAMXORA account, you can ignore this email.\n"
        "Questions? Contact support@camxora.com\n"
    )
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


def _send(msg: MIMEMultipart, to_email: str) -> bool:
    """Send a prepared message via SMTP. Thread-safe. Returns success."""
    settings = get_settings()
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
            return True
        except Exception as exc:
            logger.error("Failed to send email to %s: %s", to_email, exc)
            return False


def send_verification_email(
    to_email: str,
    code: str,
    display_name: str = "there",
    *,
    activation_link: str | None = None,
) -> bool:
    """Send a verification code email (optionally with a 24-hour link).

    Returns True on success, False on failure.
    """
    settings = get_settings()
    msg = _build_verification_email(
        code=code,
        display_name=display_name,
        from_name=settings.email_from_name,
        from_address=settings.email_from_address,
        activation_link=activation_link,
    )
    ok = _send(msg, to_email)
    if ok:
        logger.info("Verification email sent to %s", to_email)
    return ok


def send_activation_email(
    to_email: str,
    activation_link: str,
    display_name: str = "there",
) -> bool:
    """Send the recovery campaign's one-click activation email."""
    settings = get_settings()
    msg = _build_activation_email(
        display_name=display_name,
        activation_link=activation_link,
        from_name=settings.email_from_name,
        from_address=settings.email_from_address,
    )
    ok = _send(msg, to_email)
    if ok:
        logger.info("Activation email sent to %s", to_email)
    return ok


def _build_password_reset_email(
    code: str,
    display_name: str,
    reset_url: str,
    account_email: str,
    from_name: str,
    from_address: str,
    logo_url: str,
    expire_minutes: int = 15,
) -> MIMEMultipart:
    """Build the branded password-reset email."""
    html = render_password_reset_email(
        code=code,
        display_name=display_name,
        reset_url=reset_url,
        account_email=account_email,
        logo_url=logo_url,
        expire_minutes=expire_minutes,
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset your CAMXORA password"
    msg["From"] = f"{from_name} <{from_address}>"
    msg["To"] = ""  # Set by caller
    plain = (
        f"Hey {display_name},\n\n"
        "We received a request to reset your CAMXORA password.\n\n"
        f"Your reset code is: {code}\n"
        f"Reset your password: {reset_url}\n\n"
        f"This code expires in {expire_minutes} minutes.\n"
        "If you didn't request this, you can safely ignore this email.\n"
        "Your password will not change until the code is used.\n"
    )
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


def send_password_reset_email(
    to_email: str,
    code: str,
    display_name: str = "there",
    reset_url: str | None = None,
) -> bool:
    """Send a branded password-reset email via SMTP."""
    settings = get_settings()
    base_url = settings.frontend_base_url.rstrip("/")
    if not reset_url:
        reset_url = f"{base_url}/reset-password?email={quote(to_email)}"
    msg = _build_password_reset_email(
        code=code,
        display_name=display_name,
        reset_url=reset_url,
        account_email=to_email,
        from_name=settings.email_from_name,
        from_address=settings.email_from_address,
        logo_url=settings.email_logo_url,
        expire_minutes=settings.email_verification_expire_minutes,
    )
    ok = _send(msg, to_email)
    if ok:
        logger.info("Password reset email sent to %s", to_email)
    return ok


def _build_renewal_reminder_email(
    *,
    display_name: str,
    plan_name: str,
    price_display: str,
    renew_url: str,
    days_left: int | None,
    from_name: str,
    from_address: str,
) -> MIMEMultipart:
    """Build a web-music renewal reminder email."""
    if days_left is None:
        when = "soon"
    elif days_left <= 0:
        when = "today"
    else:
        when = f"in {days_left} day{'s' if days_left != 1 else ''}"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#ffffff;font-family:'Segoe UI',system-ui,sans-serif;">
  <div style="max-width:480px;margin:0 auto;padding:40px 24px;">
    <div style="text-align:center;margin-bottom:32px;">
      <div style="font-size:28px;font-weight:800;color:#7466F1;letter-spacing:2px;">CAMXORA</div>
      <div style="color:#888;font-size:14px;margin-top:8px;">Music Generation Studio</div>
    </div>
    <div style="background:#0f1629;border-radius:16px;padding:32px;text-align:center;border:1px solid rgba(116,102,241,0.15);">
      <div style="color:#eef4ff;font-size:16px;margin-bottom:16px;">Hey {display_name},</div>
      <p style="color:#c7d2fe;font-size:14px;line-height:1.6;">
        Your <strong>{plan_name}</strong> plan renews {when}. Renew for {price_display} to keep
        creating music without interruption.
      </p>
      <a href="{renew_url}" style="display:inline-block;margin-top:24px;background:linear-gradient(90deg,#7466F1,#A259FF);color:#ffffff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:600;">Renew now</a>
      <div style="color:rgba(255,255,255,0.45);font-size:12px;line-height:1.6;margin-top:24px;">
        If you don't renew, your plan ends and your account returns to the Free plan.
      </div>
    </div>
    <div style="text-align:center;margin-top:32px;color:#aaa;font-size:11px;">
      &copy; 2026 CAMXORA. All rights reserved.
    </div>
  </div>
</body>
</html>"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your CAMXORA {plan_name} plan renews {when}"
    msg["From"] = f"{from_name} <{from_address}>"
    plain = (
        f"Hey {display_name},\n\n"
        f"Your {plan_name} plan renews {when}. Renew for {price_display} to keep creating.\n"
        f"Renew: {renew_url}\n\n"
        "If you don't renew, your plan ends and your account returns to the Free plan.\n"
    )
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


def send_renewal_reminder_email(
    to_email: str,
    *,
    display_name: str,
    plan_name: str,
    price_display: str,
    renew_url: str,
    days_left: int | None,
) -> bool:
    """Send a web-music renewal reminder. Returns True on success."""
    settings = get_settings()
    msg = _build_renewal_reminder_email(
        display_name=display_name,
        plan_name=plan_name,
        price_display=price_display,
        renew_url=renew_url,
        days_left=days_left,
        from_name=settings.email_from_name,
        from_address=settings.email_from_address,
    )
    ok = _send(msg, to_email)
    if ok:
        logger.info("Renewal reminder email sent to %s", to_email)
    return ok
