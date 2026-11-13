import { test } from "node:test";
import assert from "node:assert/strict";

import {
  isRetryableStudioSyncError,
  mergeLocalDocumentIntoSunoState,
  parseStudioState,
  stateSyncEnabled,
  studioDocumentHash,
  studioProjectMetadata,
  studioSyncBackoffMs,
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

test("state sync stays off until the document schema is verified", () => {
  assert.equal(stateSyncEnabled({} as NodeJS.ProcessEnv), false);
  assert.equal(stateSyncEnabled({ STUDIO_SUNO_STATE_SYNC: "1" } as NodeJS.ProcessEnv), true);
});

test("studioProjectMetadata trims the title and falls back when blank", () => {
  assert.deepEqual(studioProjectMetadata(doc()), { title: "My Song", majorVersion: 2 });
  assert.deepEqual(studioProjectMetadata(doc({ title: "   " })), {
    title: "Untitled Project",
    majorVersion: 2,
  });
});

test("merge keeps Suno keys we do not model and writes only verified fields", () => {
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
  // Unknown and unmodelled keys survive verbatim.
  assert.deepEqual(merged.tracks, baseline.tracks);
  assert.deepEqual(merged.somethingNew, baseline.somethingNew);
  assert.deepEqual((merged.timing as { bpsAutomation: unknown[] }).bpsAutomation, []);
  // The baseline itself is never mutated, so a failed save cannot corrupt it.
  assert.equal(baseline.title, "Old");
  assert.equal((baseline.timing as { bps: number }).bps, 1);
});

test("merge refuses to invent a document when Suno gave us no baseline", () => {
  assert.equal(mergeLocalDocumentIntoSunoState(null, doc()), null);
});

test("merge leaves a non-object timing value alone", () => {
  const merged = mergeLocalDocumentIntoSunoState({ timing: "manual" }, doc());
  assert.ok(merged);
  assert.equal(merged.timing, "manual");
});
