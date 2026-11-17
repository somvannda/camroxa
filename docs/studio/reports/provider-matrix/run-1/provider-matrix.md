# Provider matrix run — 2026-11-17T08-11-16-104Z

- base: http://127.0.0.1:8100
- mode: execute
- budget: 320 credits · spent: 0 · remaining: 320
- model: V6_MINI

| # | Operation | Endpoint | Status | Credits | Platform id | musicapi job | Provider clip | Persona | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Generate a song | `/web-music/generate` | error | 0 |  |  |  |  | GET /web-music/generations/3f55666f-0044-4f5c-abf7-5b77a94bbbab → 401: [object Object] |
| 2 | Export WAV | `/web-music/generations/{task_id}/download-wav?variant=ok` | error | 0 |  |  |  |  | no source generation — the generate step must run first (or pass --task) |
| 3 | Export MP3 | `/web-music/generations/{task_id}/download?variant=ok` | error | 0 |  |  |  |  | no source generation — the generate step must run first (or pass --task) |
| 4 | Voice persona | `/web-music/studio/voice/personas` | error | 0 |  |  |  |  | no source generation — the generate step must run first (or pass --task) |
| 5 | Bounce / upload (upload + upload-extend) | `/web-music/studio/uploads → /web-music/studio/uploads/{id}/extend` | error | 0 |  |  |  |  | no source generation — the generate step must run first (or pass --task) |
| 6 | Stems — 2 track | `/web-music/studio/generations/{task_id}/stems` | error | 0 |  |  |  |  | no source generation — the generate step must run first (or pass --task) |
| 7 | Cover | `/web-music/studio/generations/{task_id}/cover` | error | 0 |  |  |  |  | no source generation — the generate step must run first (or pass --task) |
| 8 | Extend | `/web-music/studio/generations/{task_id}/extend` | error | 0 |  |  |  |  | no source generation — the generate step must run first (or pass --task) |
| 9 | Remaster | `/web-music/studio/generations/{task_id}/remaster` | error | 0 |  |  |  |  | no source generation — the generate step must run first (or pass --task) |
| 10 | Add vocals | `/web-music/studio/generations/{task_id}/add-vocals` | error | 0 |  |  |  |  | no source generation — the generate step must run first (or pass --task) |
| 11 | Add instrumental | `/web-music/studio/generations/{task_id}/add-instrumental` | error | 0 |  |  |  |  | no source generation — the generate step must run first (or pass --task) |
| 12 | Replace section | `/web-music/studio/generations/{task_id}/replace-section` | error | 0 |  |  |  |  | no source generation — the generate step must run first (or pass --task) |
| 13 | Mashup (+ fixture generation) | `/web-music/studio/mashup` | error | 0 |  |  |  |  | no source generation — the generate step must run first (or pass --task) |
| 14 | Stems — 12 track | `/web-music/studio/generations/{task_id}/stems` | error | 0 |  |  |  |  | no source generation — the generate step must run first (or pass --task) |
