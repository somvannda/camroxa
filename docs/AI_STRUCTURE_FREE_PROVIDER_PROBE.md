# AI Structure Free — Provider Probe Results

**Purpose:** Record how each lyric AI provider/model responds when we send **description only** (no structure template). Use these findings to keep acceptance rules stable and avoid per-provider code churn.

**Probe script:** `platform_api/scripts/probe_ai_structure_free_lyrics.py`  
**Sandbox runner:** `scripts/deploy/run_probe_ai_structure_free_sandbox.py`  
**Related spec:** `docs/AI_STRUCTURE_FREE_LYRICS.md`  
**Product scope:** [`PRODUCT_SCOPE.md`](./PRODUCT_SCOPE.md) — probe runs against **`platform_api`** providers; desktop validation via **`camxora_python`** only.

---

## 1. Test methodology

### What we send

| Field | Value |
|-------|-------|
| Description | Fixed test prompts (EDM gym + lo-fi study) |
| Structure template | **Not sent** |
| System prompt | `build_ai_structure_lyrics_system_prompt()` — asks model to choose section headers |
| User prompt | `build_ai_structure_lyrics_user_prompt()` — description only |
| Suno lyrics API | `build_suno_lyrics_prompt(structure_mode=ai_free)` — no section list |

### What we measure (per response)

| Metric | Source |
|--------|--------|
| `has_headers` | Any `[Section]` lines present |
| `header_count` | Total bracket headers |
| `distinct_section_labels` | Normalized unique section types |
| `content_line_count` | Non-header lyric lines after normalization |
| `starts_with_header` | First line is a header (no preamble) |
| `has_preamble` | Text before first header |
| `wrapped_single_verse` | Auto-wrapped plain text fallback applied |
| Pass/fail | `describe_ai_structure_validation_failure()` |

### Runs

- **2 runs per provider/model** with different descriptions to check consistency
- Skip providers with no active API keys in pool
- Results saved to `docs/AI_STRUCTURE_FREE_PROVIDER_PROBE.json`

---

## 2. Acceptance rules (derived from probe + spec)

These rules are implemented in `describe_ai_structure_validation_failure()`:

| Rule | Threshold | Rationale |
|------|-----------|-----------|
| Minimum content lines | ≥ 16 | Enough for Suno custom lyrics |
| Section headers | ≥ 2 distinct types **or** single `[Verse]` wrap | Chat models use Intro/Verse/Chorus; Suno may return plain text |
| First line | Must be `[Section]` after preamble strip | Downstream parsers expect headers first |
| Header format | `^\[.+\]$` | Matches Suno + existing template mode |
| Plain text fallback | Wrap as `[Verse]` if ≥ 16 lines and no headers | Suno lyrics API often skips headers |
| Exact header order | **Not required** in AI Structure mode | Provider chooses layout |

Re-run the probe after changing prompts or adding providers. Update section 3 when results change.

---

## 3. Probe results

**Last sandbox run:** 2026-07-17T06:21:18Z (`docs/AI_STRUCTURE_FREE_PROVIDER_PROBE.json`)

