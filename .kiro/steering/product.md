# Product Overview

MusicGenerator is an AI-powered music production and distribution platform consisting of three components:

1. **Desktop App** (`python_app/`) — PyQt6 desktop application for music generation, video export with spectrum visualizers, and automated YouTube upload. Targets Windows. Packaged via PyInstaller.

2. **Platform API** (`platform_api/`) — FastAPI backend providing authentication, credit/billing management, license enforcement, and proxied access to external AI services (Suno for music, Fal AI/SLAI for images, DeepSeek for LLM song drafts).

3. **Admin Portal** (`admin_portal/`) — React SPA for managing users, licenses, credit pricing, music prompts, audit logs, and rate limits.

## Key Workflows

- Generate song lyrics/structure via LLM → submit to Suno for audio → generate cover images → render video with spectrum visualizer → upload to YouTube
- Batch processing: multi-song pipelines with auto-merge into reel videos
- Credit system: plan quotas consumed first, then wallet credits; refund on failure
- Channel profiles: per-channel output settings (resolution, templates, upload config)

## External Services

- **Suno** — music generation (async callback-based)
- **Fal AI / SLAI** — image generation
- **DeepSeek / SLAI LLM** — song draft generation
- **YouTube Data API** — OAuth-based video upload
- **PostgreSQL** — persistence (both desktop app local and platform API)
- **Redis** — rate limiting, token blocklist, caching (platform API only)
