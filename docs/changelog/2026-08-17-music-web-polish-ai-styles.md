# 2026-08-17 — Music web polish + AI style generation

## Music web

- Sidebar account card shown first with user name, songs/credits, top-up; menu links below.
- Global 7px border radius and purple-themed scrollbars.
- Vocal gender adds **Both** option; Style Influence slider uses thinner ticks.
- Workspace: select-only in create form; create new workspace from right panel header.
- Styles wand calls `POST /api/v1/web-music/generate-styles` (LLM-backed, credit-priced).

## Platform API

- Operation `web_music_style` in AI routing (Admin → Settings → AI Routing → Text Generation).
- Migration `093_web_music_style_pricing` seeds draft credit pricing rows.
- `POST /api/v1/web-music/generate-styles` resolves admin routing, charges credits, returns comma-separated tags.

## Admin

- AI Routing settings: **Web Music Style Tags** operation under Text Generation.
