/**
 * CAMXORA boot entry for the hosted editor.
 *
 * The stock Rea entry (`src/main.ts`) owns the renderer, the DOM shell and the
 * rAF loop. The host adapter is imported after it so the `editor*` globals the
 * editor publishes exist before the adapter subscribes to them. Keeping this
 * order explicit in one module is safer than relying on two `<script>` tags.
 *
 * `scripts/sync-vizzy.mjs` copies this file to `src/host/boot.ts` and points
 * `index.html` at it.
 */
import "../main";
import "./host-adapter";
