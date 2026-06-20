# YouTube OAuth Apps — Technical

## Current State (verified)
- Global YouTube OAuth client id/secret are stored in app settings:
  - `youtubeClientId`, `youtubeClientSecret`
  - Set in Settings → API and used for connect/upload.
- YouTube refresh tokens are stored per Profile in `youtube_accounts.refresh_token_enc` (DPAPI encrypted).

## Data Model (Postgres)
### Table: `youtube_oauth_apps`
- `id` text primary key
- `name` text not null
- `client_id` text not null
- `client_secret_enc` text not null default '' (DPAPI encrypted base64)
- `created_at` timestamp default now()
- `updated_at` timestamp default now()

### Profiles extension
- Add column: `profiles.youtube_oauth_app_id` text not null default ''
  - empty string means “Use global settings”

## Encryption
- Use existing DPAPI helpers:
  - `services.dpapi.dpapi_encrypt_to_base64`
  - `services.dpapi.dpapi_decrypt_from_base64`
- Store `client_secret_enc` encrypted. Client ID can be stored plaintext.

## Runtime Resolution Logic
### Resolve OAuth client for a Profile
1) If `profile.youtubeOauthAppId` is set:
   - Load the OAuth app row from `youtube_oauth_apps`
   - Decrypt client secret
2) Else:
   - Use global settings `youtubeClientId` / `youtubeClientSecret`

### Connect Flow Changes
- Use the resolved OAuth client for the selected Profile.
- Preserve current multi-channel selection behavior.

### Upload Flow Changes
- Use the resolved OAuth client for the job’s Profile.
- Keep existing metadata behavior and job queue intact.

## Migration
- Extend `music_migrate.py` to create/alter:
  - `youtube_oauth_apps`
  - `profiles.youtube_oauth_app_id`

## UI Integration
- Implement CRUD screen in Settings → YouTube tab.
- Implement dropdown binding in Settings → Profiles.
