# Implementation Plan: Template Marketplace

## Overview

This plan implements a Template Marketplace spanning three components: Platform API (FastAPI backend with upload validation, catalog, and download endpoints), Desktop App (PyQt6 marketplace page with browse/install/protect flows), and Admin Portal (React management page with upload, status toggles, and delete). The implementation progresses from database schema → API service layer → API endpoints → desktop coordinator → desktop UI → admin portal UI.

> **Note:** The desktop app source directory is `camxora_python/` (not `python_app/`).

## Tasks

- [x] 1. Database schema and domain models
  - [x] 1.1 Create Alembic migration for marketplace_items table (Platform API)
    - Create migration file adding `marketplace_items` table with columns: id (UUID PK), name (VARCHAR 200), description (VARCHAR 2000), version (VARCHAR 50), author (VARCHAR 200), kind (VARCHAR 20 CHECK IN video/reel), tags (TEXT[]), status (VARCHAR 20 CHECK IN enabled/disabled DEFAULT enabled), zip_path (VARCHAR 500), preview_path (VARCHAR 500), created_at (TIMESTAMPTZ), updated_at (TIMESTAMPTZ)
    - Add UNIQUE constraint on (name, version)
    - Add indexes: `idx_marketplace_items_status`, `idx_marketplace_items_kind`, `idx_marketplace_items_created`
    - _Requirements: 1.1, 1.6, 1.8_

  - [x] 1.2 Create Alembic migration to add marketplace_item_id column to Desktop App
    - Add `marketplace_item_id TEXT DEFAULT NULL` column to the local `video_templates` table
    - Add partial index `idx_video_templates_marketplace_item` on marketplace_item_id WHERE NOT NULL
    - _Requirements: 6.1, 6.5_

  - [x] 1.3 Create Pydantic schemas for marketplace (Platform API)
    - Create `platform_api/models/marketplace_schemas.py` with: `ManifestSchema`, `MarketplaceItemResponse`, `MarketplaceItemListResponse`, `MarketplaceItemUpdateRequest`, `CatalogQueryParams`
    - Include all field validators (min_length, max_length, Literal types for kind)
    - _Requirements: 1.2, 1.4, 1.5, 2.5, 2.7, 3.1, 3.7_

  - [x] 1.4 Create TypeScript types for marketplace (Admin Portal)
    - Create `admin_portal/src/types/marketplace.ts` with: `MarketplaceItem`, `MarketplaceListResponse`, `MarketplaceItemUpdate` interfaces
    - _Requirements: 8.1_

- [x] 2. Platform API — Marketplace repository
  - [x] 2.1 Implement MarketplaceRepository
    - Create `platform_api/repositories/marketplace_repo.py` implementing `MarketplaceRepositoryPort`
    - Implement: `create`, `get_by_id`, `find_by_name_version`, `list_all` (paginated with total count), `list_enabled` (paginated, filterable by kind and search), `update`, `delete`
    - Search: case-insensitive partial match on name, description, and tags (using ILIKE or array unnest)
    - Ordering: `created_at DESC` for catalog queries
    - Use raw asyncpg queries following existing repository patterns
    - _Requirements: 1.1, 1.8, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.5_

