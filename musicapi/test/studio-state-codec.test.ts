import { test } from "node:test";
import assert from "node:assert/strict";

import {
  beatsFromSeconds,
  bpmFromState,
  emptySunoState,
  mergeSunoProjectIntoLocal,
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
        offset: 1,
        fadeIn: 0.5,
        sunoAssetId: "9f8e7d6c-5b4a-4392-8170-6f5e4d3c2b1a",
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
    type: "clip",
  });
  assert.equal(audioClips[0].clipId, "9f8e7d6c-5b4a-4392-8170-6f5e4d3c2b1a");
  assert.equal(audioClips[0].startBeats, 16);
  assert.equal(audioClips[0].readStartBeats, 2);
  assert.equal(audioClips[0].fadeInBeats, 1);
  assert.deepEqual(audioClips[0].loop, { enabled: false, startBeats: 2, endBeats: 24 });
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

test("section markers become Suno sections with beat ranges", () => {
  const data = localDocument();
  data.markers = [
    { id: "m2", time: 16, label: "Chorus", color: "#00ff00" },
    { id: "m1", time: 4, label: "Intro" },
  ];
  const { state } = projectDocumentToSunoState({
    title: "Marked",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline: null,
  });
  const sections = state.sections as Record<string, Record<string, unknown>>;
  assert.deepEqual(Object.keys(sections).sort(), ["m1", "m2"]);
  assert.deepEqual(sections.m1, {
    id: "m1",
    name: "Intro",
    startBeats: 8,
    endBeats: 32,
    color: "#7c5cff",
  });
  // The last section closes at the next marker; a marker past the content end
  // still gets a positive range.
  assert.equal(sections.m2.startBeats, 32);
  assert.equal(sections.m2.endBeats, 33);

  const projected = sunoStateToProjectData(state);
  assert.deepEqual(
    projected.markers.map((marker) => [marker.id, marker.time, marker.label]),
    [
      ["m1", 4, "Intro"],
      ["m2", 16, "Chorus"],
    ]
  );
});

test("loading a Suno document replaces the local markers with Suno's sections", () => {
  const local: LocalDocument = {
    tracks: [],
    lanes: [],
    markers: [{ id: "old", time: 1, label: "Old" }],
  };
  const merged = mergeSunoProjectIntoLocal(local, {
    bpm: 120,
    timeSignature: "4/4",
    tracks: [],
    lanes: [],
    markers: [{ id: "new", time: 8, label: "New" }],
  });
  assert.deepEqual(merged.data.markers, [{ id: "new", time: 8, label: "New" }]);
});

test("a fresh Suno project has the fields the client validates", () => {
  const state = emptySunoState("Untitled Project");
  assert.ok(state.timing);
  assert.ok(Array.isArray(state.tracks));
  assert.equal(state.majorVersion, 2);
});

test("loading a Suno document updates matched tracks and clips", () => {
  const local: LocalDocument = {
    tracks: [
      {
        id: "track-1",
        name: "Old name",
        volume: 10,
        pan: 0,
        index: 0,
        clipIds: ["clip-1"],
      },
    ],
    lanes: [{ id: "clip-1", sunoId: "suno-clip", title: "Old", start: 0, duration: 1 }],
  };
  const merged = mergeSunoProjectIntoLocal(local, {
    bpm: 90,
    timeSignature: "3/4",
    tracks: [
      {
        id: "suno-track",
        sunoId: "suno-track",
        name: "New name",
        volume: 55,
        pan: -20,
        muted: true,
        solo: false,
        hidden: false,
        index: 0,
        clipIds: ["suno-clip"],
      },
    ],
    lanes: [
      {
        id: "suno-clip",
        sunoId: "suno-clip",
        title: "New",
        start: 4,
        duration: 8,
        midi: { notes: [] },
      },
    ],
  });
  const track = merged.data.tracks?.[0];
  assert.equal(track?.id, "track-1");
  assert.equal(track?.name, "New name");
  assert.equal(track?.volume, 55);
  assert.equal(track?.muted, true);
  assert.equal(track?.sunoId, "suno-track");
  const clip = merged.data.lanes?.find((entry) => entry.id === "clip-1");
  assert.equal(clip?.start, 4);
  assert.equal(clip?.duration, 8);
  assert.deepEqual(clip?.midi, { notes: [] });
  assert.deepEqual(merged.keptLocalClips, []);
});

test("loading never deletes a local-only clip or its track", () => {
  const local: LocalDocument = {
    tracks: [
      { id: "track-1", name: "Mine", index: 0, clipIds: ["clip-upload"] },
    ],
    lanes: [{ id: "clip-upload", title: "Upload", start: 0, duration: 4 }],
  };
  const merged = mergeSunoProjectIntoLocal(local, {
    bpm: 120,
    timeSignature: "4/4",
    tracks: [],
    lanes: [],
  });
  assert.deepEqual(merged.keptLocalClips, ["clip-upload"]);
  assert.equal(merged.data.tracks?.length, 1);
  assert.deepEqual(merged.data.tracks?.[0].clipIds, ["clip-upload"]);
  assert.deepEqual(merged.droppedTracks, []);
});

test("loading adds Suno tracks and clips that the local project lacks", () => {
  const local: LocalDocument = { tracks: [{ id: "track-1", index: 0, clipIds: [] }], lanes: [] };
  const merged = mergeSunoProjectIntoLocal(local, {
    bpm: 120,
    timeSignature: "4/4",
    tracks: [
      {
        id: "suno-track-2",
        sunoId: "suno-track-2",
        name: "From Suno",
        volume: 80,
        pan: 0,
        muted: false,
        solo: false,
        hidden: false,
        index: 1,
        clipIds: ["suno-clip-2"],
      },
    ],
    lanes: [
      {
        id: "suno-clip-2",
        sunoId: "suno-clip-2",
        title: "Suno audio",
        start: 2,
        duration: 4,
        sunoAssetId: "asset-1",
      },
    ],
  });
  const added = merged.data.tracks?.find((track) => track.sunoId === "suno-track-2");
  assert.ok(added);
  assert.equal(added?.name, "From Suno");
  const clip = merged.data.lanes?.find((entry) => entry.sunoId === "suno-clip-2");
  assert.ok(clip);
  assert.equal(clip?.sunoAssetId, "asset-1");
  assert.deepEqual(added?.clipIds, [clip?.id]);
});

test("an empty local-only track is dropped when Suno no longer has it", () => {
  const local: LocalDocument = {
    tracks: [
      { id: "track-1", index: 0, clipIds: [] },
      { id: "track-2", index: 1, clipIds: [] },
    ],
    lanes: [],
  };
  const merged = mergeSunoProjectIntoLocal(local, {
    bpm: 120,
    timeSignature: "4/4",
    tracks: [
      {
        id: "suno-track",
        name: "Kept",
        volume: 80,
        pan: 0,
        muted: false,
        solo: false,
        hidden: false,
        index: 0,
        clipIds: [],
      },
    ],
    lanes: [],
  });
  // The first local track matches by position (it was never pulled, so it has
  // no sunoId); the extra empty local track is dropped.
  assert.deepEqual(
    merged.data.tracks?.map((track) => track.id),
    ["track-1"]
  );
  assert.deepEqual(merged.droppedTracks, ["track-2"]);
});
