"""Branded, email-client-safe HTML templates for CAMXORA auth emails.

The templates deliberately use table-based layout and inline CSS. Gmail and
Outlook strip or rewrite large parts of <style>, so the visual design must not
depend on classes, flexbox, grid, or external stylesheets.

Both render functions return the exact HTML that is attached to the outgoing
message. The preview script renders the same functions with local sample data.
"""

from __future__ import annotations

from html import escape
from string import Template

DEFAULT_LOGO_URL = "https://camxora.com/email/camxora-logo.png"

# The shell is shared by every transactional auth email. Placeholders are
# substituted with already-escaped values so user display names cannot inject
# markup into the message.
_SHELL = Template(
    """<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="x-apple-disable-message-reformatting">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <title>$title</title>
  <!--[if mso]>
  <noscript>
    <xml>
      <o:OfficeDocumentSettings>
        <o:PixelsPerInch>96</o:PixelsPerInch>
      </o:OfficeDocumentSettings>
    </xml>
  </noscript>
  <![endif]-->
  <style>
    html, body { margin: 0 !important; padding: 0 !important; width: 100% !important; }
    * { -ms-text-size-adjust: 100%; -webkit-text-size-adjust: 100%; }
    table, td { mso-table-lspace: 0pt !important; mso-table-rspace: 0pt !important; border-collapse: collapse !important; }
    img { -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }
    a { text-decoration: none; }
    @media screen and (max-width: 620px) {
      .email-container { width: 100% !important; }
      .brand-padding { padding: 26px 22px 0 !important; }
      .hero-padding { padding: 18px 22px 0 !important; }
      .card-padding { padding: 22px 22px 30px !important; }
      .code-text { font-size: 32px !important; letter-spacing: 8px !important; }
    }
  </style>
</head>
<body style="margin:0;padding:0;background-color:#F4F1FA;">
  <div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;color:#F4F1FA;">
    $preheader
  </div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#F4F1FA" style="background-color:#F4F1FA;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" class="email-container" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:600px;">
          <tr>
            <td style="background-color:#0A0D1A;border:1px solid #241B3F;border-radius:20px;overflow:hidden;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#0A0D1A" style="background-color:#0A0D1A;">
                <tr>
                  <td style="height:4px;background-color:#7C3AED;font-size:0;line-height:0;">&nbsp;</td>
                </tr>
                <tr>
                  <td class="brand-padding" style="padding:30px 40px 0 40px;">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td style="padding-right:10px;">
                          <img src="$logo_url" width="40" height="40" alt="CAMXORA" style="display:block;width:40px;height:40px;border-radius:10px;">
                        </td>
                        <td style="font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:18px;font-weight:800;letter-spacing:0.18em;color:#FFFFFF;">
                          CAMXORA
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td class="hero-padding" style="padding:22px 40px 0 40px;">
                    <div style="font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#A78BFA;">
                      $eyebrow
                    </div>
                    <h1 style="margin:14px 0 0 0;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:30px;line-height:1.2;font-weight:800;letter-spacing:-0.02em;color:#FFFFFF;">
                      $title
                    </h1>
                  </td>
                </tr>
                <tr>
                  <td class="card-padding" style="padding:24px 40px 36px 40px;">
                    <p style="margin:0 0 14px 0;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:16px;line-height:1.6;color:#F7F5FF;">
                      Hey $display_name,
                    </p>
                    <p style="margin:0 0 24px 0;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:15px;line-height:1.7;color:#B9B2CE;">
                      $intro
                    </p>

                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#12172B" style="background-color:#12172B;border:1px solid #32245C;border-radius:14px;">
                      <tr>
                        <td align="center" style="padding:22px 16px 20px 16px;">
                          <div style="font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#A78BFA;">
                            $code_label
                          </div>
                          <div class="code-text" style="padding:10px 0 8px 0;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:40px;line-height:1.15;font-weight:800;letter-spacing:12px;color:#FFFFFF;">
                            $code
                          </div>
                          <div style="font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:12px;line-height:1.5;color:#9D96B3;">
                            $expiry
                          </div>
                        </td>
                      </tr>
                    </table>

                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td align="center" style="padding:26px 0 0 0;">
                          <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                            <tr>
                              <td align="center" bgcolor="#7C3AED" style="border-radius:12px;mso-padding-alt:16px 30px;">
                                <a href="$cta_url" target="_blank" style="display:inline-block;padding:16px 30px;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:15px;font-weight:700;line-height:1.2;color:#FFFFFF;text-decoration:none;border-radius:12px;">
                                  $cta_label
                                </a>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>

                    <p style="margin:18px 0 0 0;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:12px;line-height:1.6;color:#8F88A6;text-align:center;">
                      $cta_hint
                    </p>
                    <p style="margin:6px 0 0 0;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:12px;line-height:1.6;color:#A78BFA;text-align:center;word-break:break-all;">
                      <a href="$cta_url" target="_blank" style="color:#A78BFA;text-decoration:underline;">$cta_url</a>
                    </p>

                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td style="padding:26px 0 0 0;">
                          <div style="height:1px;background-color:#241B3F;font-size:0;line-height:0;">&nbsp;</div>
                        </td>
                      </tr>
                    </table>

                    <p style="margin:22px 0 0 0;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:12px;line-height:1.7;color:#8F88A6;">
                      $security_note
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <tr>
            <td align="center" style="padding:22px 12px 0 12px;">
              <p style="margin:0 0 6px 0;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:12px;line-height:1.6;color:#5F5872;">
                $footer_note
              </p>
              <p style="margin:0;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:11px;line-height:1.7;color:#8A839D;">
                CAMXORA &middot; Music, made by you.<br>
                Need help? <a href="mailto:support@camxora.com" style="color:#7C3AED;text-decoration:none;">support@camxora.com</a>
              </p>
              <p style="margin:10px 0 0 0;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:11px;line-height:1.6;color:#9A93AC;">
                &copy; 2026 CAMXORA. All rights reserved.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
)


def _render(
    *,
    title: str,
    preheader: str,
    eyebrow: str,
    display_name: str,
    intro: str,
    code_label: str,
    code: str,
    expiry: str,
    cta_label: str,
    cta_url: str,
    cta_hint: str,
    security_note: str,
    footer_note: str,
    logo_url: str,
) -> str:
    """Render the shared shell with escaped user-controlled values."""
    return _SHELL.substitute(
        title=escape(title),
        preheader=escape(preheader),
        eyebrow=escape(eyebrow),
        display_name=escape(display_name),
        intro=intro,
        code_label=escape(code_label),
        code=escape(code),
        expiry=escape(expiry),
        cta_label=escape(cta_label),
        cta_url=escape(cta_url, quote=True),
        cta_hint=escape(cta_hint),
        security_note=security_note,
        footer_note=escape(footer_note),
        logo_url=escape(logo_url, quote=True),
    )


def render_verification_email(
    *,
    code: str,
    display_name: str,
    verify_url: str,
    account_email: str,
    logo_url: str = DEFAULT_LOGO_URL,
    expire_minutes: int = 15,
) -> str:
    """Return the branded email-verification HTML."""
    intro = (
        "Welcome to Camxora. Use the code below to verify your email address "
        "and activate your account."
    )
    security_note = (
        "If you didn't create a Camxora account, you can safely ignore this "
        "email. Your address will not be activated without this code."
    )
    footer_note = (
        f"You received this email because an account verification was requested "
        f"for {account_email}."
    )
    return _render(
        title="Verify your email",
        preheader=f"Your Camxora verification code is {code}. It expires in {expire_minutes} minutes.",
        eyebrow="Verify your email",
        display_name=display_name,
        intro=intro,
        code_label="Your verification code",
        code=code,
        expiry=f"Expires in {expire_minutes} minutes. Do not share this code.",
        cta_label="Verify email",
        cta_url=verify_url,
        cta_hint="Button not working? Copy this link into your browser:",
        security_note=security_note,
        footer_note=footer_note,
        logo_url=logo_url,
    )


def render_password_reset_email(
    *,
    code: str,
    display_name: str,
    reset_url: str,
    account_email: str,
    logo_url: str = DEFAULT_LOGO_URL,
    expire_minutes: int = 15,
) -> str:
    """Return the branded password-reset HTML."""
    intro = (
        "We received a request to reset the password for your Camxora account. "
        "Enter the code below to confirm the request, then choose a new password."
    )
    security_note = (
        "If you didn't request this, you can safely ignore this email. Your "
        "password will not change until the code above is used."
    )
    footer_note = (
        f"You received this email because a password reset was requested for "
        f"{account_email}."
    )
    return _render(
        title="Reset your password",
        preheader=f"Your Camxora password reset code is {code}. It expires in {expire_minutes} minutes.",
        eyebrow="Password reset",
        display_name=display_name,
        intro=intro,
        code_label="Your reset code",
        code=code,
        expiry=f"Expires in {expire_minutes} minutes. Do not share this code.",
        cta_label="Enter reset code",
        cta_url=reset_url,
        cta_hint="Button not working? Copy this link into your browser:",
        security_note=security_note,
        footer_note=footer_note,
        logo_url=logo_url,
    )
