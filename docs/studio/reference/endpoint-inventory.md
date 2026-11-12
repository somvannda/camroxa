# Reference endpoint inventory

Generated 2026-10-30T12:48:34.726Z from 134 public chunks (mode: **anonymous**).

- Unique endpoints: **322** (428 occurrences)
- Studio-related endpoints: **81**

> Derived facts only: paths, methods and field names. No source is copied.
> This is a specification source, never a runtime dependency (D-002).

## Studio-related endpoints

| Method | Path | Body fields | Query fields | Params |
|---|---|---|---|---|
| GET | `/api/clip/{clip_id}` | — | — | `clip_id` |
| GET | `/api/clip/{clip_id}/permissions` | — | — | `clip_id` |
| POST | `/api/clip/{clip_id}/permissions/grants` | `grantee_handle`, `capabilities` | — | `clip_id` |
| DELETE | `/api/clip/{clip_id}/permissions/grants/{grantee_uid}` | — | — | `clip_id`, `grantee_uid` |
| PATCH | `/api/clip/{clip_id}/permissions/visibility` | `general_audience` | — | `clip_id` |
| GET | `/api/clip/{clip_id}/stems` | — | `page` | `clip_id` |
| GET | `/api/clip/{clip_id}/stems/pages` | — | — | `clip_id` |
| GET | `/api/clips/{clip_id}/attribution` | — | — | `clip_id` |
| POST | `/api/clips/{clip_id}/toggle_remixes` | `can_remix` | — | `clip_id` |
| POST | `/api/clips/{clip_id}/toggle_show_remixes` | `show_remix` | — | `clip_id` |
| POST | `/api/clips/adjust-speed` | `clip_id`, `speed_multiplier`, `keep_pitch`, `title` | — | — |
| GET | `/api/clips/aligned_clip_siblings` | — | `clip_id` | — |
| GET | `/api/clips/aligned_clips` | — | `history_clip_id`, `history_end_seconds_gte`, `history_end_seconds_lte`, `future_clip_id`, `future_start_seconds_gte`, `future_start_seconds_lte` | — |
| GET | `/api/clips/get_songs_by_ids` | — | `ids` | — |
| POST | `/api/clips/reverse-clip` | `clip_id`, `title` | — | — |
| GET | `/api/download/clip/{clip_id}` | — | `format` | `clip_id` |
| GET | `/api/download/sample-pack/{clip_id}` | — | `job_id` | `clip_id` |
| POST | `/api/download/sample-pack/{clip_id}` | — | — | `clip_id` |
| GET | `/api/edit/action/{action_clip_id}` | — | — | `action_clip_id` |
| POST | `/api/edit/crop/{clip_id}` | `crop_start_s`, `crop_end_s`, `is_crop_remove`, `title`, `ui_surface` | — | `clip_id` |
| POST | `/api/edit/fade/{clip_id}` | `fade_in_time`, `fade_out_time`, `title` | — | `clip_id` |
| GET | `/api/gen/{clip_id}/aligned_lyrics/v2` | — | — | `clip_id` |
| POST | `/api/gen/{clip_id}/aligned_lyrics/v2` | — | — | `clip_id` |
| GET | `/api/gen/{clip_id}/aligned_lyrics/v3` | — | — | `clip_id` |
| POST | `/api/gen/{clip_id}/aligned_lyrics/v3` | `lyrics`, `enable_augmentation` | — | `clip_id` |
| POST | `/api/gen/{clip_id}/comment` | — | — | `clip_id` |
| GET | `/api/gen/{clip_id}/comments` | — | `cursor`, `order`, `id`, `deeplink` | `clip_id` |
| GET | `/api/gen/{clip_id}/comments/count` | — | — | `clip_id` |
| POST | `/api/gen/{clip_id}/convert_wav` | — | — | `clip_id` |
| GET | `/api/gen/{clip_id}/downbeats` | — | — | `clip_id` |
| GET | `/api/gen/{clip_id}/midi` | — | — | `clip_id` |
| GET | `/api/gen/{clip_id}/novelty-sections` | — | — | `clip_id` |
| POST | `/api/gen/{clip_id}/toggle_comments` | `can_comment` | — | `clip_id` |
| GET | `/api/gen/{clip_id}/wav_file` | — | — | `clip_id` |
| GET | `/api/gen/{clip_id}/waveform-aggregates` | — | — | `clip_id` |
| POST | `/api/persona/{persona_id}/toggle_love` | — | — | `persona_id` |
| POST | `/api/persona/create` | — | — | — |
| GET | `/api/persona/get-followed-personas` | — | `page` | — |
| GET | `/api/persona/get-loved-personas` | — | `page` | — |
| GET | `/api/persona/get-persona/{persona_id}` | — | — | `persona_id` |
| GET | `/api/persona/get-personas` | — | `page` | — |
| GET | `/api/personalization/memory` | — | — | — |
| GET | `/api/personalization/settings` | — | — | — |
| POST | `/api/personalization/settings` | `styles_augmentation` | — | — |
| POST | `/api/playlist/update_clips` | `playlist_id`, `update_type`, `metadata`, `recommendation_metadata` | — | — |
| POST | `/api/preferences/clip-review/opt-out` | — | — | — |
| GET | `/api/preferences/clip-review/pending` | — | — | — |
| POST | `/api/preferences/clip-review/submit` | `prompt_id`, `choice`, `feedback`, `listen_time_seconds_clip_a`, `listen_time_seconds_clip_b`, `listen_time_seconds_total` | — | — |
| GET | `/api/processed_clip/{processed_clip_id}/waveform-aggregates` | — | — | `processed_clip_id` |
| POST | `/api/profiles/pin-clip/{clip_id}` | `submit_to_contest`, `max_pins` | — | `clip_id` |
| GET | `/api/profiles/pinned-clips` | — | — | — |
| POST | `/api/project/{project_id}/clips` | `update_type`, `metadata` | — | `project_id` |
| GET | `/api/project/{project_id}/pinned-clips` | — | — | `project_id` |
| DELETE | `/api/recommend/feedback/song/{clip_id}` | — | — | `clip_id` |
| POST | `/api/recommend/feedback/song/{clip_id}` | — | — | `clip_id` |
| GET | `/api/studio-assets` | — | `limit`, `cursor` | — |
| POST | `/api/studio-assets` | `upload_id`, `title` | — | — |
| GET | `/api/studio-assets/{asset_id}` | — | — | `asset_id` |
| GET | `/api/studio-assets/library` | — | `media_type`, `category` | — |
| POST | `/api/studio-assets/uploads` | `media_type`, `extension`, `category` | — | — |
| GET | `/api/studio/{project_id}/version/{version_id}` | — | — | `project_id`, `version_id` |
| GET | `/api/studio/{project_id}/versions` | — | `return_days_only` | `project_id` |
| GET | `/api/studio/clip/{clip_id}/download` | — | `format` | `clip_id` |
| GET | `/api/studio/clips/{clip_id}/projects` | — | — | `clip_id` |
| POST | `/api/studio/create-or-load-project-for-clip/{clip_id}` | — | — | `clip_id` |
| POST | `/api/studio/create-project` | — | — | — |
| GET | `/api/studio/list-projects` | — | `cursor`, `limit`, `name`, `archived`, `sort_order`, `bookmarked` | — |
| GET | `/api/studio/project_revision/{revision_id}` | — | — | `revision_id` |
| POST | `/api/studio/project_revision/{revision_id}/clone` | `title` | — | `revision_id` |
| GET | `/api/studio/project/{project_id}` | — | — | `project_id` |
| POST | `/api/studio/project/{project_id}/archive` | — | — | `project_id` |
| POST | `/api/studio/project/{project_id}/bookmark` | `bookmarked` | — | `project_id` |
| POST | `/api/studio/project/{project_id}/metadata` | `title`, `notes`, `image_s3_id` | — | `project_id` |
| POST | `/api/studio/project/{project_id}/unarchive` | — | — | `project_id` |
| POST | `/api/studio/render-state` | `title`, `lyrics`, `state`, `project_id`, `start_beats`, `end_beats`, `downbeats`, `web_client_pathname`, `render_engine`, `encode_latents`, `tags`, `negative_tags`, `style_summary`, `caption`, `studio_project_id`, `studio_project_version_id`, `export_mode` | — | — |
| POST | `/api/studio/render-state-multitrack` | — | — | — |
| POST | `/api/studio/save-project` | `project_id`, `state`, `title`, `base_version_id` | — | — |
| POST | `/api/uploads/audio/{upload_id}/initialize-clip` | `downbeats` | — | `upload_id` |
| POST | `/api/video/generate/{clip_id}` | — | — | `clip_id` |
| GET | `/api/video/generate/{clip_id}/status` | — | — | `clip_id` |
| GET | `/api/video/hooks/suggested_clips` | — | `page_size`, `is_liked`, `is_public_only`, `start_index`, `search_term` | — |

