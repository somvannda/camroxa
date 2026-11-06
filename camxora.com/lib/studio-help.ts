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
    body: "Recording is not implemented in this build, so arming is disabled rather than pretending to record.",
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
  { keys: "Home / End", action: "Playhead to the start / end" },
  { keys: "A / Shift T", action: "Add an audio track" },
  { keys: "U", action: "Open the library on Uploads" },
  { keys: "Ctrl/⌘ + L", action: "Toggle loop" },
  { keys: "Shift C", action: "Toggle the metronome" },
  { keys: "Ctrl/⌘ + A", action: "Select all clips" },
  { keys: "Ctrl/⌘ + C", action: "Copy the selected clips" },
  { keys: "Ctrl/⌘ + X", action: "Cut the selection" },
  { keys: "Ctrl/⌘ + V", action: "Paste at the playhead" },
  { keys: "Ctrl/⌘ + D", action: "Duplicate the selection" },
  { keys: "Delete / Backspace", action: "Delete the selection" },
  { keys: "Shift M / Shift S", action: "Mute / solo the focused track" },
  { keys: "Shift H", action: "Hide & mute the focused track" },
  { keys: "Shift F", action: "Toggle a short fade on the selected clip" },
  { keys: "Shift Alt H", action: "Show all hidden tracks" },
  { keys: "F2", action: "Rename the focused track" },
  { keys: "4", action: "Toggle the library drawer" },
  { keys: "Ctrl/⌘ + Z", action: "Undo" },
  { keys: "Ctrl/⌘ + Shift + Z", action: "Redo (Ctrl/⌘ + Y also works)" },
  { keys: "Ctrl/⌘ + + / −", action: "Zoom in / out" },
  { keys: "Ctrl + Shift + ,", action: "Open Studio settings" },
  { keys: "?", action: "Open this shortcut list" },
];
