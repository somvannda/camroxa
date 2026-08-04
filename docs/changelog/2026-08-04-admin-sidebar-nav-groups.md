# Admin sidebar nav groups

**Date:** 2026-08-04  
**Surfaces:** admin_portal

## Summary

Grouped the flat admin sidebar into labeled sections so operators can find pages faster. Rebased onto latest `main` so **User Spent** and other recently merged items stay in the menu.

## Groups

| Section | Items |
|---------|-------|
| Overview | Dashboard |
| Accounts | Users, Subscriptions, Plans, Redeem Codes, Invitations |
| Billing | Credits, Usage, User Spent, Finance |
| Content | Blog Posts, Music Prompts, Content Pools, Image Packs, Marketplace |
| Operations | Music Streaming, Streaming Jobs, Rate Limits, Key Pool, Job Queue, Pipeline Ops |
| System | Audit Log, Client Logs, Desktop Notifications, Software Updates, Settings |

Collapsed mode keeps icon-only links and uses separators between groups instead of labels. Top bar page titles updated for nav pages that were missing titles.

## Files

- `admin_portal/src/components/layout/sidebar.tsx`
- `admin_portal/src/components/layout/top-bar.tsx`