- [x] 3. Platform API — Marketplace service
  - [x] 3.1 Implement MarketplaceService — upload validation and storage
    - Create `platform_api/services/marketplace_service.py` implementing `MarketplaceServicePort`
    - Implement `upload_template(file_content, filename)`:
      1. Validate file size ≤ 10MB before extraction
      2. Open zip in memory, validate root-level files (template.json, preview.png, manifest.json)
      3. Validate manifest.json schema (required fields, kind enum, tags constraints)
      4. Validate template.json is parseable JSON
      5. Validate preview.png has PNG signature bytes (`\x89PNG\r\n\x1a\n`)
      6. Check duplicate (name, version) via repository
      7. Store zip and preview to filesystem under `MARKETPLACE_STORAGE_PATH`
      8. Create MarketplaceItem record with status='enabled'
    - Implement file cleanup on failure (remove partial writes)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9_

  - [x] 3.2 Implement MarketplaceService — catalog and management methods
    - Implement `list_items(page, page_size)` for admin view (all items)
    - Implement `get_catalog(page, page_size, kind, search)` for public view (enabled only)
    - Implement `update_item(item_id, update)` with metadata validation
    - Implement `enable_item(item_id)` and `disable_item(item_id)`
    - Implement `delete_item(item_id)` — remove DB record then delete files (log orphans on file failure)
    - Implement `get_preview_path(item_id)` and `get_download_path(item_id)` with status checks
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.5_

  - [ ]* 3.3 Write property test for upload round-trip (Property 1)
    - **Property 1: Upload round-trip preserves manifest metadata**
    - For any valid manifest (name 1-200 chars, description 1-2000 chars, version 1-50 chars, author 1-200 chars, kind ∈ {video, reel}, tags 0-20 items each 1-50 chars), uploading SHALL produce a MarketplaceItem whose metadata exactly matches the manifest with status='enabled'
    - **Validates: Requirements 1.1, 1.6**

  - [ ]* 3.4 Write property test for missing file detection (Property 2)
    - **Property 2: Zip structure validation identifies missing files**
    - For any zip whose root-level file set is a proper subset of {template.json, preview.png, manifest.json}, upload SHALL be rejected listing exactly the absent files
    - **Validates: Requirements 1.2, 1.3**

  - [ ]* 3.5 Write property test for invalid manifest fields (Property 3)
    - **Property 3: Manifest field validation identifies invalid fields**
    - For any manifest with missing or empty required fields, upload SHALL be rejected identifying each invalid field by name
    - **Validates: Requirements 1.4**

  - [ ]* 3.6 Write property test for duplicate detection (Property 4)
    - **Property 4: Duplicate name+version detection**
    - For two bundles sharing the same (name, version), uploading the second SHALL be rejected with duplicate-item error including the conflicting name and version
    - **Validates: Requirements 1.8**

- [x] 4. Checkpoint - Ensure service layer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Platform API — Marketplace router
  - [x] 5.1 Create marketplace router with admin endpoints
    - Create `platform_api/routers/marketplace.py` with admin-protected endpoints:
      - `POST /marketplace/upload` — multipart file upload (max 10MB)
      - `GET /marketplace/admin/items` — paginated admin list (page, page_size params)
      - `PATCH /marketplace/items/{id}` — update metadata
      - `POST /marketplace/items/{id}/enable` — enable item
      - `POST /marketplace/items/{id}/disable` — disable item
      - `DELETE /marketplace/items/{id}` — delete item and files
    - Return structured error responses matching existing error envelope pattern
    - _Requirements: 1.1, 1.7, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 5.2 Create marketplace router with public endpoints
    - Add authenticated-user endpoints to marketplace router:
      - `GET /marketplace/catalog` — paginated catalog (page, page_size, kind, search params)
      - `GET /marketplace/items/{id}/preview` — serve PNG with content-type image/png
      - `GET /marketplace/items/{id}/download` — serve zip with content-type application/zip and content-disposition attachment
    - Enforce authentication on all public endpoints (401 for unauthenticated)
    - Enforce 403 on download of disabled items
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 5.3 Register marketplace router in app factory
    - Import and include `marketplace.router` in `platform_api/main.py`
    - Wire dependencies for `MarketplaceService` and `MarketplaceRepository` in dependencies
    - Add `marketplace_storage_path` setting to `platform_api/config.py`
    - _Requirements: 1.1_

  - [ ]* 5.4 Write property test for enable/disable catalog visibility (Property 5)
    - **Property 5: Enable/disable controls catalog visibility**
    - For any Marketplace_Item, disabling excludes from public catalog; enabling includes it. Disabled items never appear in catalog.
    - **Validates: Requirements 2.2, 2.3, 3.1**

  - [ ]* 5.5 Write property test for metadata update persistence (Property 6)
    - **Property 6: Metadata update persistence**
    - For any valid update (name 1-200 chars, description 1-2000 chars, tags ≤ 20 items each ≤ 50 chars), applying update then fetching returns exact submitted values
    - **Validates: Requirements 2.5**

  - [ ]* 5.6 Write property test for invalid metadata rejection (Property 7)
    - **Property 7: Invalid metadata update rejection**
    - For any update with at least one invalid field, SHALL be rejected without modifying the existing record
    - **Validates: Requirements 2.7**

  - [ ]* 5.7 Write property test for kind filter (Property 8)
    - **Property 8: Kind filter returns only matching items**
    - For any set of enabled items and kind filter, response contains only and all items matching that kind
    - **Validates: Requirements 3.2**

  - [ ]* 5.8 Write property test for search matching (Property 9)
    - **Property 9: Search matches name, description, or tags**
    - For any enabled item and case-insensitive substring of its name/description/tags, searching with that substring includes the item
    - **Validates: Requirements 3.3**

  - [ ]* 5.9 Write property test for catalog ordering (Property 10)
    - **Property 10: Catalog ordering is newest-first**
    - For any set of enabled items, catalog response is ordered by created_at descending
    - **Validates: Requirements 3.5**

  - [ ]* 5.10 Write property test for download round-trip (Property 11)
    - **Property 11: Download round-trip preserves zip content**
    - For any uploaded zip, downloading returns bytes identical to the original
    - **Validates: Requirements 4.1**

