# Credits-only API × platform map

**Date:** 2026-08-23  
**Branch:** `feature/credits-only-api-v3`  
**Env:** sandbox. There is **no v4**. CutLuy checkout is nested at `/api/v1/v2/...`.

Prefixes from [platform_api/main.py](../platform_api/main.py): `/api/v1` + `/api/v3`.

Legend: **D** desktop · **M** music web · **P** user portal · **W** website · **A** admin · **H** webhook/internal · **wallet** touches credits/plans.

## Who calls what (now)

| Client | Prefixes | Wallet / plan doors |
|---|---|---|
| Desktop | `/api/v1` only | Charge is server-side on generate. `/credits/operation-costs`, `/licenses/validate`, `/users/me`. No `/api/v3`. |
| Music web | `/api/v1` + `/api/v1/v2` + `/api/v3` | Header: `GET /api/v3/me/credits`. Cards: `/api/v3/plans/public` then v1. Checkout: `/api/v1/v2/subscriptions\|topups`. Generate: `POST /api/v1/web-music/generate`. |
| User portal | `/api/v1` (relative) | `/plans/public`, `/billing/*`, `/credits/balance`, `/credits/packs`, `/credits/quota-status`. Same `credit_wallets`. Not on v3. |
| Website | `/api/v1` | `/plans/public`, `/plans/public/usage-rates`. Display only. |
| Admin | `/api/v1` + `/api/v3` | Catalog/wallet extras: `/api/v3/plans`, `PATCH /api/v3/admin/plans/:id`, `GET /api/v3/users/:id/credits`. Most ops stay `/api/v1/admin/*`, `/credits/*`, `/plans`, `/licenses`. |

## Routers (`/api/v1` unless noted)

| Router | Prefix | Who | Wallet? |
|---|---|---|---|
| health | `/health` + `/api/v1/health` | probes, A/P | no |
| auth | `/auth` | D M P A | no |
| billing | `/billing` | P (desktop checkout / packs / add-on) | yes — cash, not CutLuy web |
| users | `/users` | D M P A | yes — list plan/wallet |
| licenses | `/licenses` | D validate; A CRUD | yes — desktop entitlement |
| plans | `/plans` | W P M A | yes — public catalog |
| credits | `/credits` | D costs; P balance; A pricing/adjust | yes |
| profiles | `/profiles` | D | no |
| profile_video_templates | `/profiles` | D | no |
| prompts | `/prompts` | D A | no |
| redeem_codes | `/redeem-codes` | A P | yes if `credit_grant` |
| generation | `/generation` | D | yes — Suno debit |
| batch | `/batches` | D A | yes |
| content_pools | `/content-pools` | D | no |
| callbacks | `/callbacks` | H Suno | yes (complete/fail) |
| control_panel | `/control-panel` | P | no |
| ws | `/ws` | D | no |
| settings | `/settings` | D A | fail-absorb copy |
| stats | `/stats` | D | no |
| progress | `/progress` | D | no |
| youtube | `/youtube` | D A | no |
| admin | `/admin` | A usage/finance/user-spend | yes |
| admin_pipeline | `/admin/pipeline` | A | waive = no debit |
| admin_invitations | `/admin/invitations` | A | no |
| blog_posts | (blog) | W A | no |
| admin_content_pools | `/admin/content-pools` | A | no |
| client_logs | | D A | no |
| key_pool | `/admin/key-pool` | A | no |
| media | `/media` | D M A | no |
| music_history | `/music` | D | no |
| music_languages | `/music` | D | no |
| admin_music_languages | `/admin/music-languages` | A | no |
| suno_blocklist | `/generation` | D | no |
| suno_blocklist_admin | `/admin/suno-blocklist` | A | no |
| music_downloads | `/music/downloads` | D | no |
| image_jobs | `/image-jobs` | D | yes |
| image_sample_packs | `/image-sample-packs` | D | no |
| admin_image_sample_packs | `/admin/image-sample-packs` | A | no |
| channel_setup | `/channel-setup` | D | yes |
| channel_prompts | `/channel-prompts` | D | no |
| ai_routing | `/admin/ai-routing` | A | pricing fallback |
| marketplace | `/marketplace` | D A | no |
| public_desktop | `/public` | D updater | no |
| streaming_public | `/public/streaming` | M W | no |
| streaming_admin | `/admin/streaming` | A | no |
| streaming_library | `/streaming/library` | M | no |
| web_music | `/web-music` | M | yes — generate/quota |
| web_music_licenses | `/web-music/licenses` | M playback | no |
| web_music_plans_admin | `/plans/web-music` | A leftover (not mounted on `/plans`) | stale |
| v2_subscriptions | `/v2/subscriptions` | M checkout | yes — fulfill writes v3 grant |
| v2_credits | `/v2/credits` | M history; header fallback only | leftover pot should be 0 |
| v2_topups | `/v2/topups` | M | yes — fulfill writes pack lot |
| webhooks_cutluy | `/webhooks` | H | yes |
| v3_billing | `/api/v3` | M A | yes — quote/wallet/public/leftover |

## Shared HTTP both paid clients actually call

Auth login/register/refresh/logout and `GET /api/v1/users/me`. Generate is **not** the same URL (desktop `/generation/suno`, web `/web-music/generate`). Same debit model when `credits_only_v3_charge` is On.

## Stale doors this sitting recasts

- Admin `/users` Tag = `users.products` (Music/Studio). Drop from UI. Plan = license else web sub else Free.
- Admin `/users` Credits `used/daily` for Music tags. One wallet number.
- Admin `/licenses` listed only `licenses`. Union `web_subscriptions`.
- User-spent `plan_id` filter was license-only. Include web sub.
- Portal `/credits/quota-status` still exists; E2E must not treat meters as live billing.
