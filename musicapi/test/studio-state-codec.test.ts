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
  SUNO_SYNTH_PLUGIN_ID,
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
        fadeOut: 1.5,
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
  assert.equal(audioClips[0].fadeOutBeats, 3);
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
  const song = project.lanes.find((clip) => clip.title === "Song");
  assert.equal(song?.fadeIn, 0.5);
  assert.equal(song?.fadeOut, 1.5);
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

test("effects map onto Suno plugin instances with translated params", () => {
  const data = localDocument();
  data.chains = {
    "track-1": [
      {
        entryId: "fx-1",
        pluginId: "compressor",
        presetName: "Custom",
        presetId: "preset-1",
        params: { threshold: -20, ratio: 4, knee: 6, attack: 10, release: 120, gain: 3 },
      },
      {
        entryId: "fx-2",
        pluginId: "reverb",
        presetName: "Custom",
        params: { time: 3, mix: 30, width: 100, damping: 40, predelay: 20, lowCut: 120, highCut: 14000 },
      },
    ],
  };
  const { state } = projectDocumentToSunoState({
    title: "FX",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline: null,
  });
  const chain = (state.tracks as Array<Record<string, unknown>>)[0].signalChain as Array<
    Record<string, unknown>
  >;
  const effects = chain.filter((entry) => entry.pluginVersionId !== SUNO_SYNTH_PLUGIN_ID);
  assert.equal(effects.length, 2);
  assert.equal(effects[0].pluginVersionId, "a4838315-d631-4255-946c-c65531bc9cd4");
  assert.equal(effects[0].presetId, "preset-1");
  assert.equal(effects[0].bypassed, false);
  assert.deepEqual(effects[0].paramAutomation, {});
  assert.equal((effects[0].params as Record<string, number>).output, 3);
  assert.equal((effects[0].params as Record<string, number>).threshold, -20);
  assert.equal(effects[1].pluginVersionId, "dec400a6-9dac-4c8a-b553-dd7bd2eb5f29");
  assert.equal((effects[1].params as Record<string, number>).highCut, 14000);
});

test("plugins without a verified translation are left out of the Suno chain", () => {
  const data = localDocument();
  data.chains = {
    "track-1": [
      { entryId: "fx-1", pluginId: "custom", params: { drive: 0.5 } },
      { entryId: "fx-2", pluginId: "gate", params: { threshold: -40, floor: -60, attack: 2, hold: 50 } },
    ],
  };
  const { state } = projectDocumentToSunoState({
    title: "FX partial",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline: null,
  });
  const chain = (state.tracks as Array<Record<string, unknown>>)[0].signalChain as Array<
    Record<string, unknown>
  >;
  const effects = chain.filter((entry) => entry.pluginVersionId !== SUNO_SYNTH_PLUGIN_ID);
  assert.equal(effects.length, 1);
  assert.equal(effects[0].pluginVersionId, "14fb47e6-c951-4a35-bfa6-f14d2396b4d0");
});

test("the EQ maps four bands and disables the fifth and sixth", () => {
  const data = localDocument();
  data.chains = {
    "track-1": [
      {
        entryId: "eq-1",
        pluginId: "eq",
        presetName: "Custom",
        params: {
          "band1.freq": 80,
          "band1.q": 0.7,
          "band1.gain": -3,
          "band1.on": 1,
          "band4.on": 0,
        },
      },
    ],
  };
  const { state } = projectDocumentToSunoState({
    title: "EQ",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline: null,
  });
  const chain = (state.tracks as Array<Record<string, unknown>>)[0].signalChain as Array<
    Record<string, unknown>
  >;
  const eq = chain.find((entry) => entry.pluginVersionId === "b1a718a1-839f-48d8-9482-ef6f64d490f0");
  assert.ok(eq);
  const params = eq?.params as Record<string, unknown>;
  assert.equal(params.freq1, 80);
  assert.equal(params.gain1, -3);
  assert.equal(params.enabled1, true);
  assert.equal(params.enabled4, false);
  assert.equal(params.enabled5, false);
  assert.equal(params.enabled6, false);
});