- [x] 6. Checkpoint - Ensure API endpoint tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Desktop App — Marketplace coordinator
  - [x] 7.1 Create marketplace database queries module
    - Create `camxora_python/database/marketplace_queries.py`
    - Implement: `insert_installed_template(uid, name, source, template_json, kind, user_id, marketplace_item_id)`, `get_by_marketplace_item_id(marketplace_item_id, user_id)`, `update_installed_template(uid, name, template_json, kind, updated_at)`, `delete_template(uid)`
    - _Requirements: 6.1, 6.5, 6.6_

  - [x] 7.2 Implement MarketplaceCoordinator
    - Create `camxora_python/features/marketplace/__init__.py` and `camxora_python/features/marketplace/coordinator.py`
    - Constructor-inject: `http_client` (httpx.Client with auth), `db_config`, `user_id`, `on_install_complete` callback, `on_error` callback, optional `logger`
    - Implement `fetch_catalog(page, kind, search)` — GET /marketplace/catalog with 15s timeout
    - Implement `install_template(item_id)` — download zip (30s timeout), extract template.json + manifest.json, check if already installed, INSERT into video_templates with source='marketplace'
    - Implement `reinstall_template(item_id)` — download, UPDATE existing record preserving uid and created_at
    - Implement `is_installed(marketplace_item_id)` — check local DB
    - Handle errors: network timeout, corrupt zip, invalid JSON, disk space
    - Clean up partial files on failure
    - _Requirements: 5.2, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ]* 7.3 Write property test for installation record (Property 13)
    - **Property 13: Installation creates correct local record**
    - For any valid marketplace template download, installed record SHALL have: non-empty uid, name from manifest, source='marketplace', template JSON matching template.json, kind from manifest, user_id, marketplace_item_id reference, valid timestamps
    - **Validates: Requirements 6.1, 6.5**

  - [ ]* 7.4 Write property test for reinstall preservation (Property 14)
    - **Property 14: Reinstall preserves identity while updating content**
    - For any installed template, reinstalling SHALL preserve uid and created_at, update template JSON/name/kind, update updated_at
    - **Validates: Requirements 6.6**

- [x] 8. Desktop App — Template protection logic
  - [x] 8.1 Implement read-only enforcement for marketplace templates
    - Modify existing template editing logic to check `source` field
    - Disable "Save" action when source='marketplace', show read-only badge/tooltip
    - Implement "Save As" flow: prompt for name (default "{original_name} - Copy", max 100 chars, non-empty non-whitespace), create new record with source='user', new uid, user-provided name, current template JSON
    - Validate name input: reject empty/whitespace-only strings
    - Handle "Save As" failure: show error, retain modifications in editor, allow retry
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 8.2 Add marketplace template visual distinction
    - Display distinct badge/icon on installed marketplace templates in the template list
    - Distinguish from user-created and builtin templates
    - Implement delete confirmation dialog for marketplace templates
    - _Requirements: 7.5, 7.6_

  - [ ]* 8.3 Write property test for read-only enforcement (Property 15)
    - **Property 15: Read-only enforcement by source**
    - For any template record, "Save" SHALL be disabled iff source='marketplace'; source='user' or 'builtin' SHALL have "Save" enabled
    - **Validates: Requirements 7.1**

  - [ ]* 8.4 Write property test for Save As independence (Property 16)
    - **Property 16: "Save As" creates independent user copy**
    - For any installed marketplace template and valid name (1-100 chars, non-whitespace), "Save As" SHALL create a new record with different uid, source='user', user-provided name, current JSON. Original record unchanged.
    - **Validates: Requirements 7.2**

  - [ ]* 8.5 Write property test for whitespace name rejection (Property 17)
    - **Property 17: Whitespace-only names rejected in "Save As"**
    - For any string of only whitespace or empty, submitting as "Save As" name SHALL be rejected with no record created
    - **Validates: Requirements 7.3**

