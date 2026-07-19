# Implementation changelogs (engineering)

This folder holds **cross-cutting engineering notes** — not the primary release log for each product surface.

## Per-surface release logs

Each deployable app keeps its own changelog next to its code:

| Surface | File |
|---------|------|
| User portal | [`user_portal/CHANGELOG.md`](../../user_portal/CHANGELOG.md) |
| Music portal | [`music_web/CHANGELOG.md`](../../music_web/CHANGELOG.md) |
| Admin portal | [`admin_portal/CHANGELOG.md`](../../admin_portal/CHANGELOG.md) |
| Platform API | [`platform_api/CHANGELOG.md`](../../platform_api/CHANGELOG.md) |
| Website | [`website/CHANGELOG.md`](../../website/CHANGELOG.md) |
| Desktop app | [`CHANGELOG.md`](../../CHANGELOG.md) (repo root) |

See [`docs/CHANGELOG_GUIDE.md`](../CHANGELOG_GUIDE.md) for the full policy.

## Files in this folder

Use naming: `YYYY-MM-DD-<short-slug>.md`

Required sections: Summary, Product impact, Technical impact, Files touched, Migration/deploy, Tests, Follow-ups.

Use when work spans multiple surfaces, touches billing/migrations, or needs deploy/incident detail beyond a surface changelog bullet.
