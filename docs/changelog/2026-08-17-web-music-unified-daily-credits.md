# Web music unified daily credits (Suno model)

**Date:** 2026-08-17  
**Surfaces:** platform_api, music_web

## Summary

Replaced the separate “5 free songs/day” counter with a unified **credit wallet** for all web music users.

## Credit model

| User type | Credits | Reset |
|-----------|---------|-------|
| Free | 50 credits/day (= 5 songs at 10 credits/song) | Daily at billing midnight (Asia/Phnom_Penh) |
| Subscriber | Monthly plan credits + top-up purchases | Monthly credits reset each billing period; top-ups never expire |

All generation and AI assist (style/lyrics) deduct from the same credit pool.

## Backend

- Migration `095_web_music_daily_credits`: `web_music_daily_usage.credits_used`, setting `web_music_free_daily_credits=50`
- `CreditService` (v2): unified balance, consume, and refund for subscription pools or daily free pool
- `WebMusicService`: always charges credits (except Desktop Pro license bypass on web)

## Frontend

- Sidebar shows **Credits** and **Songs** (= credits ÷ 10) only
- Free users see “X of 50 free credits today · resets daily”
- Create page gates on credits ≥ 10

## Admin

- Adjust free daily allowance via system setting `web_music_free_daily_credits` (default 50)