- [x] 9. Checkpoint - Ensure desktop app tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Desktop App — Marketplace page UI
  - [x] 10.1 Create marketplace view
    - Create `camxora_python/views/marketplace_view.py` with paginated grid layout
    - Display template cards with: preview thumbnail (fixed size), name, description (truncated to 120 chars + ellipsis), kind badge
    - Kind filter controls (All, video, reel)
    - Pagination controls (20 items per page)
    - Loading indicator while fetching
    - Error state with retry button
    - Empty state message when no templates match
    - "Install" button on each card, disabled during download with progress indicator
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 10.2 Create marketplace page controller
    - Create `camxora_python/views/marketplace_page_controller.py`
    - Wire MarketplaceCoordinator to marketplace_view signals
    - Handle catalog fetch on page load and filter change
    - Handle install button click → coordinator.install_template → success notification (auto-dismiss 5s)
    - Handle already-installed detection → prompt reinstall
    - Handle 15s catalog timeout as failure
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6, 6.2, 6.3, 6.4, 6.6, 6.7_

  - [ ]* 10.3 Write property test for description truncation (Property 12)
    - **Property 12: Description truncation at 120 characters**
    - For any description, displayed text SHALL be full text if ≤ 120 chars, or first 120 chars + "…" if > 120 chars
    - **Validates: Requirements 5.5**

- [x] 11. Checkpoint - Ensure desktop UI tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Admin Portal — Marketplace hooks and API layer
  - [x] 12.1 Create TanStack Query hooks for marketplace
    - Create `admin_portal/src/hooks/use-marketplace.ts`
    - Queries: `useMarketplaceItems(page)` — admin item list with pagination
    - Mutations: `useUploadTemplate()` — multipart upload, `useToggleStatus(id)` — enable/disable, `useDeleteItem(id)` — delete with confirmation, `useUpdateItem(id)` — metadata update
    - Configure query invalidation on mutations
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 13. Admin Portal — Marketplace management page
  - [x] 13.1 Create marketplace page with items table
    - Create `admin_portal/src/pages/marketplace/index.tsx`
    - Paginated table with columns: preview thumbnail, name, kind, author, version, status (enabled/disabled badge), tags, created_at
    - Pagination controls (25 items per page matching API default)
    - Loading skeleton while data loads
    - Error state with retry option
    - "Upload Template" button in page header
    - _Requirements: 8.1, 8.5_

  - [x] 13.2 Create marketplace table component
    - Create `admin_portal/src/components/marketplace/marketplace-table.tsx`
    - Status toggle per row (calls enable/disable, reverts on error)
    - Delete button per row with confirmation dialog showing item name
    - Optimistic UI updates with rollback on API error
    - _Requirements: 8.1, 8.3, 8.4_

  - [x] 13.3 Create upload dialog component
    - Create `admin_portal/src/components/marketplace/upload-dialog.tsx`
    - File input accepting only .zip files, client-side 10MB size check
    - Upload progress indicator during API call
    - Display validation errors returned by API inline
    - On success: close dialog, invalidate items query, show new item in table
    - _Requirements: 8.2_

  - [x] 13.4 Register marketplace page in app router
    - Add `/marketplace` route to `admin_portal/src/App.tsx`
    - Add "Marketplace" item to main navigation
    - _Requirements: 8.1_

  - [ ]* 13.5 Write component tests for marketplace page
    - Test page renders items table with mocked data (MSW handlers)
    - Test upload dialog flow: file selection, upload, success/error display
    - Test status toggle interaction and error rollback
    - Test delete confirmation dialog flow
    - Test loading and error states
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation uses Python (Hypothesis) for Platform API and Desktop App property tests, and TypeScript (fast-check + Vitest) for Admin Portal tests
- Template zips and preview images are stored on the server filesystem under `MARKETPLACE_STORAGE_PATH` (configurable, defaults to `./marketplace_storage`)
- Desktop App local DB uses the existing `video_templates` table extended with `marketplace_item_id` column
- The marketplace catalog only returns enabled items; disabled items are hidden from desktop users immediately

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "1.4"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["3.1", "3.2"] },
    { "id": 3, "tasks": ["3.3", "3.4", "3.5", "3.6", "5.1", "5.2"] },
    { "id": 4, "tasks": ["5.3", "5.4", "5.5", "5.6", "5.7", "5.8", "5.9", "5.10"] },
    { "id": 5, "tasks": ["7.1", "12.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "7.4"] },
    { "id": 7, "tasks": ["8.1", "8.2", "10.1"] },
    { "id": 8, "tasks": ["8.3", "8.4", "8.5", "10.2", "10.3"] },
    { "id": 9, "tasks": ["13.1", "13.2", "13.3", "13.4"] },
    { "id": 10, "tasks": ["13.5"] }
  ]
}
```
