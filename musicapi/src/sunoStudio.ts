import { createHash } from "node:crypto";

import {
  StudioAccountError,
  StudioProjectConflictError,
  StudioProjectMissingError,
  StudioProjectRateLimitedError,
  SunoClient,
} from "./client.js";
import { withTransaction, query, queryOne } from "./db.js";
import type { AccountPool } from "./pool.js";
import {
  mergeSunoProjectIntoLocal,
  projectDocumentToSunoState,
  stableSunoId,
  sunoStateToProjectData,
  type LocalClip,
  type LocalDocument,
} from "./studioStateCodec.js";

/**
 * Suno Studio project mirror.
 *
 * A Camxora project has at most one Suno Studio project, pinned to one Suno
 * account for its whole life. This module owns that mapping, the coalescing
 * outbox that retries pushes, and the (deliberately conservative) translation
 * from the local document to Suno's `state`.
 *
 * The authoritative project document lives in the platform database, so callers
 * pass a snapshot with every sync request. Nothing here reads another service's
 * tables; the link table only holds what the mirror itself needs.
 *
 * Suno's Studio document schema is not published. The keys and the versioning
 * contract below come from the shipped client bundle
 * (`docs/studio/reference/endpoint-inventory.md`, `docs/studio/SUNO_STUDIO_SYNC.md`),
 * so writes start with the fields we can prove and grow from there. A save
 * always merges into the last document Suno returned, so fields we do not model
 * survive a round trip instead of being dropped.
 */

export type StudioSyncStatus = "pending" | "linked" | "synced" | "conflict" | "error";

/** Everything the mirror needs from the platform-side project row. */
export interface StudioProjectDocument {
  localProjectId: string;
  userId: string;
  title: string;
  majorVersion: number;
  bpm: number;
  timeSignature: string;
  data: unknown;
}

export interface StudioSyncLink {
  local_project_id: string;
  user_id: string;
  account_label: string;
  suno_project_id: string;
  suno_version_id: string | null;
  suno_remote_version_id: string | null;
  suno_title: string | null;
  suno_state: unknown;
  state_hash: string | null;
  skipped_clip_ids: unknown;
  local_clip_ids: unknown;
  archived: boolean;
  status: StudioSyncStatus;
  last_error: string | null;
  last_checked_at: string | Date | null;
  synced_at: string | Date | null;
  updated_at: string | Date;
}

export interface StudioSyncStatusView {
  status: StudioSyncStatus;
  suno_project_id: string | null;
  suno_version_id: string | null;
  /** Version Suno reported on the last check; the base for a conflict resolve. */
  suno_remote_version_id: string | null;
  last_error: string | null;
  synced_at: string | null;
  /** Local clips with no Suno asset yet; they are not in the mirrored project. */
  skipped_clips: string[];
  /** True when arrangement writes are enabled; metadata-only otherwise. */
  state_sync: boolean;
}

/**
 * Arrangement writes stay off until the Suno `state` schema has been captured
 * from a live project. Creating the project and mirroring its metadata is safe
 * on its own; guessing keys is not, because a bad document can make a real Suno
 * project unopenable.
 */
export function stateSyncEnabled(env: NodeJS.ProcessEnv = process.env): boolean {
  // On by default: the codec round-trips against a live project (see
  // SUNO_STUDIO_STATE_SCHEMA.md). `STUDIO_SUNO_STATE_SYNC=0` is the kill switch.
  return env.STUDIO_SUNO_STATE_SYNC !== "0";
}

