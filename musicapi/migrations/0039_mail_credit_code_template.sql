-- 0039_mail_credit_code_template — ready-made mail for a standalone credit code.
--
-- The seeded promo template is written for a percent discount ("20% off",
-- CTA to /dashboard/billing). Pairing it with a `credit` campaign would mail
-- copy that does not match the code. This template is the correct partner for
-- that kind: it links /dashboard/redeem?code={{code}} and prints the credit
-- amount from {{discount_credits}}.
--
-- DO NOTHING on conflict: an operator may have edited the template in the mail
-- console, and a deploy must not overwrite their copy. Fresh databases get the
-- same row from scripts/mail-templates-seed.sql.

INSERT INTO mail_templates (key, locale, name, subject, html, text, vars, send_mode)
VALUES
  ('credit_code', 'en', 'credit code', 'Your {{discount_credits}} CAMXORA credits', '<div style="display:none;max-height:0;overflow:hidden;opacity:0;">
    {{discount_credits}} credits, no purchase needed. Your code expires in {{code_expires_days}} days.
  </div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,''Segoe UI'',Roboto,Helvetica,Arial,sans-serif;">

          <tr><td style="background:#7466F1;height:4px;line-height:4px;font-size:0;">&nbsp;</td></tr>

          <tr>
            <td style="padding:28px 32px 0;">
              <span style="font-size:15px;font-weight:700;letter-spacing:.14em;color:#7466F1;">CAMXORA</span>
            </td>
          </tr>

          <tr>
            <td style="padding:20px 32px 0;">
              <h1 style="margin:0;font-size:24px;line-height:1.3;color:#111827;font-weight:700;">
                {{discount_credits}} credits, on us
              </h1>
              <p style="margin:12px 0 0;font-size:15px;line-height:1.65;color:#374151;">
                Hi {{first_name}} &mdash; here is a code for <strong>{{discount_credits}} credits</strong>.
                No purchase needed: redeem it and the credits land on your balance.
              </p>
            </td>
          </tr>

          <tr>
            <td align="center" style="padding:24px 32px 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f5f3ff;border:1px dashed #a78bfa;border-radius:10px;">
                <tr>
                  <td align="center" style="padding:20px;">
                    <p style="margin:0 0 6px;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#7c3aed;">
                      Your code
                    </p>
                    <p style="margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:24px;font-weight:700;letter-spacing:.12em;color:#111827;">
                      {{code}}
                    </p>
                    <p style="margin:8px 0 0;font-size:12px;color:#6b7280;">
                      Expires in {{code_expires_days}} days &middot; one use &middot; this account only
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <tr>
            <td align="left" style="padding:24px 32px 8px;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:#7466F1;border-radius:8px;">
                    <a href="{{app_url}}/dashboard/redeem?code={{code}}" style="display:inline-block;padding:13px 24px;font-size:14px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">
                      Redeem my {{discount_credits}} credits
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <tr>
            <td style="padding:8px 32px 0;">
              <p style="margin:0;font-size:13px;line-height:1.6;color:#6b7280;">
                Redeem the code from your dashboard. If it says the code is invalid, make sure you are
                signed in to the same account this email was sent to &mdash; codes are issued per person.
              </p>
            </td>
          </tr>

          <tr>
            <td style="padding:28px 32px 0;">
              <div style="height:1px;background:#e5e7eb;line-height:1px;font-size:0;">&nbsp;</div>
            </td>
          </tr>

          <tr>
            <td style="padding:18px 32px 32px;">
              <p style="margin:0;font-size:12px;line-height:1.6;color:#6b7280;">
                You are receiving this because you have a CAMXORA account.
                <a href="{{unsubscribe_url}}" style="color:#6b7280;text-decoration:underline;">Unsubscribe</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>', NULL, ARRAY['app_url', 'code', 'code_expires_days', 'discount_credits', 'first_name', 'unsubscribe_url']::text[], 'manual')
ON CONFLICT (key, locale) WHERE key IS NOT NULL DO NOTHING;
