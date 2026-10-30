/**
 * Pure chain operations for the Studio plugin chain.
 *
 * All functions are immutable and side-effect free so the editor can use them
 * inside a reducer, in undo history, and in tests without an AudioContext.
 *
 * Reference semantics (spec §48–§50):
 * - chain order is signal order;
 * - a plugin may appear more than once (slots are keyed by `entryId`);
 * - editing a parameter marks the preset dirty → the header shows `Custom`
 *   and an `Update` action;
 * - each slot can be bypassed and popped out independently.
 */

import {
  createChainEntry,
  getPlugin,
  sanitizeParams,
  type PluginChainEntry,
  type PluginId,
} from "@/lib/studio-plugins";

let counter = 0;

/** Deterministic-enough id: stable within a session, unique across slots. */
export function nextEntryId(pluginId: PluginId): string {
  counter += 1;
  return `${pluginId}-${Date.now().toString(36)}-${counter}`;
}

export function addPlugin(
  chain: PluginChainEntry[],
  pluginId: PluginId,
  atIndex?: number
): PluginChainEntry[] {
  const entry = createChainEntry(pluginId, nextEntryId(pluginId));
  const index = atIndex == null ? chain.length : Math.min(Math.max(atIndex, 0), chain.length);
  return [...chain.slice(0, index), entry, ...chain.slice(index)];
}

export function removePlugin(chain: PluginChainEntry[], entryId: string): PluginChainEntry[] {
  return chain.filter((entry) => entry.entryId !== entryId);
}

export function movePlugin(
  chain: PluginChainEntry[],
  entryId: string,
  toIndex: number
): PluginChainEntry[] {
  const from = chain.findIndex((entry) => entry.entryId === entryId);
  if (from < 0) return chain;
  const target = Math.min(Math.max(toIndex, 0), chain.length - 1);
  if (from === target) return chain;
  const next = chain.slice();
  const [entry] = next.splice(from, 1);
  next.splice(target, 0, entry);
  return next;
}

/**
 * Set one parameter. Values are clamped through the registry, and the slot is
 * marked dirty so the UI can offer `Update` (reference: preset label "Custom").
 */
export function setParam(
  chain: PluginChainEntry[],
  entryId: string,
  key: string,
  value: number
): PluginChainEntry[] {
  return chain.map((entry) => {
    if (entry.entryId !== entryId) return entry;
    const params = sanitizeParams(entry.pluginId, { ...entry.params, [key]: value });
    const changed = params[key] !== entry.params[key];
    if (!changed) return entry;
    return { ...entry, params, dirty: true };
  });
}

export function setParamSet(
  chain: PluginChainEntry[],
  entryId: string,
  params: Record<string, number>
): PluginChainEntry[] {
  return chain.map((entry) =>
    entry.entryId === entryId
      ? { ...entry, params: sanitizeParams(entry.pluginId, { ...entry.params, ...params }), dirty: true }
      : entry
  );
}

/** Commit the tweak to the named preset (reference: `Update` writes it back). */
export function commitPreset(
  chain: PluginChainEntry[],
  entryId: string,
  presetName?: string
): PluginChainEntry[] {
  return chain.map((entry) =>
    entry.entryId === entryId
      ? {
          ...entry,
          presetName: presetName ?? (entry.presetName === "Custom" ? "Default" : entry.presetName),
          dirty: false,
        }
      : entry
  );
}

/** Load a preset: replaces params wholesale and clears the dirty state. */
export function applyPreset(
  chain: PluginChainEntry[],
  entryId: string,
  preset: { id: string | null; name: string; params: Record<string, number>; mode?: string }
): PluginChainEntry[] {
  return chain.map((entry) =>
    entry.entryId === entryId
      ? {
          ...entry,
          presetId: preset.id,
          presetName: preset.name,
          mode: preset.mode ?? entry.mode,
          params: sanitizeParams(entry.pluginId, preset.params),
          dirty: false,
        }
      : entry
  );
}

export function toggleBypass(chain: PluginChainEntry[], entryId: string): PluginChainEntry[] {
  return chain.map((entry) =>
    entry.entryId === entryId ? { ...entry, bypassed: !entry.bypassed } : entry
  );
}

export function togglePoppedOut(chain: PluginChainEntry[], entryId: string): PluginChainEntry[] {
  return chain.map((entry) =>
    entry.entryId === entryId ? { ...entry, poppedOut: !entry.poppedOut } : entry
  );
}

export function setMode(
  chain: PluginChainEntry[],
  entryId: string,
  mode: string
): PluginChainEntry[] {
  return chain.map((entry) => {
    if (entry.entryId !== entryId) return entry;
    const plugin = getPlugin(entry.pluginId);
    if (!plugin?.modes?.some((m) => m.id === mode)) return entry;
    return { ...entry, mode };
  });
}

/** Slots that actually affect audio, in signal order. */
export function activeChain(chain: PluginChainEntry[]): PluginChainEntry[] {
  return chain.filter((entry) => !entry.bypassed && getPlugin(entry.pluginId));
}

/**
 * Drop unknown plugin ids and unknown parameters from a persisted chain, so a
 * stale or hostile project document cannot reach the audio graph.
 */
export function sanitizeChain(input: unknown): PluginChainEntry[] {
  if (!Array.isArray(input)) return [];
  const out: PluginChainEntry[] = [];
  const seen = new Set<string>();
  for (const raw of input) {
    if (!raw || typeof raw !== "object") continue;
    const candidate = raw as Partial<PluginChainEntry>;
    if (typeof candidate.pluginId !== "string") continue;
    const plugin = getPlugin(candidate.pluginId);
    if (!plugin) continue;
    const entryId =
      typeof candidate.entryId === "string" && candidate.entryId && !seen.has(candidate.entryId)
        ? candidate.entryId
        : nextEntryId(plugin.id);
    seen.add(entryId);
    const mode =
      typeof candidate.mode === "string" && plugin.modes?.some((m) => m.id === candidate.mode)
        ? candidate.mode
        : plugin.modes?.[0]?.id;
    out.push({
      entryId,
      pluginId: plugin.id,
      presetId: typeof candidate.presetId === "string" ? candidate.presetId : null,
      presetName: typeof candidate.presetName === "string" ? candidate.presetName : "Default",
      dirty: Boolean(candidate.dirty),
      mode,
      params: sanitizeParams(
        plugin.id,
        candidate.params as Record<string, unknown> | undefined
      ),
      assetId: typeof candidate.assetId === "string" ? candidate.assetId : null,
      bypassed: Boolean(candidate.bypassed),
      poppedOut: Boolean(candidate.poppedOut),
    });
  }
  return out;
}

/** Sanitise a whole `trackId -> chain` map from a persisted document. */
export function sanitizeChainMap(input: unknown): Record<string, PluginChainEntry[]> {
  if (!input || typeof input !== "object") return {};
  const out: Record<string, PluginChainEntry[]> = {};
  for (const [trackId, value] of Object.entries(input as Record<string, unknown>)) {
    if (typeof trackId !== "string" || !trackId) continue;
    const chain = sanitizeChain(value);
    if (chain.length) out[trackId] = chain;
  }
  return out;
}
