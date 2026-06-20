# Implementation Plan: Admin Portal

## Overview

Build a React SPA admin portal with Vite, TypeScript, TanStack Query, and shadcn/ui that communicates with the Platform API backend. Implementation proceeds from project scaffolding → core infrastructure (auth, HTTP client, layout) → domain feature pages → testing.

## Tasks

- [x] 1. Project scaffolding and core configuration
  - [x] 1.1 Initialize Vite + React + TypeScript project
    - Create `admin_portal/` directory with `npm create vite@latest` template (react-ts)
    - Add `package.json` with dependencies: react, react-dom, react-router-dom, @tanstack/react-query, axios, tailwindcss, postcss, autoprefixer, zod, react-hook-form, @hookform/resolvers, lucide-react
    - Add dev dependencies: vitest, @testing-library/react, @testing-library/jest-dom, @testing-library/user-event, msw, fast-check, jsdom
    - Create `vite.config.ts`, `tsconfig.json`, `tailwind.config.ts`, `postcss.config.js`
    - Create `.env.example` with `VITE_API_BASE_URL=http://localhost:8000`
    - _Requirements: 12.1, 12.4_

  - [x] 1.2 Set up Tailwind CSS and shadcn/ui theming
    - Create `src/styles/globals.css` with Tailwind directives and deep blue (slate-900/950) theme CSS variables
    - Configure `tailwind.config.ts` with shadcn theme colors (slate palette, blue accents)
    - Initialize shadcn/ui with `npx shadcn-ui@latest init` and install base components: Button, Input, Card, Skeleton, Dialog, Table, Badge, Toast, Select, Separator, Tooltip, DropdownMenu, Form, Label, Textarea, Progress
    - Create `src/lib/utils.ts` with `cn()` helper
    - _Requirements: 11.1, 11.2, 2.5_

  - [x] 1.3 Define TypeScript domain models and API types
    - Create `src/types/models.ts` with all domain interfaces: User, License, Plan, PlanOffer, CreditPricing, CreditPack, MusicDescription, MusicStructure, RateLimitConfig, AuditEntry, HealthStatus, ServiceHealth
    - Create `src/types/api.ts` with request/response types: PaginatedResponse, UserListParams, AuditLogParams, CreditAdjustmentRequest, CreateLicenseRequest, AssignLicenseRequest, CreateOfferRequest, CreatePricingRequest, UpdateRateLimitRequest, CreatePromptRequest
    - Create `src/types/auth.ts` with TokenPair and AuthContextValue interfaces
    - _Requirements: 4.1, 5.4, 6.1, 7.1, 8.1, 9.1, 10.1_

- [x] 2. Core infrastructure (HTTP client, auth, query client)
  - [x] 2.1 Implement HTTP client with JWT interceptor
    - Create `src/lib/http-client.ts` with Axios instance
    - Configure base URL from `VITE_API_BASE_URL` environment variable
    - Add request interceptor to attach `Authorization: Bearer <token>` header
    - Add response interceptor to handle 401: attempt token refresh, retry original request, redirect to login on refresh failure
    - Exclude `/auth/login` and `/auth/refresh` endpoints from token attachment
    - _Requirements: 12.5, 1.1, 1.2, 1.3_

  - [x] 2.2 Implement auth context and token management
    - Create `src/lib/auth.ts` with module-level closure for token storage (access + refresh tokens in memory only)
    - Create `src/hooks/use-auth.ts` with AuthContext providing: isAuthenticated, isLoading, adminEmail, login(), logout(), getAccessToken(), setTokens()
    - Implement login: POST to `/api/v1/auth/login`, store tokens, decode email from JWT
    - Implement logout: POST to `/api/v1/auth/logout`, clear tokens, redirect to `/login`
    - Implement automatic refresh: call `/api/v1/auth/refresh` when access token expires
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6_

  - [x] 2.3 Configure TanStack Query client
    - Create `src/lib/query-client.ts` with QueryClient instance
    - Configure defaults: `retry: 3` for network errors, `retry: false` for 4xx, staleTime of 30 seconds
    - Set up global error handling for mutations (toast notifications)
    - _Requirements: 12.3_

  - [x]* 2.4 Write property test for HTTP client JWT attachment
    - **Property 14: HTTP client attaches JWT to all API requests**
    - Test that for any request URL (excluding login/refresh), the Authorization header is present with the current token
    - **Validates: Requirements 12.5**

