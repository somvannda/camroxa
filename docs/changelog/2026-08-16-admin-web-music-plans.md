# Admin web music plans management

**Date:** 2026-08-16  
**Surfaces:** platform_api, admin_portal

## Summary

Admin `/plans` page now includes a separate **Web Music Plans** section for managing music.camxora.com subscriptions and top-up packs, independent of desktop channel plans.

## Added

### API (`/api/v1/plans/web-music/...`)

- `GET/POST /plans/web-music/plans` — list/create web music subscription tiers
- `PATCH/DELETE /plans/web-music/plans/{id}` — update/delete (delete blocked when subscribers exist)
- `GET/POST /plans/web-music/topups` — list/create credit top-up packs
- `PATCH/DELETE /plans/web-music/topups/{id}` — update/delete packs

Web music plan fields: price, billing cycle, monthly credits, features (music/images/topup), public visibility, display order, active flag.

### Admin portal

- **Web Music Plans** card on `/plans` — tier grouping by display order (monthly/yearly rows)
- **Web Music Top-Up Packs** card — manage one-time credit packs
- Desktop subscription section excludes `plan_type=web_music` rows

## Changed

- `Plan` domain/repo SELECT includes `plan_type`, `monthly_credits`, `features`, `is_public`, `display_order`
- Admin desktop `Plan` list response includes `plan_type` for client filtering
