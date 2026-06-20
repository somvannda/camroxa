# Requirements Document

## Introduction

The Admin Portal is a standalone React web application that provides a comprehensive management interface for the Platform API. It enables administrators to manage users, licenses, plans, credits, music prompts, rate limits, and monitor system health — all through a modern UI built with shadcn/ui components, Lucide icons, and a deep blue color theme. The portal communicates with the existing Platform API backend (FastAPI) via its authenticated Admin endpoints.

## Glossary

- **Admin_Portal**: The React web application providing administrative management capabilities for the Platform API
- **Platform_API**: The existing FastAPI backend service that exposes admin-authenticated REST endpoints
- **Dashboard**: The main landing page of the Admin Portal showing system health, key metrics, and recent activity
- **Data_Table**: A paginated, sortable, filterable table component used to display collections of records
- **Auth_Module**: The module responsible for admin login, JWT token management, and session persistence
- **Navigation_Shell**: The persistent sidebar and top bar layout providing navigation between portal sections
- **Toast_Notification**: A brief, non-blocking message displayed to confirm action success or report errors

## Requirements

### Requirement 1: Authentication and Session Management

**User Story:** As an admin, I want to log in with my Platform API credentials and maintain a persistent session, so that I can securely access the admin portal without repeated logins.

#### Acceptance Criteria

1. WHEN an admin submits valid email and password credentials, THE Auth_Module SHALL authenticate against the Platform API `/api/v1/auth/login` endpoint and store the returned JWT access token and refresh token
2. WHEN the stored access token expires, THE Auth_Module SHALL automatically request a new access token using the refresh token via `/api/v1/auth/refresh`
3. IF the refresh token request fails (401 response), THEN THE Auth_Module SHALL clear all stored tokens and redirect the admin to the login page
4. WHILE the admin is not authenticated, THE Admin_Portal SHALL restrict access to all pages except the login page
5. WHEN the admin clicks the logout button, THE Auth_Module SHALL call the `/api/v1/auth/logout` endpoint, clear stored tokens, and redirect to the login page
6. THE Auth_Module SHALL store tokens in memory with the refresh token in an httpOnly-equivalent secure storage mechanism

### Requirement 2: Navigation and Layout Shell

**User Story:** As an admin, I want a persistent sidebar navigation with clear section labels, so that I can quickly move between different management areas.

#### Acceptance Criteria

1. THE Navigation_Shell SHALL display a collapsible sidebar with navigation links to: Dashboard, Users, Licenses, Plans, Credits, Music Prompts, Rate Limits, and Audit Log
2. THE Navigation_Shell SHALL use Lucide icons alongside each navigation label for visual identification
3. THE Navigation_Shell SHALL highlight the currently active section in the sidebar
4. THE Navigation_Shell SHALL display the logged-in admin's email and a logout button in the top bar
5. THE Navigation_Shell SHALL apply the shadcn deep blue theme consistently across all pages with dark backgrounds (slate-900/950) and blue accent colors
6. WHEN the sidebar is collapsed, THE Navigation_Shell SHALL display only icons with tooltips showing the section name on hover

### Requirement 3: Dashboard Overview

**User Story:** As an admin, I want a dashboard showing system health and key metrics at a glance, so that I can quickly assess the platform's status.

#### Acceptance Criteria

1. WHEN the Dashboard page loads, THE Admin_Portal SHALL fetch and display the Platform API health status from `GET /health`
2. WHEN the Dashboard page loads, THE Admin_Portal SHALL fetch and display the external Suno API credit balance from `GET /api/v1/admin/suno-balance`
3. THE Dashboard SHALL display health status using color-coded indicators: green for healthy, yellow for degraded, red for unhealthy
4. THE Dashboard SHALL display summary metric cards for: total users, active licenses, Suno balance, and system health status
5. WHEN a health service shows degraded or unhealthy status, THE Dashboard SHALL display which specific services are affected

### Requirement 4: User Management

**User Story:** As an admin, I want to view, search, and manage user accounts, so that I can handle account issues and maintain the user base.

#### Acceptance Criteria

