import { test } from "node:test";
import assert from "node:assert/strict";

import {
  beatsFromSeconds,
  bpmFromState,
  emptySunoState,
  noteId,
  projectDocumentToSunoState,
  secondsFromBeats,
  stableSunoId,
  sunoStateToProjectData,
  timeSignatureFromState,
  timeSignatureParts,
  type LocalDocument,
} from "../src/studioStateCodec.js";

function localDocument(): LocalDocument {
  return {
    masterVolume: 100,
    loopStart: 0,
    loopEnd: 8,
    tracks: [
      {
        id: "track-1",
        name: "Keys",
        color: "#111111",
        volume: 80,
        pan: -50,
        muted: false,
        solo: true,
        hidden: false,
        index: 0,
        clipIds: ["clip-1"],
      },
      {
        id: "track-2",
        name: "Audio",
        color: "#222222",
        volume: 100,
        pan: 0,
        index: 1,
        clipIds: ["clip-audio", "clip-song"],
      },
    ],
    lanes: [
      {
        id: "clip-1",
        title: "Chords",
        start: 2,
        duration: 4,
        midi: {
          notes: [{ id: "n1", pitch: 60, start: 0.5, length: 1, velocity: 90 }],
        },
      },
      { id: "clip-audio", title: "Local upload", start: 0, duration: 4, audioUrl: "/x.wav" },
      {
        id: "clip-song",
        title: "Song",
        start: 8,
        duration: 4,
        songId: "9f8e7d6c-5b4a-4392-8170-6f5e4d3c2b1a",
      },
    ],
  };
}

function build(baseline: Record<string, unknown> | null = null) {
  return projectDocumentToSunoState({
    title: "My Song",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data: localDocument(),
    baseline,
  });
}

test("tempo and meter convert to Suno's beats-per-second fields", () => {
  const { state } = build();
  assert.deepEqual(state.timing, { type: "manual", bps: 2, bpsAutomation: [], lockBPS: false });
  assert.deepEqual(state.timeSignatureChanges, [
    { startBeats: 0, subdivisionsPerBar: 4, beatsPerSubdivision: 1 },
  ]);
  assert.equal(state.title, "My Song");
  assert.equal(state.majorVersion, 2);
  assert.deepEqual(timeSignatureParts("6/8"), { subdivisionsPerBar: 6, beatsPerSubdivision: 0.5 });
  assert.equal(timeSignatureFromState([{ subdivisionsPerBar: 3, beatsPerSubdivision: 1 }]), "3/4");
  assert.equal(bpmFromState({ bps: 2 }), 120);
});

test("mixer values map onto amplitude, balance, mute, solo and type", () => {
  const { state } = build();
  const tracks = state.tracks as Array<Record<string, unknown>>;
  assert.equal(tracks.length, 2);
  assert.equal(tracks[0].name, "Keys");
  assert.equal(tracks[0].type, "midi");
  assert.equal(tracks[0].amplitude, 0.8);
  assert.equal(tracks[0].balance, -0.5);
  assert.equal(tracks[0].solo, true);
  assert.equal(tracks[1].type, "audio");
});

test("clips convert seconds to beats and MIDI notes get numeric ids", () => {
  const { state } = build();
  const tracks = state.tracks as Array<Record<string, unknown>>;
  const midiClip = (tracks[0].clips as Array<Record<string, unknown>>)[0];
  assert.equal(midiClip.startBeats, 4);
  assert.equal(midiClip.endBeats, 12);
  assert.equal(midiClip.type, "midi");
  const midi = midiClip.midi as { notes: Array<Record<string, unknown>> };
  assert.equal(midi.notes.length, 1);
  assert.equal(midi.notes[0].startBeats, 1);
  assert.equal(midi.notes[0].durationBeats, 2);
  assert.equal(midi.notes[0].pitch, 60);
  assert.equal(typeof midi.notes[0].id, "number");
  assert.ok((midi.notes[0].id as number) > 0);
});

test("an audio clip without a Suno asset is skipped and reported", () => {
  const { state, skippedClipIds } = build();
  const tracks = state.tracks as Array<Record<string, unknown>>;
  const audioClips = tracks[1].clips as Array<Record<string, unknown>>;
  assert.deepEqual(skippedClipIds, ["clip-audio"]);
  assert.equal(audioClips.length, 1);
  assert.deepEqual(audioClips[0].asset, {
    id: "9f8e7d6c-5b4a-4392-8170-6f5e4d3c2b1a",
    type: "song",
  });
});

test("unknown Suno keys survive a rebuild", () => {
  const { state } = build({
    markersRegistry: { warp_a: { "0": 0 } },
    libraryPanelState: { searchOpen: false },
    layout: { midiAutomationLaneHeight: 40 },
  });
  assert.deepEqual(state.markersRegistry, { warp_a: { "0": 0 } });
  assert.deepEqual(state.libraryPanelState, { searchOpen: false });
  assert.deepEqual(state.layout, { midiAutomationLaneHeight: 40 });
});

test("an empty local document never wipes the Suno-only tracks", () => {
  const baseline = {
    tracks: [{ id: "suno-track", name: "From Suno", type: "audio", clips: [] }],
  };
  const { state } = projectDocumentToSunoState({
    title: "Legacy",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data: {},
    baseline,
  });
  assert.deepEqual(state.tracks, baseline.tracks);
});

test("the reverse projection reads bpm, meter, tracks and notes back", () => {
  const { state } = build();
  const project = sunoStateToProjectData(state);
  assert.equal(project.bpm, 120);
  assert.equal(project.timeSignature, "4/4");
  assert.equal(project.tracks.length, 2);
  assert.equal(project.tracks[0].volume, 80);
  assert.equal(project.tracks[0].pan, -50);
  assert.equal(project.lanes.length, 2); // one local upload was skipped
  const chords = project.lanes.find((clip) => clip.title === "Chords");
  assert.ok(chords?.midi?.notes?.length === 1);
  assert.equal(chords?.midi?.notes?.[0].start, 0.5);
  assert.equal(chords?.midi?.notes?.[0].length, 1);
});

test("ids are stable per local id and valid UUIDs", () => {
  const a = stableSunoId("clip-1");
  assert.equal(a, stableSunoId("clip-1"));
  assert.notEqual(a, stableSunoId("clip-2"));
  assert.match(a, /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-a[0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.equal(noteId("n1", 0), noteId("n1", 99));
  assert.equal(beatsFromSeconds(1.5, 2), 3);
  assert.equal(secondsFromBeats(3, 2), 1.5);
});

test("a fresh Suno project has the fields the client validates", () => {
  const state = emptySunoState("Untitled Project");
  assert.ok(state.timing);
  assert.ok(Array.isArray(state.tracks));
  assert.equal(state.majorVersion, 2);
});
