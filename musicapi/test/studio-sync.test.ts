import { test } from "node:test";
import assert from "node:assert/strict";

import {
  chooseStudioAccount,
  coverageSummary,
  decideStateSync,
  isRetryableStudioSyncError,
  mergeLocalDocumentIntoSunoState,
  parseStudioState,
  stateSyncEnabled,
  studioDocumentHash,
  studioProjectMetadata,
  studioSyncBackoffMs,
  STUDIO_STATE_COVERAGE,
  type StudioProjectDocument,
} from "../src/sunoStudio.js";
import { StudioAccountError, StudioProjectConflictError } from "../src/client.js";

function doc(overrides: Partial<StudioProjectDocument> = {}): StudioProjectDocument {
  return {
    localProjectId: "11111111-1111-4111-8111-111111111111",
    userId: "22222222-2222-4222-8222-222222222222",
    title: "  My Song  ",
    majorVersion: 2,
    bpm: 128,
    timeSignature: "4/4",
    data: { tracks: [], lanes: [] },
    ...overrides,
  };
}

test("parseStudioState accepts an object or a JSON string and rejects junk", () => {
  assert.deepEqual(parseStudioState({ a: 1 }), { a: 1 });
  assert.deepEqual(parseStudioState('{"a":1}'), { a: 1 });
  assert.equal(parseStudioState(""), null);
  assert.equal(parseStudioState("not json"), null);
  assert.equal(parseStudioState("[1,2]"), null);
  assert.equal(parseStudioState(null), null);
});

test("studioDocumentHash ignores key order but changes with content", () => {
  assert.equal(
    studioDocumentHash({ tracks: [], bpm: 120 }),
    studioDocumentHash({ bpm: 120, tracks: [] })
  );
  assert.notEqual(
    studioDocumentHash({ tracks: [] }),
    studioDocumentHash({ tracks: [{ id: "t1" }] })
  );
});

test("studioSyncBackoffMs climbs then stays at the hourly ceiling", () => {
  assert.deepEqual(
    [1, 2, 3, 4, 5, 6, 20].map(studioSyncBackoffMs),
    [2_000, 8_000, 30_000, 120_000, 600_000, 3_600_000, 3_600_000]
  );
});

test("a dead session or a stale version is not retried; provider blips are", () => {
  assert.equal(isRetryableStudioSyncError(new StudioAccountError("expired")), false);
  assert.equal(isRetryableStudioSyncError(new StudioProjectConflictError("v2")), false);
  assert.equal(isRetryableStudioSyncError(new Error("fetch failed")), true);
  assert.equal(isRetryableStudioSyncError(new Error("Suno 429 too many requests")), true);
});

test("state sync is on by default and can be killed with an env flag", () => {
  assert.equal(stateSyncEnabled({} as NodeJS.ProcessEnv), true);
  assert.equal(stateSyncEnabled({ STUDIO_SUNO_STATE_SYNC: "0" } as NodeJS.ProcessEnv), false);
  assert.equal(stateSyncEnabled({ STUDIO_SUNO_STATE_SYNC: "1" } as NodeJS.ProcessEnv), true);
});

test("studioProjectMetadata trims the title and falls back when blank", () => {
  assert.deepEqual(studioProjectMetadata(doc()), { title: "My Song", majorVersion: 2 });
  assert.deepEqual(studioProjectMetadata(doc({ title: "   " })), {
    title: "Untitled Project",
    majorVersion: 2,
  });
});

test("merge writes the verified fields and keeps the rest of the baseline", () => {
  const baseline = {
    title: "Old",
    majorVersion: 2,
    timing: { bps: 1, bpsAutomation: [] },
    tracks: { t1: { name: "Keep me" } },
    somethingNew: { nested: true },
  };
  const merged = mergeLocalDocumentIntoSunoState(baseline, doc({ bpm: 120 }));
  assert.ok(merged);
  assert.equal(merged.title, "My Song");
  assert.equal(merged.majorVersion, 2);
  assert.equal((merged.timing as { bps: number }).bps, 2);
  // Keys the codec does not model survive verbatim.
  assert.deepEqual(merged.somethingNew, baseline.somethingNew);
  // The arrangement is regenerated from the local document, not copied.
  assert.ok(Array.isArray(merged.tracks));
  // The baseline itself is never mutated, so a failed save cannot corrupt it.
  assert.equal(baseline.title, "Old");
  assert.equal(baseline.timing.bps, 1);
});

test("merge builds a complete document even without a baseline", () => {
  const merged = mergeLocalDocumentIntoSunoState(null, doc());
  assert.equal(merged.title, "My Song");
  assert.deepEqual(merged.timing, {
    type: "manual",
    bps: 2.133333,
    bpsAutomation: [],
    lockBPS: false,
  });
  assert.ok(Array.isArray(merged.tracks));
  assert.ok(merged.selection);
});