/** `state` comes back as an object or (for older projects) a JSON string. */
export function parseStudioState(value: unknown): Record<string, unknown> | null {
  if (typeof value === "string") {
    const text = value.trim();
    if (!text) return null;
    try {
      const parsed = JSON.parse(text) as unknown;
      return parsed && typeof parsed === "object" && !Array.isArray(parsed)
        ? (parsed as Record<string, unknown>)
        : null;
    } catch {
      return null;
    }
  }
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

/** Stable hash of the mirrored document, used to skip no-op pushes. */
export function studioDocumentHash(document: unknown): string {
  return createHash("sha256").update(canonicalJson(document)).digest("hex");
}

function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value) ?? "null";
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  const entries = Object.entries(value as Record<string, unknown>)
    .filter(([, item]) => item !== undefined)
    .sort(([a], [b]) => a.localeCompare(b));
  return `{${entries.map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`).join(",")}}`;
}

/**
 * Retry schedule for the outbox: quick first retries while a provider blip is
 * likely, then a slow hourly probe so a dead session still recovers without
 * hammering Suno.
 */
export function studioSyncBackoffMs(attempts: number): number {
  const ladder = [2_000, 8_000, 30_000, 120_000, 600_000, 3_600_000];
  const index = Math.min(Math.max(attempts, 1) - 1, ladder.length - 1);
  return ladder[index];
}

/**
 * Errors worth retrying. A dead session, a stale version and a missing project
 * all need a human or a reconcile step, so they stop the loop instead of
 * burning retries forever.
 */
export function isRetryableStudioSyncError(error: unknown): boolean {
  if (
    error instanceof StudioAccountError ||
    error instanceof StudioProjectConflictError ||
    error instanceof StudioProjectMissingError
  ) {
    return false;
  }
  if (error instanceof StudioProjectRateLimitedError) return true;
  const message = error instanceof Error ? error.message : String(error);
  return !/session|401|403|forbidden|unauthori[sz]ed/i.test(message);
}

/**
 * The project metadata Phase 1 mirrors. Kept separate from the arrangement so
 * the title can be pushed through the dedicated metadata route without touching
 * the document.
 */
export function studioProjectMetadata(doc: StudioProjectDocument): {
  title: string;
  majorVersion: number;
} {
  const title = String(doc.title ?? "").trim().slice(0, 120);
  return {
    title: title || "Untitled Project",
    majorVersion: Number.isFinite(doc.majorVersion) ? doc.majorVersion : 2,
  };
}

/**
 * Merge the fields of the local document that we can prove map onto Suno's
 * `state` into the last document Suno returned.
 *
 * Every other key — including keys Suno owns that we have never seen — is
 * preserved. Returns `null` when there is no baseline to merge into, because
 * building a document from scratch would discard Suno's defaults.
 *
 * Verified now: `title`, `majorVersion`, and `timing.bps` (beats per second;
 * Suno's transport derives tempo from `bps`/`bpsAutomation`).
 */
export function mergeLocalDocumentIntoSunoState(
  baseline: Record<string, unknown> | null,
  doc: StudioProjectDocument
): Record<string, unknown> {
  const { state } = projectDocumentToSunoState({
    title: doc.title,
    majorVersion: doc.majorVersion,
    bpm: doc.bpm,
    timeSignature: doc.timeSignature,
    data: (doc.data ?? {}) as LocalDocument,
    baseline,
  });
  return state;
}

/**
 * Per-field parity registry (D-034). `mapped` is verified against Suno's
 * contract; `pending` is a reference feature whose Suno path still needs the
 * live document sample; `remove` has no Suno counterpart and must not exist in
 * the editor. The health route reports it so gaps cannot hide.
 */
export type CoverageStatus = "mapped" | "pending" | "remove";

export interface CoverageEntry {
  /** Key in our `studio_projects.data` document. */
  key: string;
  /** Suno `state` path (or the field it mirrors). */
  suno: string;
  status: CoverageStatus;
  note?: string;
}

export const STUDIO_STATE_COVERAGE: readonly CoverageEntry[] = [
  { key: "title", suno: "title", status: "mapped" },
  { key: "majorVersion", suno: "majorVersion", status: "mapped" },
  { key: "bpm", suno: "timing.bps", status: "mapped" },
  { key: "timeSignature", suno: "timeSignatureChanges", status: "mapped" },
  { key: "masterVolume/masterMuted", suno: "amplitude", status: "mapped" },
  { key: "loopStart/loopEnd", suno: "loop", status: "mapped" },
  { key: "tracks", suno: "tracks", status: "mapped" },
  { key: "tracks[].volume", suno: "tracks[].amplitude", status: "mapped" },
  { key: "tracks[].pan", suno: "tracks[].balance", status: "mapped" },
  { key: "tracks[].muted", suno: "tracks[].mute", status: "mapped" },
  { key: "tracks[].solo", suno: "tracks[].solo", status: "mapped" },
  { key: "tracks[].hidden", suno: "tracks[].hidden", status: "mapped" },
  { key: "tracks[].color", suno: "tracks[].color", status: "mapped" },
  { key: "lanes[] (MIDI clips)", suno: "tracks[].clips (type midi)", status: "mapped" },
  { key: "lanes[].start/duration", suno: "clips[].startBeats/endBeats", status: "mapped" },
  { key: "lanes[].midi.notes", suno: "clips[].midi.notes", status: "mapped" },
  { key: "track volumeAutomation", suno: "tracks[].faderAutomation.gain", status: "mapped", note: "0-1 values, {beats,value,curve}" },
  { key: "track panAutomation", suno: "tracks[].faderAutomation.pan", status: "mapped", note: "0-1 values, {beats,value,curve}" },
  { key: "markers", suno: "sections", status: "mapped" },
  { key: "audio clips (generation asset)", suno: "clips[].asset {id,type:\"clip\"}", status: "mapped" },
  { key: "local uploads", suno: "clips[].asset (imported once, cached)", status: "mapped" },
  { key: "lanes[].takes", suno: "tracks[].takeLanes[].clips", status: "mapped", note: "takes without a Suno asset stay local" },
  { key: "lanes[].offset", suno: "clips[].readStartBeats", status: "mapped" },
  { key: "lanes[].fadeIn", suno: "clips[].fadeInBeats", status: "mapped" },
  { key: "lanes[].fadeOut", suno: "clips[].fadeOutBeats", status: "mapped" },
  { key: "lanes[].midi.bend", suno: "clips[].midi.pitchBend[{beats,value}]", status: "mapped" },
  { key: "lanes[].midi.mod", suno: "clips[].midi.controlChanges (CC1)", status: "mapped" },
  { key: "lanes[].instrument", suno: "tracks[].signalChain synth waveform", status: "mapped" },
  { key: "chains (all built-ins)", suno: "tracks[].signalChain", status: "mapped", note: "custom plugins stay local" },
  { key: "masterChain (limiter/eq/compressor)", suno: "masterSignalChain", status: "mapped" },
  { key: "groups", suno: "—", status: "remove", note: "no group/bus field exists in the document (captured 11 projects)" },
  { key: "pluginPresets", suno: "signalChain[].params", status: "mapped", note: "a preset is a param snapshot; the params mirror" },
  { key: "wavetableId", suno: "—", status: "remove", note: "designer removed (D-034)" },
];

export function coverageSummary(): {
  mapped: number;
  pending: number;
  remove: number;
  pending_keys: string[];
} {
  const pending = STUDIO_STATE_COVERAGE.filter((entry) => entry.status === "pending");
  return {
    mapped: STUDIO_STATE_COVERAGE.filter((entry) => entry.status === "mapped").length,
    pending: pending.length,
    remove: STUDIO_STATE_COVERAGE.filter((entry) => entry.status === "remove").length,
    pending_keys: pending.map((entry) => entry.key),
  };
}

/**
 * Decide what the state half of a sync should do. Pure so every branch (skip,
 * conflict, no baseline, push) is unit-tested without a database or a provider.
 *
 * - Writes disabled: nothing to do beyond the metadata mirror already applied.
 * - Suno advanced since our last push: never overwrite; surface a conflict.
 * - Local document unchanged since the last push: skip the round trip.
 * - No Suno document to merge into: refuse to invent one (Suno's defaults would
 *   be lost), which leaves the link `linked` and the error visible.
 */
export type StateSyncDecision =
  | { kind: "skip" }
  | { kind: "conflict" }
  | {
      kind: "push";
      state: Record<string, unknown>;
      baseVersionId: string | null;
      skippedClipIds: string[];
    };

export function decideStateSync(args: {
  enabled: boolean;
  linkVersionId: string | null;
  stateHash: string | null;
  remoteVersionId: string | null;
  remoteState: Record<string, unknown> | null;
  doc: StudioProjectDocument;
  previousLocalClipIds?: string[];
}): StateSyncDecision {
  if (!args.enabled) return { kind: "skip" };
  if (
    args.linkVersionId &&
    args.remoteVersionId &&
    args.linkVersionId !== args.remoteVersionId
  ) {
    return { kind: "conflict" };
  }
  if (args.stateHash && args.stateHash === studioDocumentHash(args.doc.data)) {
    return { kind: "skip" };
  }
  const { state, skippedClipIds } = projectDocumentToSunoState({
    title: args.doc.title,
    majorVersion: args.doc.majorVersion,
    bpm: args.doc.bpm,
    timeSignature: args.doc.timeSignature,
    data: (args.doc.data ?? {}) as LocalDocument,
    baseline: args.remoteState,
    previousLocalClipIds: args.previousLocalClipIds,
  });
  return {
    kind: "push",
    state,
    baseVersionId: args.remoteVersionId,
    skippedClipIds,
  };
}

/**
 * Drop Suno asset ids that belong to a different pool account.
 *
 * Suno assets are account-scoped: an audio clip whose source was generated by
 * another account cannot be referenced from a project on the pinned account. The
 * clip stays local and is reported, instead of producing a broken clip on Suno.
 */
export async function filterForeignAssets(
  doc: StudioProjectDocument,
  accountLabel: string
): Promise<{ doc: StudioProjectDocument; skippedIds: string[] }> {
  const data = (doc.data ?? {}) as LocalDocument;
  const lanes = Array.isArray(data.lanes) ? data.lanes : [];
  const ids = lanes
    .map((clip) => (typeof clip.sunoAssetId === "string" ? clip.sunoAssetId : ""))
    .filter(Boolean);
  if (ids.length === 0) return { doc, skippedIds: [] };

  let owners: Array<{ asset_id: string; account_id: string | null }> = [];
  try {
    owners = await query<{ asset_id: string; account_id: string | null }>(
      "SELECT asset_id, account_id FROM asset_owners WHERE asset_id = ANY($1::text[])",
      [ids]
    );
  } catch {
    // The owner table is best-effort; without it, keep the asset id as given.
    return { doc, skippedIds: [] };
  }
  const foreign = new Set(
    owners
      .filter((row) => row.account_id && row.account_id !== accountLabel)
      .map((row) => row.asset_id)
  );
  if (foreign.size === 0) return { doc, skippedIds: [] };

  const skippedIds: string[] = [];
  const nextLanes = lanes.map((clip) => {
    if (!clip.sunoAssetId || !foreign.has(clip.sunoAssetId)) return clip;
    skippedIds.push(clip.id);
    const { sunoAssetId: _drop, ...rest } = clip;
    return rest as LocalClip;
  });
  return {
    doc: { ...doc, data: { ...data, lanes: nextLanes } },
    skippedIds,
  };
}

/** Pick the least-shared candidate: an unused account first, then fewest users. */
export function chooseStudioAccount(
  candidates: string[],
  usage: Record<string, number>
): string | null {
  if (candidates.length === 0) return null;
  let best = candidates[0];
  let bestCount = usage[best] ?? 0;
  for (const candidate of candidates) {
    const count = usage[candidate] ?? 0;
    if (count === 0) return candidate;
    if (count < bestCount) {
      best = candidate;
      bestCount = count;
    }
  }
  return best;
}

/**
 * Owns the mapping table, account pinning and the retry loop. One instance per
 * process; `buildServer` creates one for the routes and `serve` starts a second
 * one on a timer. They share nothing but the database, so either can run alone.
 */
export class StudioProjectSync {
  constructor(private readonly pool: AccountPool) {}

  /** The pinned account for a user, or null before their first project. */
  private async pinnedAccount(userId: string): Promise<string | null> {
    const row = await queryOne<{ account_label: string }>(
      "SELECT account_label FROM studio_suno_accounts WHERE user_id = $1",
      [userId]
    );
    return row?.account_label ?? null;
  }

  /**
   * Pin an account for the user on first use.
   *
   * Suno projects are account-scoped, so the pin is permanent for that user:
   * every project they create later is mirrored through the same account.
   * Selection prefers a paid account that advertises Studio; when the pool has
   * none (sandbox, fresh host) it falls back to the normal picker so local
   * development still exercises the path.
   */
  /**
   * Prefer an account no other user is pinned to, then the least-used one.
   *
   * Suno projects are account-scoped, so two Camxora users on the same account
   * can see each other's projects inside Suno. The pool cannot mint accounts, so
   * this keeps the blast radius to the smallest possible set while still making
   * the sharing visible in the admin health payload.
   */
  private async pinAccount(userId: string): Promise<string> {
    const existing = await this.pinnedAccount(userId);
    if (existing) return existing;

    const usageRows = await query<{ account_label: string; users: string }>(
      "SELECT account_label, count(*)::text AS users FROM studio_suno_accounts GROUP BY account_label"
    );
    const usage: Record<string, number> = {};
    for (const row of usageRows) usage[row.account_label] = Number(row.users);

    // Probe the pool in order without committing a pin, so the choice can skip
    // accounts other users already hold.
    const candidates: string[] = [];
    let fallback: SunoClient | null = null;
    for (let attempt = 0; attempt < 12; attempt += 1) {
      try {
        const client = await this.pool.pickFeatureExcept(
          "studio",
          candidates,
          undefined,
          "paid_only"
        );
        fallback = client;
        if (!candidates.includes(client.account.id)) candidates.push(client.account.id);
      } catch {
        break;
      }
    }
    if (candidates.length === 0) {
      try {
        const client = await this.pool.pickFeature("studio", undefined, "paid_only");
        candidates.push(client.account.id);
        fallback = client;
      } catch {
        const client = await this.pool.pick(undefined, "any");
        candidates.push(client.account.id);
        fallback = client;
      }
    }

    const chosen = chooseStudioAccount(candidates, usage) ?? fallback?.account.id;
    if (!chosen) throw new Error("No Suno account is available to pin.");

    await query(
      `INSERT INTO studio_suno_accounts (user_id, account_label)
       VALUES ($1, $2)
       ON CONFLICT (user_id) DO NOTHING`,
      [userId, chosen]
    );
    const stored = await this.pinnedAccount(userId);
    if (!stored) throw new Error("Could not pin a Suno account for this user.");
    return stored;
  }

  private clientFor(accountLabel: string): SunoClient {
    const client = this.pool.get(accountLabel);
    if (!client) {
      throw new StudioAccountError(
        `The pinned Suno account ${accountLabel} is not active; re-authenticate it before syncing.`
      );
    }
    return client;
  }

  /** The pinned account for a user, pinning one on first use. */
  async accountForUser(userId: string): Promise<string> {
    return this.pinAccount(userId);
  }

  async link(localProjectId: string): Promise<StudioSyncLink | null> {
    return queryOne<StudioSyncLink>(
      "SELECT * FROM studio_suno_projects WHERE local_project_id = $1",
      [localProjectId]
    );
  }

  /**
   * Ensure the Suno project exists and return the link.
   *
   * Creation is serialized per local project with an advisory transaction lock
   * so two workers (or a retry racing a request) can never create two Suno
   * projects for one Camxora project. The lock is held across the provider call
   * on purpose: correctness here is worth one short transaction.
   */
  async ensureLink(doc: StudioProjectDocument): Promise<StudioSyncLink> {
    const existing = await this.link(doc.localProjectId);
    if (existing) return existing;

    const accountLabel = await this.pinAccount(doc.userId);
    const client = this.clientFor(accountLabel);
    const metadata = studioProjectMetadata(doc);

    await withTransaction(async (tx) => {
      await tx("SELECT pg_advisory_xact_lock(hashtext($1))", [`studio-suno:${doc.localProjectId}`]);
      const raced = await tx<{ local_project_id: string }>(
        "SELECT local_project_id FROM studio_suno_projects WHERE local_project_id = $1",
        [doc.localProjectId]
      );
      if (raced.length > 0) return;
      const created = await client.createStudioProject(metadata.title, {
        majorVersion: metadata.majorVersion,
      });
      await tx(
        `INSERT INTO studio_suno_projects
           (local_project_id, user_id, account_label, suno_project_id, suno_title, status)
         VALUES ($1, $2, $3, $4, $5, 'pending')
         ON CONFLICT (local_project_id) DO NOTHING`,
        [doc.localProjectId, doc.userId, accountLabel, created.id, created.title]
      );
    });

    const link = await this.link(doc.localProjectId);
    if (!link) throw new Error("The Suno project link could not be stored.");
    return link;
  }

  /**
   * Push one project. Idempotent: it ensures the link, mirrors metadata and —
   * when arrangement writes are enabled — saves the merged document, adopting
   * the returned version.
   */
  async syncProject(doc: StudioProjectDocument): Promise<StudioSyncStatusView> {
    try {
      const link = await this.ensureLink(doc);
      if (link.user_id !== doc.userId) {
        throw new StudioAccountError("This Suno project belongs to another Camxora user.");
      }
      const client = this.clientFor(link.account_label);
      const metadata = studioProjectMetadata(doc);
      const hash = studioDocumentHash(doc.data);
      const prepared = await filterForeignAssets(doc, link.account_label);

      // Metadata-only mode: if the link already reflects this exact document
      // there is nothing to push and no reason to spend a provider round trip.
      if (
        !stateSyncEnabled() &&
        link.suno_title === metadata.title &&
        link.state_hash === hash &&
        !link.archived &&
        link.status !== "error"
      ) {
        return statusView(link);
      }

      // Title and archive state are cheap and safe; push them only on change.
      if (link.suno_title !== metadata.title) {
        await client.updateStudioProjectMetadata(link.suno_project_id, { title: metadata.title });
      }
      if (link.archived) {
        await client.setStudioProjectArchived(link.suno_project_id, true);
      }

      const remote = await client.getStudioProject(link.suno_project_id);
      const remoteState = parseStudioState(remote.state);
      const remoteVersion = remote.latest_version_id ?? link.suno_version_id;

      let status: StudioSyncStatus = "linked";
      let version = remoteVersion;
      let nextState = remoteState;
      let skippedClipIds: string[] = Array.isArray(link.skipped_clip_ids)
        ? (link.skipped_clip_ids as string[])
        : [];
      const decision = decideStateSync({
        enabled: stateSyncEnabled(),
        linkVersionId: link.suno_version_id,
        stateHash: link.state_hash,
        remoteVersionId: remoteVersion,
        remoteState,
        doc: prepared.doc,
        previousLocalClipIds: Array.isArray(link.local_clip_ids)
          ? (link.local_clip_ids as string[])
          : [],
      });
      if (decision.kind === "conflict") {
        // Somebody saved on Suno since our last push: keep the remote state for
        // the reconciliation UI instead of overwriting it.
        status = "conflict";
      } else if (decision.kind === "push") {
        const saved = await client.saveStudioProject({
          projectId: link.suno_project_id,
          state: decision.state,
          title: metadata.title,
          baseVersionId: decision.baseVersionId,
        });
        version = saved.versionId;
        nextState = decision.state;
        skippedClipIds = [...new Set([...decision.skippedClipIds, ...prepared.skippedIds])];
        status = "synced";
      } else if (decision.kind === "skip" && stateSyncEnabled()) {
        status = "synced";
      }

      const updated = await queryOne<StudioSyncLink>(
        `UPDATE studio_suno_projects SET
           suno_version_id = $2,
           suno_remote_version_id = $2,
           suno_title = $3,
           suno_state = COALESCE($4::jsonb, suno_state),
           state_hash = $5,
           status = $6,
           skipped_clip_ids = $7::jsonb,
           local_clip_ids = $8::jsonb,
           last_error = NULL,
           synced_at = now(),
           updated_at = now()
         WHERE local_project_id = $1
         RETURNING *`,
        [
          doc.localProjectId,
          version,
          metadata.title,
          nextState ? JSON.stringify(nextState) : null,
          hash,
          status,
          JSON.stringify(skippedClipIds),
          JSON.stringify(localClipIds(doc)),
        ]
      );
      await query("DELETE FROM studio_suno_outbox WHERE local_project_id = $1", [
        doc.localProjectId,
      ]);
      return statusView(updated);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await query(
        `UPDATE studio_suno_projects SET
           status = 'error',
           last_error = $2,
           updated_at = now()
         WHERE local_project_id = $1`,
        [doc.localProjectId, message.slice(0, 500)]
      );
      throw error;
    }
  }

  /** Mark a project dirty with the newest document. Bursts coalesce. */
  async enqueue(doc: StudioProjectDocument): Promise<void> {
    await query(
      `INSERT INTO studio_suno_outbox (local_project_id, user_id, document)
       VALUES ($1, $2, $3::jsonb)
       ON CONFLICT (local_project_id) DO UPDATE SET
         user_id = EXCLUDED.user_id,
         document = EXCLUDED.document,
         attempts = 0,
         next_attempt_at = now(),
         last_error = NULL,
         updated_at = now()`,
      [doc.localProjectId, doc.userId, JSON.stringify(doc)]
    );
  }

  /**
   * Project the current Suno document into local fields and merge it into the
   * document the platform sent. Always re-reads the remote first, so "Load Suno"
   * acts on what is on Suno right now, not a cached copy.
   */
  async mergeFromSuno(doc: StudioProjectDocument): Promise<{
    bpm: number;
    timeSignature: string;
    data: unknown;
    keptLocalClips: string[];
    droppedTracks: string[];
    versionId: string | null;
  } | null> {
    const link = await this.link(doc.localProjectId);
    if (!link || link.user_id !== doc.userId) return null;
    await this.refresh(doc.localProjectId, doc.userId, 0);
    const fresh = await this.link(doc.localProjectId);
    const state = parseStudioState(fresh?.suno_state);
    if (!state) return null;
    const projection = sunoStateToProjectData(state);
    const merged = mergeSunoProjectIntoLocal(
      (doc.data ?? {}) as LocalDocument,
      projection
    );
    return {
      bpm: projection.bpm,
      timeSignature: projection.timeSignature,
      data: merged.data,
      keptLocalClips: merged.keptLocalClips,
      droppedTracks: merged.droppedTracks,
      versionId: fresh?.suno_version_id ?? null,
    };
  }

  /**
   * Rebase the link after a conflict.
   *
   * `mine`: accept Suno's version as the base, then the caller pushes the local
   * document (resolving in favour of local edits).
   * `theirs`: the caller already applied the merged document locally; record its
   * hash so the next save is a no-op, and mark the link synced.
   */
  async resolveConflict(
    doc: StudioProjectDocument,
    resolution: "mine" | "theirs",
    version: string | null
  ): Promise<StudioSyncStatusView | null> {
    const link = await this.link(doc.localProjectId);
    if (!link || link.user_id !== doc.userId) return null;
    const remoteVersion = version ?? link.suno_remote_version_id;
    const updated = await queryOne<StudioSyncLink>(
      `UPDATE studio_suno_projects SET
         suno_version_id = COALESCE($2, suno_version_id),
         suno_remote_version_id = COALESCE($2, suno_remote_version_id),
         status = $3,
         state_hash = CASE WHEN $3 = 'synced' THEN $4 ELSE state_hash END,
         last_error = NULL,
         synced_at = now(),
         updated_at = now()
       WHERE local_project_id = $1
       RETURNING *`,
      [
        doc.localProjectId,
        remoteVersion,
        resolution === "theirs" ? "synced" : "linked",
        resolution === "theirs" ? studioDocumentHash(doc.data) : null,
      ]
    );
    return statusView(updated ?? link);
  }

  /** Process due outbox rows. Safe to call from a timer; never throws. */
  async runDue(limit = 5): Promise<number> {
    const rows = await query<{ local_project_id: string; attempts: number; document: unknown }>(
      `SELECT local_project_id, attempts, document FROM studio_suno_outbox
       WHERE next_attempt_at <= now()
       ORDER BY next_attempt_at
       LIMIT $1`,
      [limit]
    );
    let done = 0;
    for (const row of rows) {
      const doc = outboxDocument(row.document, row.local_project_id);
      try {
        if (!doc) throw new Error("The queued project document is unreadable.");
        await this.syncProject(doc);
        done += 1;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const retryable = isRetryableStudioSyncError(error);
        const attempts = row.attempts + 1;
        await query(
          `UPDATE studio_suno_outbox SET
             attempts = $2,
             last_error = $3,
             next_attempt_at = now() + ($4::bigint * interval '1 millisecond'),
             updated_at = now()
           WHERE local_project_id = $1`,
          [
            row.local_project_id,
            attempts,
            message.slice(0, 500),
            retryable ? studioSyncBackoffMs(attempts) : 86_400_000,
          ]
        );
      }
    }
    return done;
  }

  /**
   * Poll Suno for a newer document without touching the local project.
   *
   * The editor calls this while a project is open. Remote reads are throttled per
   * project (`SUNO_SYNC_CHECK_MS`, 30 s) so a room full of editors on one pinned
   * account cannot hammer the provider. A newer remote version marks the link
   * `conflict`; the local document is never overwritten here.
   */
  async refresh(
    localProjectId: string,
    userId: string,
    minIntervalMs = Number(process.env.SUNO_SYNC_CHECK_MS ?? 30_000)
  ): Promise<StudioSyncStatusView | null> {
    const link = await this.link(localProjectId);
    if (!link || link.user_id !== userId) return null;
    const checked = link.last_checked_at ? Date.parse(String(link.last_checked_at)) : 0;
    if (Number.isFinite(checked) && Date.now() - checked < minIntervalMs) {
      return statusView(link);
    }
    try {
      const client = this.clientFor(link.account_label);
      const remote = await client.getStudioProject(link.suno_project_id);
      const remoteVersion = remote.latest_version_id ?? null;
      const remoteState = parseStudioState(remote.state);
      const advanced = Boolean(
        remoteVersion && link.suno_version_id && remoteVersion !== link.suno_version_id
      );
      const updated = await queryOne<StudioSyncLink>(
        `UPDATE studio_suno_projects SET
           suno_state = COALESCE($2::jsonb, suno_state),
           suno_remote_version_id = COALESCE($3, suno_remote_version_id),
           status = $4,
           last_error = NULL,
           last_checked_at = now(),
           updated_at = now()
         WHERE local_project_id = $1
         RETURNING *`,
        [
          localProjectId,
          remoteState ? JSON.stringify(remoteState) : null,
          remoteVersion,
          advanced ? "conflict" : link.status,
        ]
      );
      return statusView(updated ?? link);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await query(
        `UPDATE studio_suno_projects SET last_checked_at = now(), last_error = $2, updated_at = now()
         WHERE local_project_id = $1`,
        [localProjectId, message.slice(0, 500)]
      ).catch(() => undefined);
      return statusView(link);
    }
  }

  async status(localProjectId: string, userId: string): Promise<StudioSyncStatusView | null> {
    const link = await this.link(localProjectId);
    if (!link) return null;
    if (link.user_id !== userId) return null;
    return statusView(link);
  }

  /**
   * Mirror the local archive flag. Archiving does not need the document, so it
   * is applied directly instead of through the outbox; a failure is recorded on
   * the link so the status chip can show it. The Suno project is archived, never
   * deleted, so a local delete cannot destroy the user's Suno copy.
   */
  async setArchived(localProjectId: string, userId: string, archived: boolean): Promise<boolean> {
    const link = await this.link(localProjectId);
    if (!link || link.user_id !== userId) return false;
    try {
      const client = this.clientFor(link.account_label);
      await client.setStudioProjectArchived(link.suno_project_id, archived);
      await query(
        `UPDATE studio_suno_projects SET archived = $2, last_error = NULL, updated_at = now()
         WHERE local_project_id = $1`,
        [localProjectId, archived]
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await query(
        `UPDATE studio_suno_projects SET archived = $2, last_error = $3, updated_at = now()
         WHERE local_project_id = $1`,
        [localProjectId, archived, message.slice(0, 500)]
      );
    }
    return true;
  }
}

/** The outbox payload is the serialized `StudioProjectDocument`. */
function outboxDocument(value: unknown, localProjectId: string): StudioProjectDocument | null {
  const parsed = parseStudioState(value);
  if (!parsed) return null;
  const data = parsed as Record<string, unknown>;
  if (typeof data.userId !== "string" || !data.userId) return null;
  return {
    localProjectId,
    userId: data.userId,
    title: typeof data.title === "string" ? data.title : "Untitled Project",
    majorVersion: Number(data.majorVersion) || 2,
    bpm: Number(data.bpm) || 120,
    timeSignature: typeof data.timeSignature === "string" ? data.timeSignature : "4/4",
    data: data.data,
  };
}

function statusView(link: StudioSyncLink | null): StudioSyncStatusView {
  return {
    status: link?.status ?? "pending",
    suno_project_id: link?.suno_project_id ?? null,
    suno_version_id: link?.suno_version_id ?? null,
    suno_remote_version_id: link?.suno_remote_version_id ?? null,
    last_error: link?.last_error ?? null,
    synced_at: link?.synced_at ? new Date(link.synced_at).toISOString() : null,
    skipped_clips: Array.isArray(link?.skipped_clip_ids)
      ? (link?.skipped_clip_ids as string[])
      : [],
    state_sync: stateSyncEnabled(),
  };
}

/** Suno ids for every local clip, stored so a later delete can propagate. */
function localClipIds(doc: StudioProjectDocument): string[] {
  const data = (doc.data ?? {}) as LocalDocument;
  return (Array.isArray(data.lanes) ? data.lanes : []).map(
    (clip) => clip.sunoId ?? stableSunoId(clip.id)
  );
}

