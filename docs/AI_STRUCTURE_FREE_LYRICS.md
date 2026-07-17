# AI Structure Free — Lyric Generation Mode

Feature spec for letting users **skip fixed song structure templates** and allow AI providers (Chat LLMs + Suno Lyrics API) to invent their own section layout — while Camxora accepts the result as-is instead of forcing lyrics into a predefined `[Verse]` / `[Chorus]` template.

**Status:** Deployed to sandbox (2026-07-17). Provider probe: OpenAI, DeepSeek, Suno PASS; Slai blocked by sandbox 401 until key pool is refreshed.  
**Related:** `platform_api/services/generation_service.py`, `camxora_python/features/music/widgets/automation_card.py`  
**Product scope:** [`PRODUCT_SCOPE.md`](./PRODUCT_SCOPE.md) — desktop work is **`camxora_python` only**; `camxora/` (Electron) and `python_app/` are excluded. Server-side: `platform_api`; portals as needed.

---

## 1. What you mean (confirmed)

Today the app works like this:

1. User picks a **Structure** from dropdown (e.g. `[Intro] → [Verse] → [Chorus] → …`)
2. Server loads the full structure template from `music_structures`
3. Lyric AI generates text, then the pipeline **forces** output to match that exact header order
4. Suno music generation receives bracket-section lyrics

**Structure free** means:

- User does **not** pick a template structure (or picks a sentinel like **“AI Structure”**)
- We **do not send** section headers as a fill-in-the-blank template
- We **do send** description, language, creativity, and provider choice
- AI returns lyrics **with whatever structure it chooses** (`[Verse]`, `[Hook]`, `[Bridge]`, etc.)
- Camxora **accepts** that structure in the response — validate loosely, store on song, pass to Suno

This is the inverse of today’s two-step chat flow (freeform draft → shape into template).

---

## 2. Current architecture (why change is non-trivial)

### Structure is enforced in many places

| Stage | File | Behavior |
|-------|------|----------|
| API validation | `platform_api/routers/generation.py` | Rejects draft if structure missing or has no `[Section]` headers |
| Draft service | `platform_api/services/generation_service.py` | `submit_draft()` requires structure content |
| Chat lyrics | Same | Step 1: no headers → Step 2: **shape** into template |
| Suno lyrics | Same | 200-char prompt includes section labels → deterministic `assign_draft_lyrics_to_structure()` |
| Validation | Same | `validate_lyrics_structure()` — exact header count & order |
| Batch | `platform_api/services/batch_service.py` | Every song gets a `structure_id`; shuffle picks from pool |
| UI | `automation_card.py`, `MusicWorkspacePage.tsx` | Structure dropdown required for Generate |

### Partial “free” plumbing already exists

When `structure_headers` is empty:

- `split_freeform_lyrics_to_structure()` returns lyrics unchanged
- `describe_structure_validation_failure()` only requires ≥32 lines (no header order)

So the backend can accept AI-chosen structure — but **nothing sets empty headers today** because upstream gates block it.

---

## 3. Recommendation

### Add an explicit mode — do not overload “empty structure”

Introduce a first-class enum:

```typescript
structure_mode: "template" | "ai_free"
```

| Mode | Structure dropdown | Server behavior |
|------|-------------------|-----------------|
| `template` (default) | User picks structure (current) | Force lyrics into template |
| `ai_free` | Shows **“AI Structure”** (static sentinel) | No template; accept AI sections |

**Why not just hide the dropdown?**  
Explicit mode keeps batch history, credits, and API validation unambiguous. “No structure selected” should remain an error in template mode.

### Keep bracket headers in output

Suno custom mode and downstream tooling (bilingual plans, video lyric timeline) expect `[Section]` markers. Structure free means **AI picks sections**, not **plain text without sections**.

Exception: if routed to Suno lyrics API and it returns plain text, run a light **auto-section** pass (single `[Verse]` wrapper) as last resort.

---

## 4. UI design — keep it simple

### Music workspace (`automation_card.py`)

Replace the structure dropdown behavior when AI Structure is enabled:

```
┌─────────────────────────────────────────────────────────┐
│ Description:  [ EDM / Workout Gym          ▼ ]          │
│ Structure:    [ AI Structure               ▼ ]  ← NEW   │
│               ├─ AI Structure        (recommended label)  │
│               ├─ ─────────────────                      │
│               ├─ Tech House Standard                      │
│               ├─ Pop Verse-Chorus                       │
│               └─ … user/admin templates …               │
└─────────────────────────────────────────────────────────┘
```