1. WHEN the Users page loads, THE Admin_Portal SHALL fetch and display a paginated user list from `GET /api/v1/users` with default page size of 25
2. THE Data_Table SHALL support filtering users by status (active, suspended, deleted) and registration date range
3. WHEN an admin clicks a user row, THE Admin_Portal SHALL display user details including email, display name, role, status, and registration date
4. WHEN an admin submits a user update form, THE Admin_Portal SHALL send a PATCH request to `/api/v1/users/{id}` with the updated fields (display_name, role)
5. WHEN an admin confirms a user suspension, THE Admin_Portal SHALL send a POST request to `/api/v1/users/{id}/suspend` with the provided reason
6. WHEN an admin confirms user reactivation, THE Admin_Portal SHALL send a POST request to `/api/v1/users/{id}/reactivate`
7. WHEN an admin confirms user deletion, THE Admin_Portal SHALL display a confirmation dialog and then send a DELETE request to `/api/v1/users/{id}`
8. IF a user management API call returns an error, THEN THE Admin_Portal SHALL display the error message in a Toast_Notification without navigating away from the page

### Requirement 5: License Management

**User Story:** As an admin, I want to create, assign, and revoke licenses, so that I can control user access to platform features.

#### Acceptance Criteria

1. WHEN the admin submits the create license form with a selected plan, THE Admin_Portal SHALL send a POST request to `/api/v1/licenses` with the plan_id
2. WHEN the admin submits the assign license form, THE Admin_Portal SHALL send a POST request to `/api/v1/licenses/{id}/assign` with the target user_id
3. WHEN the admin confirms license revocation, THE Admin_Portal SHALL send a POST request to `/api/v1/licenses/{id}/revoke`
4. THE Admin_Portal SHALL display license details including: license key, associated plan, assigned user, status, activation date, and expiration date
5. IF a license operation returns a 409 conflict (duplicate plan), THEN THE Admin_Portal SHALL display a clear error message indicating the user already has an active license for that plan type

### Requirement 6: Plan Configuration

**User Story:** As an admin, I want to view and modify subscription plans and manage promotional offers, so that I can control pricing and quotas.

#### Acceptance Criteria

1. WHEN the Plans page loads, THE Admin_Portal SHALL fetch and display all plans from `GET /api/v1/plans` showing name, price, profile allowance, monthly quota, daily limit, and active status
2. WHEN an admin submits plan updates, THE Admin_Portal SHALL send a PATCH request to `/api/v1/plans/{id}` with only the changed fields
3. THE Admin_Portal SHALL validate plan form inputs client-side: price_cents >= 0, profile_allowance >= 1, monthly_song_quota >= 0, billing_cycle_days >= 1
4. WHEN the Offers section loads, THE Admin_Portal SHALL fetch and display active promotional offers from `GET /api/v1/plans/offers`
5. WHEN an admin creates a new offer, THE Admin_Portal SHALL send a POST request to `/api/v1/plans/offers` with plan_id, promo_price_cents, and max_redemptions
6. THE Admin_Portal SHALL display offer progress (current_redemptions / max_redemptions) as a visual progress indicator

### Requirement 7: Credit System Management

**User Story:** As an admin, I want to manage credit pricing, view credit packs, and adjust user balances, so that I can control the platform's monetization.

#### Acceptance Criteria

1. WHEN the Credit Pricing section loads, THE Admin_Portal SHALL fetch and display all pricing entries from `GET /api/v1/credits/pricing` showing model, operation type, credits per operation, external cost, and margin
2. WHEN an admin creates a new pricing entry, THE Admin_Portal SHALL send a POST request to `/api/v1/credits/pricing` with model_identifier, operation_type, credits_per_operation, and external_cost_cents
3. WHEN an admin updates a pricing entry, THE Admin_Portal SHALL send a PUT request to `/api/v1/credits/pricing` with the full updated record
4. WHEN the Credit Packs section loads, THE Admin_Portal SHALL fetch and display available packs from `GET /api/v1/credits/packs`
5. WHEN an admin submits a balance adjustment, THE Admin_Portal SHALL send a POST request to `/api/v1/credits/adjust` with user_id, amount (positive or negative integer), and reason
6. THE Admin_Portal SHALL validate that adjustment amount is non-zero and reason is provided before submitting
7. IF a pricing creation returns 409 (duplicate entry), THEN THE Admin_Portal SHALL display an error indicating the model/operation combination already exists

### Requirement 8: Music Prompt Management

**User Story:** As an admin, I want to manage song descriptions and structures used by the generation pipeline, so that I can control the creative output quality.

#### Acceptance Criteria