test("the master limiter and EQ map; other master effects stay local", () => {
  const data = localDocument();
  data.masterChain = [
    { type: "limiter", enabled: true, params: { lookahead: 5, preGain: -2, attack: 2, release: 80 } },
    { type: "eq", enabled: true, amount: 0.75 },
    { type: "compressor", enabled: true, amount: 0.5 },
  ];
  const { state } = projectDocumentToSunoState({
    title: "Master",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline: null,
  });
  const master = state.masterSignalChain as Array<Record<string, unknown>>;
  assert.equal(master.length, 3);
  assert.equal(master[0].pluginVersionId, "bf422c67-c85e-4b6d-9db9-1769c5912941");
  assert.deepEqual(master[0].params, { lookahead: 5, preGain: -2, attack: 2, release: 80 });
  assert.equal(master[1].pluginVersionId, "b1a718a1-839f-48d8-9482-ef6f64d490f0");
  const eqParams = master[1].params as Record<string, unknown>;
  assert.equal(eqParams.gain3, 6);
  assert.equal(eqParams.enabled3, true);
  assert.equal(eqParams.enabled1, false);
  assert.equal(master[2].pluginVersionId, "a4838315-d631-4255-946c-c65531bc9cd4");
  const compParams = master[2].params as Record<string, number>;
  assert.equal(compParams.threshold, -18);
  assert.equal(compParams.ratio, 5);
});

test("chains and the master limiter project back from a Suno document", () => {
  const data = localDocument();
  data.chains = {
    "track-1": [
      {
        entryId: "fx-1",
        pluginId: "reverb",
        presetName: "Custom",
        params: { time: 3, mix: 30, width: 100, damping: 40, predelay: 20, lowCut: 120, highCut: 14000 },
      },
    ],
  };
  data.masterChain = [{ type: "limiter", enabled: true, params: { lookahead: 5, preGain: 0, attack: 1, release: 60 } }];
  const { state } = projectDocumentToSunoState({
    title: "Round trip",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline: null,
  });
  const projected = sunoStateToProjectData(state);
  const trackId = projected.tracks[0].id;
  assert.equal(projected.chains[trackId]?.length, 1);
  assert.equal(projected.chains[trackId]?.[0].pluginId, "reverb");
  assert.equal((projected.chains[trackId]?.[0].params as Record<string, number>).mix, 30);
  assert.equal(projected.masterChain.length, 1);
  assert.equal(projected.masterChain[0].type, "limiter");
});

test("delay maps its mode, beats and 0–1 wet controls", () => {
  const data = localDocument();
  data.chains = {
    "track-1": [
      {
        entryId: "fx-delay",
        pluginId: "delay",
        mode: "tempo",
        presetName: "Custom",
        params: { time: 500, feedback: 40, mix: 25, lowCut: 120, highCut: 12000 },
      },
    ],
  };
  const { state } = projectDocumentToSunoState({
    title: "Delay",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline: null,
  });
  const chain = (state.tracks as Array<Record<string, unknown>>)[0].signalChain as Array<
    Record<string, unknown>
  >;
  const delay = chain.find(
    (entry) => entry.pluginVersionId === "e2b9270b-5099-4e2b-8ddc-c3a2b2cbe31e"
  );
  assert.ok(delay);
  const params = delay?.params as Record<string, unknown>;
  assert.equal(params.milliseconds, 500);
  assert.equal(params.beats, 1);
  assert.equal(params.mode, "tempo");
  assert.equal(params.feedback, 0.4);
  assert.equal(params.mix, 0.25);

  const projected = sunoStateToProjectData(state);
  const trackId = projected.tracks[0].id;
  const entry = projected.chains[trackId]?.[0];
  assert.equal(entry?.mode, "tempo");
  assert.equal((entry?.params as Record<string, number>).time, 500);
  assert.equal((entry?.params as Record<string, number>).feedback, 40);
  assert.equal((entry?.params as Record<string, number>).mix, 25);
});