- [x] 3. Layout and navigation shell
  - [x] 3.1 Implement auth guard component
    - Create `src/components/layout/auth-guard.tsx`
    - Wrap protected routes; redirect unauthenticated users to `/login`
    - Show loading spinner while checking auth state
    - _Requirements: 1.4_

  - [x] 3.2 Implement navigation shell with sidebar and top bar
    - Create `src/components/layout/navigation-shell.tsx` as the authenticated layout wrapper
    - Create `src/components/layout/sidebar.tsx` with collapsible nav items using Lucide icons: LayoutDashboard, Users, KeyRound, CreditCard, Coins, Music, Gauge, ScrollText
    - Create `src/components/layout/top-bar.tsx` displaying admin email and logout button
    - Implement active route highlighting on the current nav item
    - Implement collapsed state with icon-only mode and tooltips
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 3.3 Set up React Router with lazy-loaded routes
    - Create `src/App.tsx` with QueryClientProvider, AuthProvider, RouterProvider
    - Create `src/main.tsx` as entry point rendering App
    - Define routes: `/login`, `/dashboard`, `/users`, `/licenses`, `/plans`, `/credits`, `/prompts`, `/rate-limits`, `/audit-log`
    - Wrap all routes except `/login` with AuthGuard
    - Implement lazy loading with React.lazy() for each page component
    - _Requirements: 12.2, 1.4_

  - [x]* 3.4 Write property test for auth guard
    - **Property 1: Auth guard restricts unauthenticated access**
    - For any route path other than `/login`, verify redirect to login when unauthenticated
    - **Validates: Requirements 1.4**

  - [x]* 3.5 Write property test for navigation highlighting
    - **Property 2: Active navigation highlighting matches current route**
    - For any valid route path, verify exactly one nav item is highlighted matching the current path
    - **Validates: Requirements 2.3**

- [x] 4. Shared components (data table, loading, error, toast)
  - [x] 4.1 Implement generic data table component
    - Create `src/components/data-table/data-table.tsx` with DataTableProps<T> interface
    - Create `src/components/data-table/pagination.tsx` with page navigation controls
    - Create `src/components/data-table/column-header.tsx` for sortable column headers
    - Create `src/components/data-table/filter-bar.tsx` for filter UI container
    - Support loading skeletons, empty state, row click handler
    - _Requirements: 4.1, 10.3, 11.4_

  - [x] 4.2 Implement shared UI components
    - Create `src/components/shared/loading-skeleton.tsx` for page-level loading state
    - Create `src/components/shared/error-state.tsx` with error message and retry button
    - Create `src/components/shared/confirm-dialog.tsx` for destructive action confirmation
    - Create `src/components/shared/toast-provider.tsx` wrapping shadcn Toaster
    - _Requirements: 11.4, 11.5, 4.7, 4.8_

  - [x]* 4.3 Write property tests for loading and error states
    - **Property 11: Loading state shows skeleton placeholders**
    - **Property 12: Error state shows retry action**
    - **Validates: Requirements 11.4, 11.5**

- [x] 5. Checkpoint - Core infrastructure verification
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Login page
  - [x] 6.1 Implement login page
    - Create `src/pages/login.tsx` with email/password form using React Hook Form + Zod
    - Integrate with useAuth().login() method
    - Display inline validation errors for empty fields
    - Show API error messages in toast on login failure
    - Redirect to `/dashboard` on successful login
    - Disable submit button and show spinner during login request
    - _Requirements: 1.1, 11.6_

  - [x]* 6.2 Write property test for submit button disabled state
    - **Property 13: Submit buttons disabled during pending mutations**
    - Verify submit button is disabled and shows spinner when mutation is pending
    - **Validates: Requirements 11.6**

