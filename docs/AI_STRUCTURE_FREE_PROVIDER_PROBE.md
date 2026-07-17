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

**Last sandbox run:** 2026-07-17T04:42:31Z (`docs/AI_STRUCTURE_FREE_PROVIDER_PROBE.json`)

| Provider | Model | Run | Headers | Distinct sections | Content lines | Preamble | Pass | Notes |
|----------|-------|-----|---------|-------------------|---------------|----------|------|-------|
| openai | gpt-4o-mini | 1 | 8 | bridge, chorus, intro, outro, verse 1, verse 2 | 30 | no | PASS | Bracket headers, no preamble |
| openai | gpt-4o-mini | 2 | 7 | bridge, chorus, intro, outro, verse 1, verse 2 | 26 | no | PASS | Consistent layout |
| openai | gpt-4o | 1 | 10 | bridge, chorus, drop, intro, outro, pre-chorus, verse 1, verse 2 | 30 | no | PASS | EDM prompt |
| openai | gpt-4o | 2 | 7 | bridge, chorus, intro, outro, verse 1, verse 2 | 26 | no | PASS | Lo-fi prompt |
| openai | gpt-4-turbo | 1 | 10 | bridge, chorus, intro, outro, pre-chorus, verse 1, verse 2 | 34 | no | PASS | |
| openai | gpt-4-turbo | 2 | 8 | bridge, chorus, intro, outro, verse 1, verse 2, verse 3 | 30 | no | PASS | |
| deepseek | deepseek-chat | 1 | 10 | bridge, chorus, drop, intro, outro, pre-chorus, verse | 36 | no | PASS | |
| deepseek | deepseek-chat | 2 | 7 | bridge, chorus, intro, outro, verse 1, verse 2 | 24 | no | PASS | |
| deepseek | deepseek-reasoner | 1 | 12 | bridge, chorus, drop, intro, outro, pre-chorus, verse 1, verse 2 | 38 | no | PASS | |
| deepseek | deepseek-reasoner | 2 | 7 | bridge, chorus, intro, outro, verse 1, verse 2 | 23 | no | PASS | |
| slai | xiaomi/mimo-v2.5-pro | 1 | — | — | — | — | ERROR | HTTP 401 on chat completion (sandbox key) |
| slai | xiaomi/mimo-v2.5-pro | 2 | — | — | — | — | ERROR | HTTP 401 on chat completion (sandbox key) |
| suno | lyrics | 1 | 9 | bridge, chorus, final chorus, intro, pre-chorus, verse 1, verse 2 | 70 | no | PASS | Suno lyrics API with bracket headers |
| suno | lyrics | 2 | 8 | bridge, chorus, final chorus, pre-chorus, verse 1, verse 2 | 52 | no | PASS | Both runs passed on latest probe |

**Summary:** OpenAI and DeepSeek chat models consistently return bracket section headers with at least 16 content lines and no preamble. Suno lyrics API returned headers on both runs in the latest probe (an earlier run hit a transient Suno rephrase error). Slai probe failed with **401** — verify the sandbox Slai pool key before treating Slai as validated.

Re-run after deploy:

```bash
python scripts/deploy/run_probe_ai_structure_free_sandbox.py
```

### Observed patterns (sandbox)

| Provider | Behavior |
|----------|----------|
| OpenAI / DeepSeek | Bracket headers (`[Verse]`, `[Chorus]`, ...), 7-12 headers, no preamble |
| Suno Lyrics API | Bracket headers on success; occasional transient Suno API errors |
| Slai | Not validated — 401 auth failure on sandbox |

### Slai sandbox key refresh (manual)

If Slai rows show **HTTP 401** after `run_probe_ai_structure_free_sandbox.py`, refresh the Slai API key in the sandbox provider pool (admin portal or DB `provider_keys`) before re-running the probe. This does not block other providers; treat Slai as optional until the key is renewed.

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