test("MIDI bend and mod lanes become Suno point lists", () => {
  const data = localDocument();
  data.lanes = [
    {
      id: "clip-lanes",
      title: "Lanes",
      start: 0,
      duration: 4,
      midi: {
        notes: [{ id: "n1", pitch: 60, start: 0, length: 1, velocity: 100 }],
        bend: [
          { at: 0, value: -0.5 },
          { at: 2, value: 0.25 },
        ],
        mod: [{ at: 1, value: 0.8 }],
      },
    },
  ];
  data.tracks = [
    { id: "track-lanes", name: "Lead", index: 0, clipIds: ["clip-lanes"] },
  ];
  const { state } = projectDocumentToSunoState({
    title: "Lanes",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline: null,
  });
  const clip = (state.tracks as Array<Record<string, unknown>>)[0].clips as Array<
    Record<string, unknown>
  >;
  const midi = clip[0].midi as Record<string, unknown>;
  assert.deepEqual(midi.pitchBend, [
    { beats: 0, value: -0.5 },
    { beats: 4, value: 0.25 },
  ]);
  assert.deepEqual(midi.controlChanges, [
    { controller: 1, channel: 0, points: [{ beats: 2, value: 0.8 }] },
  ]);

  const projected = sunoStateToProjectData(state);
  const lane = projected.lanes[0];
  assert.deepEqual(lane.midi?.bend, [
    { at: 0, value: -0.5 },
    { at: 2, value: 0.25 },
  ]);
  assert.deepEqual(lane.midi?.mod, [{ at: 1, value: 0.8 }]);
});

test("a clip deleted locally is removed from the mirrored arrangement", () => {
  const deletedLocalId = "clip-deleted";
  const deletedSunoId = stableSunoId(deletedLocalId);
  const baseline = {
    tracks: [
      {
        id: stableSunoId("track-1"),
        name: "Track",
        type: "audio",
        clips: [
          {
            id: deletedSunoId,
            type: "audio",
            asset: { id: "asset-1", type: "clip" },
            startBeats: 0,
            endBeats: 8,
          },
        ],
      },
    ],
  };
  const data: LocalDocument = {
    tracks: [{ id: "track-1", name: "Track", index: 0, clipIds: [] }],
    lanes: [],
  };
  const withoutHistory = projectDocumentToSunoState({
    title: "Delete",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline,
  });
  assert.equal(
    ((withoutHistory.state.tracks as Array<Record<string, unknown>>)[0].clips as unknown[]).length,
    1
  );

  const withHistory = projectDocumentToSunoState({
    title: "Delete",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline,
    previousLocalClipIds: [deletedSunoId],
  });
  assert.equal(
    ((withHistory.state.tracks as Array<Record<string, unknown>>)[0].clips as unknown[]).length,
    0
  );
});

test("MidI tracks get a synth instance with our waveform", () => {
  const data = localDocument();
  data.lanes = [
    {
      id: "clip-midi",
      title: "Lead",
      start: 0,
      duration: 4,
      instrument: "triangle",
      midi: { notes: [{ id: "n1", pitch: 60, start: 0, length: 1, velocity: 100 }] },
    },
  ];
  data.tracks = [{ id: "track-midi", name: "Lead", index: 0, clipIds: ["clip-midi"] }];
  const { state } = projectDocumentToSunoState({
    title: "Synth",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline: null,
  });
  const track = (state.tracks as Array<Record<string, unknown>>)[0];
  const chain = track.signalChain as Array<Record<string, unknown>>;
  assert.equal(chain[0].pluginVersionId, SUNO_SYNTH_PLUGIN_ID);
  assert.equal((chain[0].params as Record<string, unknown>).waveform1, "triangle");

  const projected = sunoStateToProjectData(state);
  assert.equal(projected.lanes[0].midi?.instrument, "triangle");
});

