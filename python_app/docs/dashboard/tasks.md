# Dashboard (Tasks)

## Milestone 1 — Dashboard UI (No Cost DB Yet)
- [ ] Implement Dashboard on the `home` page (left-nav label `Dashboard`, key `home`)
- [ ] Build KPI card row (active/failed/songs/images/mp4/merged/youtube/credits)
- [ ] Add Pipeline Health panel (stage distribution + top blockers)
- [ ] Add Recent Failures table (reuse Progress row meta and right-click actions)
- [ ] Add Recent Activity table (derived events from existing DB tables)
- [ ] Add filters (date range + profile) and “Active only”
- [ ] Performance: background collection + UI apply + caching (reuse Progress patterns)
- [ ] Update `DEVELOPMENT_LOG.md`

## Milestone 2 — Cost Tracking (Auditable)
- [ ] Add `cost_events` table migration
- [ ] Insert cost events from:
  - [ ] Suno credits checks (credits used per batch/run)
  - [ ] Image generation provider calls (units per image)
  - [ ] LLM calls (requests per call; tokens if available)
  - [ ] YouTube uploads (uploads per job)
- [ ] Dashboard “Cost + Usage” panel backed by `cost_events`
- [ ] Add “Cost Details” dialog (shows calculation + raw events)
- [ ] Update docs (`technical.md`) and `DEVELOPMENT_LOG.md`

## Validation Checklist
- [ ] Dashboard loads without blocking UI
- [ ] Numbers match Progress and History for the same date filters
- [ ] No filesystem scans happen when Dashboard not active
- [ ] Cost events never store secrets
