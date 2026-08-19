# Phase 1 follow-up: CutLuy payments, email verification UI, auth layout

**Date:** 2026-08-16

## CutLuy payment flow fixes

- Load CutLuy credentials from `PLATFORM_CUTLUY_*` settings (was reading unset `CUTLUY_*` env names).
- Added asyncpg pool adapter for v2 credit/subscription services (`fetch_one`, transactions).
- Fixed subscription purchase API to resolve plans by UUID and create checkout sessions correctly.
- Fixed webhook handler JSON parsing (body was consumed twice) and signature verification bridge.
- Fixed credit transaction inserts to use existing `credit_transactions.ref_id` schema.
- Tagged payment metadata with `type: subscription|topup` for webhook routing.

## Email verification UI

- Added `/verify-email` page with code entry and resend support.
- Register now redirects to verify-email after account creation.
- Added `sendVerificationEmail` and `verifyEmailCode` client helpers.

## Login/register UI

- Shared compact `AuthFormShell` matching home marketing chrome (single header/footer via shell).
- Removed duplicate large card logos and reduced vertical padding on auth forms.
- Register copy clarifies credits come from subscribing, not free signup bonus.
- Explicit Turnstile widget render/remount fixes reset console errors on auth pages.
- Sidebar **Upgrade to Pro** and credit **Subscribe** open in-app pricing modal (not external `/pricing`).
- Create form column is more compact, capped to viewport height, with internal scroll + pinned Create footer.
- User-portal-style fixed sidebar with pinned bottom account/upgrade card on every app page.
- Create form uses collapsible Lyrics/Styles/More Options sections, taller style field, tick sliders, and floating Create CTA (violet theme).

## Register 500 fix

- Fixed Python scoping bug in `/auth/register`: inner `get_settings` import made verification crash when Turnstile token was absent, leaving orphan users without verification codes.
