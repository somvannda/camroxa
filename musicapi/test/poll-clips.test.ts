import { test } from "node:test";
import assert from "node:assert/strict";
import { SunoClient, type Clip } from "../src/client.js";

/**
 * Drive `SunoClient.pollClips` with a stubbed `getClips` so we can assert it
 * waits for *every* requested clip id before returning. `pollClips` only calls
 * `this.getClips`, so a minimal stand-in is enough.
 */
function pollWith(
  ids: string[],
  responses: Clip[][],
  opts: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<Clip[]> {
  let i = 0;
  const fake = {
    getClips: async (): Promise<Clip[]> => responses[Math.min(i++, responses.length - 1)],
  };
  return SunoClient.prototype.pollClips.call(
    fake as unknown as SunoClient,
    ids,
    opts.timeoutMs ?? 1_000,
    opts.intervalMs ?? 1,
  );
}

test("pollClips waits for every requested clip, not just the first terminal subset", async () => {
  // Regression: the feed transiently returns only one of a generation's two
  // clips. Returning on that first all-terminal subset dropped the second
  // version, so only one of the two generated songs was ever stored.
  const first: Clip[] = [{ id: "a", status: "complete" }];
  const second: Clip[] = [
    { id: "a", status: "complete" },
    { id: "b", status: "complete" },
  ];
  const clips = await pollWith(["a", "b"], [first, second]);
  assert.deepEqual(clips.map((c) => c.id).sort(), ["a", "b"]);
});

test("pollClips keeps polling while the second clip is still generating", async () => {
  const clips = await pollWith(["a", "b"], [
    [
      { id: "a", status: "complete" },
      { id: "b", status: "streaming" },
    ],
    [
      { id: "a", status: "complete" },
      { id: "b", status: "complete" },
    ],
  ]);
  assert.deepEqual(clips.map((c) => c.id).sort(), ["a", "b"]);
});

test("pollClips times out when a requested id never reports back", async () => {
  await assert.rejects(
    () => pollWith(["a", "b"], [[{ id: "a", status: "complete" }]], { intervalMs: 1, timeoutMs: 20 }),
    /Timed out waiting for clip completion/,
  );
});

test("pollClips returns immediately when a single clip is terminal", async () => {
  const clips = await pollWith(["only"], [[{ id: "only", status: "complete" }]]);
  assert.deepEqual(clips.map((c) => c.id), ["only"]);
});
