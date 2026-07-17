# Requirements Document

## Introduction

The Template Marketplace feature adds a centralized marketplace for video templates, allowing admins to upload curated template bundles and desktop app users to browse, install, and use them. Templates are packaged as zip files containing the template JSON, a preview image, and metadata. The marketplace bridges the Platform API (storage and catalog), Admin Portal (upload and management), and Desktop App (browsing, installation, and usage). Installed marketplace templates are read-only — users must "Save As" to create editable copies.

## Glossary

- **Marketplace**: The centralized catalog of video templates made available to authenticated Desktop_App users through the Platform_API
- **Template_Bundle**: A zip archive containing a template.json file, a preview.png image, and a manifest.json metadata file, representing a single marketplace listing
- **Manifest**: The manifest.json file within a Template_Bundle that contains metadata fields: name, description, version, author, kind (video or reel), and tags
- **Marketplace_Item**: A database record in the Platform_API representing a published template listing with its metadata, preview image path, zip storage path, and enabled/disabled status
- **Platform_API**: The FastAPI backend service that stores Template_Bundles and serves the marketplace catalog and download endpoints
- **Admin_Portal**: The React SPA where admins upload, enable, disable, and delete Marketplace_Items
- **Desktop_App**: The PyQt6 desktop application where users browse and install marketplace templates
- **Installed_Template**: A video template record in the Desktop_App's local video_templates table with source='marketplace', installed from the Marketplace
- **User_Copy**: A video template record in the Desktop_App's local video_templates table with source='user', created by saving modifications to an Installed_Template via "Save As"
- **Preview_Image**: The preview.png file from a Template_Bundle, used as the thumbnail in marketplace listings

## Requirements

### Requirement 1: Template Bundle Upload (Admin)

**User Story:** As an Admin, I want to upload video template zip bundles through the Admin Portal, so that I can publish curated templates to the marketplace for users to install.

#### Acceptance Criteria

1. WHEN an Admin uploads a valid Template_Bundle zip file, THE Platform_API SHALL extract and validate the zip contents, store the zip file and preview image on the server filesystem, create a Marketplace_Item record with metadata from the manifest.json, and return the created Marketplace_Item record
2. WHEN an Admin uploads a Template_Bundle, THE Platform_API SHALL validate that the zip contains exactly three required files at the archive root level (not nested in subdirectories): template.json (parseable JSON conforming to the video template schema), preview.png (a file with valid PNG signature bytes that is decodable as an image), and manifest.json (valid JSON containing name, description, version, author, kind, and tags fields)
3. IF an uploaded zip file is missing any required file (template.json, preview.png, or manifest.json) at the archive root level, THEN THE Platform_API SHALL reject the upload with a validation error listing the missing files
4. IF an uploaded zip file contains a manifest.json with missing or empty required fields (name, description, version, author, kind), THEN THE Platform_API SHALL reject the upload with a validation error indicating which fields are invalid
5. IF an uploaded zip file contains a manifest.json where the kind field is not one of "video" or "reel", THEN THE Platform_API SHALL reject the upload with a validation error indicating the valid kind values
6. WHEN a Marketplace_Item is created from a valid upload, THE Platform_API SHALL set the item status to enabled by default
7. IF the uploaded zip file exceeds 10 MB, THEN THE Platform_API SHALL reject the upload with a file-size-exceeded error before processing the zip contents
8. IF an Admin uploads a Template_Bundle whose manifest name and version match an existing Marketplace_Item, THEN THE Platform_API SHALL reject the upload with a duplicate-item error indicating the conflicting item name and version
9. IF an uploaded zip file contains a template.json that is not parseable as JSON or does not conform to the video template schema, THEN THE Platform_API SHALL reject the upload with a validation error indicating the template.json is invalid

### Requirement 2: Marketplace Item Management (Admin)

**User Story:** As an Admin, I want to manage marketplace template listings through the Admin Portal, so that I can enable, disable, or remove templates from the marketplace catalog.

#### Acceptance Criteria

1. WHEN an Admin requests the marketplace item list, THE Platform_API SHALL return a paginated list of all Marketplace_Items (default page size 25, maximum 100) with fields: id, name, description, version, author, kind, tags, status (enabled or disabled), preview image URL, and created_at timestamp
2. WHEN an Admin disables a Marketplace_Item, THE Platform_API SHALL set the item status to disabled and immediately exclude it from the public catalog returned to Desktop_App users
3. WHEN an Admin enables a previously disabled Marketplace_Item, THE Platform_API SHALL set the item status to enabled and immediately include it in the public catalog returned to Desktop_App users
4. WHEN an Admin deletes a Marketplace_Item, THE Platform_API SHALL remove the database record and the associated stored files (zip and preview image) from the server filesystem; IF file deletion fails after the database record is removed, THEN THE Platform_API SHALL log the orphaned file paths and still return a success response to the Admin
5. WHEN an Admin updates a Marketplace_Item's metadata (name, description, tags), THE Platform_API SHALL validate that name is non-empty and at most 200 characters, description is non-empty and at most 2000 characters, and tags contains at most 20 items each at most 50 characters, persist the valid changes, and return the updated record
6. IF an Admin attempts to manage a Marketplace_Item that does not exist, THEN THE Platform_API SHALL return a 404 Not Found response
7. IF an Admin submits a metadata update with invalid field values (empty name, name exceeding 200 characters, empty description, description exceeding 2000 characters, or tags exceeding the defined limits), THEN THE Platform_API SHALL reject the update with a validation error indicating which fields are invalid

