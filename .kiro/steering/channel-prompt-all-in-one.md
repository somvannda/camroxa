# Plan: Channel Prompts All-in-One Form

## Problem

Currently, setting up channel onboarding prompts for each Music Description (genre) requires creating **6 separate prompts** one by one:

1. **Title** — channel name generation prompt
2. **Logo** — logo generation prompt
3. **Cover** — cover/banner generation prompt
4. **Description** — channel description prompt
5. **Keyword** — SEO keywords prompt
6. **Tag** — tags prompt

With 6 genres, that's **36 individual form submissions**. Currently only 2 prompts exist (both for "EDM / Workout Gym"). This is the #1 friction point for admins.

## Solution

Add an **"All-in-One" tab** to the Prompts page in the admin portal. One form per genre that creates/updates all 6 channel prompts at once.

---

## Changes

### 1. Admin Portal — New "All-in-One" Tab

**File: `admin_portal/src/pages/prompts/index.tsx`**

Add a 4th tab called "Channel Setup" (or "All-in-One") alongside the existing 3 tabs:

```
[Music Descriptions] [Music Structures] [Channel Prompts] [Channel Setup]
```

The Channel Setup tab contains:

```
┌─────────────────────────────────────────────────────┐
│  Channel Setup — All-in-One                         │
│                                                     │
│  Music Description (Genre)    [ dropdown ▼ ]        │
│                                                     │
│  ┌─ Channel Name Prompt ──────────────────────────┐ │
│  │  System prompt for generating channel names    │ │
│  │  ┌───────────────────────────────────────────┐ │ │
│  │  │ textarea                                   │ │ │
│  │  └───────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────┘ │
│                                                     │
│  ┌─ Logo Prompt ─────────────────────────────────┐  │
│  │  System prompt for generating channel logo    │  │
│  │  ┌───────────────────────────────────────────┐│  │
│  │  │ textarea                                   ││  │
│  │  └───────────────────────────────────────────┘│  │
│  └────────────────────────────────────────────────┘  │
│                                                     │
│  ┌─ Cover Art Prompt ────────────────────────────┐  │
│  │  System prompt for generating channel banner  │  │
│  │  ┌───────────────────────────────────────────┐│  │
│  │  │ textarea                                   ││  │
│  │  └───────────────────────────────────────────┘│  │
│  └────────────────────────────────────────────────┘  │
│                                                     │
│  ┌─ Description Prompt ──────────────────────────┐  │
│  │  System prompt for generating channel desc    │  │
│  │  ┌───────────────────────────────────────────┐│  │
│  │  │ textarea                                   ││  │
│  │  └───────────────────────────────────────────┘│  │
│  └────────────────────────────────────────────────┘  │
│                                                     │
│  ┌─ Keywords Prompt ─────────────────────────────┐  │
│  │  System prompt for generating SEO keywords    │  │
│  │  ┌───────────────────────────────────────────┐│  │
│  │  │ textarea                                   ││  │
│  │  └───────────────────────────────────────────┘│  │
│  └────────────────────────────────────────────────┘  │
│                                                     │
│  ┌─ Tags Prompt ─────────────────────────────────┐  │
│  │  System prompt for generating tags            │  │
│  │  ┌───────────────────────────────────────────┐│  │
│  │  │ textarea                                   ││  │
│  │  └───────────────────────────────────────────┘│  │
│  └────────────────────────────────────────────────┘  │
│                                                     │
│              [ Save All Prompts ]                    │
└─────────────────────────────────────────────────────┘
```

**Behaviour:**
- Genre dropdown populated from `useDescriptions()` (same data as onboarding wizard)
- When genre is selected, fetch existing channel prompts for that genre's `match_key` and pre-fill the textareas
- "Save All Prompts" creates or updates all 6 channel prompts in parallel via existing API
- Shows success toast after all saves complete
- Empty textareas are skipped (not created/updated)

### 2. Admin Portal — New Hook

**File: `admin_portal/src/hooks/use-channel-prompt-bundle.ts`** (new file)

Custom hook that wraps the existing `useChannelPrompts` + `useCreateChannelPrompt` + `useUpdateChannelPrompt`:

```typescript
// useChannelPromptBundle(matchKey: string)
// - Fetches all channel prompts where match_key = matchKey
// - Returns a map: { title: string, logo: string, cover: string, description: string, keyword: string, tag: string }
// - saveAll(prompts) → creates/updates all 6 prompts
```

Key functions:
- `useChannelPromptBundle(matchKey: string)` — loads existing prompts for a genre
- `saveAll(prompts)` — upserts all 6 prompts (create if not exists, update if exists)
- Uses the existing `/api/v1/channel-prompts` endpoints (no new backend endpoints needed)

### 3. Backend — No Changes Needed

The existing CRUD endpoints (`POST /channel-prompts`, `PUT /channel-prompts/:id`) already support all operations. The admin portal can:
1. `GET /channel-prompts?match_key=EDM` to fetch existing prompts
2. `POST /channel-prompts` to create new ones
3. `PUT /channel-prompts/:id` to update existing ones

The `UNIQUE(name, category)` constraint means we need a lookup step before save:
- For each category, check if a prompt with `name="Channel {Category}"` + `match_key=<selected>` exists
- If yes → `PUT` (update)
- If no → `POST` (create)

### 4. Existing Channel Prompts Tab — Keep As-Is

The individual Channel Prompts tab stays for fine-grained editing. The All-in-One tab is the快速 setup path.

---

## Implementation Steps

1. **Create `useChannelPromptBundle` hook** in `admin_portal/src/hooks/`
2. **Create `ChannelSetupTab` component** in `admin_portal/src/pages/prompts/`
3. **Add "Channel Setup" tab** to the prompts page tab list
4. **Test**: Select genre → verify existing prompts load → edit → save → verify all 6 prompts created/updated in DB

---

## Files to Modify

| File | Change |
|------|--------|
| `admin_portal/src/pages/prompts/index.tsx` | Add 4th tab + import `ChannelSetupTab` |
| `admin_portal/src/hooks/use-channel-prompt-bundle.ts` | **New** — hook for bulk prompt management |
| `admin_portal/src/pages/prompts/channel-setup-tab.tsx` | **New** — the all-in-one form component |

---

## No Backend Changes

All existing API endpoints are sufficient. The frontend handles the orchestration.

---

## Verification

1. Open admin portal → Music Prompts → Channel Setup tab
2. Select "EDM / Workout Gym" → should show existing Channel Name + Logo prompts pre-filled
3. Fill in Cover, Description, Keywords, Tags prompts → click Save
4. Verify all 6 prompts exist in `channel_prompts` table with correct `match_key`
5. Switch to Channel Prompts tab → verify all 6 appear
6. Start onboarding in desktop app → select EDM genre → verify prompts are used correctly