test("distortion and chorus translate their enum and division params", () => {
  const data = localDocument();
  data.chains = {
    "track-1": [
      {
        entryId: "fx-dist",
        pluginId: "distortion",
        mode: "fold",
        params: { drive: 50, tilt: -20, freq: 2000 },
        presetName: "Custom",
      },
      {
        entryId: "fx-chorus",
        pluginId: "chorus",
        params: { rate: 1, depth: 40, mix: 30 },
        presetName: "Custom",
      },
    ],
  };
  const { state } = projectDocumentToSunoState({
    title: "Drive",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline: null,
  });
  const chain = (state.tracks as Array<Record<string, unknown>>)[0].signalChain as Array<
    Record<string, unknown>
  >;
  const dist = chain.find(
    (entry) => entry.pluginVersionId === "20c5b585-bdd5-45ad-9640-5b1fd68955f6"
  );
  const distParams = dist?.params as Record<string, unknown>;
  assert.equal(distParams.Shape, "Fold");
  assert.equal(distParams["Input Gain"], 12);
  assert.equal(distParams["Pre Tilt"], -20);
  assert.equal(distParams["Post Cutoff"], 2000);

  const chorus = chain.find(
    (entry) => entry.pluginVersionId === "537ba288-f700-4c96-b103-c84e2b62fab6"
  );
  const chorusParams = chorus?.params as Record<string, unknown>;
  // 1 Hz at 120 BPM = 2 cycles/beat → 1/2 note.
  assert.equal(chorusParams["rate (1/16, 1/8, 1/4)"], "1/2");
  assert.equal(chorusParams.depth, 0.4);
  assert.equal(chorusParams.mix, 0.3);
});

test("alternate takes become take-lane clips when they have a Suno asset", () => {
  const data = localDocument();
  data.tracks = [{ id: "track-takes", name: "Takes", index: 0, clipIds: ["clip-take"] }];
  data.lanes = [
    {
      id: "clip-take",
      title: "Main",
      start: 0,
      duration: 4,
      sunoAssetId: "asset-main",
      takes: [
        { id: "take-1", title: "Main", active: true, sunoAssetId: "asset-main" },
        { id: "take-2", title: "Cover", active: false, sunoAssetId: "asset-cover" },
        { id: "take-3", title: "Local only", active: false },
      ],
    },
  ];
  const { state } = projectDocumentToSunoState({
    title: "Takes",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline: null,
  });
  const track = (state.tracks as Array<Record<string, unknown>>)[0];
  const lanes = track.takeLanes as Array<Record<string, unknown>>;
  assert.equal(lanes.length, 1);
  assert.equal(lanes[0].dismissed, false);
  const clips = lanes[0].clips as Array<Record<string, unknown>>;
  assert.equal(clips.length, 1);
  assert.deepEqual(clips[0].asset, { id: "asset-cover", type: "clip" });
  assert.equal(track.takeLanesExpanded, true);
});

test("take lanes without a mirrorable take stay as Suno had them", () => {
  const baseline = {
    tracks: [
      {
        id: stableSunoId("track-1"),
        name: "Track",
        type: "audio",
        clips: [],
        takeLanes: [{ id: "suno-lane", name: "Suno take", clips: [] }],
      },
    ],
  };
  const { state } = projectDocumentToSunoState({
    title: "Keep",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data: localDocument(),
    baseline,
  });
  const track = (state.tracks as Array<Record<string, unknown>>)[0];
  assert.deepEqual(track.takeLanes, baseline.tracks[0].takeLanes);
});

test("volume and pan automation map to faderAutomation gain and pan", () => {
  const data = localDocument();
  data.tracks = [
    {
      id: "track-auto",
      name: "Auto",
      index: 0,
      clipIds: [],
      volumeAutomation: [
        { time: 0, value: 85 },
        { time: 8, value: 0 },
      ],
      panAutomation: [
        { time: 0, value: -50 },
        { time: 4, value: 50 },
      ],
    },
  ];
  const { state } = projectDocumentToSunoState({
    title: "Automation",
    majorVersion: 2,
    bpm: 120,
    timeSignature: "4/4",
    data,
    baseline: null,
  });
  const track = (state.tracks as Array<Record<string, unknown>>)[0];
  assert.deepEqual(track.faderAutomation, {
    gain: [
      { beats: 0, value: 0.85, curve: 1 },
      { beats: 16, value: 0, curve: 1 },
    ],
    pan: [
      { beats: 0, value: -0.5, curve: 1 },
      { beats: 8, value: 0.5, curve: 1 },
    ],
  });

  const projected = sunoStateToProjectData(state);
  assert.deepEqual(projected.tracks[0].volumeAutomation, [
    { time: 0, value: 85 },
    { time: 8, value: 0 },
  ]);
  assert.deepEqual(projected.tracks[0].panAutomation, [
    { time: 0, value: -50 },
    { time: 4, value: 50 },
  ]);
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
