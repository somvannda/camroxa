# YouTube OAuth Apps — Requirements

## Goal
- Support multiple YouTube OAuth client configurations (client id + client secret) stored in Postgres and managed in the Python app UI.
- Allow each Music Profile to select which OAuth app to use for YouTube connect/upload.
- Preserve backward compatibility with the existing global `youtubeClientId` / `youtubeClientSecret` settings.

## User Stories
1) As Boss, I can create multiple YouTube OAuth app configs and reuse them across many profiles.
2) As Boss, I can select an OAuth app per Profile so the correct client id/secret is used when connecting and uploading.
3) As Boss, I can rotate a client secret for an OAuth app without rebuilding profiles.
4) As Boss, I can keep refresh tokens secure and never expose secrets in logs.

## Functional Requirements
### OAuth Apps
- CRUD operations:
  - Create OAuth app config (name, client id, client secret)
  - Update OAuth app config
  - Delete OAuth app config (blocked if it is currently referenced by any profile)
- Storage:
  - OAuth app configs stored in Postgres table(s)
  - Client secret stored encrypted at rest using Windows DPAPI (same approach as YouTube refresh tokens)

### Profile Selection
- Each Profile has `youtubeOauthAppId`:
  - Empty value means “Use global YouTube OAuth client settings”
  - Non-empty value references one of the stored OAuth app configs
- YouTube Connect uses the selected OAuth app for that Profile.
- YouTube Upload uses the selected OAuth app for that Profile.

### Backward Compatibility
- Existing global fields remain:
  - Settings → API: `YouTube OAuth client id`, `YouTube OAuth client secret`
- If a profile does not select an OAuth app, connect/upload uses the global fields.

## Non-Goals
- No automatic migration of existing profiles to a new OAuth app config (optional future improvement).
- No remote secret vault integration (DPAPI is used locally).
