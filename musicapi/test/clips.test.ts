import { test } from "node:test";
import assert from "node:assert/strict";
import { collectClipObjects, extractClipIds } from "../src/clips.js";

test("extractClipIds flattens nested clips and dedups", () => {
  const result = [
    {
      clips: [
        { id: "a", audio_url: "u" },
        { id: "b", audio_url: "u" },
      ],
    },
    { id: "a", audio_url: "u" }, // duplicate id
  ];
  assert.deepEqual(extractClipIds(result).sort(), ["a", "b"]);
});

test("extractClipIds ignores objects without a media url", () => {
  assert.deepEqual(extractClipIds([{ id: "x" }, { id: "y", image_url: "i" }]), ["y"]);
});

test("collectClipObjects descends into data and sunoData", () => {
  const out: Array<Record<string, unknown>> = [];
  collectClipObjects(
    { data: [{ id: "d", audioUrl: "u" }], sunoData: [{ id: "s", video_url: "v" }] },
    out,
  );
  assert.deepEqual(out.map((c) => c.id).sort(), ["d", "s"]);
});

test("extractClipIds returns [] for non-clip payloads", () => {
  assert.deepEqual(extractClipIds(null), []);
  assert.deepEqual(extractClipIds({ status: "ok" }), []);
  assert.deepEqual(extractClipIds("nope"), []);
});
