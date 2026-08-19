# Web Music: Upgrade Modal for Quota Exceeded

**Date:** 2026-08-16  
**Surfaces:** music_web  
**Type:** Feature

## Summary

Added a modal popup that displays upgrade options when users exhaust their daily 5-song free quota. The modal presents three paid plans with pricing and features to encourage conversion.

## What Changed

### Frontend (`music_web`)

**New Component:**
- Created `upgrade-modal.tsx` - A reusable modal component that displays upgrade options when quota is exceeded
  - Responsive design with gradient background matching Suno's style
  - Three pricing tiers: Starter ($10/mo), Creator ($30/mo), Studio ($50/mo)
  - Shows free plan comparison at the top
  - Features all plan benefits (generations, MP3/WAV downloads, AI lyrics, music library)
  - Highlights the middle "Creator" tier as most popular

**Updated Component:**
- `create-page-client.tsx`:
  - Added `showUpgradeModal` state to control modal visibility
  - Enhanced error handling in `onCreate()` to detect quota exceeded errors
  - Automatically opens upgrade modal when error message includes "free songs today"
  - Modal can be closed by clicking backdrop or X button

## User Flow

1. User tries to create a song when daily quota (5 songs) is exhausted
2. API returns error: "You've used your 5 free songs today. Try again tomorrow or upgrade to Pro."
3. Upgrade modal automatically appears showing:
   - Current free plan (5 songs/day)
   - Three paid upgrade options
   - Feature comparison
   - Subscribe buttons (not yet wired to payment)
4. User can close modal and see error message below create button

## Pricing Plans Displayed

| Plan | Price | Generations/mo | Potential Versions | Features |
|------|-------|----------------|-------------------|----------|
| 🟢 Starter | $10/mo | 120 | 240 | MP3, WAV, AI lyrics, Library |
| 🔵 Creator ⭐ | $30/mo | 400 | 800 | MP3, WAV, AI lyrics, Library |
| 🟣 Studio | $50/mo | 800 | 1,600 | MP3, WAV, AI lyrics, Library |

All plans include:
- 2 versions per generation
- Free MP3 downloads
- Free WAV downloads
- AI lyrics generator
- Music library access

## Technical Details

- Modal uses Tailwind CSS with backdrop blur and gradient backgrounds
- Responsive grid layout (stacks on mobile, 3 columns on desktop)
- Smooth fade-in/fade-out transitions
- Prevents body scroll when open
- Closes on backdrop click or X button
- Subscribe buttons ready for future Stripe integration

## Next Steps

- Wire subscribe buttons to actual payment flow (Stripe integration)
- Add plan selection state management
- Implement backend subscription endpoints
- Add success/error handling for subscription

## Testing

1. Go to https://music.sandbox.camxora.com/create
2. Generate 5 songs to exhaust daily quota
3. Try to generate a 6th song
4. Upgrade modal should appear automatically
5. Verify all three pricing plans display correctly
6. Test modal close functionality (X button and backdrop click)
