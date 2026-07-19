# AI Architecture

This document describes how CAMXORA routes AI work from admin configuration to provider HTTP calls. The goal is **provider/purpose separation**: adding a model should be a registry change, not a rewrite of business logic.

## Layer overview

```
Admin AI Routing (per operation)
        ↓
AIRoutingService.resolve(operation)
        ↓
Purpose handler (prompt + expected response shape)
        ↓
Provider gateway (text or image)
        ↓
Model registry (ids, aliases, quirks)
        ↓
HTTP client (OpenAI-compatible, FAL, SLAI, Suno, CALA)
```

| Layer | Location | Responsibility |
|---|---|---|
| Types & operations | `platform_api/ai/types.py` | `Operation`, `ServiceType`, defaults |
| Model registry | `platform_api/ai/registry.py` | Model specs, aliases, cost tiers, FAL API ids |
| Routing | `platform_api/services/ai_routing_service.py` | Resolve operation → provider + model |
| Parsing | `platform_api/ai/parsing/response_parser.py` | Markdown fences, JSON recovery (all providers) |
| Text gateway | `platform_api/ai/providers/text/gateway.py` | openai / deepseek / slai chat |
| Image gateway | `platform_api/ai/providers/image/gateway.py` | openai / fal / slai / cala images |
| Purposes | `platform_api/ai/purposes/` | Draft routing, channel text, channel generation |

## Operations (admin slots)

| Operation | Service type | Wired in |
|---|---|---|
| `channel_name` | text | Channel setup |
| `channel_description` | text | Channel setup |
| `channel_keywords` | text | Channel setup |
| `channel_tags` | text | Channel setup |
| `lyric` | text | Draft, polish, batch |
| `title` | text | Draft (split mode when assignment differs from lyric) |
| `album` | text | Draft (split mode when assignment differs from lyric) |
| `channel_logo` | image | Channel setup |
| `channel_cover` | image | Channel setup |
| `background_image` | image | Generation, batch, image jobs |
| `thumbnail_image` | image | Generation, image jobs |
| `music` | music | Suno generation, batch |

## Adding a new model (existing provider)

Edit **`platform_api/ai/registry.py`** only.

### Text example (OpenAI)

```python
OPENAI_TEXT_MODELS["gpt-4.1"] = ModelSpec(
    api_id="gpt-4.1",
    supports_json_mode=True,
    cost_tier="~$0.01/1K",
)
```

`PROVIDER_SUB_MODELS` and admin dropdowns update automatically.

After adding a model, click **Admin → Credits → Seed from registry** (or run
`python -m platform_api.scripts.seed_model_costs`). This **adds missing** model
cost rows only; existing manual costs and all credit pricing are kept unless you
use **Refresh estimates** (overwrite).

Then use **Seed missing pricing** to create **needs-review** credit pricing rows
only for registry catalog pairs not yet in the pricing table. Existing pricing
is never overwritten. **Auto-generate (routing)** is separate — it only covers
pairs required by AI routing assignments.

### Local desktop ops (video / merge)

Video export and auto-merge are not AI providers. Defaults live in
`platform_api/services/local_platform_operations.py` and seed as:

- `ai_model_costs`: `local` / `video` and `local` / `video_merge` at **$0 COGS**
- `credit_pricing`: **3** and **10** display credits list price (COGS 0)

**Seed from registry** restores missing local rows without touching your other
pricing. Use **Auto-generate pricing** only for AI routing pairs (margin-based).

### SLAI text with quirks (e.g. MiMo)

```python
SLAI_TEXT_MODELS["xiaomi/mimo-v2.5-pro"] = ModelSpec(
    api_id="xiaomi/mimo-v2.5-pro",
    aliases=("mimo-v2.5-pro",),
    supports_json_mode=False,
    extra_payload={
        "stream": False,
        "thinking": {"type": "disabled"},
    },
    cost_tier="SLAI",
)
```

### FAL image

```python
FAL_IMAGE_MODELS["flux-2"] = ModelSpec(
    api_id="fal-ai/flux/v2",
    cost_tier="~$0.04/img",
)
```

`resolve_fal_api_model_id()` maps admin ids to fal.ai endpoints via `ModelSpec.api_id`.

## Adding a new provider

1. Add HTTP client under `platform_api/clients/` (if needed).
2. Register capabilities in `platform_api/ai/types.py` → `PROVIDER_CAPABILITIES`.
3. Add model map in `platform_api/ai/registry.py`.
4. Extend the appropriate gateway (`text/gateway.py` or `image/gateway.py`).
5. Add key-pool provider name and admin pricing.

Purpose handlers and routers should **not** need changes unless the API shape is fundamentally different.

## Adding a new purpose (new operation)

1. Add `Operation` enum value in `platform_api/ai/types.py`.
2. Map it in `OPERATION_SERVICE_TYPE`.
3. Create a purpose module under `platform_api/ai/purposes/`.
4. Wire router/service to call `AIRoutingService.resolve("<operation>")`.
5. Expose the slot in admin AI routing UI.

## Draft generation modes

| Mode | When | Behavior |
|---|---|---|
| Combined | `title`, `album`, and `lyric` use the same provider+model | One JSON call: `{title, album, lyrics}` |
| Split | Any of the three assignments differ | Three calls via each slot's routing |

Split mode is automatic; no admin toggle required.

## Response parsing rules

- All text purposes use `response_parser.py` (never provider-specific parsing in routers).
- JSON mode is enabled via `json_response_format()` when the model supports it.
- `TextProviderGateway` retries without `json_object` on HTTP 400 from OpenAI-compatible APIs.
- Channel keywords/tags accept JSON objects, arrays, or loose comma/newline lists.

## Key files (quick reference)

```
platform_api/ai/
  registry.py                 # ← add models here
  types.py
  parsing/response_parser.py
  providers/text/gateway.py
  providers/image/
    gateway.py
    openai.py
  purposes/
    channel_generation.py     # generate_channel_text()
    channel_text.py           # parse_* helpers
    draft_routing.py          # title/album/lyric split detection

platform_api/services/
  ai_routing_service.py
  generation_service.py       # uses text + image gateways
  image_dispatch.py           # thin wrapper over image gateway
```

## Testing

- `platform_api/tests/test_ai_layer.py` — parsing, registry, draft routing
- `platform_api/tests/test_generation_service.py` — draft, suno, image flows
- `platform_api/tests/test_channel_setup_router.py` — channel setup endpoints

After registry or gateway changes, run:

```bash
cd platform_api
python -m pytest tests/test_ai_layer.py tests/test_generation_service.py tests/test_channel_setup_router.py -q
```

## Restart required

Restart the **platform API** after changing Python AI modules so routing and gateways reload.