### Requirement 3: Marketplace Catalog Browsing (Public API)

**User Story:** As an authenticated Desktop_App user, I want to browse available marketplace templates with preview images and descriptions, so that I can discover templates to install.

#### Acceptance Criteria

1. WHEN an authenticated User requests the marketplace catalog, THE Platform_API SHALL return a paginated list of enabled Marketplace_Items with fields: id, name, description, version, author, kind, tags, and preview image URL, using a default page size of 25 and a maximum page size of 100
2. WHEN an authenticated User requests the marketplace catalog with a kind filter (video or reel), THE Platform_API SHALL return only Marketplace_Items matching the specified kind
3. WHEN an authenticated User requests the marketplace catalog with a search query (between 1 and 100 characters), THE Platform_API SHALL return Marketplace_Items where the name, description, or tags contain the search term (case-insensitive partial match)
4. THE Platform_API SHALL serve preview images via a dedicated endpoint that returns the PNG file with content-type header set to image/png
5. THE Platform_API SHALL order marketplace catalog results by created_at descending (newest first) by default
6. IF an unauthenticated request is made to the marketplace catalog or preview image endpoints, THEN THE Platform_API SHALL return a 401 Unauthorized response
7. IF an authenticated User requests the marketplace catalog with an invalid kind filter value (not "video" or "reel"), THEN THE Platform_API SHALL return a validation error indicating the valid kind values
8. IF the preview image file for a Marketplace_Item is not found on the server filesystem, THEN THE Platform_API SHALL return a 404 Not Found response

### Requirement 4: Template Download

**User Story:** As an authenticated Desktop_App user, I want to download a template zip from the marketplace, so that I can install it into my local template collection.

#### Acceptance Criteria

1. WHEN an authenticated User requests to download a Marketplace_Item by its id, THE Platform_API SHALL return the stored Template_Bundle zip file as a binary stream with content-type header set to application/zip and content-disposition header set to attachment with the filename matching the stored zip filename
2. IF a User requests to download a Marketplace_Item that does not exist, THEN THE Platform_API SHALL return a 404 Not Found response
3. IF a User requests to download a Marketplace_Item that is disabled, THEN THE Platform_API SHALL return a 403 Forbidden response indicating the item is not available
4. IF an unauthenticated User requests to download a Marketplace_Item, THEN THE Platform_API SHALL return a 401 Unauthorized response
5. IF the stored zip file for a Marketplace_Item is missing or unreadable on the server filesystem, THEN THE Platform_API SHALL return a 500 error response indicating the file is unavailable

### Requirement 5: Desktop App Marketplace Page

**User Story:** As a Desktop_App user, I want a dedicated Marketplace page in the application where I can browse available templates with thumbnails and descriptions, so that I can find templates to enhance my video production.

#### Acceptance Criteria

1. THE Desktop_App SHALL display a Marketplace page accessible from the main navigation that shows a paginated grid of available marketplace templates with preview thumbnails, names, descriptions, and kind indicators (video or reel), displaying up to 20 templates per page with navigation controls to load additional pages
2. WHEN the Marketplace page loads, THE Desktop_App SHALL fetch the marketplace catalog from the Platform_API and display the results; WHILE the catalog is loading, THE Desktop_App SHALL display a loading indicator; IF the catalog has not responded within 15 seconds, THE Desktop_App SHALL treat the request as failed
3. IF the Platform_API is unreachable or returns an error when fetching the catalog, THEN THE Desktop_App SHALL display an error message indicating the failure and a retry button that re-fetches the catalog when clicked
4. WHEN a User selects a kind filter (All, video, or reel) on the Marketplace page, THE Desktop_App SHALL filter the displayed templates to show only items matching the selected kind; WHEN "All" is selected, THE Desktop_App SHALL display templates of both kinds
5. THE Desktop_App SHALL display each marketplace template card with the preview image scaled to a fixed thumbnail size, the template name, the description truncated to a maximum of 120 characters with an ellipsis appended when exceeded, and a kind badge indicating "video" or "reel"
6. IF the marketplace catalog returns zero templates (either overall or after applying a kind filter), THEN THE Desktop_App SHALL display an empty-state message indicating that no templates are available for the current selection

### Requirement 6: Template Installation

**User Story:** As a Desktop_App user, I want to click "Install" on a marketplace template to add it to my local template collection, so that I can use it for video generation.

#### Acceptance Criteria