test("a non-object timing in the baseline is replaced by a structured block", () => {
  const merged = mergeLocalDocumentIntoSunoState({ timing: "manual" }, doc({ bpm: 120 }));
  assert.ok(merged);
  assert.deepEqual(merged.timing, {
    type: "manual",
    bps: 2,
    bpsAutomation: [],
    lockBPS: false,
  });
});

test("state sync is skipped while arrangement writes are disabled", () => {
  const decision = decideStateSync({
    enabled: false,
    linkVersionId: "v1",
    stateHash: null,
    remoteVersionId: "v2",
    remoteState: { timing: { bps: 2 } },
    doc: doc(),
  });
  assert.deepEqual(decision, { kind: "skip" });
});

test("a remote version ahead of the last push is a conflict, never an overwrite", () => {
  const decision = decideStateSync({
    enabled: true,
    linkVersionId: "v1",
    stateHash: null,
    remoteVersionId: "v2",
    remoteState: { timing: { bps: 2 } },
    doc: doc(),
  });
  assert.deepEqual(decision, { kind: "conflict" });
});

test("an unchanged document skips the round trip", () => {
  const current = doc({ data: { tracks: [], lanes: [] } });
  const decision = decideStateSync({
    enabled: true,
    linkVersionId: "v1",
    stateHash: studioDocumentHash(current.data),
    remoteVersionId: "v1",
    remoteState: { timing: { bps: 2 } },
    doc: current,
  });
  assert.deepEqual(decision, { kind: "skip" });
});

test("a document that changed is merged into the remote baseline and pushed", () => {
  const current = doc({ bpm: 90, data: { tracks: [{ id: "t1" }] } });
  const decision = decideStateSync({
    enabled: true,
    linkVersionId: "v1",
    stateHash: null,
    remoteVersionId: "v1",
    remoteState: { timing: { bps: 2, bpsAutomation: [] }, unknownKey: 1 },
    doc: current,
  });
  assert.equal(decision.kind, "push");
  if (decision.kind !== "push") return;
  assert.equal(decision.baseVersionId, "v1");
  assert.equal((decision.state.timing as { bps: number }).bps, 1.5);
  assert.equal(decision.state.unknownKey, 1);
});

test("the first push after a create uses the remote version as its base", () => {
  const decision = decideStateSync({
    enabled: true,
    linkVersionId: null,
    stateHash: null,
    remoteVersionId: "v7",
    remoteState: { timing: { bps: 2 } },
    doc: doc(),
  });
  assert.equal(decision.kind, "push");
  if (decision.kind !== "push") return;
  assert.equal(decision.baseVersionId, "v7");
});

test("no remote baseline still pushes a fresh project document", () => {
  const decision = decideStateSync({
    enabled: true,
    linkVersionId: null,
    stateHash: "stale",
    remoteVersionId: null,
    remoteState: null,
    doc: doc(),
  });
  assert.equal(decision.kind, "push");
  if (decision.kind !== "push") return;
  assert.equal(decision.baseVersionId, null);
  assert.ok(Array.isArray(decision.state.tracks));
  assert.deepEqual(decision.skippedClipIds, []);
});

test("account pinning prefers an unused account, then the least shared", () => {
  assert.equal(chooseStudioAccount([], {}), null);
  assert.equal(
    chooseStudioAccount(["acct-a", "acct-b"], { "acct-a": 2 }),
    "acct-b"
  );
  assert.equal(
    chooseStudioAccount(["acct-a", "acct-b"], { "acct-a": 3, "acct-b": 1 }),
    "acct-b"
  );
  assert.equal(
    chooseStudioAccount(["acct-a", "acct-b"], { "acct-a": 1, "acct-b": 1 }),
    "acct-a"
  );
});

test("the coverage registry counts every field and names the pending ones", () => {
  const summary = coverageSummary();
  assert.equal(summary.mapped + summary.pending + summary.remove, STUDIO_STATE_COVERAGE.length);
  assert.ok(summary.mapped >= 25);
  // The four parity items closed in this pass are mapped.
  for (const key of [
    "local uploads",
    "lanes[].takes",
    "chains (all built-ins)",
    "masterChain (limiter/eq/compressor)",
    "lanes[].instrument",
    "lanes[].midi.bend",
    "lanes[].midi.mod",
  ]) {
    assert.ok(!summary.pending_keys.includes(key), `${key} should be mapped`);
  }
  // A removed feature must never quietly return as a "pending" mapping.
  const removed = STUDIO_STATE_COVERAGE.filter((entry) => entry.status === "remove");
  assert.deepEqual(removed.map((entry) => entry.key).sort(), ["groups", "wavetableId"]);
  // Designed plugins are authored by Suno's agent, so their chain entries mirror
  // through catalogPluginId + pluginVersionId (no local-only exception).
  assert.ok(!summary.pending_keys.includes("designed plugins (Suno agent)"));
});
