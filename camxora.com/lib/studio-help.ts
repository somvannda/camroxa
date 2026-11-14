/**
 * What's This? help registry (reference §7 / §38 / §62.2).
 *
 * The reference exposes every control name through its hover system; the captured list
 * lives in §62.2. The *names* are generic UI nouns, but the descriptions there are their
 * copy, so every sentence below is written for this editor (D-004).
 *
 * A control opts in with `data-help="<id>"`; unknown ids render no card rather than a
 * blank one.
 */

export type HelpEntry = {
  /** Short control name shown as the card's heading. */
  title: string;
  /** One or two sentences: what it does and the consequence of changing it. */
  body: string;
};

export const HELP_ENTRIES: Record<string, HelpEntry> = {
  tempo: {
    title: "Tempo",
    body: "Sets the song's BPM. Bar width on the canvas follows it, so clips keep their musical position when you change it.",
  },
  "time-signature": {
    title: "Time signature",
    body: "How many beats make a bar. Stored with the project and used when bars are counted.",
  },
  play: {
    title: "Play / pause",
    body: "Starts playback from the playhead. Clicking the ruler moves the playhead without starting.",
  },
  "back-to-start": {
    title: "Back to start",
    body: "Moves the playhead to zero. Playback stops so you can start from the top.",
  },
  loop: {
    title: "Loop",
    body: "Repeats the loop range. Drag the round handle on the timeline to move the end.",
  },
  metronome: {
    title: "Metronome",
    body: "Plays a click on every beat while the transport runs, with the first beat of each bar accented. Clicks are not part of the exported mix.",
  },
  undo: {
    title: "Undo",
    body: "Steps back through arrangement changes. The editor keeps the last 50 documents.",
  },
  redo: {
    title: "Redo",
    body: "Re-applies a change you undid, until you make a new one.",
  },
  export: {
    title: "Export",
    body: "Renders locally in the browser: full mix, one file per track, the loop range, or the project document.",
  },
  library: {
    title: "Library",
    body: "Opens the drawer with your songs, workspaces, projects and uploads. Add an item to the selected track.",
  },
  speed: {
    title: "Audition speed",
    body: "Cycles 1×, 0.5× and 2× for checking timing. Exports always render at normal speed.",
  },
  meter: {
    title: "Master peak",
    body: "Peak level at the master output while playing. The estimate is sample peak, not a certified loudness meter.",
  },
  project: {
    title: "Project",
    body: "Project menu: new, open, rename, duplicate, versions, sharing, settings and the quick-start overlay.",
  },
  "plugin-compressor": {
    title: "Compressor",
    body: "Evens out dynamics: threshold, ratio and knee set how hard peaks are reduced, then makeup gain restores level.",
  },
  "plugin-convolution": {
    title: "Convolution",
    body: "Places the signal in a sampled room: an impulse response shapes the result, and the mix blends it back.",
  },
  "plugin-delay": {
    title: "Delay",
    body: "Echo with feedback and mix; free-running in milliseconds or synced to the beat.",
  },
  "plugin-distortion": {
    title: "Distortion",
    body: "Waveshaping drive into a tone stage; tilt, bias and fold shape the character.",
  },
  "plugin-eq": {
    title: "EQ",
    body: "Four bands of parametric shaping: pick a band, choose its shape, then set frequency, Q and gain on the curve or the knobs.",
  },
  "plugin-gate": {
    title: "Gate",
    body: "Silences the signal below the threshold, with floor, attack and hold controlling how the gate closes and reopens.",
  },
  "plugin-limiter": {
    title: "Limiter",
    body: "Brickwall lookahead limiter: drives the signal into a fixed ceiling so peaks never pass it.",
  },
  "plugin-reverb": {
    title: "Reverb",
    body: "Algorithmic reverb with decay, mix, width, damping, predelay and low/high cut.",
  },
  "plugin-rhythm-gate": {
    title: "Rhythm Gate",
    body: "Transport-synced rhythmic gate: rate sets the division, depth the cut, attack and release its shape.",
  },
  clip: {
    title: "Clip",
    body: "Drag to move the clip, double-click to open its editor, or right-click for split, rename, colour, stems and download.",
  },
  "track-mute": {
    title: "Mute track",
    body: "Silences this track. Any soloed track overrides mute, so solo wins while it is on.",
  },
  "track-solo": {
    title: "Solo track",
    body: "Silences every track that is not soloed. Turn it off to hear the full arrangement again.",
  },
  "track-arm": {
    title: "Arm track",
    body: "Picks the track Record captures onto. One track is armed at a time; Record in the transport starts and stops the take.",
  },
  record: {
    title: "Record",
    body: "Captures the chosen microphone onto the armed track and rolls the transport. Stop recording ends the take and places it at the playhead.",
  },
  "record-input": {
    title: "Recording input",
    body: "Chooses which microphone Record uses. The setting belongs to this browser, not the project, so it never syncs.",
  },
  "record-count-in": {
    title: "Count-in",
    body: "Plays one bar of clicks before a take starts, at the project tempo and meter. Off by default; the setting is per browser.",
  },
  "track-volume": {
    title: "Track level",
    body: "Level applied to every clip on this track, during playback and export.",
  },
  zoom: {
    title: "Zoom",
    body: "Changes how many pixels one bar takes. Fit shows the whole arrangement at once.",
  },
  "add-track": {
    title: "Add track",
    body: "Opens the add-track menu. Audio adds an empty track, Upload opens your imported audio, and MIDI is not built in this editor.",
  },
  master: {
    title: "Main level",
    body: "Sets the overall output for playback and for the mix and range exports. Per-track files are bounced without it so they can be reimported.",
  },
  "master-mute": {
    title: "Mute main",
    body: "Silences everything downstream of the tracks without moving the fader. Exports follow it, so a muted bounce is silent.",
  },
};