**Rules:**

- **“AI Structure”** is always the first option (static sentinel, `structure_id = null`, `structure_mode = ai_free`)
- When selected: disable **Shuffle structure** checkbox (nothing to shuffle)
- Tooltip: *“AI chooses section layout (Intro, Verse, Chorus, …). You don’t pick a template.”*
- When user picks any other item: `structure_mode = template`, existing behavior unchanged

### Settings (optional, Phase B)

- Default structure mode: Template vs AI Structure (`defaultStructureMode` in user settings)
- Admin can hide AI Structure for restricted accounts (unlikely needed on sandbox)

### History table

- Structure column shows **“AI Structure”** instead of blank when `structure_mode = ai_free`
- Batch retry still works — lyric retry re-runs with same mode

### No new page required

Single dropdown change keeps UX familiar. Avoid a separate toggle + dropdown (two controls for one concept).

---

## 5. Provider behavior by routing

Admin AI routing slot **`lyric`** can point to:

| Provider | Structure free behavior |
|----------|-------------------------|
| **OpenAI / DeepSeek / Slai** | One-shot prompt: *“Write full song lyrics with section headers you choose…”* — skip step 2 shape |
| **Suno Lyrics API** | Prompt omits our section list; Suno returns text → accept as-is; optional light header normalization |

Title and album slots unchanged (still use description + language; structure may be omitted from title/album prompts or replaced with *“structure decided by lyric model”*).

### Suno Lyrics API constraint

`build_suno_lyrics_prompt()` is capped at **200 characters**. For AI Structure mode:

```
{description}; {language}; write lyrics with your own section headers
```

Do **not** embed section names from templates.

### Suno music submit

No change expected — already accepts arbitrary bracketed lyrics.

---

## 6. Backend changes

### API schema

**`DraftRequest` / batch create:**

```python
structure_mode: Literal["template", "ai_free"] = "template"
structure_id: UUID | None = None  # required when template; null when ai_free
```

**Validation rules:**

```python
if structure_mode == "template":
    require structure_id + bracket headers in resolved content
elif structure_mode == "ai_free":
    structure_id must be null; skip template resolution
```

### `generation_service.py`

| Function | Change |
|----------|--------|
| `submit_draft()` | Branch on `structure_mode`; allow empty `structure_headers` for `ai_free` |
| `_submit_split_draft()` | Skip step-2 shape + `assign_draft_lyrics_to_structure()` when `ai_free` |
| `_build_freeform_lyrics_user_prompt()` | **Invert** rule: headers allowed and encouraged |
| New `build_ai_structure_lyrics_system_prompt()` | Instruct model to pick sensible sections for genre/mood |
| `validate_lyrics_structure()` | New path: `validate_ai_structure_lyrics()` — min lines, ≥2 distinct sections, no exact order match |
| `build_suno_lyrics_prompt()` | Short prompt without template sections when `ai_free` |

### `batch_service.py`

| Function | Change |
|----------|--------|
| `_resolve_song_structure_ids()` | Return `None` for all songs when batch `structure_mode = ai_free` |
| `create_batch()` | Accept `structure_mode`; store on `batches` table (new column) |
| Song rows | `structure_id` nullable for ai_free |

### Database

```sql
ALTER TABLE batches ADD COLUMN structure_mode VARCHAR(20) NOT NULL DEFAULT 'template';
-- songs.structure_id already nullable in practice for some paths; enforce nullable for ai_free
```

### Bilingual lyrics

`build_section_language_plan()` today maps languages per template header.

For AI Structure:

- **Option A (recommended):** After lyrics generated, parse headers from result → build language plan dynamically
- **Option B:** Use whole-lyrics language split without per-section plan (simpler, less precise)

---

## 7. Validation rules (AI Structure mode)

Replace exact template matching with rules tuned from provider probe results (`docs/AI_STRUCTURE_FREE_PROVIDER_PROBE.md`):

