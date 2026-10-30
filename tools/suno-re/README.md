# Suno reference extraction toolkit

Repeatable tooling for learning from the **publicly shipped** Suno web client, so we
can design our own API and UI faster.

## Boundary (non-negotiable)

- We fetch only assets a normal visitor downloads: the HTML of a public route and the
  `/_next/static/**` chunks it references.
- We **never** call private endpoints, bypass auth, or scrape account data.
- We store **derived facts only** (endpoint paths, method, field names, labels).
  Minified source is not committed. Raw chunks stay in a temp directory.
- Nothing derived here is a runtime dependency of our product (see D-002 in
  `docs/studio/PROJECT_DECISIONS.md`). It is a specification source, not an integration.

## Scripts

| Script | Purpose |
|---|---|
| `fetch-bundle.mjs` | Download a public route's HTML + every JS chunk it references into a temp dir. |
| `extract-contracts.mjs` | Parse chunks → `docs/studio/reference/endpoint-inventory.json` and `.md`. |
| `check-musicapi-parity.mjs` | Compare the reference inventory with our own routes and print coverage. |

## Usage

```bash
# 1. fetch (temp dir outside the repo)
node tools/suno-re/fetch-bundle.mjs --url https://suno.com/studio --out "$TEMP/suno-re"

# 2. extract
node tools/suno-re/extract-contracts.mjs --chunks "$TEMP/suno-re/chunks"

# 3. compare with our stack
node tools/suno-re/check-musicapi-parity.mjs
```

## What this unlocks

1. **Contract-first API work.** The reference inventory tells us which capabilities
   exist, their HTTP shape, and their field names. We then design *our* contract for
   the same capability instead of guessing.
2. **Coverage tracking.** `check-musicapi-parity.mjs` turns "do we support stems,
   replace-section, mashup…" into a number instead of an opinion.
3. **Faster UI discovery.** UI strings present in shared chunks (`Metronome`, `Takes`,
   `automation`, …) seed the control inventory. Route-scoped chunks only load when
   authenticated; see the limitation below.

## Known limitation

The marketing route loads the shared API client but not the authenticated Studio
editor bundle, so control labels that live only in the editor route (`Add track`,
`Piano Roll`, …) are absent until a signed-in session's chunks are captured. API
contracts, however, are fully recoverable: they ship in shared chunks.

Record which mode a run used:

- `anonymous` — public route only (current).
- `authenticated` — route chunks captured while signed in (needs a live session).