## All endpoints

| Method | Path |
|---|---|
| GET | `/api/{entity_type}/{entity_id}/permissions/invites` |
| POST | `/api/{entity_type}/{entity_id}/permissions/invites` |
| DELETE | `/api/{entity_type}/{entity_id}/permissions/invites/{grantee_uid}` |
| GET | `/api/agent/ably-token` |
| POST | `/api/agent/author-plugin` |
| GET | `/api/agent/author-plugin/{job_id}` |
| POST | `/api/agent/compact` |
| GET | `/api/agent/conversation/{project_id}` |
| POST | `/api/agent/conversation/{project_id}/entries` |
| POST | `/api/agent/conversation/{project_id}/used-actions` |
| POST | `/api/agent/plugin-load-failures` |
| GET | `/api/agent/profiles` |
| POST | `/api/agent/run-completions` |
| POST | `/api/agent/step` |
| POST | `/api/agent/step-v2` |
| POST | `/api/agent/tool-executions` |
| POST | `/api/auth/verify-token` |
| GET | `/api/billing/auto-reload` |
| POST | `/api/billing/auto-reload/disable` |
| POST | `/api/billing/auto-reload/enable` |
| POST | `/api/billing/auto-reload/nudge-check` |
| GET | `/api/billing/conversion-tracking` |
| POST | `/api/billing/create-portal` |
| GET | `/api/billing/info` |
| GET | `/api/billing/pending-churn-offer` |
| POST | `/api/billing/set-default-payment-method` |
| GET | `/api/billing/usage-plan-descriptions` |
| GET | `/api/billing/usage-plan-faq` |
| GET | `/api/billing/usage-plan-web-table-comparison` |
| GET | `/api/billing/usage-plans` |
| POST | `/api/c/check` |
| GET | `/api/clip/{clip_id}` |
| GET | `/api/clip/{clip_id}/permissions` |
| POST | `/api/clip/{clip_id}/permissions/grants` |
| DELETE | `/api/clip/{clip_id}/permissions/grants/{grantee_uid}` |
| PATCH | `/api/clip/{clip_id}/permissions/visibility` |
| GET | `/api/clip/{clip_id}/stems` |
| GET | `/api/clip/{clip_id}/stems/pages` |
| GET | `/api/clips/{clip_id}/attribution` |
| POST | `/api/clips/{clip_id}/toggle_remixes` |
| POST | `/api/clips/{clip_id}/toggle_show_remixes` |
| POST | `/api/clips/adjust-speed` |
| GET | `/api/clips/aligned_clip_siblings` |
| GET | `/api/clips/aligned_clips` |
| GET | `/api/clips/get_songs_by_ids` |
| POST | `/api/clips/reverse-clip` |
| GET | `/api/cms/nudges/{slug}` |
| POST | `/api/cms/nudges/{slug}/seen` |
| DELETE | `/api/comment/{comment_id}` |
| POST | `/api/comment/{comment_id}/reaction` |
| GET | `/api/comment/{comment_id}/replies` |
| POST | `/api/comment/{comment_id}/report` |
| POST | `/api/comment/block-user` |
| POST | `/api/comment/unblock-user` |
| GET | `/api/contests` |
| GET | `/api/custom-model/{custom_model_id}/permissions` |
| DELETE | `/api/custom-model/{custom_model_id}/permissions/grants/{grantee_uid}` |
| POST | `/api/custom-model/{custom_model_id}/permissions/leave` |
| POST | `/api/custom-model/archive` |
| GET | `/api/custom-model/bases` |
| POST | `/api/custom-model/create` |
| PUT | `/api/custom-model/edit` |
| GET | `/api/custom-model/pending` |
| GET | `/api/custom-model/shared` |
| GET | `/api/download/clip/{clip_id}` |
| GET | `/api/download/sample-pack/{clip_id}` |
| POST | `/api/download/sample-pack/{clip_id}` |
| GET | `/api/edit/action/{action_clip_id}` |
| POST | `/api/edit/crop/{clip_id}` |
| POST | `/api/edit/fade/{clip_id}` |
| POST | `/api/feed/v3` |
| POST | `/api/feed/v3/offset` |
| GET | `/api/forbidden` |
| GET | `/api/gen/{clip_id}/aligned_lyrics/v2` |
| POST | `/api/gen/{clip_id}/aligned_lyrics/v2` |
| GET | `/api/gen/{clip_id}/aligned_lyrics/v3` |
| POST | `/api/gen/{clip_id}/aligned_lyrics/v3` |
| POST | `/api/gen/{clip_id}/comment` |
| GET | `/api/gen/{clip_id}/comments` |
| GET | `/api/gen/{clip_id}/comments/count` |
| POST | `/api/gen/{clip_id}/convert_wav` |
| GET | `/api/gen/{clip_id}/downbeats` |
| GET | `/api/gen/{clip_id}/midi` |
| GET | `/api/gen/{clip_id}/novelty-sections` |
| POST | `/api/gen/{clip_id}/toggle_comments` |
| GET | `/api/gen/{clip_id}/wav_file` |
| GET | `/api/gen/{clip_id}/waveform-aggregates` |
| POST | `/api/gen/{gen_id}/increment_action_count` |
| POST | `/api/gen/{gen_id}/increment_play_count/v2` |
| POST | `/api/gen/{gen_id}/listen_milestone` |
| POST | `/api/gen/{gen_id}/set_audio_description` |
| POST | `/api/gen/{gen_id}/set_display_tags` |
| POST | `/api/gen/{gen_id}/set_metadata` |
| POST | `/api/gen/{gen_id}/set_visibility` |
| POST | `/api/gen/{gen_id}/unlock-preview` |
| POST | `/api/gen/{gen_id}/update_feedback_state` |
| POST | `/api/gen/{gen_id}/update_reaction_type` |
| POST | `/api/gen/bulk_increment_play_counts/v2` |
| POST | `/api/gen/increment_action_counts` |
| POST | `/api/gen/trash` |
| POST | `/api/generate/concat/v2` |
| GET | `/api/generate/cowrite-lyrics/models` |
| POST | `/api/generate/lyrics-mashup` |
| GET | `/api/generate/lyrics/{lyrics_id}` |
| POST | `/api/generate/sum` |
| POST | `/api/generate/upsample` |
| GET | `/api/generate/v2-web` |
| POST | `/api/instrument/describe-doodle` |
| POST | `/api/invite` |
| GET | `/api/lyricists` |
| POST | `/api/lyricists` |
| DELETE | `/api/lyricists/{lyricist_id}` |
| GET | `/api/lyricists/{lyricist_id}` |
| PATCH | `/api/lyricists/{lyricist_id}` |
| GET | `/api/lyrics-projects` |
| POST | `/api/lyrics-projects` |
| DELETE | `/api/lyrics-projects/{project_id}` |
| GET | `/api/lyrics-projects/{project_id}` |
| PATCH | `/api/lyrics-projects/{project_id}` |
| POST | `/api/lyrics-projects/{project_id}/flush` |
| POST | `/api/mango/rights` |
| GET | `/api/music_player/playbar_state` |
| POST | `/api/music_player/playbar_state` |
| GET | `/api/notification/v2/badge-count` |
| POST | `/api/notification/v2/clear-badge` |
| POST | `/api/notification/v2/read` |
| GET | `/api/notification/v3` |
| POST | `/api/onboarding/audio-upload/abort` |
| POST | `/api/onboarding/audio-upload/remove` |
| POST | `/api/onboarding/back` |
| POST | `/api/onboarding/complete` |
| GET | `/api/onboarding/current` |
| POST | `/api/onboarding/skip` |
| POST | `/api/onboarding/start` |
| POST | `/api/onboarding/submit` |
| POST | `/api/persona/{persona_id}/toggle_love` |
| POST | `/api/persona/create` |
| GET | `/api/persona/get-followed-personas` |
| GET | `/api/persona/get-loved-personas` |
| GET | `/api/persona/get-persona/{persona_id}` |
| GET | `/api/persona/get-personas` |
| GET | `/api/personalization/memory` |
| GET | `/api/personalization/settings` |
| POST | `/api/personalization/settings` |
| POST | `/api/playlist_reaction/{playlist_id}/increment_play_count` |
| POST | `/api/playlist_reaction/{playlist_id}/set_visibility` |
| POST | `/api/playlist_reaction/{playlist_id}/update_reaction_type` |
| GET | `/api/playlist/{playlist_id}` |
| POST | `/api/playlist/create` |
| GET | `/api/playlist/me` |
| POST | `/api/playlist/set_metadata` |
| POST | `/api/playlist/trash` |
| POST | `/api/playlist/update_clips` |
| PATCH | `/api/playlist/v2/{playlist_id}` |
| POST | `/api/playlist/v2/{playlist_id}/cover-image` |
| DELETE | `/api/playlist/v2/{playlist_id}/save` |
| POST | `/api/playlist/v2/{playlist_id}/save` |
| POST | `/api/playlist/v2/{playlist_id}/tracks/add` |
| POST | `/api/playlist/v2/{playlist_id}/tracks/remove` |
| POST | `/api/playlist/v2/{playlist_id}/tracks/reorder-by-index` |
| POST | `/api/playlist/v2/{playlist_id}/trash` |
| POST | `/api/plugins` |
| GET | `/api/plugins/{plugin_id}` |
| POST | `/api/plugins/{plugin_id}/archive` |
| POST | `/api/plugins/{plugin_id}/default-version` |
| POST | `/api/plugins/{plugin_id}/metadata` |
| GET | `/api/plugins/{plugin_id}/presets` |
| POST | `/api/plugins/{plugin_id}/presets` |
| GET | `/api/plugins/{plugin_id}/presets/{preset_id}` |
| POST | `/api/plugins/{plugin_id}/save` |
| POST | `/api/plugins/{plugin_id}/unarchive` |
| GET | `/api/plugins/{plugin_id}/versions` |
| GET | `/api/plugins/catalog` |
| GET | `/api/plugins/version/{plugin_version_id}` |
| POST | `/api/preferences/clip-review/opt-out` |
| GET | `/api/preferences/clip-review/pending` |
| POST | `/api/preferences/clip-review/submit` |
| PUT | `/api/privacy/data-sharing-consent` |
| GET | `/api/processed_clip/{processed_clip_id}/waveform-aggregates` |
| POST | `/api/profiles` |
| GET | `/api/profiles/{handle}` |
| GET | `/api/profiles/{handle}/info` |
| POST | `/api/profiles/follow` |
| GET | `/api/profiles/mutual-followers` |
| POST | `/api/profiles/pin-clip/{clip_id}` |
| GET | `/api/profiles/pinned-clips` |
| POST | `/api/project` |
| GET | `/api/project/{project_id}` |
| POST | `/api/project/{project_id}/clips` |
| DELETE | `/api/project/{project_id}/collaborators` |
| GET | `/api/project/{project_id}/collaborators` |
| DELETE | `/api/project/{project_id}/collaborators/me` |
| POST | `/api/project/{project_id}/invite` |
| POST | `/api/project/{project_id}/metadata` |
| DELETE | `/api/project/{project_id}/pin` |
| POST | `/api/project/{project_id}/pin` |
| GET | `/api/project/{project_id}/pinned-clips` |
| GET | `/api/project/feed` |
| GET | `/api/project/me` |
| POST | `/api/project/trash` |
| GET | `/api/prompts/suggestions` |
| POST | `/api/prompts/suggestions/contextual` |
| POST | `/api/prompts/upsample` |
| GET | `/api/prompts/v2` |
| POST | `/api/prompts/v2` |
| DELETE | `/api/prompts/v2/{prompt_id}` |
| POST | `/api/queue/inject` |
| POST | `/api/queue/start` |
| POST | `/api/realtime/token` |
| DELETE | `/api/recommend/feedback/song/{clip_id}` |
| POST | `/api/recommend/feedback/song/{clip_id}` |
| GET | `/api/report_v2/refund_prompt` |
| POST | `/api/report_v2/refund_prompt/clicked` |
| POST | `/api/search` |
| POST | `/api/search/history` |
| POST | `/api/search/users` |
| GET | `/api/session` |
| POST | `/api/share/attribute` |
| GET | `/api/share/code/{share_id}` |
| POST | `/api/share/event` |
| POST | `/api/share/link` |
| GET | `/api/share/stats` |
| POST | `/api/signout` |
| POST | `/api/song_copy/send-song` |
| POST | `/api/statsig/experiment` |
| GET | `/api/statsig/experiment/forked-onboarding` |
| GET | `/api/studio-assets` |
| POST | `/api/studio-assets` |
| GET | `/api/studio-assets/{asset_id}` |
| GET | `/api/studio-assets/library` |
| POST | `/api/studio-assets/uploads` |
| GET | `/api/studio/{project_id}/version/{version_id}` |
| GET | `/api/studio/{project_id}/versions` |
| GET | `/api/studio/clip/{clip_id}/download` |
| GET | `/api/studio/clips/{clip_id}/projects` |
| POST | `/api/studio/create-or-load-project-for-clip/{clip_id}` |
| POST | `/api/studio/create-project` |
| GET | `/api/studio/list-projects` |
| GET | `/api/studio/project_revision/{revision_id}` |
| POST | `/api/studio/project_revision/{revision_id}/clone` |
| GET | `/api/studio/project/{project_id}` |
| POST | `/api/studio/project/{project_id}/archive` |
| POST | `/api/studio/project/{project_id}/bookmark` |
| POST | `/api/studio/project/{project_id}/metadata` |
| POST | `/api/studio/project/{project_id}/unarchive` |
| POST | `/api/studio/render-state` |
| POST | `/api/studio/render-state-multitrack` |
| POST | `/api/studio/save-project` |
| GET | `/api/survey/survey-questions/{group_id}` |
| POST | `/api/survey/survey-responses` |
| GET | `/api/unified/explore` |
| POST | `/api/unified/feed` |
| GET | `/api/unified/homepage` |
| GET | `/api/unified/homepage/explore` |
| GET | `/api/unified/homepage/explore/mobile` |
| GET | `/api/unified/library` |
| POST | `/api/unified/search/omnisearch` |
| POST | `/api/unified/search/suggest` |
| DELETE | `/api/unified/search/suggest/history` |
| DELETE | `/api/unified/search/suggest/history/item` |
| POST | `/api/uploads/audio` |
| GET | `/api/uploads/audio/{upload_id}` |
| POST | `/api/uploads/audio/{upload_id}/initialize-clip` |
| POST | `/api/uploads/audio/{upload_id}/upload-finish` |
| POST | `/api/uploads/image` |
| POST | `/api/uploads/image/{upload_id}/upload-finish` |
| POST | `/api/uploads/midi` |
| POST | `/api/uploads/midi/{upload_id}/upload-finish` |
| POST | `/api/uploads/video` |
| GET | `/api/uploads/video/{upload_id}` |
| POST | `/api/uploads/video/{upload_id}/upload-finish` |
| POST | `/api/user/delete-account` |
| GET | `/api/user/get_user_session_id` |
| GET | `/api/user/me` |
| GET | `/api/user/metadata` |
| POST | `/api/user/reset_onboarding` |
| GET | `/api/user/tos_acceptance` |
| POST | `/api/user/tos_acceptance` |
| POST | `/api/user/update_user_config` |
| POST | `/api/user/user_config` |
| POST | `/api/user/vip_program_acceptance` |
| GET | `/api/v2/integrations` |
| DELETE | `/api/v2/integrations/musixmatch` |
| POST | `/api/v2/integrations/musixmatch/authorize-url` |
| PUT | `/api/video_gen/favorite` |
| POST | `/api/video_gen/history` |
| POST | `/api/video_gen/pending_batches` |
| POST | `/api/video_gen/poll_batches` |
| POST | `/api/video_gen/video/{video_id}/first-frame` |
| POST | `/api/video_gen/video/{video_id}/last-frame` |
| POST | `/api/video_gen/video/generate` |
| POST | `/api/video/generate/{clip_id}` |
| GET | `/api/video/generate/{clip_id}/status` |
| GET | `/api/video/hooks/{hook_id}` |
| DELETE | `/api/video/hooks/comments/{comment_id}` |
| POST | `/api/video/hooks/comments/{comment_id}/reaction` |
| GET | `/api/video/hooks/comments/{comment_id}/replies` |
| POST | `/api/video/hooks/comments/{comment_id}/report` |
| POST | `/api/video/hooks/comments/{hook_id}/comment` |
| GET | `/api/video/hooks/comments/{hook_id}/comments` |
| GET | `/api/video/hooks/comments/{hook_id}/comments/count` |
| POST | `/api/video/hooks/create` |
| POST | `/api/video/hooks/fetch_hook_lyrics` |
| GET | `/api/video/hooks/suggested_clips` |
| GET | `/api/visual/assets` |
| DELETE | `/api/visual/assets/{id}` |
| GET | `/api/visual/assets/{id}` |
| POST | `/api/visual/assets/uploads` |
| POST | `/api/visual/assets/uploads/{id}/complete` |
| GET | `/api/visual/characters` |
| DELETE | `/api/visual/characters/{assetId}` |
| PUT | `/api/visual/characters/{assetId}` |
| GET | `/api/visual/cost` |
| GET | `/api/visual/generations` |
| POST | `/api/visual/generations` |
| GET | `/api/visual/generations/{id}` |
| DELETE | `/api/visual/generations/{id}/takes/{take}` |
| GET | `/api/visual/models` |
| GET | `/api/visual/presets` |
| POST | `/api/visual/prompts/rewrite` |
| POST | `/api/visual/signals` |
| POST | `/api/visual/workflows/{name}/run` |
