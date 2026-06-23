# Requirements Document

## Introduction

The AI Service Switcher enables admins to configure which AI provider handles each operation type (music generation, text/LLM operations, image generation) through the admin portal. The platform API dynamically routes requests to the configured provider based on admin settings, removing hardcoded provider logic from the generation service. Providers are populated from the Key Pool — only providers with active keys for a given operation type appear as selectable options. Switching is seamless: no code changes required, credit pricing automatically adjusts since it is already keyed by (ai_service, operation_type).

## Glossary

- **Platform_API**: The FastAPI backend service that handles authentication, credit management, and proxied access to external AI services.
- **Admin_Portal**: The React SPA for managing platform configuration, including AI service routing.
- **Generation_Service**: The platform API service class that orchestrates AI generation requests with credit management.
- **Key_Pool**: The system managing encrypted API keys per provider, with selection strategies (round-robin, priority) and automatic failover.
- **Operation_Type**: A category of AI work the platform performs — one of music_generation, image_generation, or text_generation.
- **Active_Provider**: A provider entry in the Key Pool that has at least one key with status "active" for the given operation type.
- **Service_Routing_Config**: A system_settings entry that maps an operation_type to its currently active ai_service provider.
- **Provider_Capability**: A mapping that defines which providers can handle which operation types.
- **Fallback_Provider**: A secondary provider configured per operation type that the system uses when the primary provider is unavailable.
- **Desktop_App**: The PyQt6 desktop application (python_app) that calls the Platform_API for all AI operations.

## Requirements

### Requirement 1: Provider Routing Configuration Storage

**User Story:** As an admin, I want the platform to store which AI provider is assigned to each operation type, so that routing decisions are driven by configuration rather than hardcoded logic.

#### Acceptance Criteria

1. THE Platform_API SHALL store a Service_Routing_Config entry in the system_settings table for each Operation_Type (music_generation, image_generation, text_generation).
2. WHEN no Service_Routing_Config exists for an Operation_Type, THE Platform_API SHALL use the current default provider (suno for music_generation, deepseek for text_generation, slai for image_generation).
3. THE Platform_API SHALL validate that a Service_Routing_Config value references a provider defined in the AIService enum.
4. THE Platform_API SHALL reject a Service_Routing_Config update that assigns a provider with zero active keys in the Key_Pool for the target Operation_Type.

### Requirement 2: Provider Capability Registry

**User Story:** As an admin, I want to see which providers support which operation types, so that I only assign capable providers to each operation.

#### Acceptance Criteria

1. THE Platform_API SHALL maintain a Provider_Capability mapping that defines supported operation types per provider: suno supports music_generation; deepseek supports text_generation; openai supports text_generation; slai supports image_generation and text_generation; fal supports image_generation.
2. WHEN an admin attempts to assign a provider to an Operation_Type the provider does not support, THE Platform_API SHALL reject the request with a descriptive error message.
3. THE Platform_API SHALL expose a read-only endpoint that returns the Provider_Capability mapping for use by the Admin_Portal.

### Requirement 3: Dynamic Request Routing

**User Story:** As a platform operator, I want the generation service to route requests to the configured provider at runtime, so that switching providers requires only an admin configuration change.

#### Acceptance Criteria

1. WHEN the Generation_Service receives a text_generation request, THE Generation_Service SHALL resolve the active provider from the Service_Routing_Config for text_generation and route the request to that provider's client.
2. WHEN the Generation_Service receives a music_generation request, THE Generation_Service SHALL resolve the active provider from the Service_Routing_Config for music_generation and route the request to that provider's client.
3. WHEN the Generation_Service receives an image_generation request, THE Generation_Service SHALL resolve the active provider from the Service_Routing_Config for image_generation and route the request to that provider's client.
4. THE Generation_Service SHALL resolve the Service_Routing_Config at request time, not at service initialization, so that config changes take effect without restarting the server.
5. WHEN the resolved provider has entries in the Key_Pool, THE Generation_Service SHALL route the request through the KeyPoolClientWrapper for that provider.

### Requirement 4: Fallback Provider Configuration

**User Story:** As an admin, I want to configure a fallback provider per operation type, so that requests automatically reroute when the primary provider is unavailable.

#### Acceptance Criteria

1. THE Platform_API SHALL support an optional Fallback_Provider setting per Operation_Type stored in system_settings.
2. WHEN the primary provider returns an ExternalServiceError or has no available keys, THE Generation_Service SHALL attempt the same request using the Fallback_Provider.
3. IF no Fallback_Provider is configured and the primary provider fails, THEN THE Generation_Service SHALL raise the original error to the caller.
4. THE Platform_API SHALL validate that the Fallback_Provider is different from the primary provider and supports the target Operation_Type.
5. THE Generation_Service SHALL attempt the fallback at most once per request to prevent cascading failures.

