# CutLuy webhooks → `/api/v3`

## Summary

Canonical CutLuy webhook URLs are now under `/api/v3`. Server dual-mounts the same handlers on `/api/v1` during the transition.

## Sandbox URLs (configure in CutLuy Dashboard → Webhooks)

| Surface | URL |
| ------- | --- |
| Music CutLuy (subscriptions / topups) | `https://api.sandbox.camxora.com/api/v3/webhooks/cutluy` |
| Desktop billing CutLuy | `https://api.sandbox.camxora.com/api/v3/billing/webhooks/cutluy` |

Health: `GET …/api/v3/webhooks/cutluy/health` → 200.

Production CutLuy URL change only when explicitly requested.

## Docs / Admin UI

- `docs/SANDBOX_DEPLOYMENT_GUIDE.md`, `docs/DEPLOYMENT_OPERATIONS.md`
- Admin Settings → Payments copy lists the v3 URLs
