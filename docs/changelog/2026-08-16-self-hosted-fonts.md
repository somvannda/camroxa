# Self-Hosted Fonts Migration

**Date**: 2026-08-16  
**Type**: Infrastructure  
**Impact**: Build reliability, no external Google Fonts dependency

## Problem

The `music_web` Next.js build was failing on sandbox with errors fetching Google Fonts from `fonts.gstatic.com`:

```
Module not found: Can't resolve '@vercel/turbopack-next/internal/font/google/font'
```

This was caused by using Next.js `next/font/google` which requires internet access during build to download font files from Google's CDN.

## Solution

Migrated to self-hosted fonts using the `@fontsource` npm packages:

1. **Installed font packages**:
   ```bash
   npm install @fontsource/inter @fontsource/outfit
   ```

2. **Updated `layout.tsx`**:
   - Removed `next/font/google` imports
   - Added direct CSS imports for specific font weights
   - Removed Next.js font CSS variables

3. **Updated `globals.css`**:
   - Changed `font-family: var(--font-sans)` → `font-family: 'Inter', system-ui, sans-serif`
   - Changed `font-family: var(--font-display)` → `font-family: 'Outfit', 'Inter', system-ui, sans-serif`

4. **Updated `tailwind.config.js`**:
   - Overrode preset font families
   - Set `sans: ['Inter', 'system-ui', 'sans-serif']`
   - Set `display: ['Outfit', 'Inter', 'system-ui', 'sans-serif']`

## Benefits

- **No external dependencies** during build - fonts are bundled in `node_modules`
- **Reliable builds** on sandbox and any environment (no network required)
- **Same visual appearance** - Inter and Outfit fonts unchanged
- **Better performance** - fonts are optimized and versioned by Fontsource

## Files Changed

- `music_web/package.json` - Added `@fontsource/inter`, `@fontsource/outfit`
- `music_web/src/app/layout.tsx` - Switched to self-hosted font imports
- `music_web/src/app/globals.css` - Updated font-family references
- `music_web/tailwind.config.js` - Overrode font families
- `music_web/src/app/login/page.tsx` - Fixed missing `Music2` import
- `music_web/src/app/register/page.tsx` - Fixed missing `Check` import

## Testing

- ✅ Local build succeeds (`npm run build`)
- ✅ Sandbox build succeeds (deployed via `rebuild_music_web_sandbox.py`)
- ✅ Fonts render correctly
- ✅ Typography unchanged

## Migration Notes

The shared `tailwind-preset.js` still uses CSS variables (`var(--font-sans)`, `var(--font-display)`), but `music_web` overrides them directly. Other projects (`admin_portal`, `website`, etc.) are unaffected.
