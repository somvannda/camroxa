# Production VPS deployment scripts

**Date:** 2026-07-26  
**Status:** implemented (not deployed)

## Summary
Added a dedicated production deployment entry point and production remote installer for CAMXORA. The remote installer starts nginx with HTTP servers before requesting certificates, so the HTTPS-only production configuration cannot block first certificate issuance.

## Product impact
Production deployment now targets CAMXORA public domains. If DNS or certificate issuance is unavailable, HTTP remains reachable until TLS can be completed.

## Technical impact
The local runner prefers `PRODUCTION_VPS_*` credentials and falls back to `VPS_*`. It uploads the HTTPS nginx configuration, which the remote installer applies only after the API certificate exists.

## Files touched
- Deployment: `scripts/deploy/camxora-production-remote.sh`, `scripts/deploy/deploy_production.py`
- Documentation: `docs/changelog/2026-07-26-production-deployment-scripts.md`

## Migration / deploy
No database migration is required. Configure production DNS and `CERTBOT_EMAIL`, then run `python scripts/deploy/deploy_production.py`. Do not commit `.deploy/secrets.env`.

## Tests
Static validation pending; deployment was intentionally not run.

## Follow-ups
Issue the optional `music.camxora.com` certificate after its DNS record is ready.