### Requirement 5: Admin Portal Service Switcher UI

**User Story:** As an admin, I want a dedicated UI page to view and switch the active AI provider for each operation type, so that I can manage routing without database access.

#### Acceptance Criteria

1. THE Admin_Portal SHALL display a Service Switcher page showing all three operation types with their currently configured primary provider and optional fallback provider.
2. WHEN the admin selects a new provider for an operation type, THE Admin_Portal SHALL present only providers that have active keys in the Key_Pool and support the target Operation_Type.
3. WHEN the admin confirms a provider switch, THE Admin_Portal SHALL call the Platform_API to update the Service_Routing_Config and display a success confirmation.
4. THE Admin_Portal SHALL display the current availability status (available, degraded, unavailable) for each listed provider based on Key_Pool health data.
5. IF the admin attempts to switch to a provider with "unavailable" status, THEN THE Admin_Portal SHALL display a warning and require explicit confirmation before proceeding.

### Requirement 6: Model Selection Within Provider

**User Story:** As an admin, I want to configure which specific model to use within a provider, so that I can select between model variants (e.g., gpt-5.5-pro vs gpt-5.5 on OpenAI).

#### Acceptance Criteria

1. THE Platform_API SHALL store an optional model identifier alongside each Service_Routing_Config entry in system_settings.
2. WHEN no model identifier is configured, THE Generation_Service SHALL use the provider's default model (deepseek-chat for deepseek, cgpt-web for slai, gpt-5.5 for openai).
3. WHEN a model identifier is configured, THE Generation_Service SHALL pass the configured model to the provider client for text_generation and image_generation requests.
4. THE Admin_Portal SHALL display a model selection input for each provider assignment, pre-filled with the provider's default model.

### Requirement 7: Credit Pricing Integration

**User Story:** As a platform operator, I want credit pricing to automatically reflect the active provider, so that users are charged correctly when providers are switched.

#### Acceptance Criteria

1. WHEN the Generation_Service resolves the active provider for a request, THE Generation_Service SHALL look up credit pricing using the resolved provider's ai_service and the request's operation_type.
2. IF no pricing entry exists for the resolved (ai_service, operation_type) combination, THEN THE Platform_API SHALL reject the request with a descriptive error indicating missing pricing configuration.
3. THE Admin_Portal SHALL display a notice on the Service Switcher page when a provider assignment lacks a corresponding credit pricing entry.

### Requirement 8: Service Switcher API Endpoints

**User Story:** As a frontend developer, I want well-defined API endpoints for reading and updating provider routing configuration, so that the Admin_Portal can manage the switcher.

#### Acceptance Criteria

1. THE Platform_API SHALL expose a GET endpoint that returns the current Service_Routing_Config for all operation types, including primary provider, fallback provider, model identifier, and provider availability status.
2. THE Platform_API SHALL expose a PUT endpoint that accepts an operation_type, primary provider, optional fallback provider, and optional model identifier, and updates the Service_Routing_Config after validation.
3. WHEN the PUT endpoint receives an invalid request (unsupported provider, capability mismatch, no active keys), THE Platform_API SHALL return a 422 response with specific validation error details.
4. THE Platform_API SHALL restrict both endpoints to admin-authenticated users only.

### Requirement 9: In-Progress Request Safety

**User Story:** As a platform operator, I want provider switches to be safe for in-progress operations, so that active requests complete successfully even when an admin changes the routing mid-operation.

#### Acceptance Criteria

1. WHEN an admin updates the Service_Routing_Config while requests are in progress, THE Generation_Service SHALL complete in-progress requests using the provider that was resolved at the start of each request.
2. THE Generation_Service SHALL resolve the provider once at the beginning of a request and use that provider for the entire request lifecycle including retries within that request.
3. WHEN a Suno music_generation request is in progress (callback-based, long-running), THE Platform_API SHALL continue processing callbacks from the original provider regardless of subsequent config changes.

### Requirement 10: Provider Health Visibility

**User Story:** As an admin, I want to see the health status and key availability of each provider on the switcher page, so that I can make informed routing decisions.

#### Acceptance Criteria

1. THE Platform_API SHALL expose provider health data including total keys, active keys, and availability status (available, degraded, unavailable) per provider via the service switcher GET endpoint.
2. THE Admin_Portal SHALL display a health indicator (color-coded badge) next to each provider showing its current availability status.
3. WHEN a provider's status changes to "unavailable", THE Admin_Portal SHALL visually distinguish that provider in the selection list and display a tooltip explaining the unavailability reason.