1. WHEN the Descriptions tab loads, THE Admin_Portal SHALL fetch and display all song descriptions from `GET /api/v1/prompts/descriptions` showing name, content preview, and match_key
2. WHEN an admin creates a description, THE Admin_Portal SHALL send a POST request to `/api/v1/prompts/descriptions` with name (1-100 chars), content (1-5000 chars), and optional match_key
3. WHEN an admin updates a description, THE Admin_Portal SHALL send a PUT request to `/api/v1/prompts/descriptions/{id}` with the changed fields
4. WHEN an admin confirms deletion, THE Admin_Portal SHALL send a DELETE request to `/api/v1/prompts/descriptions/{id}`
5. WHEN the Structures tab loads, THE Admin_Portal SHALL fetch and display all song structures from `GET /api/v1/prompts/structures` showing name, content preview, and match_key
6. WHEN an admin creates a structure, THE Admin_Portal SHALL send a POST request to `/api/v1/prompts/structures` with name (1-100 chars), content (1-5000 chars), and optional match_key
7. WHEN an admin updates a structure, THE Admin_Portal SHALL send a PUT request to `/api/v1/prompts/structures/{id}` with the changed fields
8. WHEN an admin confirms deletion, THE Admin_Portal SHALL send a DELETE request to `/api/v1/prompts/structures/{id}`
9. THE Admin_Portal SHALL display descriptions and structures that share the same match_key as visually paired

### Requirement 9: Rate Limit Configuration

**User Story:** As an admin, I want to view and update rate limits for API endpoints, so that I can protect the platform from abuse while ensuring fair access.

#### Acceptance Criteria

1. WHEN the Rate Limits page loads, THE Admin_Portal SHALL fetch and display all rate limit configurations from `GET /api/v1/admin/rate-limits` showing endpoint_type, max_requests, and window_seconds
2. WHEN an admin submits a rate limit update, THE Admin_Portal SHALL send a PUT request to `/api/v1/admin/rate-limits` with endpoint_type, max_requests (1-100000), and window_seconds (1-86400)
3. THE Admin_Portal SHALL validate rate limit inputs client-side: max_requests between 1 and 100,000, window_seconds between 1 and 86,400
4. WHEN a rate limit update succeeds, THE Admin_Portal SHALL display a Toast_Notification confirming the change takes effect within 5 seconds

### Requirement 10: Audit Log Viewer

**User Story:** As an admin, I want to browse and filter the system audit log, so that I can investigate user actions and system events.

#### Acceptance Criteria

1. WHEN the Audit Log page loads, THE Admin_Portal SHALL fetch and display the first page (50 entries) from `GET /api/v1/admin/audit-log`
2. THE Admin_Portal SHALL support filtering the audit log by: actor_id, action_type, resource_type, from_date, and to_date
3. THE Data_Table SHALL support pagination with page navigation controls and display total entries count
4. THE Admin_Portal SHALL display each audit entry showing: timestamp, actor, action type, target resource, outcome, and credit impact (if non-zero)
5. WHEN an admin applies filters, THE Admin_Portal SHALL re-fetch the audit log with the selected filter parameters and reset to page 1

### Requirement 11: Application Shell and Theming

**User Story:** As an admin, I want a visually consistent, responsive interface with a professional deep blue theme, so that the portal feels polished and easy to use.

#### Acceptance Criteria

1. THE Admin_Portal SHALL use shadcn/ui as the component library with the deep blue (slate) theme variant applied globally
2. THE Admin_Portal SHALL use Lucide React as the icon library for all iconography
3. THE Admin_Portal SHALL implement responsive layouts that function on viewport widths from 1024px to 2560px
4. THE Admin_Portal SHALL display loading skeletons (shadcn Skeleton component) while fetching data from the API
5. THE Admin_Portal SHALL display error states with retry actions when API requests fail
6. WHEN an API request is in progress, THE Admin_Portal SHALL disable submit buttons and show a loading spinner to prevent duplicate submissions

### Requirement 12: Project Setup and Build Configuration

**User Story:** As a developer, I want the admin portal to use modern tooling with fast builds, so that I can develop and deploy efficiently.

#### Acceptance Criteria

1. THE Admin_Portal SHALL be a Vite-powered React application using TypeScript located in the `admin_portal/` directory at the same level as `platform_api/`
2. THE Admin_Portal SHALL use React Router for client-side routing with a route per management section
3. THE Admin_Portal SHALL use TanStack Query (React Query) for server state management, caching, and automatic refetching
4. THE Admin_Portal SHALL configure the Platform API base URL via an environment variable (`VITE_API_BASE_URL`)
5. THE Admin_Portal SHALL include an HTTP client module that automatically attaches the JWT access token to all API requests and handles token refresh on 401 responses
