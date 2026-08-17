# Hide sandbox environment banner

**Date:** 2026-08-17  
**Surface:** music_web

## Summary

Removed the amber "Sandbox music portal" banner from the music web header on sandbox deployments.

## Changes

- `music_web/src/components/site-header.tsx` — removed sandbox banner block
- `music_web/src/components/shell-switcher.tsx` — removed duplicate banner from marketing header
