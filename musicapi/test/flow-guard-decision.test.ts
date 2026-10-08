import { test } from "node:test";
import assert from "node:assert/strict";
import { flowVerdict, type AssetOwner } from "../src/flowGuard.js";

// Pure decision-table coverage for the generation-flow guard. The DB-backed
// wiring is covered by flow-guard.test.ts (static) and the route coverage test.

const OWNERS: AssetOwner[] = ["caller", "other", "none"];

test("a disabled guard always returns ok (inert rollout)", () => {
  for (const owner of OWNERS) {
    assert.equal(flowVerdict({ enforced: false, owner }), "ok");
    assert.equal(
      flowVerdict({ enforced: false, owner, producedByCompletedJob: false }),
      "ok",
    );
  }
});

test("another user's asset is always foreign", () => {
  assert.equal(flowVerdict({ enforced: true, owner: "other" }), "foreign");
  assert.equal(
    flowVerdict({ enforced: true, owner: "other", producedByCompletedJob: true }),
    "foreign",
  );
});

test("an asset owned by nobody is unowned (never generated)", () => {
  assert.equal(flowVerdict({ enforced: true, owner: "none" }), "unowned");
  assert.equal(
    flowVerdict({ enforced: true, owner: "none", producedByCompletedJob: true }),
    "unowned",
  );
});

test("the caller's asset requires a completed producer", () => {
  // Completion unknown (legacy/unmapped) is grandfathered.
  assert.equal(flowVerdict({ enforced: true, owner: "caller" }), "ok");
  assert.equal(
    flowVerdict({ enforced: true, owner: "caller", producedByCompletedJob: true }),
    "ok",
  );
  assert.equal(
    flowVerdict({ enforced: true, owner: "caller", producedByCompletedJob: false }),
    "incomplete",
  );
});

test("mustBeComplete=false skips the completion check", () => {
  assert.equal(
    flowVerdict({
      enforced: true,
      owner: "caller",
      mustBeComplete: false,
      producedByCompletedJob: false,
    }),
    "ok",
  );
});