1. WHEN a User clicks "Install" on a marketplace template, THE Desktop_App SHALL download the Template_Bundle zip from the Platform_API within a 30-second timeout, extract the template.json content, and insert a new record into the local video_templates table with: a generated uid, the template name from the manifest, source set to 'marketplace', the template JSON as the template column value, the kind from the manifest, the authenticated user's user_id, and current timestamps
2. WHEN installation completes successfully, THE Desktop_App SHALL display a success notification that auto-dismisses after 5 seconds and the installed template SHALL appear in the user's template list without requiring a manual refresh
3. WHILE a template is being downloaded and installed, THE Desktop_App SHALL display a progress indicator on the template card and disable the Install button to prevent duplicate installations
4. IF the download or extraction fails (network error, timeout, corrupt zip, invalid template.json, or insufficient disk space), THEN THE Desktop_App SHALL display an error message indicating the failure reason, remove any partially written files, and allow the User to retry
5. THE Desktop_App SHALL store the Marketplace_Item id as a reference in the installed template record so that the origin marketplace item can be identified
6. IF a User attempts to install a marketplace template that is already installed (same marketplace item id exists in local video_templates), THEN THE Desktop_App SHALL inform the User that the template is already installed and offer to reinstall; WHEN the User confirms reinstall, THE Desktop_App SHALL replace the existing record's template JSON, name, and kind with the newly downloaded values while preserving the original uid and created_at timestamp
7. IF the download does not complete within 30 seconds, THEN THE Desktop_App SHALL abort the download, display a timeout error message, and allow the User to retry

### Requirement 7: Installed Template Protection

**User Story:** As a Desktop_App user, I want marketplace-installed templates to be protected from direct modification, so that I always retain the original template and can create my own variations via "Save As".

#### Acceptance Criteria

1. WHILE a User is viewing or editing an Installed_Template (source='marketplace'), THE Desktop_App SHALL disable the "Save" action and display a visual indicator (such as a read-only badge or disabled save button tooltip) that the template is read-only
2. WHEN a User clicks "Save As" on an Installed_Template, THE Desktop_App SHALL prompt the User for a name (defaulting to "{original_name} - Copy", maximum 100 characters, must not be empty or whitespace-only) and create a new video_templates record with source='user', a new generated uid, the user-provided name, and the modified template JSON, preserving the original Installed_Template unchanged
3. IF a User submits an empty or whitespace-only name in the "Save As" dialog, THEN THE Desktop_App SHALL display a validation error and prevent record creation until a valid name is provided
4. IF the "Save As" operation fails (database error or other system failure), THEN THE Desktop_App SHALL display an error message indicating the save failed, retain the user's modifications in the editor, and allow the User to retry
5. THE Desktop_App SHALL display a distinct visual badge or icon on Installed_Templates in the template list to distinguish them from user-created templates and builtin templates
6. WHEN a User attempts to delete an Installed_Template, THE Desktop_App SHALL display a confirmation dialog; upon confirmation, THE Desktop_App SHALL remove the record from the local video_templates table without affecting the marketplace listing

### Requirement 8: Admin Portal Marketplace Management Page

**User Story:** As an Admin, I want a dedicated Marketplace management page in the Admin Portal where I can view all uploaded templates, upload new ones, and manage their status, so that marketplace administration is centralized and efficient.

#### Acceptance Criteria

1. THE Admin_Portal SHALL display a Marketplace management page accessible from the main navigation that shows a paginated table of all Marketplace_Items with columns: preview thumbnail, name, kind, author, version, status (enabled/disabled), tags, and created_at date, with pagination controls matching the Platform_API page size of 25 items per page
2. WHEN an Admin clicks "Upload Template" on the Marketplace page, THE Admin_Portal SHALL display a file upload dialog accepting only .zip files up to 10 MB; after selection, THE Admin_Portal SHALL upload the file to the Platform_API, display a loading indicator during upload, and upon success display the new item details and add the item to the table without requiring a page refresh; IF the Platform_API returns validation errors, THEN THE Admin_Portal SHALL display the validation error messages returned by the API
3. WHEN an Admin toggles the status of a Marketplace_Item, THE Admin_Portal SHALL call the Platform_API to enable or disable the item and update the displayed status in the table without requiring a page refresh upon success; IF the Platform_API returns an error, THEN THE Admin_Portal SHALL revert the displayed status to its previous value and display an error message
4. WHEN an Admin clicks "Delete" on a Marketplace_Item, THE Admin_Portal SHALL display a confirmation dialog showing the item name; upon confirmation, THE Admin_Portal SHALL call the Platform_API to delete the item and remove it from the table; IF the Platform_API returns an error, THEN THE Admin_Portal SHALL dismiss the confirmation dialog and display an error message indicating the deletion failed
5. WHEN the Marketplace management page loads, THE Admin_Portal SHALL fetch the item list from the Platform_API and display a loading skeleton while data loads; IF the API returns an error, THEN THE Admin_Portal SHALL display an error message with a retry option