| Provider | Model | Run | Headers | Distinct sections | Content lines | Preamble | Pass | Notes |
|----------|-------|-----|---------|-------------------|---------------|----------|------|-------|
| openai | gpt-4o-mini | 1–2 | 7–8 | bridge, chorus, intro, outro, verse 1, verse 2 | 26–30 | no | PASS | Bracket headers, no preamble |
| openai | gpt-4o | 1–2 | 6–9 | bridge, chorus, drop, intro, outro, pre-chorus, verse 1, verse 2 | 24–34 | no | PASS | |
| openai | gpt-4-turbo | 1–2 | 8–10 | bridge, chorus, intro, outro, pre-chorus, verse 1, verse 2 | 30–34 | no | PASS | |
| deepseek | deepseek-chat | 1–2 | 7–10 | bridge, chorus, drop, intro, outro, pre-chorus, verse | 25–40 | no | PASS | |
| deepseek | deepseek-reasoner | 1–2 | 7–11 | bridge, chorus, drop, intro, outro, pre-chorus, verse 1, verse 2 | 32–42 | no | PASS | |
| slai | xiaomi/mimo-v2.5-pro | 1–2 | 7–11 | bridge, chorus, intro, outro, pre-chorus, verse 1, verse 2 | 35–55 | no | PASS | Requires `PLATFORM_SLAI_API_BASE_URL` + streaming |
| slai | gpt-5.6-sol | 1–2 | 7–11 | bridge, chorus, intro, outro, pre-chorus, verse 1, verse 2 | 46–64 | no | PASS | ~19s per run (SLAI streaming) |
| slai | gpt-5.6-terra | 1–2 | 8–11 | bridge, chorus, intro, outro, pre-chorus, verse 1, verse 2 | 32–60 | no | PASS | |
| slai | gpt-5.6-tuna | 1–2 | — | — | — | — | ERROR | SLAI API returns **404** — model id not available upstream yet |
| suno | lyrics | 1–2 | 8–9 | bridge, chorus, final chorus, intro, pre-chorus, verse 1, verse 2 | 56–64 | no | PASS | Suno lyrics API with bracket headers |

**Summary:** OpenAI, DeepSeek, and three SLAI text models (`mimo-v2.5-pro`, `gpt-5.6-sol`, `gpt-5.6-terra`) pass validation. Suno lyrics API passes on both runs. `gpt-5.6-tuna` is registered but SLAI upstream returns 404 — confirm the model id with SLAI before routing production traffic.

Re-run after deploy:

```bash
python scripts/deploy/run_probe_ai_structure_free_sandbox.py
```

### Observed patterns (sandbox)

| Provider | Behavior |
|----------|----------|
| OpenAI / DeepSeek | Bracket headers (`[Verse]`, `[Chorus]`, ...), 7–12 headers, no preamble |
| Suno Lyrics API | Bracket headers on success; occasional transient Suno API errors |
| Slai | Bracket headers when auth + base URL are configured; lyric calls must use **streaming** (`stream: true`) or SLAI's bridge times out (~6s) with 504 |

### Slai sandbox setup (ops)

Earlier probe runs showed **HTTP 401** because sandbox `platform_api/.env` lacked `PLATFORM_SLAI_API_BASE_URL`. Without it, SLAI pool keys were sent to the DeepSeek client URL. Fix:

1. Set `PLATFORM_SLAI_API_BASE_URL=https://api.slai.shop` in sandbox `.env` (included in `restore_sandbox_env.py` / `camxora-sandbox-remote.sh`).
2. Ensure the SLAI key in the admin key pool is active (keys live in DB, not `.env`).
3. SLAI text models use `stream: true` in registry `extra_payload` — non-streaming lyric prompts hit SLAI `api_bridge_timeout` (504).

`gpt-5.6-tuna`: registered as text-only; probe blocked until SLAI exposes this model id (404 from upstream).

---

## 4. When to adjust rules

Change acceptance thresholds only when:

1. Probe shows **consistent** provider output that fails validation but works in Suno music generation
2. A provider changes behavior (re-run probe quarterly or after routing changes)
3. User reports false rejections for a specific routed model

Do **not** add per-provider branching in production code unless probe proves a provider cannot meet shared rules.

---

## 5. JSON artifact schema

```json
{
  "generated_at": "ISO-8601",
  "runs_per_model": 2,
  "test_descriptions": ["..."],
  "results": [
    {
      "provider": "deepseek",
      "model": "deepseek-chat",
      "run": 1,
      "status": "PASS|FAIL|ERROR",
      "analysis": { "header_count": 5, "distinct_section_labels": ["chorus", "verse"] },
      "validation_error": null,
      "raw_preview": "...",
      "normalized_preview": "..."
    }
  ]
}
```