- [x] 7. Dashboard page
  - [x] 7.1 Implement dashboard page with health and metrics
    - Create `src/hooks/use-dashboard.ts` with queries for health status and suno balance
    - Create `src/pages/dashboard.tsx` with metric cards: total users, active licenses, Suno balance, system health
    - Implement color-coded health indicators: green (healthy), yellow (degraded), red (unhealthy)
    - Display affected services section when any service is degraded/unhealthy
    - Show loading skeletons while fetching, error state on failure
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x]* 7.2 Write property test for health status rendering
    - **Property 3: Health status rendering**
    - For any set of service health states, verify correct color indicators and affected services list
    - **Validates: Requirements 3.3, 3.5**

- [x] 8. User management page
  - [x] 8.1 Implement user list page with filters
    - Create `src/hooks/use-users.ts` with useUsers(), useUpdateUser(), useSuspendUser(), useReactivateUser(), useDeleteUser() hooks
    - Create `src/pages/users/index.tsx` with paginated DataTable, status filter, date range filter
    - Default page size of 25
    - _Requirements: 4.1, 4.2_

  - [x] 8.2 Implement user detail panel and actions
    - Create `src/pages/users/user-detail.tsx` with user info display (email, display_name, role, status, created_at)
    - Implement edit form for display_name and role with PATCH request
    - Implement suspend action with reason dialog
    - Implement reactivate action with confirmation
    - Implement delete action with confirmation dialog
    - Show toast notifications for success and error outcomes
    - _Requirements: 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x]* 8.3 Write property test for mutation error toast
    - **Property 4: API mutation errors display toast without navigation**
    - For any API error response (status >= 400), verify toast is displayed and route remains unchanged
    - **Validates: Requirements 4.8**

- [x] 9. License management page
  - [x] 9.1 Implement license page
    - Create `src/hooks/use-licenses.ts` with useLicenses(), useCreateLicense(), useAssignLicense(), useRevokeLicense() hooks
    - Create `src/pages/licenses/index.tsx` with license DataTable showing: license_key, plan, user, status, activation/expiration dates
    - Implement create license form (select plan)
    - Implement assign license form (select user)
    - Implement revoke action with confirmation
    - Handle 409 conflict with user-friendly duplicate license message
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 10. Plan configuration page
  - [x] 10.1 Implement plans page with offer management
    - Create `src/hooks/use-plans.ts` with usePlans(), useUpdatePlan(), useOffers(), useCreateOffer() hooks
    - Create `src/pages/plans/index.tsx` displaying all plans with name, price, profile_allowance, monthly_quota, daily_limit, active status
    - Implement plan edit form with Zod validation: price_cents >= 0, profile_allowance >= 1, monthly_song_quota >= 0, billing_cycle_days >= 1
    - Display promotional offers section with progress indicator (current_redemptions / max_redemptions)
    - Implement create offer form: plan_id, promo_price_cents, max_redemptions
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x]* 10.2 Write property test for plan validation
    - **Property 5: Plan form validation accepts valid inputs and rejects invalid inputs**
    - For any set of plan field values, verify schema accepts iff all constraints are met
    - **Validates: Requirements 6.3**

  - [x]* 10.3 Write property test for offer progress calculation
    - **Property 6: Offer progress calculation**
    - For any offer with current_redemptions and max_redemptions > 0, verify correct percentage rendering
    - **Validates: Requirements 6.6**

