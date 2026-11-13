# Suno agent plugin authoring (designed plugins)

**Decision (2026-11-13):** designed plugins are rebuilt on Suno's authoring agent
(option 1 in `PARITY_REMOVAL_LIST.md`). Our local deterministic designer is gone;
"Build it" asks the agent, and the resulting plugin lives in the Suno account's
plugin library so a chain entry can reference it.

Live contract captured on 2026-11-13 with the pinned account (throwaway project,
archived afterwards). Jobs are generative, spend credits and usually take a few
minutes (the probe finished in ~25 s).

## 1. Author

```
POST /api/agent/author-plugin
{
  "instruction": "Build a gentle high-pass filter with Cutoff and Mix controls.",
  "required_controls": ["Cutoff", "Mix"],
  "studioAgentSessionId": "studio_agent_project#<suno-project-id>",
  "studioProjectId": "<suno-project-id>"
}
-> 200 { "job_id": "<uuid>" }
```

`studioAgentSessionId` is the studio agent conversation id for the mirrored
project: `studio_agent_project#<suno project id>`. `GET
/api/user/get_user_session_id` returns a different (user-session) id, which the
endpoint also accepts; the conversation id is the one the reference uses per
project. `required_controls` is capped at 32 items; `instruction` is required.

Errors are JSON like `{status_code, detail, error_type, retryable}`.

## 2. Poll

```
GET /api/agent/author-plugin/{job_id}
```

Pending payload:

```json
{
  "status": "pending",
  "phase": "running",
  "queue_deadline_at_ms": 1794578382516,
  "progress": [{ "message": "Rendering test audio to verify the sound", "stage": "probe_audio" }]
}
```

Observed stages: `starting` → `submit_design_brief` → `probe_audio` → `ready`.

Ready payload adds a `descriptor` (no library ids; `id` and `pluginVersionId`
inside it are placeholders):

```json
{
  "status": "ready",
  "descriptor": {
    "displayName": "Gentle High-Pass",
    "description": "A smooth stereo high-pass filter …",
    "kind": "effect",
    "id": "agent-generated-plugin",
    "pluginVersionId": "agent-generated-plugin-version",
    "published": false,
    "revision": 1,
    "parameters": [
      { "name": "Cutoff", "label": "Cutoff", "default": 120,
        "range": { "min": 20, "max": 2000 }, "scale": "log", "unit": "hz" },
      { "name": "Mix", "label": "Mix", "default": 0.5,
        "range": { "min": 0, "max": 1 }, "scale": "linear", "unit": "percent" }
    ],
    "ports": { "audioIn": {…}, "audioOut": {…}, "extraInputs": [], "extraOutputs": [] },
    "source": { "code": "function build(g, config) { … }", "lang": "js", "metadata": {…} },
    "ui": { "compact": {…} }
  }
}
```

The descriptor is self-describing: control **names** are the parameter keys used
by `signalChain[].params`, and the code is the real DSP. Our engine does not run
that code; local playback keeps the family-based approximation from
`lib/studio-plugin-audio.ts`.

## 3. Save to the library

Creating a plugin needs the **trailing slash** — `/api/plugins` answers an HTML
404 while `/api/plugins/` works:

```
POST /api/plugins/            { "name": "Gentle High-Pass" }
-> 200 { "id": "<plugin-id>", "name": …, "is_owner": true, "published": false }
```

Then save the descriptor minus the server-managed keys (`id`,
`pluginVersionId`, `published`, `revision`):

```
POST /api/plugins/{plugin_id}/save
{ "payload": { "displayName", "description", "kind", "parameters", "ports", "source", "ui" } }
-> 200 { "plugin_version_id": "<version-id>", "revision": 1 }
```

A new plugin's first version becomes its default. `GET /api/plugins/{id}` returns
`{plugin, default_version: {plugin_version_id, payload, …}}`; the payload is what
`lib/studio-designer.ts` converts back into a local `CustomPlugin`.

## 4. Chain entry

Verified read-back on a throwaway project: this entry is accepted and echoed
verbatim.

```json
{
  "id": "<stable uuid>",
  "pluginVersionId": "<plugin_version_id>",
  "catalogPluginId": "<plugin_id>",
  "bypassed": false,
  "params": { "Cutoff": 300, "Mix": 0.6 },
  "paramAutomation": {}
}
```

`params` values are Suno's native units (percent controls are 0–1). The codec
writes `catalogPluginId`/`pluginVersionId` from the entry's `sunoPluginId` /
`sunoPluginVersionId` (or from the embedded `custom` snapshot), and on pull maps
such an entry back to `pluginId: "custom"` with the ids and a hydrated `custom`
snapshot. A pull fetches the definitions from the plugin library
(`GET /api/plugins/{id}`) so a project opened on another device still renders the
plugin; entries whose plugin was deleted keep their ids and params.

## 5. Implementation map

| Surface | Where |
|---|---|
| Provider calls | `musicapi/src/client.ts` (`authorPlugin`, `getPluginAuthoringJob`, `createPlugin`, `savePluginVersion`, `getPlugin`) |
| Job ledger + idempotent save | `musicapi/src/sunoStudio.ts` (`authorPlugin`, `pluginAuthoringJob`), migration `0045_studio_plugin_authoring.sql` |
| Internal routes | `POST/GET /internal/studio/projects/:id/plugins/author…` in `musicapi/src/server.ts` |
| Web-facing proxy | `platform_api/routers/web_music.py`, `services/web_music_service.py` |
| Designer UI | `camxora.com/lib/studio-designer.ts`, `components/studio/StudioEditorShell.tsx` |
| Mirror | `musicapi/src/studioStateCodec.ts` (`chainEntryToSuno`/`chainEntryFromSuno`, `sunoPluginToLocalCustom`) |

## 6. Probe artefacts and cleanup

- Authoring job `cf4d325a-9dcd-4d3e-bed0-02c425b496ac` (descriptor in this doc).
- Probe project `dc86a723-823b-4782-b705-105f6bdd658f` — archived.
- Chain round-trip project `fc799784-9c13-439c-b358-939df9ab2d50` — archived.
- Probe library plugin `10c35bed-09ff-4bfe-86a8-f386bc281934` — archived.

The internal route was then verified live on 2026-11-13 against musicapi `:4003`
using the already-ready job (no new credits): no token → 401, empty instruction →
400, first poll → `ready` with a created library plugin in ~1.8 s, second poll →
the same ids in <1 ms (ledger idempotency). The created plugin
`a0af0a7b-04f4-479e-a15d-4102d08d220e` was archived and the test ledger row
removed.

## 7. Still open

- Credit accounting: the agent spends Suno credits; there is no local pricing
  row for it yet, so the sync chip does not show a cost.
- The local engine approximates the authored DSP by family; sample-accurate
  parity would require running Suno's plugin code, which our engine cannot do.
