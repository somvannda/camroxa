# Logged-in shell header alignment

**Date:** 2026-08-17  
**Surface:** music_web

## Summary

Aligned the app shell top bar with the sidebar brand row and removed duplicate branding from the main header when logged in.

## Changes

- `site-header.tsx`: fixed `h-16` height to match sidebar; removed logo/title (sidebar only)
