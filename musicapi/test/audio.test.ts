import { test } from "node:test";
import assert from "node:assert/strict";

import { pickPublicAudioUrl } from "../src/audio.js";

test("pickPublicAudioUrl prefers a usable media_urls entry", () => {
  const clip = {
    media_urls: [
      { url: "https://api.suno.com/api/forbidden" },
      { url: "https://cdn.example.com/a.m4a" },
    ],
    audio_url: "https://cdn.example.com/b.mp3",
  };
  assert.equal(pickPublicAudioUrl(clip), "https://cdn.example.com/a.m4a");
});

test("pickPublicAudioUrl falls back past the forbidden placeholder", () => {
  const clip = {
    media_urls: [{ url: "https://api.suno.com/api/forbidden" }],
    stream_audio_url: "https://cdn.example.com/stream.mp3",
  };
  assert.equal(pickPublicAudioUrl(clip), "https://cdn.example.com/stream.mp3");
});

test("pickPublicAudioUrl returns null when nothing playable exists", () => {
  assert.equal(pickPublicAudioUrl({}), null);
  assert.equal(pickPublicAudioUrl({ audio_url: "https://api.suno.com/api/forbidden" }), null);
  assert.equal(pickPublicAudioUrl({ audio_url: "not-a-url" }), null);
});