- [x] 11. Credit system management page
  - [x] 11.1 Implement credits page
    - Create `src/hooks/use-credits.ts` with usePricing(), useCreatePricing(), useUpdatePricing(), usePacks(), useAdjustBalance() hooks
    - Create `src/pages/credits/index.tsx` with tabs/sections: Pricing, Packs, Balance Adjustment
    - Display pricing table: model, operation_type, credits_per_operation, external_cost
    - Implement create/update pricing forms
    - Display credit packs list
    - Implement balance adjustment form with Zod validation: amount !== 0, reason non-empty
    - Handle 409 conflict for duplicate pricing entries
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [x]* 11.2 Write property test for credit adjustment validation
    - **Property 7: Credit adjustment validation**
    - For any (amount, reason) input, verify schema accepts iff amount !== 0 AND reason.trim().length > 0
    - **Validates: Requirements 7.6**

- [x] 12. Checkpoint - Domain pages verification
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Music prompt management page
  - [x] 13.1 Implement prompts page with descriptions and structures
    - Create `src/hooks/use-prompts.ts` with hooks for descriptions CRUD and structures CRUD
    - Create `src/pages/prompts/index.tsx` with tabbed view: Descriptions | Structures
    - Display descriptions table: name, content preview, match_key
    - Display structures table: name, content preview, match_key
    - Implement create/edit/delete for descriptions (name 1-100 chars, content 1-5000 chars, optional match_key)
    - Implement create/edit/delete for structures (same validation)
    - Visually pair descriptions and structures sharing the same non-null match_key
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9_

  - [x]* 13.2 Write property test for match key pairing
    - **Property 8: Match key pairing groups correctly**
    - For any set of descriptions/structures with arbitrary match_key values, verify correct grouping
    - **Validates: Requirements 8.9**

- [x] 14. Rate limit configuration page
  - [x] 14.1 Implement rate limits page
    - Create `src/hooks/use-rate-limits.ts` with useRateLimits(), useUpdateRateLimit() hooks
    - Create `src/pages/rate-limits/index.tsx` displaying rate limit configs: endpoint_type, max_requests, window_seconds
    - Implement inline edit form with Zod validation: max_requests 1-100000, window_seconds 1-86400
    - Show toast notification confirming change takes effect within 5 seconds
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x]* 14.2 Write property test for rate limit validation
    - **Property 9: Rate limit form validation**
    - For any (max_requests, window_seconds) integers, verify schema accepts iff within valid ranges
    - **Validates: Requirements 9.3**

- [x] 15. Audit log viewer page
  - [x] 15.1 Implement audit log page
    - Create `src/hooks/use-audit-log.ts` with useAuditLog() hook accepting filter params
    - Create `src/pages/audit-log/index.tsx` with paginated DataTable (50 entries per page)
    - Display columns: timestamp, actor, action_type, target_resource, outcome, credit_impact (only if non-zero)
    - Implement filter bar: actor_id, action_type, resource_type, from_date, to_date
    - Reset to page 1 when filters change
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x]* 15.2 Write property test for audit entry rendering
    - **Property 10: Audit entry rendering includes all required fields**
    - For any valid audit entry, verify all required fields are rendered and credit_impact logic is correct
    - **Validates: Requirements 10.4**

- [x] 16. Final checkpoint - Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The project uses TypeScript throughout with Vite for fast HMR development
- All API communication goes through the HTTP client with automatic JWT handling
- shadcn/ui components provide the base UI with deep blue theming

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["2.1", "2.2", "2.3"] },
    { "id": 3, "tasks": ["2.4", "3.1", "3.2", "3.3"] },
    { "id": 4, "tasks": ["3.4", "3.5", "4.1", "4.2"] },
    { "id": 5, "tasks": ["4.3", "6.1"] },
    { "id": 6, "tasks": ["6.2", "7.1"] },
    { "id": 7, "tasks": ["7.2", "8.1"] },
    { "id": 8, "tasks": ["8.2", "8.3", "9.1"] },
    { "id": 9, "tasks": ["10.1", "11.1"] },
    { "id": 10, "tasks": ["10.2", "10.3", "11.2"] },
    { "id": 11, "tasks": ["13.1", "14.1", "15.1"] },
    { "id": 12, "tasks": ["13.2", "14.2", "15.2"] }
  ]
}
```