| Rule | Threshold |
|------|-----------|
| Minimum total lines | ≥ 16 non-header lines |
| Section headers | ≥ 2 distinct `[Section]` types, **or** single `[Verse]` auto-wrap for plain text |
| Header format | Matches `^\[.+\]$` per line |
| First line | Must be a section header (preamble stripped) |
| Duplicate headers | Allowed (e.g. multiple `[Verse]`) |
| Exact header order | **Not enforced** — provider chooses layout |
| Plain text fallback | Wrap as `[Verse]` when ≥ 16 lines and no headers (Suno lyrics API) |

Store detected headers on song metadata (optional JSON) for history/debug:

```json
{ "detected_sections": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"] }
```

---

## 8. Desktop / API payload example

### Template mode (unchanged)

```json
{
  "description_id": "…",
  "structure_id": "…",
  "structure_mode": "template",
  "shuffle_structure": false
}
```

### AI Structure mode (new)

```json
{
  "description_id": "…",
  "structure_id": null,
  "structure_mode": "ai_free",
  "shuffle_structure": false
}
```

### camxora_python settings persistence

```json
{
  "defaultStructureMode": "ai_free",
  "defaultStructureId": null,
  "selectedStructureMode": "ai_free"
}
```

When user switches back to a named template, set `structure_mode: "template"` and restore `structure_id`.

---

## 9. Phased delivery

### PR1 — Backend flag + validation path

- `structure_mode` on draft + batch APIs
- `ai_free` lyric generation for chat providers only
- Tests: no template required, lyrics with AI headers pass validation

### PR2 — Suno lyrics + batch integration

- Suno lyric routing in `ai_free` mode
- Batch create/execute with null `structure_id`
- Bilingual plan from detected headers (Option A)

### PR3 — UI (`camxora_python`)

- `automation_card.py`: AI Structure dropdown sentinel
- `music_view.py`: payload + history display

### PR4 — Polish

- Admin analytics: % batches using AI Structure
- Lyric preview shows detected sections as chips
- Optional: “Regenerate structure only” retry action

---

## 10. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Inconsistent section quality | Keep template mode as default; describe AI Structure as advanced |
| Suno 200-char prompt too vague | Pack description + genre + “use section headers” |
| Bilingual breaks without template | Dynamic header plan after generation |
| History shows blank structure | Always display “AI Structure” label |
| Users confuse AI Structure with Shuffle | Disable shuffle when AI Structure selected; tooltip copy |

---

## 11. Copy suggestions (UI)

| Element | Text |
|---------|------|
| Dropdown option | **AI Structure** |
| Tooltip | AI writes lyrics and chooses sections (Intro, Verse, Chorus, etc.). No fixed template. |
| Readiness hint | Structure: AI Structure — no template required |
| History column | AI Structure |

---

## 12. Key files

| Area | Path |
|------|------|
| Lyric pipeline | `platform_api/services/generation_service.py` |
| Draft API | `platform_api/routers/generation.py` |
| Batch API | `platform_api/routers/batch.py`, `platform_api/services/batch_service.py` |
| Suno lyrics client | `platform_api/clients/suno_client.py` |
| AI routing | `platform_api/services/ai_routing_service.py` |
| Structure catalog | `platform_api/services/prompt_service.py` |
| Desktop UI | `camxora_python/features/music/widgets/automation_card.py` |
| Desktop batch | `camxora_python/features/music/views/music_view.py` |
| Settings | `camxora_python/shared/lib/music_settings.py` |
| Tests | `platform_api/tests/test_generation_service.py` |

---

## 13. Success criteria

- [ ] User can select **AI Structure** and run batch without choosing a template
- [ ] Chat and Suno lyric providers return lyrics with AI-chosen `[Section]` headers
- [ ] Server does **not** run shape/assign-to-template for this mode
- [ ] Suno music generation succeeds with resulting lyrics
- [ ] History and batch detail show “AI Structure”
- [ ] Template mode behavior unchanged (regression tests pass)

---

## 14. FAQ

**Q: Is this the same as removing structure from Settings?**  
No. User-owned structures in Settings remain for template mode. AI Structure is a generation mode, not a delete of the catalog.

**Q: Can we use both Shuffle and AI Structure?**  
No. Shuffle applies to template pool; disable it for AI Structure.

**Q: Does Auto-Gen Image / Suno / streaming change?**  
No. Only lyric draft phase changes. Downstream automation unchanged.

**Q: Should AI Structure cost different credits?**  
Same lyric slot credits as template mode unless we add a surcharge later (not recommended initially).