export function helpFor(id: string | null | undefined): HelpEntry | null {
  if (!id) return null;
  return HELP_ENTRIES[id] ?? null;
}

/** Our real bindings, shown by Learn ▸ Keyboard Shortcuts. */
export const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: "Space", action: "Play / pause" },
  { keys: "Alt + Space", action: "Play from the start of the time selection" },
  { keys: "Home / End", action: "Jump to the song start (press again for beat 1) / the end" },
  { keys: "A / Shift T", action: "Add an audio track" },
  { keys: "U", action: "Open the library on Uploads" },
  { keys: "Ctrl/⌘ + ↑ / ↓", action: "Move the focused track up / down" },
  { keys: "Ctrl/⌘ + L", action: "Toggle loop" },
  { keys: "Shift C", action: "Toggle the metronome" },
  { keys: "Shift A", action: "Toggle the automation band" },
  { keys: "Shift Tab", action: "Swap the take lanes and automation bands" },
  { keys: "Shift L", action: "Collapse / expand the track panel" },
  { keys: "Ctrl/⌘ + S", action: "Save now (the studio also saves automatically)" },
  { keys: "MIDI editor · Ctrl/⌘ + K", action: "Toggle musical typing" },
  { keys: "MIDI editor · A–;", action: "Play notes while musical typing is on (Z/X octave, C/V velocity)" },
  { keys: "Ctrl/⌘ + A", action: "Select all clips" },
  { keys: "Ctrl/⌘ + C", action: "Copy the selected clips" },
  { keys: "Ctrl/⌘ + X", action: "Cut the selection" },
  { keys: "Ctrl/⌘ + V", action: "Paste at the playhead" },
  { keys: "Ctrl/⌘ + D", action: "Duplicate the selection" },
  { keys: "Ctrl/⌘ + E", action: "Split the selected clip at the playhead" },
  { keys: "Right-click a clip", action: "Clip menu: copy, split, rename, colour, download, stems" },
  { keys: "Drag the bar ruler", action: "Select a time range (Shift-click extends it)" },
  { keys: "Right-click the ruler", action: "Range menu: loop, duplicate/delete time, export the selection" },
  { keys: "Shift + ← / →", action: "Extend the time selection one beat" },
  { keys: "Ctrl/⌘ + Shift + D", action: "Duplicate the selected time" },
  { keys: "Ctrl/⌘ + Shift + Backspace", action: "Delete the selected time" },
  { keys: "Ctrl/⌘ + Backspace", action: "Delete the selected time on the focused track" },
  { keys: "Esc", action: "Clear the time selection" },
  { keys: "Delete / Backspace", action: "Delete the selection" },
  { keys: "Shift M / Shift S", action: "Mute / solo the focused track" },
  { keys: "0", action: "Mute / unmute the arrangement output" },
  { keys: "Shift 1 / Shift 2", action: "Double / halve the arrangement grid density" },
  { keys: "Shift H", action: "Hide & mute the focused track" },
  { keys: "Shift F", action: "Toggle a short fade on the selected clip" },
  { keys: "MIDI editor · Ctrl/⌘ + A", action: "Select every note" },
  { keys: "MIDI editor · Shift Q", action: "Quantize the selected notes" },
  { keys: "MIDI editor · 0", action: "Toggle the selected notes disabled" },
  { keys: "MIDI editor · ← / →", action: "Nudge the selected notes one grid step" },
  { keys: "MIDI editor · ↑ / ↓", action: "Transpose the selected notes a semitone" },
  { keys: "MIDI editor · Shift + ← / →", action: "Shorten / lengthen the selected notes" },
  { keys: "MIDI editor · Shift + ↑ / ↓", action: "Transpose the selected notes an octave" },
  { keys: "MIDI editor · Ctrl/⌘ + = / −", action: "Zoom the roll in / out" },
  { keys: "MIDI editor · Z", action: "Zoom to the selected notes" },
  { keys: "MIDI editor · velocity lane ↑ / ↓", action: "Raise / lower the selected notes' velocity (Shift ×10)" },
  { keys: "MIDI editor · Shift 1 / Shift 2", action: "Double / halve the grid density" },
  { keys: "MIDI editor · Delete", action: "Remove the selected notes" },
  { keys: "Shift Alt H", action: "Show all hidden tracks" },
  { keys: "F2", action: "Rename the focused track" },
  { keys: "1 / 3 / 4", action: "Toggle the assistant, take lanes, library" },
  { keys: "2", action: "Toggle the bottom plugin panel" },
  { keys: "Library · ↓ / ↑", action: "Audition the next / previous song" },
  { keys: "Library · →", action: "Replay the auditioned song from the top" },
  { keys: "Ctrl/⌘ + Z", action: "Undo" },
  { keys: "Ctrl/⌘ + Shift + Z", action: "Redo (Ctrl/⌘ + Y also works)" },
  { keys: "Ctrl/⌘ + + / −", action: "Zoom in / out" },
  { keys: "Ctrl + Shift + ,", action: "Open Studio settings" },
  { keys: "?", action: "Open this shortcut list" },
];
