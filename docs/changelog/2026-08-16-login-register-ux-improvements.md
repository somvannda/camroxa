# Login/Register UX Improvements

**Date**: 2026-08-16  
**Type**: UI Enhancement  
**Impact**: Better user experience on authentication pages

## Changes

### 1. Added Footer to Login/Register Pages

Previously, the `ShellSwitcher` component explicitly removed the footer for authentication pages:

```typescript
{isAuthPage ? null : <SiteFooter />}
```

Now the footer is displayed on all marketing pages, including login and register, providing consistent navigation and links.

### 2. Centered Forms Vertically

Added `min-h-[calc(100vh-200px)]` to the form containers on both login and register pages to ensure the forms are properly centered vertically on the page, regardless of screen height.

**Before**:
```tsx
<div className="flex items-center justify-center px-4 py-12">
```

**After**:
```tsx
<div className="flex min-h-[calc(100vh-200px)] items-center justify-center px-4 py-12">
```

### 3. Added Pricing Link to Marketing Header

The `MarketingHeader` (shown to non-logged-in users on home, login, register, etc.) previously didn't have a pricing link. Only the logged-in `SiteHeader` had one.

**Added**:
- "Pricing" button in the navigation menu with Sparkles icon
- Opens the dynamic `PricingModal` component (fetches plans from database)
- Consistent with the pricing button in the logged-in header

## Files Changed

- `music_web/src/components/shell-switcher.tsx`
  - Removed conditional footer removal for auth pages
  - Added pricing button to `MarketingHeader` navigation
  - Added `PricingModal` state and rendering
  - Added imports: `Sparkles`, `useState`, `PricingModal`

- `music_web/src/app/login/page.tsx`
  - Added `min-h-[calc(100vh-200px)]` for vertical centering

- `music_web/src/app/register/page.tsx`
  - Added `min-h-[calc(100vh-200px)]` for vertical centering

## User Impact

- ✅ Login page now has a footer with contact/about links
- ✅ Register page now has a footer with contact/about links
- ✅ Both forms are properly centered vertically
- ✅ Pricing link is visible in header on all marketing pages
- ✅ Consistent navigation experience across logged-in and logged-out states

## Testing

- ✅ Local build succeeds
- ✅ Sandbox deployment succeeds
- ✅ Footer renders on login/register pages
- ✅ Pricing modal opens from header link
