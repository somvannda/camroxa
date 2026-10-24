# CAMXORA auth email previews

These files are generated from the same renderers used by the API:

- `platform_api/services/email_templates.py`

Do not edit the generated HTML by hand. Regenerate after changing the template:

```powershell
python scripts/preview-auth-emails.py
```

Open:

```text
web-camxora/email-templates/password-reset.html
web-camxora/email-templates/verify-email.html
```

The preview script uses:

```text
http://localhost:3103/email/camxora-logo.png
```

for the logo, so the preview looks the same as the local email. Production uses:

```text
https://camxora.com/email/camxora-logo.png
```

Override preview values when needed:

```powershell
$env:CAMXORA_EMAIL_PREVIEW_BASE_URL = "https://camxora.com"
$env:CAMXORA_EMAIL_PREVIEW_LOGO_URL = "https://camxora.com/email/camxora-logo.png"
python scripts/preview-auth-emails.py
```

## Reset flow

1. `/forgot-password` sends the code and redirects to `/reset-password?email=...&sent=1`.
2. `/reset-password` confirms the six-digit code.
3. `/reset-password/new` sets the new password.

The email CTA opens `/reset-password?email=...`.
