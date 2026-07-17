# Requirements Document

## Introduction

This feature creates a clear service-based AI model routing system. Operations are grouped into service types (text generation, image generation). Each operation is assigned to a specific AI model via the Settings page. When a request comes in, the platform API resolves which AI model handles it, dispatches the request, and charges credits based on the configured pricing for that AI model + service type on the Credits page.

## Glossary

- **Service_Type**: A category of AI work — either `text_generation` or `image_generation`.
- **Operation**: A specific task performed by the platform. Each operation belongs to one Service_Type.
- **AI_Model**: A provider in the Key Pool (DeepSeek, OpenAI, FAL, SLAI, Suno) that can perform one or more Service_Types.
- **Assignment**: A stored mapping of an operation → AI_Model (+ optional sub-model). Lives in `system_settings`.
- **Credit_Pricing**: The existing `credit_pricing` table entry keyed by (ai_service, operation_type) that defines how many credits to charge. Already managed on the Credits page.

## Requirements

### Requirement 1: Service Type Registry

**User Story:** As an admin, I want a clear registry of what service types exist and which operations belong to each, so the system is organized and predictable.

#### Acceptance Criteria

1. THE Platform_API SHALL define three service types: `text_generation`, `image_generation`, and `music_generation`.
2. THE `text_generation` service type SHALL include the operations: `channel_name`, `channel_description`, `channel_keywords`, `channel_tags`, `lyric`, `title`, `album`.
3. THE `image_generation` service type SHALL include the operations: `channel_logo`, `channel_cover`, `background_image`, `thumbnail_image`.
4. THE `music_generation` service type SHALL include the operation: `music`.
5. THE Platform_API SHALL store this registry as code constants (not database) since the operations are fixed and known at build time.

### Requirement 2: AI Model Capabilities

**User Story:** As an admin, I want to know which AI models can handle which service types, so I only see valid choices when assigning models.

#### Acceptance Criteria

1. THE Platform_API SHALL define these model-to-service-type mappings: DeepSeek supports `text_generation`; OpenAI supports `text_generation` and `image_generation`; FAL supports `image_generation`; SLAI supports `text_generation` and `image_generation`; Suno supports `music_generation` and `text_generation` (lyric only).
2. THE Platform_API SHALL define sub-model options per provider: OpenAI text has `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`; OpenAI image has `dall-e-3`, `dall-e-2`; FAL image has `flux-pro`, `flux-dev`, `flux-schnell`; DeepSeek text has `deepseek-chat`, `deepseek-reasoner`; SLAI has no sub-models (single default).
3. THE admin UI SHALL only show models that support the service type required by the operation being configured.
4. THE admin UI SHALL only show models that have at least one key in the Key Pool.

### Requirement 3: Operation Assignment (Settings Page)

**User Story:** As an admin, I want a simple page in Settings where I assign one AI model per operation, so I can switch providers easily.

#### Acceptance Criteria

1. THE Admin_Portal Settings page SHALL have an "AI Routing" section (or tab) listing all operations grouped by service type.
2. EACH operation SHALL display: a label (e.g., "Channel Name"), a provider dropdown, and an optional sub-model dropdown when the selected provider has multiple models.
3. WHEN no assignment exists, THE dropdown SHALL show the default: DeepSeek for text operations, FAL for image operations.
4. THE page SHALL have one "Save" button that persists all assignments to `system_settings` atomically.
5. THE page SHALL NOT include any credit pricing fields. A small note SHALL say "Credit costs are configured on the Credits page" with a link.

### Requirement 4: Backend Request Routing

**User Story:** As a developer, I want the platform API to automatically route requests to the assigned AI model, so admin changes take effect immediately.

#### Acceptance Criteria

1. WHEN the platform API receives a generation request, it SHALL read the assignment for that operation from `system_settings` and dispatch to the correct provider client (llm_client for DeepSeek/OpenAI text, fal_client for FAL, slai_client for SLAI).
2. IF a sub-model is assigned, THE API SHALL pass it to the provider client (e.g., `model="gpt-4o-mini"` or `model_id="fal-ai/flux/pro"`).
3. IF no assignment exists for an operation, THE API SHALL use the default provider (DeepSeek for text, FAL for image).
4. IF the assigned provider has no active keys at request time, THE API SHALL return HTTP 503 with a clear error message.
5. THE channel_setup router (`/channel-setup/*` endpoints) SHALL resolve the provider from assignments instead of hardcoding `"deepseek"` for text and `"slai"` for images.
6. THE generation router (`/generation/image` endpoint) SHALL resolve the provider from assignments for `background_image` and `thumbnail_image` operations, overriding any client-supplied `provider` field.

### Requirement 5: Credit Pricing Connection

**User Story:** As an admin, I want credit charges to automatically reflect whichever AI model I've assigned, with per-operation granularity on the Credits page.

#### Acceptance Criteria

1. THE Credits page "Operation Type" dropdown SHALL be updated to include all specific operations: `channel_name`, `channel_description`, `channel_keywords`, `channel_tags`, `channel_logo`, `channel_cover`, `lyric`, `title`, `album`, `background_image`, `thumbnail_image`, `music`.
2. THE `credit_pricing` table SHALL store entries keyed by (ai_service, operation) — for example: `(deepseek, channel_name)`, `(fal, channel_logo)`, `(openai, lyric)`.
3. WHEN charging credits for a generation, THE Platform_API SHALL look up the `credit_pricing` entry using the resolved provider as `ai_service` AND the specific operation name as `operation_type`.
4. For example: if `channel_name` is assigned to OpenAI → credits are looked up as `(openai, channel_name)`. If switched to DeepSeek → lookup becomes `(deepseek, channel_name)`.
5. IF no `credit_pricing` entry exists for the (provider, operation) pair, THE Platform_API SHALL charge zero credits and log a warning.
6. THE old generic operation types (`text_generation`, `image_generation`, `channel_setup`) SHALL be replaced by the specific operation names in the dropdown. Existing pricing entries with old types remain valid but are superseded by specific entries when both exist.

### Requirement 6: API Endpoints

**User Story:** As a frontend developer, I want endpoints to read/write assignments and discover available models.

#### Acceptance Criteria

1. `GET /api/v1/admin/ai-routing` SHALL return the current assignment for every operation, including which provider and sub-model (if any) is configured, grouped by service type.
2. `PUT /api/v1/admin/ai-routing` SHALL accept a full set of assignments and persist them atomically.
3. `GET /api/v1/admin/ai-routing/providers` SHALL return available providers per service type, each with their sub-model options, filtered to only those with active keys in the Key Pool.
