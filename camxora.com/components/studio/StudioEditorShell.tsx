"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type DragEvent as ReactDragEvent } from "react";

import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import { getStudioProject, StudioConflictError, updateStudioProject, type StudioProject } from "@/lib/studio-api";
import { autoSnapshotStudioProject } from "@/lib/studio-api";
import { getStudioOperation, requestStudioStems } from "@/lib/studio-api";
import {
  createStudioPersona,
  listStudioPersonas,
  requestStudioCover,
  requestStudioExtend,
  requestStudioRemaster,
  requestStudioAddVocals,
  requestStudioAddInstrumental,
  requestStudioMashup,
  requestStudioReplaceSection,
  getStudioPricing,
  type StudioOperation,
  type StudioPersona,
} from "@/lib/studio-api";
import {
  extendedClipStart,
  resultAudioUrl,
  resultDuration,
  withTransformTake,
} from "@/lib/studio-transforms";
import {
  listStudioProjects,
  listStudioStems,
  listStudioUploads,
  uploadStudioAudio,
  type StudioStem,
  type StudioUpload,
} from "@/lib/studio-api";
import {
  createWebMusicWorkspace,
  dislikeWebMusicGeneration,
  downloadWebMusicClipWav,
  setWebMusicTrash,
  fetchWebMusicDislikedKeys,
  fetchWebMusicLikedKeys,
  likeWebMusicGeneration,
  listWebMusicWorkspaces,
  type WebMusicWorkspace,
} from "@/lib/web-music-api";
import {
  SONG_DRAG_TYPE,
  StudioLibrary,
  type LibraryView,
  type SongFilter,
} from "@/components/studio/StudioLibrary";
import { StudioClipInfo } from "@/components/studio/StudioClipInfo";
import { StudioSongDetail } from "@/components/studio/StudioSongDetail";
import { fetchGenerations, type WebMusicGeneration } from "@/lib/library-api";
import { fetchGeneration, generateSong } from "@/lib/create-api";
import { colorForTrackName, migrateLanesToTracks, sanitizeTracks, type StudioTrack } from "@/lib/studio-tracks";
import { dragToStart, isDrag, snapToGrid } from "@/lib/studio-snap";
import {
  clipRate,
  dbToGain,
  planClipPlayback,
  reverseBuffer,
  sanitizeClipAudio,
  type ClipAudioSettings,
} from "@/lib/studio-clip-audio";
import {
  deleteTimeRange,
  duplicateTimeRange,
  normaliseRange,
  type TimeRange,
} from "@/lib/studio-time";
import { buildMasterBus, type MasterChainEntry } from "@/lib/studio-master-bus";
import { renderMix, type ExportClip, type ExportTrack } from "@/lib/studio-export";
import { EXPORT_TARGET_PEAK_DB } from "@/lib/studio-normalise";
import {
  DEFAULT_STUDIO_SETTINGS,
  dragApplyPlan,
  readStudioSettings,
  writeStudioSettings,
  type StudioSettings,
} from "@/lib/studio-settings";
import { analyse, formatMeter, type MeterReading } from "@/lib/studio-meter";
import { beatAt, clicksBetween } from "@/lib/studio-metronome";
import {
  barBeatAt,
  parseBeatsPerBar,
  secondsPerBar as secondsPerBarFor,
} from "@/lib/studio-signature";
import { buildPluginChain } from "@/lib/studio-plugin-audio";
import { addCustomPlugin } from "@/lib/studio-plugin-chain";
import { clearDraft, describeDraft, loadDraft, saveDraft, type StudioDraft } from "@/lib/studio-draft";
import {
  makeUserPreset,
  sanitizeCustomPlugin,
  type CustomPlugin,
  type PluginChainEntry,
  type UserPreset,
} from "@/lib/studio-plugins";
import {
  DESIGN_CARD_SUBTITLE,
  DESIGN_PROMPT,
  designPlugin,
  type DesignResult,
} from "@/lib/studio-designer";
import { StudioPluginDock } from "@/components/studio/StudioPluginDock";
import { StudioMasterDock } from "@/components/studio/StudioMasterDock";
import { StudioTakeLanes } from "@/components/studio/StudioTakeLanes";
import { StudioSaveStatus, type SaveStatus } from "@/components/studio/StudioSaveStatus";
import { StudioHeader } from "@/components/studio/StudioHeader";
import { StudioFooter } from "@/components/studio/StudioFooter";
import { StudioMidiEditor } from "@/components/studio/StudioMidiEditor";
import { StudioAutomationPanel } from "@/components/studio/StudioAutomationPanel";
import { StudioAudioEditor } from "@/components/studio/StudioAudioEditor";
import type { WarpState } from "@/lib/studio-warp";
import {
  normalizeMidiInstrument,
  sanitizeNotes,
  sanitizePoints,
  scheduleMidiNote,
  valueAt,
  type MidiInstrument,
  type MidiNote,
} from "@/lib/studio-midi";
import { buildMidiFile } from "@/lib/studio-midi-file";
import { parseMidiFile } from "@/lib/studio-midi-import";
import { classifyStudioError } from "@/lib/studio-errors";
import { scheduleVolumeAutomation, type AutomationPoint } from "@/lib/studio-automation";
import { sanitizeSectionMarkers, type SectionMarker } from "@/lib/studio-markers";
import { ClipSourceStrip } from "@/components/studio/ClipSourceStrip";
import { StudioTrackPanel } from "@/components/studio/StudioTrackPanel";
import { StudioTimeline } from "@/components/studio/StudioTimeline";
import { StudioOnboarding } from "@/components/studio/StudioOnboarding";
import { StudioMetricsProbe } from "@/components/studio/StudioMetricsProbe";

const ROW_HEIGHT = 85;
const ROW_STEP = 86;
/** How many documents the undo stack keeps. */
const HISTORY_LIMIT = 50;
const PANEL_W = 260;
const LIBRARY_W = 360;
const ZOOM_LEVELS = [48, 64, 96, 144, 192];
/** Display labels stay lowercase; the API expects its enum values. */
const STUDIO_MODEL_API: Record<string, string> = {
  v6: "V6",
  "v6-wild": "V6_WILD",
  "v6-mini": "V6_MINI",
};
/** Clip Color swatches in the clip menu (same families as tracks). */
const CLIP_COLORS = ["#38bdf8", "#a78bfa", "#f472b6", "#fb923c", "#4ade80"];


/** Retry a library read once: a fresh session can race the first authorised fetch. */
async function fetchWithRetry<T>(run: () => Promise<T>, attempts = 2): Promise<T> {
  try {
    return await run();
  } catch (cause) {
    if (attempts <= 1) throw cause;
    await new Promise((resolve) => setTimeout(resolve, 700));
    return fetchWithRetry(run, attempts - 1);
  }
}

type ClipLike = {
  id: string;
  title?: string;
  color?: string;
  start?: number;
  duration?: number;
  volume?: number;
  pan?: number;
  muted?: boolean;
  solo?: boolean;
  groupId?: string | null;
  audioUrl?: string | null;
  songId?: string;
  offset?: number;
  fadeIn?: number;
  /** Warp markers + stretch mode (S30); parsed by `sanitizeWarp`. */
  warp?: unknown;
  /** Clip Settings audio state (S30/§81); parsed by `sanitizeClipAudio`. */
  audio?: unknown;
  midi?: { notes?: MidiNote[]; bend?: { at: number; value: number }[]; mod?: { at: number; value: number }[] };
  /** MIDI synth voice (S31); triangle when absent. */
  instrument?: MidiInstrument;
  /** Alternate takes (S29), newest first; the active one mirrors `audioUrl`. */
  takes?: Array<{
    id: string;
    title?: string;
    audioUrl?: string | null;
    duration?: number;
    active?: boolean;
  }>;
};

function clock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

function barBeat(seconds: number, bpm: number, signature: string): string {
  const { bar, beat } = barBeatAt(seconds, bpm, signature);
  return `${String(bar).padStart(3, "0")}.${beat}.1`;
}

/**
 * Studio editor shell built to the measured reference layout.
 *
 * Reads the real project, so the arrangement shown is genuine. Controls that are
 * not wired yet are disabled and labelled — none of them pretend to work.
 */
export function StudioEditorShell() {
  const { user, loading: authLoading } = useAuth();
  const [project, setProject] = useState<StudioProject | null>(null);
  const [error, setError] = useState("");
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("saved");
  const retryRef = useRef<(() => void) | null>(null);
  /** Retry that ignores the version check — used by "overwrite" (W2.2). */
  const forceRetryRef = useRef<(() => void) | null>(null);
  /** Serialized writes: at most one in flight, with the newest pending write queued. */
  const writeInFlightRef = useRef(false);
  const queuedWriteRef = useRef<{
    run: (expectedUpdatedAt: string | null) => Promise<StudioProject>;
    failure: string;
  } | null>(null);
  /** Document data that never reached the server (offline / failed write), for replay. */
  const unsavedDataRef = useRef<Record<string, unknown> | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);
  /** A draft recovered from storage after a failed or offline write (W2.3). */
  const [draft, setDraft] = useState<StudioDraft | null>(null);
  const projectRef = useRef<StudioProject | null>(null);
  /** Server version of the document, kept in sync without waiting for a render. */
  const projectVersionRef = useRef<string | null>(null);
  /** Library panel data (G12): songs, workspaces, other projects and uploads. */
  const [libraryView, setLibraryView] = useState<LibraryView>({ kind: "root" });
  /** Clip keys the viewer liked, for the Liked tile (level 2 filter). */
  const [likedKeys, setLikedKeys] = useState<string[] | null>(null);
  const [dislikedKeys, setDislikedKeys] = useState<string[] | null>(null);
  /** Song whose detail rail replaces the list after a row double-click (§100). */
  const [detailSong, setDetailSong] = useState<WebMusicGeneration | null>(null);
  /** Song auditioning from the library, and its audio element. */
  const [playingSongId, setPlayingSongId] = useState<string | null>(null);
  const [playingUploadId, setPlayingUploadId] = useState<string | null>(null);
  const previewRef = useRef<HTMLAudioElement | null>(null);
  /** Microphone capture state (D-020). */
  const [recording, setRecording] = useState(false);
  const [recordError, setRecordError] = useState("");
  const recorderRef = useRef<{
    recorder: MediaRecorder;
    stream: MediaStream;
    chunks: Blob[];
    start: number;
    trackId: string;
  } | null>(null);
  /** Guards the permission await so a double-click cannot open two streams. */
  const recordStartingRef = useRef(false);
  /** Microphone choices for the captured input picker (D-020). */
  const [inputDevices, setInputDevices] = useState<{ id: string; label: string }[]>([]);
  const [inputOpen, setInputOpen] = useState(false);
  /** 1-based beat while a one-bar count-in runs; 0 when idle (D-021). */
  const [countInBeat, setCountInBeat] = useState(0);
  /** Right rail shows the clip inspector instead of the library (spec §70). */
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [librarySongs, setLibrarySongs] = useState<WebMusicGeneration[] | null>(null);
  const [libraryWorkspaces, setLibraryWorkspaces] = useState<WebMusicWorkspace[] | null>(null);
  /** Workspace the Songs tab is filtered to; null means every song. */
  const [libraryWorkspaceId, setLibraryWorkspaceId] = useState<string | null>(null);
  const [libraryProjects, setLibraryProjects] = useState<StudioProject[] | null>(null);
  const [libraryUploads, setLibraryUploads] = useState<StudioUpload[] | null>(null);
  const [libraryStems, setLibraryStems] = useState<StudioStem[] | null>(null);
  const [playingStemId, setPlayingStemId] = useState<string | null>(null);
  const [libraryQuery, setLibraryQuery] = useState("");
  /** A failed library request; the panel offers a retry instead of pretending it is empty. */
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const librarySearchRef = useRef<HTMLInputElement | null>(null);
  /** Source generation of the selected clip, when it came from the library (G16). */
  const [clipSource, setClipSource] = useState<WebMusicGeneration | null>(null);
  /** Stem separation request state for the selected clip (W4.2). */
  const [stems, setStems] = useState<{ status: string; message?: string } | null>(null);
  /** Get Stems dialog (M1): choose the separation depth before spending credits. */
  const [stemsPrompt, setStemsPrompt] = useState<{ songId: string } | null>(null);
  const [stemsMode, setStemsMode] = useState<"vocal" | "stems" | "advanced">("stems");
  /** Clip transform in flight + the optional Cover prompt (D-033). */
  const [transformBusy, setTransformBusy] = useState<
    null | "extend" | "cover" | "remaster" | "vocals" | "instrumental" | "mashup" | "replace"
  >(null);
  const [transformPrompt, setTransformPrompt] = useState<
    { clipId: string; kind: "cover" | "vocals" | "instrumental" | "mashup" | "replace" } | null
  >(null);
  /** Lyrics for Replace Section (the provider needs them, unlike the prompt-only edits). */
  const [transformLyrics, setTransformLyrics] = useState("");
  /** Refusal card for a paid transform that could not run (credits / provider). */
  const [transformNotice, setTransformNotice] = useState<
    null | { kind: "credits" | "failed"; text: string }
  >(null);
  /** The two clips a mashup will combine (captured when the dialog opens). */
  const [mashupIds, setMashupIds] = useState<string[]>([]);
  const [transformValue, setTransformValue] = useState("");
  /** Credit price for one clip transform, from the pricing endpoint (never hard-coded). */
  const [transformCost, setTransformCost] = useState<number | null>(null);
  const [stemsPricing, setStemsPricing] = useState<{ stems2: number; stems12: number } | null>(
    null
  );
  /** Personas for Replace Section (GEN-025/026): list, creation and the selected id. */
  const [personas, setPersonas] = useState<StudioPersona[]>([]);
  const [personaBusy, setPersonaBusy] = useState(false);
  const [personaError, setPersonaError] = useState("");
  const [personaName, setPersonaName] = useState("");
  const [selectedPersonaId, setSelectedPersonaId] = useState("");

  useEffect(() => {
    if (transformPrompt?.kind !== "replace") return;
    void refreshPersonas();
    // The list only needs refreshing when the Replace Section dialog opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transformPrompt?.kind]);

  useEffect(() => {
    let active = true;
    getStudioPricing()
      .then((pricing) => {
        if (!active) return;
        setTransformCost(pricing.edit);
        setStemsPricing({ stems2: pricing.stems_2, stems12: pricing.stems_12 });
      })
      .catch(() => {
        /* the action still works; the price is just omitted */
      });
    return () => {
      active = false;
    };
  }, []);
  /** Active clip drag: every selected clip's origin plus the latest pointer delta. */
  const [drag, setDrag] = useState<{
    ids: string[];
    origins: Record<string, number>;
    deltaPx: number;
  } | null>(null);
  /** Live geometry while a trim grip is dragged; committed on release. */
  const [trimPreview, setTrimPreview] = useState<{
    id: string;
    start: number;
    duration: number;
    offset: number;
  } | null>(null);
  /** Live fade-in length while its handle is dragged (S25). */
  const [fadePreview, setFadePreview] = useState<{ id: string; fadeIn: number } | null>(null);
  /** Clip context menu (S26/§47): anchored at the click point, built from clip state. */
  const [clipMenu, setClipMenu] = useState<{ clipId: string; x: number; y: number } | null>(null);  const [clipColorOpen, setClipColorOpen] = useState(false);
  /** Clip rename dialog (clip menu ▸ Rename). */
  const [clipRename, setClipRename] = useState<{ id: string; value: string } | null>(null);
  const fadePreviewRef = useRef<typeof fadePreview>(null);
  fadePreviewRef.current = fadePreview;
  const fadeRef = useRef<{ id: string; startX: number; fadeIn: number; duration: number } | null>(
    null
  );
  const fadeStartRef = useRef<{ x: number; fadeIn: number; duration: number } | null>(null);
  /** Freshest pointer handlers, called by one stable pair of window listeners. */
  const pointerHandlersRef = useRef<{
    move: (event: PointerEvent) => void;
    up: (event: PointerEvent) => void;
  } | null>(null);
  const trimPreviewRef = useRef<typeof trimPreview>(null);
  trimPreviewRef.current = trimPreview;
  const trimRef = useRef<{
    id: string;
    edge: "start" | "end";
    startX: number;
    start: number;
    duration: number;
    offset: number;
  } | null>(null);
  const dragRef = useRef<{
    startX: number;
    ids: string[];
    origins: Record<string, number>;
    /** Ghost-drag mode, captured when the gesture starts (spec §22). */
    ghost: boolean;
  } | null>(null);
  /** Mirror of `drag` so pointer handlers can read it without a state updater. */
  const dragStateRef = useRef<{ ids: string[]; origins: Record<string, number>; deltaPx: number } | null>(
    null
  );
  /** Marquee (rubber-band) selection, in lane-local pixels. */
  const [marquee, setMarquee] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(
    null
  );
  const marqueeRef = useRef<{
    x1: number;
    y1: number;
    startX: number;
    originX: number;
    originY: number;
    moved: boolean;
    hit: string[];
  } | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  /** Track options menu (spec §65) and hidden-tracks popover (S21). */
  const [menuTrackId, setMenuTrackId] = useState<string | null>(null);
  const [hiddenOpen, setHiddenOpen] = useState(false);
  const [renameTrackId, setRenameTrackId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  /** Visible horizontal window of the timeline, for clip culling (G19). */
  const [view, setView] = useState({ left: 0, width: 0 });
  /** Scroll container, measured once so culling has a window before any scroll. */
  const timelineRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = timelineRef.current;
    if (!el) return;
    if (view.width !== 0) return;
    setView({ left: el.scrollLeft, width: el.clientWidth });
  });

  /** Press on empty lane: seek; dragging from there becomes a marquee (G6). */
  function handleLanePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    marqueeRef.current = {
      x1: x,
      y1: y,
      startX: event.clientX,
      originX: rect.left,
      originY: rect.top,
      moved: false,
      hit: [],
    };
    // Clicking empty space is "no selection" (spec §2), so the range goes too.
    setTimeSelection(null);
    setRangeMenu(null);
    setSelectedIds([]);
    setSelectedClip(null);
    seekTo(Math.max(0, Math.min(duration, (x / barWidth) * secondsPerBar)));
  }

  /** Grab a trim grip (S25): geometry follows the pointer and is written on release. */
  function handleTrimPointerDown(
    event: React.PointerEvent<HTMLElement>,
    clip: ClipLike,
    edge: "start" | "end"
  ) {
    event.stopPropagation();
    event.preventDefault();
    const start = clip.start ?? 0;
    const duration = clip.duration ?? 4;
    const offset = (clip as { offset?: number }).offset ?? 0;
    setSelectedClip(clip.id);
    setSelectedIds([clip.id]);
    trimRef.current = { id: clip.id, edge, startX: event.clientX, start, duration, offset };
    setTrimPreview({ id: clip.id, start, duration, offset });
  }

  /** Grab the fade handle (S25): a diagonal stub at the clip's top-left corner. */
  function handleFadePointerDown(event: React.PointerEvent<HTMLElement>, clip: ClipLike) {
    event.stopPropagation();
    event.preventDefault();
    const duration = clip.duration ?? 4;
    const fadeIn = Math.min((clip as { fadeIn?: number }).fadeIn ?? 0, duration);
    setSelectedClip(clip.id);
    setSelectedIds([clip.id]);
    fadeRef.current = { id: clip.id, startX: event.clientX, fadeIn, duration };
    setFadePreview({ id: clip.id, fadeIn });
  }

  function commitClipFade(id: string, fadeIn: number) {
    const data = (projectRef.current?.data || {}) as Record<string, unknown>;
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    const updated = lanes.map((clip) =>
      clip.id === id ? { ...clip, fadeIn: fadeIn > 0.0001 ? fadeIn : undefined } : clip
    );
    writeProjectData({ ...data, lanes: updated }, "the clip fade");
  }

  function commitTrim(preview: { id: string; start: number; duration: number; offset: number }) {    // Read through the ref: this can run from the global pointer handler, whose closure
    // may predate the loaded project.
    const data = (projectRef.current?.data || {}) as Record<string, unknown>;
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    const updated = lanes.map((clip) =>
      clip.id === preview.id
        ? {
            ...clip,
            start: preview.start,
            duration: preview.duration,
            offset: preview.offset > 0.0001 ? preview.offset : undefined,
          }
        : clip
    );
    writeProjectData({ ...data, lanes: updated }, "trimming the clip");
  }

  /** Press on a clip: select it (or keep the group) and start a drag session (G7/G8). */
  function handleClipPointerDown(
    event: React.PointerEvent<HTMLButtonElement>,
    clip: ClipLike,
    trackId: string
  ) {
    event.stopPropagation();
    // A right-click opens the menu; it must not clear the time range or start a drag.
    if (event.button !== 0) return;
    // Selection is contextual (spec §2): a clip press replaces a time range.
    setTimeSelection(null);
    setRangeMenu(null);
    setSelectedTrack(trackId);
    setSelectedClip(clip.id);
    // Selecting an audio clip leaves the MIDI editor; a MIDI clip opens it.
    setMidiClipId((clip as { midi?: unknown }).midi ? clip.id : null);
    if ((clip as { midi?: unknown }).midi) setAudioClipId(null);
    setAutomationOpen(false);
    const group = selectedIds.includes(clip.id) ? selectedIds : [clip.id];
    setSelectedIds(group);
    const origins: Record<string, number> = {};
    group.forEach((id) => {
      const found = clips.find((candidate) => candidate.id === id);
      if (found) origins[id] = found.start ?? 0;
    });
    dragRef.current = { startX: event.clientX, ids: group, origins, ghost: settingsRef.current.ghostDrag };
  }

  /**
   * Double-click opens the clip editor the reference opens for that clip type (§81):
   * the note grid for MIDI, the warp/stretch editor for audio.
   */
  function handleClipDoubleClick(clip: ClipLike) {
    if ((clip as { midi?: unknown }).midi) {
      setAudioClipId(null);
      setMidiClipId(clip.id);
      setAutomationOpen(false);
      return;
    }
    if (!clip.audioUrl) return;
    setMidiClipId(null);
    setAudioClipId(clip.id);
    setAutomationOpen(false);
  }

  /** Persist the warp markers / stretch state onto the clip (S30). */
  function commitWarp(clipId: string, warp: WarpState) {
    const data = currentData();
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    writeProjectData(
      { ...data, lanes: lanes.map((clip) => (clip.id === clipId ? { ...clip, warp } : clip)) },
      "the warp markers"
    );
  }

  /** Persist Volume / Loop / Reverse / Pitch / Speed onto the clip (§81). */
  function commitClipAudio(clipId: string, audio: ClipAudioSettings) {
    const data = currentData();
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    writeProjectData(
      { ...data, lanes: lanes.map((clip) => (clip.id === clipId ? { ...clip, audio } : clip)) },
      "the clip settings"
    );
  }

  const [exporting, setExporting] = useState(false);
  /** N-06: the track whose bounce is rendering right now. */
  const [bouncingTrack, setBouncingTrack] = useState<string | null>(null);
  const [exportToast, setExportToast] = useState<string | null>(null);
  const [midiClipId, setMidiClipId] = useState<string | null>(null);
  const [automationOpen, setAutomationOpen] = useState(false);
  /** Audio clip editor (S30): warp markers live beside the clip's waveform. */
  const [audioClipId, setAudioClipId] = useState<string | null>(null);
  const [promptValue, setPromptValue] = useState("");
  const [promptBusy, setPromptBusy] = useState(false);
  const [promptModel, setPromptModel] = useState("v6");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantMessages, setAssistantMessages] = useState<
    Array<{ id: string; role: "user" | "status" | "result" | "design"; text: string }>
  >([]);
  /** S45: the prompt bar is designing a plugin rather than generating a part. */
  const [designMode, setDesignMode] = useState(false);
  const [designContext, setDesignContext] = useState<string | null>(null);
  /** Restate message awaiting "Build it" / "Change something…". */
  const [designRequest, setDesignRequest] = useState<DesignResult | null>(null);
  /** Built plugin shown as a draggable card; saved to the library, never inserted. */
  const [designBuilt, setDesignBuilt] = useState<DesignResult | null>(null);
  const [pendingSong, setPendingSong] = useState<WebMusicGeneration | null>(null);
  /** Refusal state for the assistant (own addition; S60/S61 have no capture). */
  const [promptNotice, setPromptNotice] = useState<
    { kind: "credits" | "moderation"; text: string } | null
  >(null);
  const [previewingUrl, setPreviewingUrl] = useState<string | null>(null);
  const [modelOpen, setModelOpen] = useState(false);
  const [attachOpen, setAttachOpen] = useState(false);
  const promptRef = useRef<HTMLFormElement | null>(null);

  useEffect(() => {
    if (!modelOpen) return;
    const onPointer = (event: PointerEvent) => {
      if (promptRef.current && !promptRef.current.contains(event.target as Node)) {
        setModelOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setModelOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [modelOpen]);

  useEffect(() => {
    if (!attachOpen) return;
    const onPointer = (event: PointerEvent) => {
      if (promptRef.current && !promptRef.current.contains(event.target as Node)) {
        setAttachOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setAttachOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [attachOpen]);
  const [remixingSongId, setRemixingSongId] = useState<string | null>(null);
  /** Export menu setting (G11): gain-match mix/range renders to a fixed peak. */
  const [exportNormalise, setExportNormalise] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  /** Undo/redo: documents, newest last. */
  const historyRef = useRef<{ undo: { data: unknown; label: string }[]; redo: { data: unknown; label: string }[] }>(
    { undo: [], redo: [] }
  );
  const [historyState, setHistoryState] = useState({ canUndo: false, canRedo: false });
  function syncHistory() {
    setHistoryState({
      canUndo: historyRef.current.undo.length > 0,
      canRedo: historyRef.current.redo.length > 0,
    });
  }
  /** Master peak readout while playing (W4.4). */
  const [meter, setMeter] = useState<MeterReading | null>(null);
  /** Editor preferences (§22), loaded from the browser profile after mount. */
  const [settings, setSettings] = useState<StudioSettings>(DEFAULT_STUDIO_SETTINGS);
  const settingsRef = useRef(settings);
  settingsRef.current = settings;
  const [loading, setLoading] = useState(true);
  const [selectedTrack, setSelectedTrack] = useState<string | null>(null);
  const [masterSelected, setMasterSelected] = useState(false);
  const [takeLanesOpen, setTakeLanesOpen] = useState(false);
  const [selectedClip, setSelectedClip] = useState<string | null>(null);
  /** A clip explicitly attached with the prompt bar's + menu (not just selected). */
  const [attachedClipId, setAttachedClipId] = useState<string | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [tracksCollapsed, setTracksCollapsed] = useState(false);
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loop, setLoop] = useState(false);
  /** Loop / export range in seconds (spec §68). */
  const [loopStart, setLoopStart] = useState(0);
  const [loopEnd, setLoopEnd] = useState(0);
  const loopDragRef = useRef(false);
  /** Reversed source buffers, keyed by clip id + URL so Reverse is computed once. */
  const reversedBuffersRef = useRef<Map<string, AudioBuffer>>(new Map());
  /** Time selection (N-01), created by dragging on the bar ruler; not persisted. */
  const [timeSelection, setTimeSelection] = useState<TimeRange | null>(null);
  const [markers, setMarkers] = useState<SectionMarker[]>([]);
  const [rangeMenu, setRangeMenu] = useState<{ x: number; y: number } | null>(null);
  const rangeDragRef = useRef<{
    anchor: number;
    startX: number;
    moved: boolean;
    edge: "start" | "end" | null;
  } | null>(null);
  const [metronome, setMetronome] = useState(false);
  const [bpm, setBpm] = useState(120);
  /** Meter (H-13): editable in the header, persisted in the project columns. */
  const [timeSignature, setTimeSignature] = useState("4/4");
  const beatsPerBar = parseBeatsPerBar(timeSignature);
  const secondsPerBar = secondsPerBarFor(bpm, timeSignature);
  /** Master level (reference F-01/F-02), persisted in the document. */
  const [masterVolume, setMasterVolume] = useState(85);
  const [masterMuted, setMasterMuted] = useState(false);
  const masterStateRef = useRef({ volume: masterVolume, muted: masterMuted });
  masterStateRef.current = { volume: masterVolume, muted: masterMuted };
  /** Pixels per bar; 96 is the captured default (spec §44.3). */
  const [barWidth, setBarWidth] = useState(96);
  /** Audition speed (G17): 0.5x / 1x / 2x. */
  const [playbackRate, setPlaybackRate] = useState(1);
  const [projectId, setProjectId] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setProjectId(params.get("project"));
    setSettings(readStudioSettings());
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user || !projectId) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    getStudioProject(projectId)
      .then((next) => {
        if (!active) return;
        setProject(next);
        setBpm(next.bpm || 120);
        setTimeSignature(next.time_signature || "4/4");
        setMarkers(
          sanitizeSectionMarkers((next.data as { markers?: unknown } | undefined)?.markers)
        );
        const master = (next.data || {}) as { masterVolume?: unknown; masterMuted?: unknown };
        if (typeof master.masterVolume === "number" && Number.isFinite(master.masterVolume)) {
          setMasterVolume(Math.max(0, Math.min(100, master.masterVolume)));
        }
        setMasterMuted(Boolean(master.masterMuted));
        setError("");
        // A draft only surfaces when it is newer than what the server has (W2.3).
        const stored = loadDraft(projectId);
        const serverAt = next.updated_at ? new Date(next.updated_at).getTime() : 0;
        const draftAt = stored ? new Date(stored.savedAt).getTime() : 0;
        setDraft(stored && draftAt > serverAt ? stored : null);
      })
      .catch((cause) => {
        if (!active) return;
        setError(cause instanceof Error ? cause.message : "Could not open this project.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [authLoading, user, projectId]);

  const clips = useMemo<ClipLike[]>(() => {
    const data = (project?.data || {}) as { lanes?: unknown };
    return Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
  }, [project]);

  /** Song ids the open project already uses (library "In Project" filter, §19.2). */
  const projectSongIds = useMemo(() => {
    const ids = clips.map((clip) => (clip as { songId?: string }).songId);
    return [...new Set(ids.filter((id): id is string => Boolean(id)))];
  }, [clips]);

  const derivedTracks = useMemo<StudioTrack[]>(() => {
    const data = (project?.data || {}) as { tracks?: unknown };
    const stored = sanitizeTracks(data.tracks);
    if (stored.length) return stored;
    return migrateLanesToTracks(
      clips.map((clip) => ({
        id: clip.id,
        title: clip.title,
        color: clip.color,
        volume: clip.volume,
        pan: clip.pan,
        muted: clip.muted,
        solo: clip.solo,
        groupId: clip.groupId ?? null,
      }))
    );
  }, [project, clips]);

  const [localTracks, setLocalTracks] = useState<StudioTrack[] | null>(null);
  const tracks = localTracks ?? derivedTracks;

  // Pointer handlers are registered once; these refs give them the current data
  // instead of a closure captured at mount (which silently selected nothing).
  const tracksRef = useRef<StudioTrack[]>(tracks);
  const clipsRef = useRef<ClipLike[]>(clips);
  tracksRef.current = tracks;
  clipsRef.current = clips;

  useEffect(() => {
    setLocalTracks(null);
  }, [projectId]);

  /** Keep the freshest project for draft writes made from event handlers. */
  projectRef.current = project;
  /** Latest server version, updated synchronously so a queued write never goes stale. */
  projectVersionRef.current = project?.updated_at ?? projectVersionRef.current;

  /**
   * Document data read through the ref. Global pointer/key handlers can outlive the
   * render that created them, so writing `project.data` from their closure can persist a
   * document from before the project even loaded.
   */
  function currentData(): Record<string, unknown> {
    return (projectRef.current?.data || {}) as Record<string, unknown>;
  }
  /** Load the library panel's lists the first time it opens (G12). */
  useEffect(() => {
    if (!libraryOpen || !user) return;
    let active = true;
    if (librarySongs === null) {
      fetchWithRetry(() => fetchGenerations(20, libraryWorkspaceId))
        .then((items) => {
          if (active) setLibrarySongs(items);
        })
        .catch(() => {
          if (active) {
            setLibrarySongs([]);
            setLibraryError("Some library data could not load.");
          }
        });
    }
    if (libraryWorkspaces === null) {
      listWebMusicWorkspaces()
        .then((result) => {
          if (active) setLibraryWorkspaces(result.items ?? []);
        })
        .catch(() => {
          if (active) {
            setLibraryWorkspaces([]);
            setLibraryError("Some library data could not load.");
          }
        });
    }
    if (libraryProjects === null) {
      listStudioProjects(50, 0, false)
        .then((result) => {
          if (active) setLibraryProjects(result.items ?? []);
        })
        .catch(() => {
          if (active) {
            setLibraryProjects([]);
            setLibraryError("Some library data could not load.");
          }
        });
    }
    if (libraryUploads === null) {
      listStudioUploads(50)
        .then((result) => {
          if (active) setLibraryUploads(result.items ?? []);
        })
        .catch(() => {
          if (active) {
            setLibraryUploads([]);
            setLibraryError("Some library data could not load.");
          }
        });
    }
    if (libraryView.kind === "stems" && libraryStems === null) {
      listStudioStems(100)
        .then((result) => {
          if (active) setLibraryStems(result.items ?? []);
        })
        .catch(() => {
          if (active) {
            setLibraryStems([]);
            setLibraryError("Some library data could not load.");
          }
        });
    }
    if (likedKeys === null) {
      fetchWebMusicLikedKeys()
        .then((keys) => {
          if (active) setLikedKeys(keys);
        })
        .catch(() => {
          if (active) setLikedKeys([]);
        });
    }
    if (dislikedKeys === null) {
      fetchWebMusicDislikedKeys()
        .then((keys) => {
          if (active) setDislikedKeys(keys);
        })
        .catch(() => {
          if (active) setDislikedKeys([]);
        });
    }
    return () => {
      active = false;
    };
  }, [
    libraryOpen,
    user,
    librarySongs,
    libraryWorkspaceId,
    libraryWorkspaces,
    libraryProjects,
    libraryUploads,
    libraryStems,
    libraryView.kind,
    likedKeys,
    dislikedKeys,
  ]);

  /** Stop the audition when the drawer closes or the editor unmounts. */  useEffect(() => {
    if (libraryOpen) return;
    previewRef.current?.pause();
    previewRef.current = null;
    setPlayingSongId(null);
    setPlayingUploadId(null);
    setDetailSong(null);
  }, [libraryOpen]);
  useEffect(() => () => previewRef.current?.pause(), []);
  /** Never leave the microphone open after the editor unmounts. */
  useEffect(
    () => () => {
      recorderRef.current?.recorder.stop();
      recorderRef.current?.stream.getTracks().forEach((track) => track.stop());
    },
    []
  );
  /** Transport playback wins over a library audition; never run both at once. */
  useEffect(() => {
    if (!playing) return;
    previewRef.current?.pause();
    previewRef.current = null;
    setPlayingSongId(null);
    setPlayingUploadId(null);
  }, [playing]);

  /** Level 2 of the library: the song list, optionally liked-only (spec §19.1). */
  function openLibrarySongs(filter: "all" | "liked") {
    // A tile chooses the whole corpus, so it drops any workspace filter left over from
    // an earlier workspace visit.
    if (libraryWorkspaceId) {
      setLibraryWorkspaceId(null);
      setLibrarySongs(null);
    }
    setLibraryView({
      kind: "songs",
      title: filter === "liked" ? "Liked" : "All Songs",
      filter,
    });
  }

  /** The level-2 filter menu changes the corpus without leaving the list (§19.2). */
  function setLibrarySongFilter(filter: SongFilter) {
    const workspace = (libraryWorkspaces ?? []).find((item) => item.id === libraryWorkspaceId);
    setLibraryView({
      kind: "songs",
      title:
        filter === "all" && workspace
          ? workspace.name
          : filter === "liked"
            ? "Liked"
            : filter === "project"
              ? "In Project"
              : "All Songs",
      filter,
    });
  }

  /** Arm exactly one track; arming another disarms the previous one. */
  function toggleArm(trackId: string) {
    if (recording) return;
    const target = tracks.find((track) => track.id === trackId);
    if (!target) return;
    const armed = !target.armed;
    commitTracks(tracks.map((track) => ({ ...track, armed: track.id === trackId ? armed : false })));
  }

  /** Start a microphone take on the armed track and roll the transport. */
  async function startRecording() {
    if (recordStartingRef.current || recorderRef.current) return;
    setRecordError("");
    const target = tracks.find((track) => track.armed);
    if (!target) {
      setRecordError("Arm a track before recording.");
      return;
    }
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setRecordError("This browser cannot record audio.");
      return;
    }
    recordStartingRef.current = true;
    try {
      const deviceId = settingsRef.current.inputDeviceId;
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: deviceId ? { deviceId: { exact: deviceId } } : true,
      });
      if (settingsRef.current.countIn) await runCountIn();
      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      const active = { recorder, stream, chunks, start: playheadRef.current, trackId: target.id };
      recorder.onstop = () => {
        void finishRecording(active);
      };
      recorder.start();
      recorderRef.current = active;
      setRecording(true);
      if (!playing) togglePlayback();
    } catch {
      setRecordError("Microphone permission was denied.");
    } finally {
      recordStartingRef.current = false;
    }
  }

  /** One bar of clicks before the take starts (D-021). */
  async function runCountIn() {
    const beats = Math.max(1, beatsPerBar);
    const beatMs = 60_000 / Math.max(30, bpm);
    const context = new AudioContext();
    void context.resume();
    for (let index = 0; index < beats; index += 1) {
      const when = context.currentTime + 0.03;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "square";
      oscillator.frequency.value = index === 0 ? 1760 : 1100;
      gain.gain.setValueAtTime(0.0001, when);
      gain.gain.linearRampToValueAtTime(index === 0 ? 0.16 : 0.09, when + 0.002);
      gain.gain.exponentialRampToValueAtTime(0.0001, when + 0.045);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(when);
      oscillator.stop(when + 0.06);
      setCountInBeat(index + 1);
      await new Promise((resolve) => setTimeout(resolve, beatMs));
    }
    await context.close();
    setCountInBeat(0);
  }

  function toggleCountInSetting() {
    const updated = { ...settingsRef.current, countIn: !settingsRef.current.countIn };
    setSettings(updated);
    writeStudioSettings(updated);
  }

  /** List the microphones for the captured input picker, then toggle it. */
  async function toggleInputPicker() {
    if (!inputOpen) {
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        setInputDevices(
          devices
            .filter((device) => device.kind === "audioinput")
            .map((device, index) => ({
              id: device.deviceId,
              label: device.label || `Input ${index + 1}`,
            }))
        );
      } catch {
        setInputDevices([]);
      }
    }
    setInputOpen((open) => !open);
  }

  function pickInputDevice(deviceId: string | null) {
    const updated = { ...settingsRef.current, inputDeviceId: deviceId };
    setSettings(updated);
    writeStudioSettings(updated);
    setInputOpen(false);
  }

  /** Stop capture; the take is uploaded and inserted by `finishRecording`. */
  function stopRecording() {
    const active = recorderRef.current;
    if (!active) {
      setRecording(false);
      return;
    }
    try {
      active.recorder.stop();
    } catch {
      /* already stopped */
    }
    active.stream.getTracks().forEach((track) => track.stop());
    recorderRef.current = null;
    setRecording(false);
  }

  async function finishRecording(active: {
    recorder: MediaRecorder;
    stream: MediaStream;
    chunks: Blob[];
    start: number;
    trackId: string;
  }) {
    const blob = new Blob(active.chunks, { type: "audio/webm" });
    if (blob.size === 0) {
      setRecordError("The take was empty.");
      return;
    }
    let duration = Math.max(1, playheadRef.current - active.start);
    try {
      const context = new AudioContext();
      const buffer = await context.decodeAudioData(await blob.arrayBuffer());
      duration = buffer.duration;
      await context.close();
    } catch {
      /* fall back to the elapsed transport time */
    }
    const owner = tracksRef.current.find((track) => track.id === active.trackId);
    const take = (owner?.clipIds.length ?? 0) + 1;
    try {
      const upload = await uploadStudioAudio(
        new File([blob], `take-${Date.now()}.webm`, { type: "audio/webm" }),
        duration
      );
      insertClips([
        {
          trackId: active.trackId,
          clip: {
            id: `clip-take-${upload.id}`,
            title: `Take ${take}`,
            start: snapToGrid(active.start, secondsPerBar, beatsPerBar),
            duration,
            volume: 1,
            pan: 0,
            audioUrl: upload.url,
            uploadId: upload.id,
          } as ClipLike & { audioUrl?: string | null; uploadId?: string },
        },
      ]);
    } catch (cause) {
      setRecordError(cause instanceof Error ? cause.message : "Could not save the take.");
    }
  }

  function toggleRecord() {
    if (recording) stopRecording();
    else void startRecording();
  }
  function toggleSongPreview(song: WebMusicGeneration) {
    if (playingSongId === song.id) {
      previewRef.current?.pause();
      previewRef.current = null;
      setPlayingSongId(null);
      return;
    }
    const clip = song.clips?.find((candidate) => candidate.audio_url);
    if (!clip?.audio_url) return;
    previewRef.current?.pause();
    const audio = new Audio(clip.audio_url);
    previewRef.current = audio;
    setPlayingUploadId(null);
    setPlayingSongId(song.id);
    audio.onended = () => {
      setPlayingSongId((current) => (current === song.id ? null : current));
    };
    void audio.play().catch(() => {
      setPlayingSongId((current) => (current === song.id ? null : current));
    });
  }

  /** Audition an imported upload; shares the single preview element with songs. */
  function toggleUploadPreview(upload: StudioUpload) {
    if (playingUploadId === upload.id) {
      previewRef.current?.pause();
      previewRef.current = null;
      setPlayingUploadId(null);
      return;
    }
    if (!upload.url) return;
    previewRef.current?.pause();
    const audio = new Audio(upload.url);
    previewRef.current = audio;
    setPlayingSongId(null);
    setPlayingUploadId(upload.id);
    audio.onended = () => {
      setPlayingUploadId((current) => (current === upload.id ? null : current));
    };
    void audio.play().catch(() => {
      setPlayingUploadId((current) => (current === upload.id ? null : current));
    });
  }

  /** Audition a stem clip; shares the single preview element with songs/uploads. */
  function toggleStemPreview(stem: StudioStem) {
    if (playingStemId === stem.clip_id) {
      previewRef.current?.pause();
      previewRef.current = null;
      setPlayingStemId(null);
      return;
    }
    if (!stem.audio_url) return;
    previewRef.current?.pause();
    const audio = new Audio(stem.audio_url);
    previewRef.current = audio;
    setPlayingSongId(null);
    setPlayingUploadId(null);
    setPlayingStemId(stem.clip_id);
    audio.onended = () => {
      setPlayingStemId((current) => (current === stem.clip_id ? null : current));
    };
    void audio.play().catch(() => {
      setPlayingStemId((current) => (current === stem.clip_id ? null : current));
    });
  }

  /** Place a stem clip on the timeline at the playhead. */
  function addStemToTimeline(stem: StudioStem) {
    const trackId = selectedTrack ?? tracks[0]?.id;
    if (!trackId || !stem.audio_url) return;
    const label = stem.stem_type || stem.title.replace(/^.*?\(([^)]+)\)$/, "$1") || "Stem";
    insertClips([
      {
        trackId,
        clip: {
          id: `stem-${stem.clip_id}-${Date.now().toString(36)}`,
          title: label,
          start: snapToGrid(playhead, secondsPerBar, beatsPerBar),
          duration: stem.duration_seconds ?? 8,
          volume: 1,
          pan: 0,
          audioUrl: stem.audio_url,
        },
      },
    ]);
    setExportToast(`${label} added to the track at the playhead.`);
  }

  /** More menu (D-027): download the primary clip as WAV. */
  async function downloadSongWav(song: WebMusicGeneration) {
    const clip = song.clips?.find((candidate) => candidate.audio_url) ?? song.clips?.[0];
    if (!clip?.variant) {
      setExportToast("No WAV is available for this song yet.");
      return;
    }
    try {
      const filename = `${(song.title || "song").replace(/[^a-zA-Z0-9._-]+/g, "_")}.wav`;
      await downloadWebMusicClipWav(song.id, clip.variant, filename);
    } catch (cause) {
      setExportToast(cause instanceof Error ? cause.message : "Could not download the WAV.");
    }
  }

  /** More menu (D-027): move the primary clip to the trash and leave the rail. */
  async function trashSong(song: WebMusicGeneration) {
    const clip = song.clips?.find((candidate) => candidate.audio_url) ?? song.clips?.[0];
    if (!clip?.variant) return;
    try {
      await setWebMusicTrash([`${song.id}:${clip.variant}`], true);
      setLibrarySongs((previous) => (previous ?? []).filter((item) => item.id !== song.id));
      setDetailSong(null);
      setExportToast("Song moved to trash.");
    } catch {
      setExportToast("Could not move the song to trash.");
    }
  }

  /** Like/unlike the row's primary clip, updating the Liked filter optimistically. */
  async function toggleSongLike(song: WebMusicGeneration, nextLiked: boolean) {
    const clip = song.clips?.find((candidate) => candidate.audio_url) ?? song.clips?.[0];
    if (!clip) return;
    const key = `${song.id}:${clip.variant}`;
    const apply = (liked: boolean) =>
      setLikedKeys((previous) => {
        const list = new Set(previous ?? []);
        if (liked) list.add(key);
        else list.delete(key);
        return [...list];
      });
    apply(nextLiked);
    // Liking clears an existing dislike; the two are mutually exclusive.
    if (nextLiked && (dislikedKeys ?? []).includes(key)) {
      setDislikedKeys((previous) => (previous ?? []).filter((item) => item !== key));
      void dislikeWebMusicGeneration(song.id, clip.variant, false).catch(() => {});
    }
    try {
      await likeWebMusicGeneration(song.id, clip.variant, nextLiked);
    } catch {
      apply(!nextLiked);
    }
  }

  /** Dislike the row's primary clip; mirrors the Like path. */
  async function toggleSongDislike(song: WebMusicGeneration, nextDisliked: boolean) {
    const clip = song.clips?.find((candidate) => candidate.audio_url) ?? song.clips?.[0];
    if (!clip) return;
    const key = `${song.id}:${clip.variant}`;
    const apply = (disliked: boolean) =>
      setDislikedKeys((previous) => {
        const list = new Set(previous ?? []);
        if (disliked) list.add(key);
        else list.delete(key);
        return [...list];
      });
    apply(nextDisliked);
    // Disliking clears an existing like; the two are mutually exclusive.
    if (nextDisliked && (likedKeys ?? []).includes(key)) {
      setLikedKeys((previous) => (previous ?? []).filter((item) => item !== key));
      void likeWebMusicGeneration(song.id, clip.variant, false).catch(() => {});
    }
    try {
      await dislikeWebMusicGeneration(song.id, clip.variant, nextDisliked);
    } catch {
      apply(!nextDisliked);
    }
  }

  /** Retry every library request after a failure, instead of showing empty lists. */
  function retryLibrary() {
    setLibraryError(null);
    setLibrarySongs(null);
    setLibraryWorkspaces(null);
    setLibraryProjects(null);
    setLibraryUploads(null);
    setLibraryStems(null);
    setLikedKeys(null);
    setDislikedKeys(null);
  }

  /** "New workspace" on level 1 creates a default-named one, like the reference. */  async function createLibraryWorkspace() {
    const workspace = await createWebMusicWorkspace("New workspace");
    setLibraryWorkspaces((previous) => [workspace, ...(previous ?? [])]);
  }

  /** Toolbar upload (§19.2): import the file, then show it in the Uploads list. */  async function uploadLibraryAudio(file: File) {
    let duration: number | null = null;
    try {
      const context = new AudioContext();
      const buffer = await context.decodeAudioData(await file.arrayBuffer());
      duration = buffer.duration;
      await context.close();
    } catch {
      duration = null;
    }
    const typedFile =
      file.type && file.type.startsWith("audio/")
        ? file
        : new File([file], file.name, { type: "audio/mpeg" });
    const upload = await uploadStudioAudio(typedFile, duration);
    setLibraryUploads((previous) => [upload, ...(previous ?? [])]);
    setLibraryView({ kind: "uploads" });
  }

  /** Add-track ▸ Upload (§8.3) lands on the library's Uploads list. */
  function openUploadLibrary() {
    setLibraryView({ kind: "uploads" });
    setLibraryOpen(true);
  }

  /** A workspace row opens its songs (level 2); null clears the filter. */
  function openLibraryWorkspace(workspaceId: string | null) {
    setLibraryWorkspaceId(workspaceId);
    setLibrarySongs(null);
    const workspace = (libraryWorkspaces ?? []).find((item) => item.id === workspaceId);
    setLibraryView({
      kind: "songs",
      title: workspace?.name || "All Songs",
      filter: "all",
    });
  }

  /** Opening the library always starts at level 1 — the tile chooser. */
  function toggleLibrary(force?: boolean) {
    const next = force ?? !libraryOpen;
    if (next) setLibraryView({ kind: "root" });
    setLibraryOpen(next);
  }

  /** Resolve the selected clip's source song for the provenance strip (G16). */
  useEffect(() => {
    const clip = clips.find((candidate) => candidate.id === selectedClip);
    const songId = (clip as { songId?: string } | undefined)?.songId;
    if (!songId) {
      setClipSource(null);
      return;
    }
    const cached = librarySongs?.find((song) => song.id === songId);
    if (cached) {
      setClipSource(cached);
      return;
    }
    let active = true;
    fetchGenerations(50)
      .then((items) => {
        if (active) setClipSource(items.find((song) => song.id === songId) ?? null);
      })
      .catch(() => {
        if (active) setClipSource(null);
      });
    return () => {
      active = false;
    };
  }, [selectedClip, clips, librarySongs]);
  function addSongToTimeline(song: WebMusicGeneration) {
    const clip = song.clips?.find((candidate) => candidate.audio_url);
    const trackId = selectedTrack ?? tracks[0]?.id;
    if (!clip || !trackId) return;
    insertClips([
      {
        trackId,
        clip: {
          id: `clip-${song.id}-${Date.now().toString(36)}`,
          title: clip.title || song.title || "Song",
          start: snapToGrid(playhead, secondsPerBar, beatsPerBar),
          duration: clip.duration_seconds ?? 8,
          volume: 1,
          pan: 0,
          audioUrl: clip.audio_url,
          songId: song.id,
        } as ClipLike & { audioUrl?: string | null; songId?: string },
      },
    ]);
  }

  /** Drop an imported upload onto the selected (or first) track at the playhead. */
  function addUploadToTimeline(upload: StudioUpload) {
    const trackId = selectedTrack ?? tracks[0]?.id;
    if (!trackId || !upload.url) return;
    const title = upload.filename.replace(/\.[^.]+$/, "") || "Audio";
    insertClips([
      {
        trackId,
        clip: {
          id: `clip-upload-${upload.id}-${Date.now().toString(36)}`,
          title,
          start: snapToGrid(playhead, secondsPerBar, beatsPerBar),
          duration: upload.duration_seconds ?? 8,
          volume: 1,
          pan: 0,
          audioUrl: upload.url,
          uploadId: upload.id,
        } as ClipLike & { audioUrl?: string | null; uploadId?: string },
      },
    ]);
  }

  /** Drop a library song on a lane: insert where the pointer landed, snapped. */
  function dropSongOnLane(event: ReactDragEvent<HTMLDivElement>, trackId: string) {
    const songId = event.dataTransfer.getData(SONG_DRAG_TYPE);
    if (!songId) return;
    event.preventDefault();
    const song = (librarySongs ?? []).find((item) => item.id === songId);
    const clip = song?.clips?.find((candidate) => candidate.audio_url);
    if (!song || !clip) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const seconds = Math.max(0, ((event.clientX - rect.left) / barWidth) * secondsPerBar);
    insertClips([
      {
        trackId,
        clip: {
          id: `clip-${song.id}-${Date.now().toString(36)}`,
          title: clip.title || song.title || "Song",
          start: snapToGrid(seconds, secondsPerBar, beatsPerBar),
          duration: clip.duration_seconds ?? 8,
          volume: 1,
          pan: 0,
          audioUrl: clip.audio_url,
          songId: song.id,
        } as ClipLike & { audioUrl?: string | null; songId?: string },
      },
    ]);
  }

  /** Apply a recovered draft locally and try to write it (W2.3). */
  function restoreDraft() {
    if (!projectId || !draft) return;
    const data = (draft.data || {}) as StudioProject["data"];
    setProjectData(data);
    setLocalTracks(null);
    setDraft(null);
    persist(
      (expected) => updateStudioProject(projectId, { data, expectedUpdatedAt: expected }),
      "Could not restore the draft."
    );
  }

  function discardDraft() {
    if (projectId) clearDraft(projectId);
    setDraft(null);
  }

  /**
   * Single write path for project data, with history (undo/redo).
   *
   * Every data-changing action funnels through here so history is one stack rather
   * than a per-feature afterthought: push the outgoing document, apply the new one
   * optimistically, then persist through the W2.1/W2.2 path.
   */
  /** Update the document in state *and* in the ref event handlers read. */
  function setProjectData(next: StudioProject["data"]) {
    setProject((prev) => (prev ? { ...prev, data: next } : prev));
    if (projectRef.current) {
      projectRef.current = { ...projectRef.current, data: next };
    }
  }

  function writeProjectData(
    next: Record<string, unknown>,
    label: string,
    nextTracks?: StudioTrack[] | null
  ) {
    const current = (projectRef.current?.data || {}) as Record<string, unknown>;
    const history = historyRef.current;
    history.undo.push({ data: current, label });
    if (history.undo.length > HISTORY_LIMIT) history.undo.shift();
    history.redo = [];
    syncHistory();
    setProjectData(next);
    if (nextTracks !== undefined) setLocalTracks(nextTracks);
    if (!projectId) return;
    persist(
      (expected) => updateStudioProject(projectId, { data: next, expectedUpdatedAt: expected }),
      `Could not save ${label}.`
    );
  }

  function applyHistoryEntry(entry: { data: unknown; label: string }, to: "undo" | "redo") {
    if (!projectId) return;
    const current = currentData() as Record<string, unknown>;
    const history = historyRef.current;
    const opposite = to === "undo" ? history.redo : history.undo;
    opposite.push({ data: current, label: entry.label });
    const data = entry.data as Record<string, unknown>;
    setProjectData(data);
    setLocalTracks(null);
    syncHistory();
    persist(
      (expected) => updateStudioProject(projectId, { data, expectedUpdatedAt: expected }),
      `Could not ${to} ${entry.label}.`
    );
  }

  function undo() {
    const entry = historyRef.current.undo.pop();
    if (entry) applyHistoryEntry(entry, "undo");
  }

  function redo() {
    const entry = historyRef.current.redo.pop();
    if (entry) applyHistoryEntry(entry, "redo");
  }

  /**
   * Every write goes through here so the header can tell the truth about saving
   * (roadmap W2.1) and so a version mismatch can be resolved (W2.2).
   *
   * Writes are serialized. Two edits in quick succession used to send the same
   * `expected_updated_at` twice, so the second was rejected as a conflict the user never
   * caused — trivially reproducible on a slow connection. A write that arrives while
   * another is in flight is coalesced: only the newest runs, with the version the first
   * response produced.
   */
  function persist(
    run: (expectedUpdatedAt: string | null) => Promise<StudioProject>,
    failure: string
  ) {
    retryRef.current = () => persist(run, failure);
    forceRetryRef.current = () => persist(() => run(null), failure);
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      setSaveStatus("offline");
      unsavedDataRef.current = (projectRef.current?.data || {}) as Record<string, unknown>;
      if (projectId) saveDraft(projectId, projectRef.current?.data ?? null);
      return;
    }
    if (writeInFlightRef.current) {
      queuedWriteRef.current = { run, failure };
      setSaveStatus("saving");
      return;
    }
    void performWrite(run, failure);
  }

  async function performWrite(
    run: (expectedUpdatedAt: string | null) => Promise<StudioProject>,
    failure: string
  ) {
    writeInFlightRef.current = true;
    // Read the version at send time, not at schedule time: a coalesced write must build
    // on the version the previous response just produced.
    const expected = projectVersionRef.current;
    setSaveStatus("saving");
    try {
      const saved = await run(expected);
      // The response carries the new version; adopt it so the next write is based
      // on what the server actually stored.
      projectVersionRef.current = saved.updated_at ?? projectVersionRef.current;
      setProject((current) =>
        current ? { ...current, updated_at: saved.updated_at ?? current.updated_at } : current
      );
      setSaveStatus("saved");
      setError("");
      writeInFlightRef.current = false;
      const queued = queuedWriteRef.current;
      queuedWriteRef.current = null;
      if (queued) {
        void performWrite(queued.run, queued.failure);
        return;
      }
      if (projectId) {
        clearDraft(projectId);
        unsavedDataRef.current = null;
        // Versions are automatic (§25): the server throttles and bounds them, so this
        // never blocks the save and a failure here must not surface as a save failure.
        void autoSnapshotStudioProject(projectId).catch(() => undefined);
      }
    } catch (cause) {
      writeInFlightRef.current = false;
      // A failure invalidates whatever was queued: it was built on state the server
      // has not accepted, so replaying it would only produce another error.
      queuedWriteRef.current = null;
      if (cause instanceof StudioConflictError) {
        setConflict(cause.message);
        setSaveStatus("error");
        return;
      }
      // Keep the edit burst so a reload does not lose it (W2.3) and so a reconnect can
      // replay it (the online handler below).
      unsavedDataRef.current = (projectRef.current?.data || {}) as Record<string, unknown>;
      if (projectId) saveDraft(projectId, projectRef.current?.data ?? null);
      setSaveStatus(navigator.onLine === false ? "offline" : "error");
      setError(failure);
    }
  }

  /** Reload the server's version, discarding the local one (W2.2). */
  async function resolveConflictByReload() {
    if (!projectId) return;
    try {
      const fresh = await getStudioProject(projectId);
      setProject(fresh);
      setLocalTracks(null);
      setConflict(null);
      setSaveStatus("saved");
      setError("");
    } catch {
      setError("Could not reload the project.");
    }
  }

  /** Keep the local edits and write them over the newer version (W2.2). */
  function resolveConflictByOverwrite() {
    setConflict(null);
    forceRetryRef.current?.();
  }

  useEffect(() => {
    const goOnline = () => {
      // Do not claim "Saved" for a change the server never received: replay it first.
      if (unsavedDataRef.current && projectId) {
        const data = unsavedDataRef.current;
        persist(
          (expected) => updateStudioProject(projectId, { data, expectedUpdatedAt: expected }),
          "Could not save your offline changes."
        );
        return;
      }
      setSaveStatus((current) => (current === "offline" ? "saved" : current));
    };
    const goOffline = () => setSaveStatus("offline");
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      setSaveStatus("offline");
    }
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  /**
   * Unsaved-changes guard (roadmap W2.4): leaving with a write in flight, a failed
   * write, or an offline queue would silently lose the change. The reference has no
   * such guard; this is a deliberate divergence like W2.1.
   */
  useEffect(() => {
    if (saveStatus === "saved") return;
    const guard = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [saveStatus]);

  /** Seed the loop range from the project document (spec §68 persists it). */
  useEffect(() => {
    const data = currentData() as { loopStart?: unknown; loopEnd?: unknown };
    if (typeof data.loopStart === "number") setLoopStart(data.loopStart);
    if (typeof data.loopEnd === "number") setLoopEnd(data.loopEnd);
  }, [project?.id, project?.data]);

  /** Persist the loop range — the same document field the reference uses. */
  function commitLoopRange(start: number, end: number) {
    const data = currentData() as Record<string, unknown>;
    writeProjectData({ ...data, loopStart: start, loopEnd: end }, "the loop range");
  }

  /** Apply the master level to the running graph (F-01/F-02). */
  function applyMasterGain(volume: number, muted: boolean) {
    const gain = masterGainRef.current;
    if (gain) gain.gain.value = muted ? 0 : Math.max(0, Math.min(100, volume)) / 100;
  }

  /** Persist master volume / mute into the document (undoable, like the loop range). */
  function commitMaster(volume = masterVolume, muted = masterMuted) {
    const data = currentData() as Record<string, unknown>;
    writeProjectData(
      { ...data, masterVolume: volume, masterMuted: muted },
      "the master level"
    );
  }

  /** Arming the loop with no range selects the first four bars. */
  function toggleLoop() {
    if (!loop && (!loopEnd || loopEnd <= loopStart)) {
      const end = Math.min(duration, loopStart + secondsPerBar * 4);
      setLoopEnd(end);
      commitLoopRange(loopStart, end);
    }
    setLoop((value) => !value);
  }

  /** Drag the loop's right handle on the ruler (spec §68). */
  useEffect(() => {
    const move = (event: PointerEvent) => {
      if (!loopDragRef.current) return;
      const lanes = document.querySelector(".se-lanes-inner");
      if (!lanes) return;
      const rect = lanes.getBoundingClientRect();
      const seconds = ((event.clientX - rect.left) / barWidth) * secondsPerBar;
      setLoopEnd(Math.max(loopStart + secondsPerBar / beatsPerBar, snapToGrid(seconds, secondsPerBar, beatsPerBar)));
    };
    const up = () => {
      if (!loopDragRef.current) return;
      loopDragRef.current = false;
      setLoopEnd((end) => {
        commitLoopRange(loopStart, end);
        return end;
      });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  });
  /** Convert a pointer position into a project time, using the lane grid. */
  function timeAtClientX(clientX: number): number | null {
    const lanes = document.querySelector(".se-lanes-inner");
    if (!lanes) return null;
    const rect = lanes.getBoundingClientRect();
    return Math.max(0, ((clientX - rect.left) / barWidth) * secondsPerBar);
  }

  /** Snap a time to the project grid and keep it inside the arrangement. */
  function snapProjectTime(seconds: number): number {
    return Math.max(0, Math.min(duration, snapToGrid(seconds, secondsPerBar, beatsPerBar)));
  }

  /**
   * Press on the bar ruler: a click seeks, a drag selects a time range (N-01, spec §2).
   * Shift-click extends the existing range instead of starting a new one.
   */
  function handleRulerPointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    const at = timeAtClientX(event.clientX);
    if (at === null) return;
    const snapped = snapProjectTime(at);
    setSelectedIds([]);
    setSelectedClip(null);
    if (event.shiftKey) {
      const step = secondsPerBar / beatsPerBar;
      setTimeSelection((current) => {
        if (!current) return normaliseRange(snapped, snapped + step);
        // The far edge stays put; the clicked end moves to the pointer.
        const anchor = snapped < current.start ? current.end : current.start;
        return normaliseRange(anchor, snapped) ?? current;
      });
      rangeDragRef.current = null;
      return;
    }
    rangeDragRef.current = { anchor: snapped, startX: event.clientX, moved: false, edge: null };
    seekTo(snapped);
  }

  /** Grab an edge of the time selection to resize it. */
  function handleRangeHandleDown(
    event: React.PointerEvent<HTMLButtonElement>,
    edge: "start" | "end"
  ) {
    event.stopPropagation();
    event.preventDefault();
    if (!timeSelection) return;
    setSelectedIds([]);
    setSelectedClip(null);
    rangeDragRef.current = {
      anchor: edge === "start" ? timeSelection.end : timeSelection.start,
      startX: event.clientX,
      moved: false,
      edge,
    };
  }

  /** Right-click on the ruler opens the range verbs when a selection exists. */
  function handleRulerContextMenu(event: React.MouseEvent<HTMLDivElement>) {
    if (!timeSelection) return;
    event.preventDefault();
    setRangeMenu({ x: event.clientX, y: event.clientY });
  }

  /** Follow a ruler / handle drag on the window, then commit it on release. */
  useEffect(() => {
    const move = (event: PointerEvent) => {
      const session = rangeDragRef.current;
      if (!session) return;
      if (!session.moved && !isDrag(event.clientX - session.startX)) return;
      session.moved = true;
      const at = timeAtClientX(event.clientX);
      if (at === null) return;
      setTimeSelection(normaliseRange(session.anchor, snapProjectTime(at)));
    };
    const up = () => {
      rangeDragRef.current = null;
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
    };
  });

  /** Shift+arrow grows the selection one grid step at a time (spec §36). */
  function extendTimeSelection(direction: "left" | "right") {
    const step = secondsPerBar / beatsPerBar;
    setSelectedIds([]);
    setSelectedClip(null);
    setTimeSelection((current) => {
      if (!current) {
        const at = snapProjectTime(playheadRef.current);
        return direction === "right"
          ? normaliseRange(at, Math.min(duration, at + step))
          : normaliseRange(Math.max(0, at - step), at);
      }
      const next =
        direction === "right"
          ? { start: current.start, end: Math.min(duration, current.end + step) }
          : { start: Math.max(0, current.start - step), end: current.end };
      return normaliseRange(next.start, next.end);
    });
  }

  function clearTimeSelection() {
    setTimeSelection(null);
    setRangeMenu(null);
  }

  /**
   * Delete the selected time and ripple the later clips left (N-01).
   * `scope: "track"` is the reference's "Delete Time on Selected Tracks".
   */
  function deleteSelectedTime(scope: "all" | "track") {
    const range = timeSelection;
    if (!range || !projectId) return;
    const trackIds = scope === "track" ? (selectedTrack ? [selectedTrack] : []) : undefined;
    if (trackIds && trackIds.length === 0) return;
    const data = currentData();
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    const next = deleteTimeRange({ lanes, tracks }, range, trackIds);
    writeProjectData(
      { ...data, lanes: next.lanes, tracks: next.tracks },
      "deleting time",
      next.tracks
    );
    setRangeMenu(null);
  }

  /** Copy the selected time after itself and push later clips right (N-01). */
  function duplicateSelectedTime() {
    const range = timeSelection;
    if (!range || !projectId) return;
    const data = currentData();
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    const next = duplicateTimeRange({ lanes, tracks }, range);
    writeProjectData(
      { ...data, lanes: next.lanes, tracks: next.tracks },
      "duplicating time",
      next.tracks
    );
    setRangeMenu(null);
  }

  /** Point the loop at the time selection (N-09: "Loop selection"). */
  function loopTimeSelection() {
    if (!timeSelection) return;
    setLoopStart(timeSelection.start);
    setLoopEnd(timeSelection.end);
    setLoop(true);
    commitLoopRange(timeSelection.start, timeSelection.end);
    setRangeMenu(null);
  }

  function zoomBy(direction: 1 | -1) {
    setBarWidth((current) => {
      const index = ZOOM_LEVELS.indexOf(current);
      const next = index === -1
        ? direction === 1
          ? ZOOM_LEVELS[ZOOM_LEVELS.length - 1]
          : ZOOM_LEVELS[0]
        : ZOOM_LEVELS[Math.min(ZOOM_LEVELS.length - 1, Math.max(0, index + direction))];
      return next;
    });
  }

  function zoomToFit() {
    // "Fit" must actually fit the content: derive pixels-per-bar from the viewport and
    // the end of the arrangement instead of resetting to a preset (which left long or
    // short projects unchanged and still scrolling).
    const viewport = timelineRef.current?.clientWidth ?? view.width;
    const contentEnd = clips.reduce(
      (max, clip) => Math.max(max, (clip.start ?? 0) + (clip.duration ?? 0)),
      0
    );
    if (!viewport || contentEnd <= 0) {
      setBarWidth(ZOOM_LEVELS[2]);
      return;
    }
    const bars = contentEnd / secondsPerBar;
    const next = Math.max(8, Math.min(192, (viewport * 0.95) / Math.max(1, bars)));
    setBarWidth(next);
    if (timelineRef.current) timelineRef.current.scrollLeft = 0;
  }

  /** `Z` zoom-to-selection (spec §36): the time range, else the selected clips. */
  function zoomToSelection() {
    const viewport = timelineRef.current?.clientWidth ?? view.width;
    let from = timeSelection?.start;
    let to = timeSelection?.end;
    if (from == null || to == null) {
      const selected = clips.filter((clip) => selectedIds.includes(clip.id));
      if (selected.length === 0) {
        zoomToFit();
        return;
      }
      from = Math.min(...selected.map((clip) => clip.start ?? 0));
      to = Math.max(...selected.map((clip) => (clip.start ?? 0) + (clip.duration ?? 0)));
    }
    const span = Math.max(0.5, to - from);
    const bars = span / secondsPerBar;
    const next = Math.max(8, Math.min(192, (viewport * 0.9) / Math.max(1, bars)));
    setBarWidth(next);
    requestAnimationFrame(() => {
      if (timelineRef.current) {
        timelineRef.current.scrollLeft = Math.max(
          0,
          (from / secondsPerBar) * next - 16
        );
      }
    });
  }

  /** Track menu actions (spec §65). All persist through the history-aware write path. */
  function updateTrack(trackId: string, patch: Partial<StudioTrack>) {
    commitTracks(tracks.map((track) => (track.id === trackId ? { ...track, ...patch } : track)));
  }

  /** Live slider movement: update state without a history entry; commit on release. */
  function previewTrack(trackId: string, patch: Partial<StudioTrack>) {
    setLocalTracks(tracks.map((track) => (track.id === trackId ? { ...track, ...patch } : track)));
  }

  /** Capture head control: expand or collapse every visible track at once. */
  function toggleAllCollapsed() {
    const visible = tracks.filter((track) => !track.hidden);
    const next = !(visible.length > 0 && visible.every((track) => track.collapsed));
    commitTracks(
      tracks.map((track) => (track.hidden ? track : { ...track, collapsed: next }))
    );
  }

  function duplicateTrack(trackId: string) {
    const source = tracks.find((track) => track.id === trackId);
    if (!source) return;
    const stamp = Date.now().toString(36);
    const copies = clips
      .filter((clip) => source.clipIds.includes(clip.id))
      .map((clip, index) => ({ ...clip, id: `${clip.id}-copy-${stamp}-${index}` }));
    const copy: StudioTrack = {
      ...source,
      id: `track-${stamp}`,
      name: `${source.name} copy`,
      index: tracks.length,
      clipIds: copies.map((clip) => clip.id),
    };
    const data = currentData() as Record<string, unknown>;
    const nextTracks = [...tracks, copy];
    setMenuTrackId(null);
    writeProjectData(
      { ...data, lanes: [...clips, ...copies], tracks: nextTracks },
      "duplicating a track",
      nextTracks
    );
  }

  /** Hide & Mute is one action in the reference, not two (§65). */
  function hideTrack(trackId: string) {
    setMenuTrackId(null);
    setLocalTracks(
      tracks.map((track) =>
        track.id === trackId ? { ...track, hidden: true, muted: true } : track
      )
    );
    commitTracks(
      tracks.map((track) =>
        track.id === trackId ? { ...track, hidden: true, muted: true } : track
      )
    );
  }

  function showAllHidden() {
    setHiddenOpen(false);
    commitTracks(tracks.map((track) => (track.hidden ? { ...track, hidden: false } : track)));
  }

  function deleteTrack(trackId: string) {
    const track = tracks.find((candidate) => candidate.id === trackId);
    if (!track) return;
    const nextTracks = tracks
      .filter((candidate) => candidate.id !== trackId)
      .map((candidate, index) => ({ ...candidate, index }));
    const lanes = clips.filter((clip) => !track.clipIds.includes(clip.id));
    const data = currentData() as Record<string, unknown>;
    setMenuTrackId(null);
    setSelectedTrack(null);
    writeProjectData({ ...data, lanes, tracks: nextTracks }, "deleting a track", nextTracks);
  }

  function startRename(track: StudioTrack) {
    setMenuTrackId(null);
    setRenameTrackId(track.id);
    setRenameValue(track.name);
  }

  function commitRename() {
    if (!renameTrackId) return;
    const name = renameValue.trim();
    if (name) updateTrack(renameTrackId, { name });
    setRenameTrackId(null);
  }

  /**
   * Stem separation (W4.2). The reference surfaces it as "Get Stems" on a clip and
   * lands the results on new tracks, so that is the shape implemented here: request,
   * poll the operation, then add one track per returned stem at the playhead.
   */
  function openStemsDialog() {
    const clip = clips.find((candidate) => candidate.id === selectedClip) as
      | { songId?: string }
      | undefined;
    if (!clip?.songId) return;
    setStemsMode("stems");
    setStemsPrompt({ songId: clip.songId });
  }

  async function requestStems(mode: "vocal" | "stems" | "advanced") {
    const clip = clips.find((candidate) => candidate.id === selectedClip);
    const songId = (clip as { songId?: string } | undefined)?.songId;
    if (!songId) return;
    setStemsPrompt(null);
    setStems({ status: "queued" });
    try {
      const operation = await requestStudioStems({
        taskId: songId,
        variant: "ok",
        mode,
        projectId,
      });
      setStems({ status: operation.status });

      const deadline = Date.now() + 120_000;
      let current = operation;
      while (Date.now() < deadline) {
        if (current.status === "done" && current.result?.clips?.length) break;
        if (current.status === "error" || current.status === "failed") {
          const copy = classifyStudioError(current.error_message, "Stem separation failed.");
          setStems({ status: "error", message: copy.text });
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 2500));
        current = await getStudioOperation(operation.id);
        setStems({ status: current.status });
      }

      const stemsClips = current.result?.clips ?? [];
      if (stemsClips.length === 0) {
        setStems({ status: "error", message: "No stems came back." });
        return;
      }

      const stamp = Date.now().toString(36);
      const data = currentData() as Record<string, unknown>;
      const base = Math.round(playhead * 1000) / 1000;
      const addedLanes = stemsClips.map((stem, index) => ({
        id: `stem-${stamp}-${index}`,
        title: stem.label ?? stem.title ?? `Stem ${index + 1}`,
        start: base,
        duration: stem.duration_seconds ?? stem.duration ?? 8,
        volume: 1,
        pan: 0,
        audioUrl: stem.durable_url ?? stem.durableUrl ?? stem.audio_url ?? null,
        songId,
      }));
      const addedTracks: StudioTrack[] = stemsClips.map((stem, index) => ({
        id: `stem-track-${stamp}-${index}`,
        name: stem.label ?? stem.title ?? `Stem ${index + 1}`,
        color: colorForTrackName(`stem ${index}`),
        index: tracks.length + index,
        volume: 1,
        pan: 0,
        muted: false,
        solo: false,
        hidden: false,
      collapsed: false,
        groupId: null,
        chain: [],
        clipIds: [addedLanes[index].id],
      }));
      writeProjectData(
        { ...data, lanes: [...clips, ...addedLanes], tracks: [...tracks, ...addedTracks] },
        "stem separation",
        [...tracks, ...addedTracks]
      );
      setStems({ status: "added" });
    } catch (cause) {
      const copy = classifyStudioError(
        cause instanceof Error ? cause.message : cause,
        "Could not start stem separation."
      );
      setStems({ status: "error", message: copy.text });
    }
  }

  /** Surface a paid-operation failure: credits get the purchase card, anything else the reason. */
  function reportTransformFailure(cause: unknown, fallback: string) {
    const copy = classifyStudioError(cause instanceof Error ? cause.message : cause, fallback);
    setTransformNotice({
      kind: copy.kind === "credits" ? "credits" : "failed",
      text: copy.text,
    });
    setExportToast(null);
  }

  /** Poll a Studio operation until it settles (or the deadline passes). */
  async function pollOperation(    operation: StudioOperation,
    timeoutMs = 120_000
  ): Promise<StudioOperation> {
    const deadline = Date.now() + timeoutMs;
    let current = operation;
    while (Date.now() < deadline) {
      if (current.status === "done" || current.status === "error" || current.status === "failed") {
        return current;
      }
      await new Promise((resolve) => setTimeout(resolve, 2500));
      current = await getStudioOperation(operation.id);
    }
    return current;
  }

  /**
   * Clip transforms (D-033): Extend continues the clip after itself, while Cover,
   * Remaster, Add vocals and Add instrumental land as new takes on the source clip.
   * These are paid Studio operations, so the result is placed only after the operation
   * finishes.
   */
  async function runTransform(
    kind: "extend" | "cover" | "remaster" | "vocals" | "instrumental",
    clipId: string,
    prompt = ""
  ) {
    if (transformBusy) return;
    const clip = clipsRef.current.find((entry) => entry.id === clipId);
    const songId = (clip as { songId?: string } | undefined)?.songId;
    if (!clip || !songId) return;
    const label =
      kind === "extend"
        ? "Extend"
        : kind === "cover"
          ? "Cover"
          : kind === "remaster"
            ? "Remaster"
            : kind === "vocals"
              ? "Add vocals"
              : "Add instrumental";
    setClipMenu(null);
    setTransformBusy(kind);
    setExportToast(`${label} queued…`);
    try {
      const operation =
        kind === "extend"
          ? await requestStudioExtend({
              taskId: songId,
              variant: "ok",
              continueAt: extendedClipStart(clip),
              projectId,
            })
          : kind === "cover"
            ? await requestStudioCover({
                taskId: songId,
                variant: "ok",
                prompt,
                projectId,
              })
            : kind === "remaster"
              ? await requestStudioRemaster({ taskId: songId, variant: "ok", projectId })
              : kind === "vocals"
                ? await requestStudioAddVocals({
                    taskId: songId,
                    variant: "ok",
                    prompt,
                    projectId,
                  })
                : await requestStudioAddInstrumental({
                    taskId: songId,
                    variant: "ok",
                    prompt,
                    projectId,
                  });
      const current = await pollOperation(operation);
      if (current.status !== "done") {
        throw new Error(current.error_message ?? `${label} failed.`);
      }
      const result = current.result?.clips?.[0];
      if (!result) throw new Error("No audio came back.");
      const stamp = Date.now().toString(36);
      const data = currentData() as Record<string, unknown>;

      if (kind === "extend") {
        const lane: ClipLike = {
          id: `ext-${stamp}`,
          title: `${clip.title ?? "Clip"} (extended)`,
          start: extendedClipStart(clip),
          duration: resultDuration(result, clip.duration ?? 8),
          volume: 1,
          pan: 0,
          audioUrl: resultAudioUrl(result),
          songId,
        };
        const nextTracks = tracks.map((track) =>
          track.clipIds.includes(clip.id)
            ? { ...track, clipIds: [...track.clipIds, lane.id] }
            : track
        );
        writeProjectData(
          { ...data, lanes: [...clipsRef.current, lane], tracks: nextTracks },
          "the extension",
          nextTracks
        );
        setSelectedClip(lane.id);
        setExportToast("Extension added after the clip.");
      } else {
        const lanes = clipsRef.current.map((entry) =>
          entry.id === clip.id ? withTransformTake(entry, label, result, stamp) : entry
        );
        writeProjectData({ ...data, lanes }, `${label.toLowerCase()} result`);
        setSelectedClip(clip.id);
        setTakeLanesOpen(true);
        setExportToast(`${label} added as a new take.`);
      }
    } catch (cause) {
      reportTransformFailure(cause, `${label} failed.`);
    } finally {
      setTransformBusy(null);
    }
  }

  /**
   * Mashup (D-033): two selected clips with a source generation become one new song on
   * its own track, starting where the earliest source clip starts.
   */
  async function runMashup(clipIds: string[], prompt = "") {
    if (transformBusy) return;
    const sources = clipIds
      .map((id) => clipsRef.current.find((entry) => entry.id === id))
      .filter((entry): entry is ClipLike => Boolean(entry?.songId));
    if (sources.length !== 2) return;
    setClipMenu(null);
    setTransformBusy("mashup");
    setExportToast("Mashup queued…");
    try {
      const operation = await requestStudioMashup({
        clips: sources.map((entry) => ({ taskId: entry.songId as string, variant: "ok" })),
        prompt,
        projectId,
      });
      const current = await pollOperation(operation);
      if (current.status !== "done") {
        throw new Error(current.error_message ?? "Mashup failed.");
      }
      const result = current.result?.clips?.[0];
      if (!result) throw new Error("No audio came back.");
      const stamp = Date.now().toString(36);
      const data = currentData() as Record<string, unknown>;
      const start = Math.min(...sources.map((entry) => entry.start ?? 0));
      const lane: ClipLike = {
        id: `mash-${stamp}`,
        title: "Mashup",
        start,
        duration: resultDuration(result, sources[0].duration ?? 8),
        volume: 1,
        pan: 0,
        audioUrl: resultAudioUrl(result),
      };
      const track: StudioTrack = {
        id: `mash-track-${stamp}`,
        name: "Mashup",
        color: colorForTrackName("mashup"),
        index: tracks.length,
        volume: 80,
        pan: 0,
        muted: false,
        solo: false,
        hidden: false,
        collapsed: false,
        groupId: null,
        chain: [],
        clipIds: [lane.id],
      };
      const nextTracks = [...tracks, track];
      writeProjectData(
        { ...data, lanes: [...clipsRef.current, lane], tracks: nextTracks },
        "the mashup",
        nextTracks
      );
      setSelectedTrack(track.id);
      setSelectedClip(lane.id);
      setExportToast("Mashup added as a new track.");
    } catch (cause) {
      reportTransformFailure(cause, "Mashup failed.");
    } finally {
      setTransformBusy(null);
    }
  }

  async function refreshPersonas() {
    setPersonaBusy(true);
    setPersonaError("");
    try {
      const next = await listStudioPersonas();
      setPersonas(next);
      setSelectedPersonaId((current) => {
        const stillComplete =
          current &&
          next.some(
            (persona) => persona.provider_persona_id === current && persona.status === "complete"
          );
        if (stillComplete) return current;
        return (
          next.find(
            (persona) => persona.status === "complete" && persona.provider_persona_id
          )?.provider_persona_id ?? ""
        );
      });
    } catch (cause) {
      setPersonaError(cause instanceof Error ? cause.message : "Could not load personas.");
    } finally {
      setPersonaBusy(false);
    }
  }

  async function createPersonaForClip(clipId: string) {
    if (personaBusy) return;
    const clip = clipsRef.current.find((entry) => entry.id === clipId) as
      | {
          id: string;
          title?: string;
          songId?: string;
          style?: string;
          variant?: string;
          offset?: number;
          duration?: number;
        }
      | undefined;
    if (!clip?.songId) {
      setPersonaError("This clip has no source generation to build a persona from.");
      return;
    }
    const name = personaName.trim() || `${clip.title ?? "Clip"} persona`;
    setPersonaBusy(true);
    setPersonaError("");
    try {
      const created = await createStudioPersona({
        taskId: clip.songId,
        name,
        styles: clip.style,
        description: `Created from ${clip.title ?? "clip"}`,
        vocalStartS: clip.offset ?? 0,
        vocalEndS: (clip.offset ?? 0) + (clip.duration ?? 0),
        variant: clip.variant ?? "ok",
      });
      setPersonas((current) => [created, ...current]);
      setPersonaName("");
      setExportToast("Persona submitted; it will appear when ready.");
      window.setTimeout(() => void refreshPersonas(), 8000);
      window.setTimeout(() => void refreshPersonas(), 20000);
    } catch (cause) {
      setPersonaError(cause instanceof Error ? cause.message : "Could not create persona.");
    } finally {
      setPersonaBusy(false);
    }
  }

  /**
   * Replace Section (GEN-018): the N-01 time range is rewritten with new lyrics. The
   * provider returns the whole arrangement with that span re-sung, so it lands as a take
   * on the source clip like the other variant transforms.
   */
  async function runReplaceSection(clipId: string, lyrics: string) {
    if (transformBusy) return;
    const clip = clipsRef.current.find((entry) => entry.id === clipId);
    const songId = (clip as { songId?: string } | undefined)?.songId;
    const range = timeSelection;
    if (!clip || !songId || !range) return;
    if (!lyrics.trim()) {
      setTransformNotice({ kind: "failed", text: "Replace section needs lyrics." });
      return;
    }
    const clipStart = clip.start ?? 0;
    const clipEnd = clipStart + (clip.duration ?? 0);
    const from = Math.max(range.start, clipStart);
    const to = Math.min(range.end, clipEnd);
    if (to - from < 0.05) {
      setTransformNotice({
        kind: "failed",
        text: "Select a time range inside the clip first.",
      });
      return;
    }
    const offset = (clip as { offset?: number }).offset ?? 0;
    setClipMenu(null);
    setTransformBusy("replace");
    setExportToast("Replace section queued…");
    try {
      const operation = await requestStudioReplaceSection({
        taskId: songId,
        variant: "ok",
        startS: Math.max(0, offset + (from - clipStart)),
        endS: Math.max(0, offset + (to - clipStart)),
        lyrics,
        personaId: selectedPersonaId || null,
        projectId,
      });
      const current = await pollOperation(operation);
      if (current.status !== "done") {
        throw new Error(current.error_message ?? "Replace section failed.");
      }
      const result = current.result?.clips?.[0];
      if (!result) throw new Error("No audio came back.");
      const stamp = Date.now().toString(36);
      const data = currentData() as Record<string, unknown>;
      const lanes = clipsRef.current.map((entry) =>
        entry.id === clip.id ? withTransformTake(entry, "Replace section", result, stamp) : entry
      );
      writeProjectData({ ...data, lanes }, "the replaced section");
      setSelectedClip(clip.id);
      setTakeLanesOpen(true);
      setExportToast("Replaced section added as a new take.");
    } catch (cause) {
      reportTransformFailure(cause, "Replace section failed.");
    } finally {
      setTransformBusy(null);
    }
  }

  /** Toggle a boolean track flag and persist it (G21: mute, solo). */
  function toggleTrackFlag(trackId: string, flag: "muted" | "solo") {
    const next = tracks.map((track) =>
      track.id === trackId ? { ...track, [flag]: !track[flag] } : track
    );
    commitTracks(next);
  }

  /** Persist the track list into the project document. */
  function commitTracks(next: StudioTrack[]) {
    const base = currentData() as Record<string, unknown>;
    writeProjectData({ ...base, tracks: next }, "the track list", next);
  }

  function addTrack() {
    const next: StudioTrack = {
      id: `track-${Date.now().toString(36)}`,
      name: `Track ${tracks.length + 1}`,
      color: colorForTrackName(`Track ${tracks.length + 1}`),
      index: tracks.length,
      volume: 80,
      pan: 0,
      muted: false,
      solo: false,
      hidden: false,
      collapsed: false,
      groupId: null,
      chain: [],
      clipIds: [],
    };
    commitTracks([...tracks, next]);
    setSelectedTrack(next.id);
  }

  /** Create a MIDI track with a four-bar empty clip and open the editor (S31/S64). */
  function addMidiTrack() {
    const stamp = Date.now().toString(36);
    const trackId = `track-${stamp}`;
    const clipId = `clip-${stamp}`;
    const name = `MIDI ${tracks.length + 1}`;
    const color = colorForTrackName(name);
    const nextTrack: StudioTrack = {
      id: trackId,
      name,
      color,
      index: tracks.length,
      volume: 80,
      pan: 0,
      muted: false,
      solo: false,
      hidden: false,
      collapsed: false,
      groupId: null,
      chain: [],
      clipIds: [clipId],
    };
    const clip: ClipLike = {
      id: clipId,
      title: "MIDI clip",
      start: 0,
      duration: secondsPerBar * 4,
      color,
      midi: { notes: [] },
    };
    const data = currentData() as Record<string, unknown>;
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    writeProjectData(
      { ...data, lanes: [...lanes, clip], tracks: [...tracks, nextTrack] },
      "a MIDI track",
      [...tracks, nextTrack]
    );
    setSelectedTrack(trackId);
    setMidiClipId(clipId);
  }

/** Replace a MIDI automation lane (pitch bend or modulation). */
  function setMidiLanes(clipId: string, lane: "bend" | "mod", points: { at: number; value: number }[]) {
    const data = currentData() as Record<string, unknown>;
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    writeProjectData(
      {
        ...data,
        lanes: lanes.map((clip) =>
          clip.id === clipId
            ? { ...clip, midi: { ...(clip.midi ?? { notes: [] }), [lane]: points } }
            : clip
        ),
      },
      "MIDI automation"
    );
  }

  /** Replace a MIDI clip's notes through the same document writer as every edit. */
  function setMidiNotes(clipId: string, notes: MidiNote[]) {
    const data = currentData() as Record<string, unknown>;
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    writeProjectData(
      {
        ...data,
        lanes: lanes.map((clip) =>
          clip.id === clipId ? { ...clip, midi: { notes } } : clip
        ),
      },
      "MIDI notes"
    );
  }

  /** MIDI synth voice (S31): one instrument per clip, persisted with the document. */
  function setMidiInstrument(clipId: string, instrument: MidiInstrument) {
    const data = currentData() as Record<string, unknown>;
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    writeProjectData(
      {
        ...data,
        lanes: lanes.map((clip) => (clip.id === clipId ? { ...clip, instrument } : clip)),
      },
      "the MIDI instrument"
    );
  }

  const derivedChains = useMemo<Record<string, PluginChainEntry[]>>(() => {
    const data = (project?.data || {}) as { chains?: unknown };
    return (data.chains as Record<string, PluginChainEntry[]>) || {};
  }, [project]);

  /** Designed plugins saved in this project's library (S45). */
  const customPlugins = useMemo<CustomPlugin[]>(() => {
    const raw = (project?.data as { customPlugins?: unknown } | undefined)?.customPlugins;
    if (!Array.isArray(raw)) return [];
    return raw
      .map((entry) => sanitizeCustomPlugin(entry))
      .filter((entry): entry is CustomPlugin => entry !== null);
  }, [project]);

  const derivedMasterChain = useMemo<MasterChainEntry[]>(() => {
    const raw = (project?.data as { masterChain?: unknown } | undefined)?.masterChain;
    return Array.isArray(raw) ? (raw as MasterChainEntry[]) : [];
  }, [project]);
  const [localMasterChain, setLocalMasterChain] = useState<MasterChainEntry[] | null>(null);
  const masterChain = localMasterChain ?? derivedMasterChain;

  const [localChains, setLocalChains] = useState<Record<string, PluginChainEntry[]> | null>(null);
  const chains = localChains ?? derivedChains;
  const chainsRef = useRef(chains);
  chainsRef.current = chains;
  /** Chain nodes built for the current playback, keyed by track (live param updates). */
  const chainRuntimeRef = useRef<Map<string, { update: (entryId: string, params: Record<string, number>) => void }>>(
    new Map()
  );
  /** Per-track gain nodes for the current playback (live volume / mute / solo). */
  const trackGainRef = useRef<Map<string, GainNode>>(new Map());
  /** Master gain node for the current playback (live fader / main mute). */
  const masterGainRef = useRef<GainNode | null>(null);
  /** Structure of the chains the engine was built with (ids, plugins, bypass state). */
  const chainStructureRef = useRef<string>("");

  useEffect(() => {
    setLocalChains(null);
    setLocalMasterChain(null);
    setMasterSelected(false);
  }, [projectId]);

  useEffect(() => {
    if (midiClipId) setTakeLanesOpen(false);
  }, [midiClipId]);

  useEffect(() => {
    if (audioClipId) setTakeLanesOpen(false);
  }, [audioClipId]);

  /** Persist the master chain into the project document (S48). */
  function commitMasterChain(next: MasterChainEntry[]) {
    setLocalMasterChain(next);
    const base = currentData() as Record<string, unknown>;
    writeProjectData({ ...base, masterChain: next }, "the master chain");
  }

  /** Persist one track's plugin chain into the project document. */
  function commitChain(trackId: string, next: PluginChainEntry[]) {
    const merged = { ...chains, [trackId]: next };
    setLocalChains(merged);
    const base = currentData() as Record<string, unknown>;
    writeProjectData({ ...base, chains: merged }, "the plugin chain");
  }

  /** S46 "Save preset…": the current slot settings become a reusable project preset. */
  function savePluginPreset(
    pluginId: string,
    name: string,
    params: Record<string, number>,
    mode?: string
  ) {
    const data = currentData() as Record<string, unknown>;
    const existing = Array.isArray(data.pluginPresets)
      ? (data.pluginPresets as UserPreset[])
      : [];
    const preset = makeUserPreset(pluginId, name, params, mode);
    writeProjectData(
      { ...data, pluginPresets: [...existing, preset] },
      "a preset"
    );
    setExportToast(`Preset “${preset.name}” saved.`);
  }

  /** Persist new start positions for one or more clips (drag result). */
  function commitClipStarts(next: Record<string, number>) {
    if (!projectId) return;
    const data = currentData() as Record<string, unknown>;
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    const updated = lanes.map((clip) =>
      next[clip.id] !== undefined ? { ...clip, start: next[clip.id] } : clip
    );
    writeProjectData({ ...data, lanes: updated }, "the clip move");
  }

  function commitClipStart(clipId: string, start: number) {
    commitClipStarts({ [clipId]: start });
  }

  /** Copy buffer for CTRL C / V, holding the owning track so paste stays in place. */
  const clipboardRef = useRef<{ clip: ClipLike; trackId: string }[]>([]);
  /** Set when a delete should move DOM focus to the surviving clip (G9). */
  const focusPendingRef = useRef(false);
  /** Bumped by "Show Quick Start again"; the overlay re-opens on change. */
  const [quickStartToken, setQuickStartToken] = useState(0);

  /** Insert new clips into their owner tracks and persist lanes + tracks together. */
  function insertClips(entries: { clip: ClipLike; trackId: string }[]) {
    if (!projectId || entries.length === 0) return;
    const data = currentData() as Record<string, unknown>;
    const lanes = [...clips, ...entries.map((entry) => entry.clip)];
    const additions = new Map<string, string[]>();
    entries.forEach((entry) => {
      additions.set(entry.trackId, [...(additions.get(entry.trackId) || []), entry.clip.id]);
    });
    const nextTracks = tracks.map((track) =>
      additions.has(track.id)
        ? { ...track, clipIds: [...track.clipIds, ...(additions.get(track.id) || [])] }
        : track
    );
    setSelectedIds(entries.map((entry) => entry.clip.id));
    writeProjectData({ ...data, lanes, tracks: nextTracks }, "adding clips", nextTracks);
  }

  /** The clips the user is acting on: an explicit selection, else the focused clip. */
  function activeClipIds(): string[] {
    if (selectedIds.length > 0) return selectedIds;
    return selectedClip ? [selectedClip] : [];
  }

  function ownerOf(clipId: string): string | null {
    const track = tracks.find((candidate) => candidate.clipIds.includes(clipId));
    return track ? track.id : null;
  }

  function copySelection() {
    const ids = activeClipIds();
    clipboardRef.current = ids
      .map((id) => {
        const clip = clips.find((candidate) => candidate.id === id);
        const trackId = ownerOf(id);
        return clip && trackId ? { clip: { ...clip }, trackId } : null;
      })
      .filter((entry): entry is { clip: ClipLike; trackId: string } => entry !== null);
  }

  function duplicateEntries(entries: { clip: ClipLike; trackId: string }[], offset: number) {
    const stamp = Date.now().toString(36);
    return entries.map((entry, index) => ({
      trackId: entry.trackId,
      clip: {
        ...entry.clip,
        id: `${entry.clip.id}-copy-${stamp}-${index}`,
        // Never let a duplicate land before zero.
        start: Math.max(0, (entry.clip.start ?? 0) + offset),
      },
    }));
  }

  function pasteSelection() {
    const entries = clipboardRef.current;
    if (entries.length === 0) return;
    const earliest = Math.min(...entries.map((entry) => entry.clip.start ?? 0));
    const target = snapToGrid(playhead, secondsPerBar, beatsPerBar);
    insertClips(duplicateEntries(entries, target - earliest));
  }

  function duplicateSelection() {
    const ids = activeClipIds();
    const entries = ids
      .map((id) => {
        const clip = clips.find((candidate) => candidate.id === id);
        const trackId = ownerOf(id);
        return clip && trackId ? { clip, trackId } : null;
      })
      .filter((entry): entry is { clip: ClipLike; trackId: string } => entry !== null);
    if (entries.length === 0) return;
    insertClips(duplicateEntries(entries, secondsPerBar));
  }

  /** Remove the selected clips, then hand keyboard focus to a neighbour (G9). */
  function deleteSelection() {
    const ids = activeClipIds();
    if (ids.length === 0 || !projectId) return;
    if (audioClipId && ids.includes(audioClipId)) setAudioClipId(null);
    if (midiClipId && ids.includes(midiClipId)) setMidiClipId(null);

    const removed = clips.filter((clip) => ids.includes(clip.id));
    const remaining = clips.filter((clip) => !ids.includes(clip.id));
    const nextTracks = tracks.map((track) => ({
      ...track,
      clipIds: track.clipIds.filter((id) => !ids.includes(id)),
    }));

    // Focus the closest survivor on the same track as the first removed clip, so
    // keyboard users keep their place instead of landing on <body> (G9).
    const anchorTrack = ownerOf(removed[0]?.id ?? "");
    const anchorStart = removed[0]?.start ?? 0;
    const candidate =
      clips
        .filter(
          (clip) =>
            !ids.includes(clip.id) &&
            (anchorTrack ? ownerOf(clip.id) === anchorTrack : true)
        )
        .sort(
          (a, b) =>
            Math.abs((a.start ?? 0) - anchorStart) - Math.abs((b.start ?? 0) - anchorStart)
        )[0] ?? null;

    setSelectedIds(candidate ? [candidate.id] : []);
    setSelectedClip(candidate ? candidate.id : null);
    focusPendingRef.current = Boolean(candidate);

    const data = currentData() as Record<string, unknown>;
    writeProjectData({ ...data, lanes: remaining, tracks: nextTracks }, "deleting clips", nextTracks);
  }

  /** Clip menu ▸ Clip Color: a per-clip override of the track colour. */
  function setClipColor(clipId: string, color: string) {
    const data = currentData();
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    writeProjectData(
      { ...data, lanes: lanes.map((clip) => (clip.id === clipId ? { ...clip, color } : clip)) },
      "the clip colour"
    );
  }

  /**
   * Split at a time (spec §47: Split ctrl E). The right half keeps its musical place by
   * carrying the source offset forward, so audio does not shift.
   */
  /** Stamp a ruler section marker from the clip (S46, clip menu "Create Section"). */
  function createSectionFromClip(clip: ClipLike) {
    const time = Math.max(0, clip.start ?? playhead);
    const label = (clip.title || `Section ${markers.length + 1}`).slice(0, 80);
    const marker: SectionMarker = {
      id: `marker-${Date.now().toString(36)}`,
      time: Math.round(time * 1000) / 1000,
      label,
      color: "#3dafff",
    };
    const next = [...markers, marker].sort((a, b) => a.time - b.time);
    setMarkers(next);
    writeProjectData({ ...currentData(), markers: next }, "a section marker");
  }

  function removeSectionMarker(id: string) {
    const next = markers.filter((marker) => marker.id !== id);
    setMarkers(next);
    writeProjectData({ ...currentData(), markers: next }, "removing a section marker");
  }

  function splitClips(ids: string[], at: number) {
    const data = currentData();
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    const stamp = Date.now().toString(36);
    const replacements = new Map<string, string[]>();
    const nextLanes: ClipLike[] = [];
    for (const clip of lanes) {
      if (!ids.includes(clip.id)) {
        nextLanes.push(clip);
        continue;
      }
      const start = clip.start ?? 0;
      const duration = clip.duration ?? 4;
      if (at <= start + 0.001 || at >= start + duration - 0.001) {
        nextLanes.push(clip);
        continue;
      }
      const rightId = `${clip.id}-split-${stamp}`;
      nextLanes.push({ ...clip, duration: at - start });
      nextLanes.push({
        ...clip,
        id: rightId,
        start: at,
        duration: start + duration - at,
        offset: (clip.offset ?? 0) + (at - start),
        fadeIn: undefined,
      });
      replacements.set(clip.id, [clip.id, rightId]);
    }
    if (replacements.size === 0) return;
    const nextTracks = tracks.map((track) => ({
      ...track,
      clipIds: track.clipIds.flatMap((id) => replacements.get(id) ?? [id]),
    }));
    writeProjectData(
      { ...data, lanes: nextLanes, tracks: nextTracks },
      "splitting the clip",
      nextTracks
    );
  }

  function commitClipRename() {
    if (!clipRename) return;
    const title = clipRename.value.trim();
    const id = clipRename.id;
    setClipRename(null);
    if (!title) return;
    const data = currentData();
    const lanes = Array.isArray(data.lanes) ? (data.lanes as ClipLike[]) : [];
    writeProjectData(
      { ...data, lanes: lanes.map((clip) => (clip.id === id ? { ...clip, title } : clip)) },
      "renaming the clip"
    );
  }

  /** Clip menu ▸ Download .WAV: render just this clip, at unity. */
  /**
   * Download the selected MIDI clips as one Standard MIDI file (N-05). The captured
   * string is explicit that the unit is the selection, so several clips keep their
   * timeline positions in a single file.
   */
  function downloadMidi(fallbackClipId: string) {
    setClipMenu(null);
    const ids = activeClipIds();
    const pool = ids.length > 0 ? ids : [fallbackClipId];
    const chosen = pool
      .map((id) => clipsRef.current.find((clip) => clip.id === id))
      .filter((clip): clip is ClipLike => Boolean(clip?.midi?.notes?.length));
    if (chosen.length === 0) return;
    const bytes = buildMidiFile(chosen, { bpm });
    const suffix = chosen.length === 1 ? "MIDI" : `MIDI (${chosen.length} clips)`;
    download(bytes, `${project?.title || "studio"} - ${suffix}.mid`, "audio/midi");
    setExportToast(
      `MIDI download started${chosen.length > 1 ? ` for ${chosen.length} clips` : ""}!`
    );
  }

  /** Import a Standard MIDI File into the open MIDI clip (N-05's counterpart). */
  async function importMidiFile(file: File) {
    if (!midiClip) return;
    try {
      const parsed = parseMidiFile(await file.arrayBuffer());
      if (parsed.notes.length === 0) {
        setExportToast("No notes found in that MIDI file.");
        return;
      }
      const stamp = Date.now().toString(36);
      const notes = sanitizeNotes(
        parsed.notes.map((note, index) => ({
          ...note,
          id: `note-${stamp}-${index}`,
        }))
      );
      const data = currentData() as Record<string, unknown>;
      const lanes = clipsRef.current.map((clip) =>
        clip.id === midiClip.id
          ? { ...clip, midi: { ...(clip.midi ?? {}), notes } }
          : clip
      );
      const nextBpm = parsed.bpm || bpm;
      const nextSignature = `${parsed.timeSignature[0]}/${parsed.timeSignature[1]}`;
      setBpm(nextBpm);
      setTimeSignature(nextSignature);
      writeProjectData(
        {
          ...data,
          bpm: nextBpm,
          time_signature: nextSignature,
          lanes,
        },
        "the MIDI import"
      );
      setExportToast(`Imported ${notes.length} MIDI notes.`);
    } catch (cause) {
      setExportToast(
        cause instanceof Error ? cause.message : "Could not read that MIDI file."
      );
    }
  }

  async function downloadClipWav(clipId: string) {
    setClipMenu(null);
    try {
      const clip = clipsRef.current.find((item) => item.id === clipId);
      if (!clip) return;
      const buffers = await decodeClips();
      const exportClips = clipsRef.current.map((item) => ({
        id: item.id,
        start: item.start,
        duration: item.duration,
        offset: item.offset,
        fadeIn: item.fadeIn,
        audioUrl: item.audioUrl ?? null,
        audio: item.audio as Partial<ClipAudioSettings> | undefined,
        instrument: item.instrument,
      }));
      const exportTracks = tracks.map((track) => ({
        id: track.id,
        name: track.name,
        volume: track.volume,
        muted: track.muted,
        solo: track.solo,
        volumeAutomation: track.volumeAutomation,
        clipIds: track.clipIds,
      }));
      const chain = (currentData() as { masterChain?: MasterChainEntry[] }).masterChain;
      const wav = await renderMix(buffers, exportClips, exportTracks, {
        chain,
        chains,
        clipIds: new Set([clipId]),
        honourSolo: false,
        masterGain: 1,
      });
      const name = (clip.title || "clip").replace(/[\\/:*?"<>|]/g, "-");
      download(wav, `${name}.wav`, "audio/wav");
    } catch {
      setError("Could not render this clip.");
    }
  }

  /** Right-click a clip: select it and open the state-built menu at the pointer. */
  function handleClipContextMenu(event: React.MouseEvent<HTMLButtonElement>, clip: ClipLike) {
    event.preventDefault();
    event.stopPropagation();
    setSelectedClip(clip.id);
    // Right-clicking a clip inside a multi-selection keeps it, so group actions
    // (mashup) can run from the menu.
    if (!selectedIds.includes(clip.id)) setSelectedIds([clip.id]);
    setClipColorOpen(false);
    setClipMenu({ clipId: clip.id, x: event.clientX, y: event.clientY });
  }

  /** After a delete, move real DOM focus to the surviving clip. */
  useEffect(() => {
    if (!focusPendingRef.current) return;
    focusPendingRef.current = false;
    const element = document.querySelector<HTMLElement>(".se-clip.selected");
    element?.focus();
  }, [selectedIds]);

  /** Dismiss the clip menu on an outside press or Escape. */
  useEffect(() => {
    if (!clipMenu) return;
    const onPointer = (event: PointerEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest(".se-clip-menu")) return;
      setClipMenu(null);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setClipMenu(null);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [clipMenu]);

  /** Dismiss the time-selection menu the same way. */
  useEffect(() => {
    if (!rangeMenu) return;
    const onPointer = (event: PointerEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest(".se-clip-menu")) return;
      setRangeMenu(null);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setRangeMenu(null);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [rangeMenu]);

  /** CTRL/CMD + C / V / D on the arrangement (spec §36). */
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }

      // Escape drops the time range; dialogs and menus handle their own dismissal.
      if (
        event.key === "Escape" &&
        !event.metaKey &&
        !event.ctrlKey &&
        timeSelection &&
        !document.querySelector('[role="dialog"], [role="alertdialog"]')
      ) {
        event.preventDefault();
        clearTimeSelection();
        return;
      }

      // BACKSPACE / DELETE remove the selection (spec §36). The CTRL variants below
      // are time edits, so they are left alone here.
      if (
        (event.key === "Backspace" || event.key === "Delete") &&
        !event.metaKey &&
        !event.ctrlKey
      ) {
        if (activeClipIds().length === 0) return;
        event.preventDefault();
        deleteSelection();
        return;
      }

      // Unmodified keys (spec §11/§36): Space transport, Home/End, add-track letters,
      // and the SHIFT variants captured in the shortcut overlay.
      if (!event.metaKey && !event.ctrlKey) {
        if (document.querySelector('[role="dialog"], [role="alertdialog"]')) return;
        if (event.code === "Space") {
          event.preventDefault();
          togglePlayback();
          return;
        }
        if (event.key === "Home") {
          event.preventDefault();
          setPlaying(false);
          void stopAudio();
          stopClicks();
          scheduledThroughRef.current = 0;
          setPlayhead(0);
          return;
        }
        if (event.key === "End") {
          event.preventDefault();
          seekTo(duration);
          return;
        }
        if (event.key === "F2") {
          const focused = tracks.find((track) => track.id === selectedTrack);
          if (focused) {
            event.preventDefault();
            startRename(focused);
          }
          return;
        }

        const letter = event.key.toLowerCase();
        if (event.altKey && event.shiftKey && letter === "h") {
          event.preventDefault();
          showAllHidden();
          return;
        }
        if (event.altKey) return;

        if (event.shiftKey) {
          // N-01: SHIFT ←/→ grows the time selection one grid step at a time.
          if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
            event.preventDefault();
            extendTimeSelection(event.key === "ArrowRight" ? "right" : "left");
            return;
          }
          if (letter === "c") {
            event.preventDefault();
            setMetronome((value) => {
              if (value) {
                stopClicks();
                return false;
              }
              scheduledThroughRef.current = playheadRef.current;
              return true;
            });
            return;
          }
          if (letter === "t") {
            event.preventDefault();
            addTrack();
            return;
          }
          if (letter === "m" && selectedTrack) {
            const focused = tracks.find((track) => track.id === selectedTrack);
            if (focused) {
              event.preventDefault();
              updateTrack(focused.id, { muted: !focused.muted });
            }
            return;
          }
          if (letter === "s" && selectedTrack) {
            const focused = tracks.find((track) => track.id === selectedTrack);
            if (focused) {
              event.preventDefault();
              updateTrack(focused.id, { solo: !focused.solo });
            }
            return;
          }
          if (letter === "h" && selectedTrack) {
            event.preventDefault();
            hideTrack(selectedTrack);
            return;
          }
          if (letter === "f") {
            const id = selectedClip ?? selectedIds[0];
            const clip = id ? clipsRef.current.find((item) => item.id === id) : undefined;
            if (clip) {
              event.preventDefault();
              // Captured rule (N-10): fades only apply to audio arrangements.
              if ((clip as { midi?: { notes?: unknown[] } }).midi) {
                setExportToast("Fades only apply to audio arrangements.");
                return;
              }
              const current = (clip as { fadeIn?: number }).fadeIn ?? 0;
              commitClipFade(
                clip.id,
                current > 0 ? 0 : Math.min(0.5, (clip.duration ?? 4) / 4)
              );
            }
            return;
          }
          return;
        }

        if (letter === "a") {
          event.preventDefault();
          addTrack();
          return;
        }
        if (letter === "u") {
          event.preventDefault();
          openUploadLibrary();
          return;
        }
        if (event.key === "4") {
          event.preventDefault();
          toggleLibrary();
          return;
        }
      }

      // Plain Z zooms to the time range or selected clips (spec §36).
      if (
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey &&
        event.key.toLowerCase() === "z"
      ) {
        event.preventDefault();
        zoomToSelection();
        return;
      }

      if (!(event.metaKey || event.ctrlKey) || event.altKey) return;
      const key = event.key.toLowerCase();
      // N-01: destructive time edits act on the selected range.
      if (event.key === "Backspace") {
        event.preventDefault();
        deleteSelectedTime(event.shiftKey ? "all" : "track");
        return;
      }
      if (key === "d" && event.shiftKey) {
        event.preventDefault();
        duplicateSelectedTime();
        return;
      }
      // Toggle loop (spec §36: CTRL L).
      if (key === "l") {
        event.preventDefault();
        toggleLoop();
        return;
      }
      // Select all / cut (spec §36). The clip editor owns Ctrl+A while it is open.
      if (key === "a") {
        if (audioClipId) return;
        event.preventDefault();
        setSelectedIds(clipsRef.current.map((clip) => clip.id));
        setSelectedClip(null);
        return;
      }
      if (key === "x") {
        event.preventDefault();
        copySelection();
        deleteSelection();
        return;
      }
      // Undo / redo (spec §36). Shift+Z is redo alongside Y.
      if (key === "z") {
        event.preventDefault();
        if (event.shiftKey) redo();
        else undo();
        return;
      }
      if (key === "y") {
        event.preventDefault();
        redo();
        return;
      }
      // Zoom (spec §36): CTRL = / CTRL -
      if (key === "=" || key === "+") {
        event.preventDefault();
        zoomBy(1);
        return;
      }
      // Split at the playhead (spec §47: ctrl E).
      if (key === "e") {
        event.preventDefault();
        splitClips(activeClipIds(), playhead);
        return;
      }
      if (key === "-") {
        event.preventDefault();
        zoomBy(-1);
        return;
      }
      if (key !== "c" && key !== "v" && key !== "d") return;
      event.preventDefault();
      if (key === "c") copySelection();
      else if (key === "v") pasteSelection();
      else duplicateSelection();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  /** Commit whatever the current drag session moved. */
  function draggedLanes(current: {
    ids: string[];
    origins: Record<string, number>;
    deltaPx: number;
  }): ClipLike[] {
    const lanes = Array.isArray(currentData().lanes)
      ? (currentData() as { lanes: ClipLike[] }).lanes
      : clipsRef.current;
    return lanes.map((clip) => {
      const origin = current.origins[clip.id];
      if (origin === undefined) return clip;
      const start = dragToStart(origin, current.deltaPx, barWidth, secondsPerBar, beatsPerBar);
      return Math.abs(start - origin) > 0.0001 ? { ...clip, start } : clip;
    });
  }

  function commitDrag(current: { ids: string[]; origins: Record<string, number>; deltaPx: number }) {
    const next: Record<string, number> = {};
    for (const id of current.ids) {
      const origin = current.origins[id];
      if (origin === undefined) continue;
      const start = dragToStart(origin, current.deltaPx, barWidth, secondsPerBar, beatsPerBar);
      if (Math.abs(start - origin) > 0.0001) next[id] = start;
    }
    if (Object.keys(next).length > 0) commitClipStarts(next);
  }

  const duration = useMemo(() => {
    const end = clips.reduce((max, clip) => Math.max(max, (clip.start ?? 0) + (clip.duration ?? 0)), 0);
    return Math.max(240, Math.ceil(end));
  }, [clips]);

  /** Transport: advance the playhead in real time while playing. */
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const delta = Math.min(0.25, (now - last) / 1000);
      last = now;
      const current = playheadRef.current;
      const loopActive = loopRef.current && loopEndRef.current > loopStartRef.current;
      const limit = loopActive ? loopEndRef.current : durationRef.current;
      let next = current + delta * rateRef.current;
      if (limit > 0 && next >= limit) {
        if (loopActive) {
          // Loop repeats the selected range, not the whole project (spec §68), and the
          // engine must follow: restart from the loop start when it wraps.
          next = loopStartRef.current;
          restartAudioGuarded(next);
        } else if (loopRef.current) {
          next = 0;
          restartAudioGuarded(0);
        } else {
          next = durationRef.current;
        }
      }
      // Loop wrap moves the playhead backwards; clicks must restart from there.
      if (next < current) scheduledThroughRef.current = next;
      if (metronomeRef.current) scheduleClicks(current, next + 0.35);
      setPlayhead(next);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, duration, loop]);

  useEffect(() => {
    if (playing && !loop && playhead >= duration) setPlaying(false);
  }, [playing, loop, playhead, duration]);

  /** Minimal playback engine: decode each clip's audio and schedule it from the playhead. */
  const audioRef = useRef<{
    ctx: AudioContext;
    sources: AudioScheduledSourceNode[];
    analyser?: AnalyserNode;
    disposeChains?: (() => void)[];
    /** Sidechain ducking control loop (S43). */
    duckTimer?: number;
  } | null>(null);
  /** Decoded buffers keyed by URL, so a restart (ghost-drag apply) does not refetch. */
  const bufferCacheRef = useRef<Map<string, AudioBuffer>>(new Map());
  /** Latest values for pointer handlers that outlive the render they were made in. */
  const playheadRef = useRef(playhead);
  playheadRef.current = playhead;
  const playingRef = useRef(playing);
  playingRef.current = playing;
  const metronomeRef = useRef(metronome);
  metronomeRef.current = metronome;
  const beatsPerBarRef = useRef(beatsPerBar);
  beatsPerBarRef.current = beatsPerBar;
  const barWidthRef = useRef(barWidth);
  barWidthRef.current = barWidth;
  const secondsPerBarRef = useRef(secondsPerBar);
  secondsPerBarRef.current = secondsPerBar;
  const bpmRef = useRef(bpm);
  bpmRef.current = bpm;
  const rateRef = useRef(playbackRate);
  rateRef.current = playbackRate;
  const durationRef = useRef(0);
  durationRef.current = duration;
  const loopRef = useRef(loop);
  loopRef.current = loop;
  const loopStartRef = useRef(loopStart);
  loopStartRef.current = loopStart;
  const loopEndRef = useRef(loopEnd);
  loopEndRef.current = loopEnd;
  /** Guards against stacking stop/start pairs when playback wraps repeatedly. */
  const restartingRef = useRef(false);
  /** Song time up to which metronome clicks have already been scheduled. */
  const scheduledThroughRef = useRef(0);
  /** Clicks already scheduled, so switching the metronome off can silence them. */
  const clickNodesRef = useRef<OscillatorNode[]>([]);

  async function stopAudio() {
    const engine = audioRef.current;
    if (!engine) return;
    if (engine.duckTimer !== undefined) {
      window.clearInterval(engine.duckTimer);
      engine.duckTimer = undefined;
    }
    engine.sources.forEach((source) => {
      try {
        source.stop();
      } catch {
        /* already stopped */
      }
    });
    engine.sources = [];
    engine.disposeChains?.forEach((dispose) => {
      try {
        dispose();
      } catch {
        /* nodes may already be disconnected */
      }
    });
    engine.disposeChains = [];
  }

  /** Stop and re-schedule from `from` with a specific arrangement (drag apply, §22). */
  function restartAudio(from: number, arrangement: ClipLike[]) {
    void (async () => {
      await stopAudio();
      await startAudio(from, arrangement);
    })();
  }

  /** Restart without stacking: a loop wrap can fire while the last restart is running. */
  function restartAudioGuarded(from: number, arrangement: ClipLike[] = clipsRef.current) {
    if (restartingRef.current) return;
    restartingRef.current = true;
    void (async () => {
      try {
        await stopAudio();
        await startAudio(from, arrangement);
      } finally {
        restartingRef.current = false;
      }
    })();
  }

  /** Move the playhead; while playing, the engine follows so audio stays in sync. */
  function seekTo(seconds: number) {
    setPlayhead(seconds);
    if (playingRef.current) restartAudioGuarded(seconds);
  }

  /** Identity of a chain's *shape*; parameter values are not part of it. */
  function chainStructure(entries: PluginChainEntry[] | undefined): string {
    return (entries ?? [])
      .map(
        (entry) =>
          `${entry.entryId}:${entry.pluginId}:${entry.bypassed ? 1 : 0}:${
            entry.sidechain ? `${entry.sidechain.trackId}/${entry.sidechain.tap}` : "-"
          }`
      )
      .join(">");
  }

  function chainMapStructure(map: Record<string, PluginChainEntry[] | undefined>): string {
    return Object.entries(map)
      .filter(([, entries]) => entries && entries.length > 0)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([trackId, entries]) => `${trackId}=${chainStructure(entries)}`)
      .join(";");
  }

  /** Silence clicks that were scheduled but have not sounded yet. */
  function stopClicks() {
    clickNodesRef.current.forEach((node) => {
      try {
        node.stop();
      } catch {
        /* already stopped */
      }
    });
    clickNodesRef.current = [];
  }

  /**
   * Schedule metronome clicks for the window [from, to) with a short lookahead.
   *
   * Position-driven rather than pre-scheduled for the whole song: it survives loop
   * wraps and seeks, and a long project cannot queue thousands of oscillators.
   */
  function scheduleClicks(from: number, to: number) {
    const engine = audioRef.current;
    if (!engine) return;
    const until = Math.min(to, durationRef.current);
    if (until <= from) return;
    if (from < scheduledThroughRef.current - 0.01) scheduledThroughRef.current = from;
    const start = Math.max(from, scheduledThroughRef.current);
    if (until <= start) return;
    const context = engine.ctx;
    for (const click of clicksBetween(start, until, bpmRef.current, beatsPerBarRef.current)) {
      const delay = Math.max(0.005, (click.time - from) / rateRef.current);
      const when = context.currentTime + delay;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "square";
      oscillator.frequency.value = click.accent ? 1760 : 1100;
      gain.gain.setValueAtTime(0.0001, when);
      gain.gain.linearRampToValueAtTime(click.accent ? 0.16 : 0.09, when + 0.002);
      gain.gain.exponentialRampToValueAtTime(0.0001, when + 0.045);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(when);
      oscillator.stop(when + 0.06);
      clickNodesRef.current.push(oscillator);
    }
    scheduledThroughRef.current = until;
    if (clickNodesRef.current.length > 64) {
      clickNodesRef.current = clickNodesRef.current.slice(-64);
    }
  }

  async function startAudio(from: number, arrangement: ClipLike[] = clips) {
    // Record the structure before any await: the live-chain effect may run while the
    // graph is still decoding, and must not mistake that for a shape change.
    chainStructureRef.current = chainMapStructure(chainsRef.current);
    chainRuntimeRef.current = new Map();
    trackGainRef.current = new Map();
    const context = audioRef.current?.ctx ?? new AudioContext();
    await context.resume();

    const cache = bufferCacheRef.current;
    await Promise.all(
      arrangement.map(async (clip) => {
        const url = (clip as { audioUrl?: string | null }).audioUrl;
        if (!url || cache.has(url)) return;
        try {
          const response = await fetch(url);
          if (!response.ok) return;
          const data = await response.arrayBuffer();
          cache.set(url, await context.decodeAudioData(data));
        } catch {
          /* skip clips that cannot be decoded */
        }
      })
    );

    const now = context.currentTime;
    const master = context.createGain();
    master.gain.value = masterStateRef.current.muted ? 0 : masterStateRef.current.volume / 100;
    masterGainRef.current = master;

    // Master chain (W4.1): the bus is a real node graph, not a hard-coded gain.
    const masterChain = ((): MasterChainEntry[] => {
      const data = currentData() as { masterChain?: unknown };
      const raw = Array.isArray(data.masterChain) ? (data.masterChain as MasterChainEntry[]) : [];
      // A default limiter matches the reference, which ships master with one (§91).
      return raw.length > 0 ? raw : [{ type: "limiter", amount: 0.5 }];
    })();
    const bus = buildMasterBus(context, masterChain);
    master.connect(bus.input);
    // Meter the master output (W4.4) without altering the signal.
    const analyser = context.createAnalyser();
    analyser.fftSize = 2048;
    bus.output.connect(analyser);
    analyser.connect(context.destination);
    audioRef.current = { ctx: context, sources: [], analyser, disposeChains: [] };

    // Per-track input: gain plus the track's plugin chain, shared by its clips so an
    // effect is heard once instead of being duplicated per clip.
    const trackInputs = new Map<string, AudioNode>();
    /** Pre-fx tap per track, for a compressor keyed by another track (S43). */
    const preTaps = new Map<string, GainNode>();
    /** Per-track duck gain, between the plugin chain and the fader. */
    const duckGains = new Map<string, GainNode>();
    const duckSpecs: Array<{ target: string; source: string; tap: "pre" | "post" }> = [];
    function trackInput(trackId: string, volume: number): AudioNode {
      const existing = trackInputs.get(trackId);
      if (existing) return existing;
      const gain = context.createGain();
      gain.gain.value = Math.max(0, volume) / 100;
      gain.connect(master);
      trackGainRef.current.set(trackId, gain);
      const duckGain = context.createGain();
      duckGain.connect(gain);
      const entries = chainsRef.current[trackId] ?? [];
      let input: AudioNode = duckGain;
      if (entries.length > 0) {
        const chain = buildPluginChain(context, entries);
        chain.output.connect(duckGain);
        audioRef.current?.disposeChains?.push(chain.dispose);
        chainRuntimeRef.current.set(trackId, { update: chain.update });
        input = chain.input;
        for (const entry of entries) {
          if (entry.sidechain) {
            duckSpecs.push({
              target: trackId,
              source: entry.sidechain.trackId,
              tap: entry.sidechain.tap,
            });
          }
        }
      }
      const pre = context.createGain();
      pre.connect(input);
      preTaps.set(trackId, pre);
      duckGains.set(trackId, duckGain);
      trackInputs.set(trackId, pre);
      return pre;
    }

    // Track volume automation is scheduled on the shared track gain before any clip
    // sources are created, so the curve is already in place when playback starts.
    const anySoloAtStart = tracks.some((track) => track.solo);
    for (const track of tracks) {
      if (!track.volumeAutomation?.length) continue;
      const audible = !track.muted && (!anySoloAtStart || track.solo);
      trackInput(track.id, audible ? track.volume : 0);
      const gain = trackGainRef.current.get(track.id);
      if (gain && audible) {
        scheduleVolumeAutomation(gain.gain, track.volumeAutomation, {
          from,
          when: now,
          rate: playbackRate,
          fallback: track.volume,
        });
      }
    }

    for (const clip of arrangement) {
      const url = (clip as { audioUrl?: string | null }).audioUrl;
      const buffer = url ? bufferCacheRef.current.get(url) : undefined;
      if (!buffer) continue;
      const start = clip.start ?? 0;
      const duration = clip.duration ?? buffer.duration;
      if (start + duration <= from) continue;
      const track = tracks.find((item) => item.clipIds.includes(clip.id));
      // Sources are always scheduled; mute/solo are applied through the track gain so
      // toggling them mid-playback is heard immediately (and undoable by unmuting).
      const anySolo = tracks.some((item) => item.solo);
      const audible = track ? !track.muted && (!anySolo || track.solo) : true;
      const volume = audible ? (track?.volume ?? 80) : 0;

      const when = now + Math.max(0, start - from) / playbackRate;
      const intoClip = Math.max(0, from - start);
      const settings = sanitizeClipAudio((clip as { audio?: unknown }).audio);
      const rate = playbackRate * clipRate(settings);
      let sourceBuffer = buffer;
      if (settings.reverse) {
        const key = `${clip.id}:${url ?? ""}`;
        const cached = reversedBuffersRef.current.get(key);
        if (cached) {
          sourceBuffer = cached;
        } else {
          const reversed = reverseBuffer(context, buffer);
          reversedBuffersRef.current.set(key, reversed);
          sourceBuffer = reversed;
        }
      }
      const plan = planClipPlayback({
        bufferDuration: buffer.duration,
        clipDuration: duration,
        intoClip,
        offset: Math.max(0, (clip as { offset?: number }).offset ?? 0),
        rate,
        reverse: settings.reverse,
        loop: settings.loop,
      });
      const source = context.createBufferSource();
      source.buffer = sourceBuffer;
      // Audition speed (G17) and the clip's pitch/speed all scale the source, so clips
      // stay in sync with each other.
      source.playbackRate.value = rate;
      if (plan.loop) {
        source.loop = true;
        source.loopStart = plan.loopStart;
        source.loopEnd = plan.loopEnd;
      }
      const destination = trackInput(track?.id ?? clip.id, volume);
      // Volume is its own node so the fade automation stays a 0→1 ramp.
      let nodeInput: AudioNode = destination;
      if (settings.gainDb !== 0) {
        const volumeNode = context.createGain();
        volumeNode.gain.value = dbToGain(settings.gainDb);
        volumeNode.connect(destination);
        nodeInput = volumeNode;
      }
      const fadeIn = Math.min(
        (clip as { fadeIn?: number }).fadeIn ?? 0,
        duration
      );
      if (fadeIn > 0) {
        const clipGain = context.createGain();
        const initial = intoClip >= fadeIn ? 1 : intoClip / fadeIn;
        clipGain.gain.setValueAtTime(initial, when);
        if (intoClip < fadeIn) {
          clipGain.gain.linearRampToValueAtTime(1, when + (fadeIn - intoClip) / playbackRate);
        }
        clipGain.connect(nodeInput);
        source.connect(clipGain);
      } else {
        source.connect(nodeInput);
      }
      if (plan.loop) {
        source.start(when, plan.bufferStart);
        // A looped clip still ends with its timeline length.
        source.stop(when + Math.max(0.05, (duration - intoClip) / playbackRate));
      } else {
        source.start(
          when,
          plan.bufferStart,
          Math.max(0.05, plan.bufferLength ?? duration - intoClip)
        );
      }
      audioRef.current?.sources.push(source);
    }

    // MIDI clips: synth voices into the same track input, so chains, mute, solo and
    // volume all apply exactly like audio clips.
    for (const clip of arrangement) {
      const notes = sanitizeNotes((clip as ClipLike).midi?.notes);
      if (notes.length === 0) continue;
      const start = clip.start ?? 0;
      const track = tracks.find((item) => item.clipIds.includes(clip.id));
      const anySolo = tracks.some((item) => item.solo);
      const audible = track ? !track.muted && (!anySolo || track.solo) : true;
      const volume = audible ? (track?.volume ?? 80) : 0;
      const destination = trackInput(track?.id ?? clip.id, volume);
      for (const note of notes) {
        const absolute = start + note.start;
        if (absolute + note.length <= from) continue;
        const when = now + Math.max(0, absolute - from) / playbackRate;
        const clipMidi = (clip as ClipLike).midi;
        const bend = valueAt(sanitizePoints(clipMidi?.bend, -1, 1), note.start, 0);
        const mod = valueAt(sanitizePoints(clipMidi?.mod, 0, 1), note.start, 0);
        audioRef.current?.sources.push(
          ...scheduleMidiNote(
            context,
            destination,
            note,
            when,
            playbackRate,
            { bend, mod },
            normalizeMidiInstrument((clip as ClipLike).instrument)
          )
        );
      }
    }

    // S43: one control-rate analyser per sidechain route, ducking the target track.
    const duckNodes: Array<{ gain: GainNode; analyser: AnalyserNode }> = [];
    for (const spec of duckSpecs) {
      const source =
        spec.tap === "post" ? trackGainRef.current.get(spec.source) : preTaps.get(spec.source);
      const target = duckGains.get(spec.target);
      if (!source || !target || spec.source === spec.target) continue;
      const keyAnalyser = context.createAnalyser();
      keyAnalyser.fftSize = 256;
      source.connect(keyAnalyser);
      duckNodes.push({ gain: target, analyser: keyAnalyser });
    }
    if (duckNodes.length && audioRef.current) {
      const frame = new Float32Array(256);
      const timer = window.setInterval(() => {
        for (const node of duckNodes) {
          node.analyser.getFloatTimeDomainData(frame);
          let sum = 0;
          for (let index = 0; index < frame.length; index += 1) sum += frame[index] * frame[index];
          const rms = Math.sqrt(sum / frame.length);
          const duck = 1 - Math.min(0.8, Math.max(0, (rms - 0.01) * 3.5));
          node.gain.gain.setTargetAtTime(duck, context.currentTime, 0.06);
        }
      }, 50);
      audioRef.current.duckTimer = timer;
    }
  }

  /** Decode every clip's audio once, for export (W4.3). */
  async function decodeClips(): Promise<Map<string, AudioBuffer>> {
    const context = new AudioContext();
    const map = new Map<string, AudioBuffer>();
    try {
      await Promise.all(
        clips.map(async (clip) => {
          const url = (clip as { audioUrl?: string | null }).audioUrl;
          if (!url) return;
          try {
            const response = await fetch(url);
            if (!response.ok) return;
            map.set(clip.id, await context.decodeAudioData(await response.arrayBuffer()));
          } catch {
            /* skip undecodable clips */
          }
        })
      );
    } finally {
      void context.close();
    }
    return map;
  }

  function download(bytes: BlobPart | Uint8Array, filename: string, type: string) {
    const part = bytes instanceof Uint8Array ? new Blob([bytes as unknown as ArrayBufferView<ArrayBuffer>]) : bytes;
    const url = URL.createObjectURL(new Blob([part], { type }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  }

  /**
   * Export matrix (W4.3): full mix, one file per track, or the project document.
   * Deliberately the same shape as the reference — pick a scope, get a file, no dialog
   * (§87) — but rendered locally so nothing is queued server-side.
   */
  async function runExport(scope: "mix" | "tracks" | "json" | "range") {
    if (!project) return;
    setExportOpen(false);
    if (scope === "json") {
      download(JSON.stringify(project, null, 2), `${project.title || "project"}.json`, "application/json");
      setExportToast("Project download started!");
      return;
    }
    setExporting(true);
    try {
      const buffers = await decodeClips();
      const exportClips: ExportClip[] = clips.map((clip) => ({
        id: clip.id,
        start: clip.start,
        duration: clip.duration,
        offset: (clip as { offset?: number }).offset,
        fadeIn: (clip as { fadeIn?: number }).fadeIn,
        audioUrl: (clip as { audioUrl?: string | null }).audioUrl ?? null,
        audio: clip.audio as Partial<ClipAudioSettings> | undefined,
        midi: (clip as ClipLike).midi,
        instrument: (clip as ClipLike).instrument,
      }));
      const exportTracks: ExportTrack[] = tracks.map((track) => ({
        id: track.id,
        name: track.name,
        volume: track.volume,
        muted: track.muted,
        solo: track.solo,
        volumeAutomation: track.volumeAutomation,
        clipIds: track.clipIds,
      }));
      const chain = (currentData() as { masterChain?: MasterChainEntry[] }).masterChain;
      // Mix/range only: per-track files must keep their relative balance (G11).
      const normalise = exportNormalise ? EXPORT_TARGET_PEAK_DB : null;
      const trackChains = chains;
      const masterGain = masterMuted ? 0 : masterVolume / 100;

      if (scope === "mix") {
        const wav = await renderMix(buffers, exportClips, exportTracks, {
          chain,
          chains: trackChains,
          normalise,
          masterGain,
        });
        download(wav, `${project.title || "mix"}.wav`, "audio/wav");
        setExportToast("Full mix download started!");
      } else if (scope === "range") {
        // Exports the time selection, or the loop range as the reference fallback (§87).
        const bounds = timeSelection ?? { start: loopStart, end: loopEnd };
        const wav = await renderMix(buffers, exportClips, exportTracks, {
          chain,
          chains: trackChains,
          normalise,
          masterGain,
          from: bounds.start,
          to: bounds.end,
        });
        download(wav, `${project.title || "mix"} - selection.wav`, "audio/wav");
        setExportToast("Selection download started!");
      } else {
        for (const track of exportTracks) {
          const wav = await renderMix(buffers, exportClips, exportTracks, {
            chain,
            chains: trackChains,
            clipIds: new Set(track.clipIds),
            honourSolo: false,
          });
          const label = (track.name || track.id).replace(/[\\/:*?"<>|]/g, "-");
          download(wav, `${project.title || "project"} - ${label}.wav`, "audio/wav");
        }
        setExportToast("One file per track download started!");
      }
    } catch {
      setError("Export failed. Check that the clips still have audio.");
    } finally {
      setExporting(false);
    }
  }

  /**
   * Bounce a track (N-06): render that track's clips through its own effect chain,
   * ignoring the solo state of the other tracks (bouncing a soloed-out track must not
   * be silent — the same rule as the per-track export, G39).
   *
   * When upload storage is available the render is placed back as a `(bounced)` track
   * and the source is muted; otherwise the WAV downloads instead (B-007).
   */
  async function bounceTrack(trackId: string) {
    const track = tracks.find((candidate) => candidate.id === trackId);
    if (!track || !project || bouncingTrack) return;
    if (track.clipIds.length === 0) {
      setError("This track has no clips to bounce.");
      return;
    }
    const sourceClips = track.clipIds
      .map((id) => clips.find((clip) => clip.id === id))
      .filter((clip): clip is ClipLike => Boolean(clip));
    const start = Math.min(...sourceClips.map((clip) => clip.start ?? 0));
    const end = Math.max(
      ...sourceClips.map((clip) => (clip.start ?? 0) + (clip.duration ?? 0))
    );
    const span = Math.max(0.1, end - start);

    setBouncingTrack(trackId);
    // The reference reports "Exporting on track #": name the track while it renders.
    setExportToast(`Bouncing ${track.name || `track ${tracks.indexOf(track) + 1}`}…`);
    try {
      const buffers = await decodeClips();
      const exportClips: ExportClip[] = clips.map((clip) => ({
        id: clip.id,
        start: clip.start,
        duration: clip.duration,
        offset: (clip as { offset?: number }).offset,
        fadeIn: (clip as { fadeIn?: number }).fadeIn,
        audioUrl: (clip as { audioUrl?: string | null }).audioUrl ?? null,
        audio: clip.audio as Partial<ClipAudioSettings> | undefined,
        midi: (clip as ClipLike).midi,
        instrument: (clip as ClipLike).instrument,
      }));
      const exportTracks: ExportTrack[] = tracks.map((candidate) => ({
        id: candidate.id,
        name: candidate.name,
        volume: candidate.volume,
        muted: candidate.muted,
        solo: candidate.solo,
        volumeAutomation: candidate.volumeAutomation,
        clipIds: candidate.clipIds,
      }));
      const wav = await renderMix(buffers, exportClips, exportTracks, {
        chain: (currentData() as { masterChain?: MasterChainEntry[] }).masterChain,
        chains,
        clipIds: new Set(track.clipIds),
        honourSolo: false,
        // A bounce is the track alone: no master fader, no master mute.
        masterGain: 1,
      });
      const label = (track.name || track.id).replace(/[\\/:*?"<>|]/g, "-");
      const filename = `${project.title || "project"} - ${label} (bounce).wav`;

      try {
        const blob = new Blob([wav as unknown as ArrayBufferView<ArrayBuffer>], {
          type: "audio/wav",
        });
        const upload = await uploadStudioAudio(
          new File([blob], filename, { type: "audio/wav" }),
          span
        );
        placeBounce(track, upload.url, start, span);
        setExportToast(`Bounce on ${label} added as a new track.`);
      } catch {
        // Storage is not configured on this deployment (B-007): keep the render useful.
        download(wav, filename, "audio/wav");
        setExportToast(
          `Bounce on ${label} downloaded — storage is off, so it was not placed.`
        );
      }
    } catch {
      setError("Bounce failed. Check that the clips still have audio.");
      setExportToast(null);
    } finally {
      setBouncingTrack(null);
    }
  }

  /** Render-in-place result: one bounced track, with the source muted (N-06). */
  function placeBounce(source: StudioTrack, url: string, start: number, duration: number) {
    const stamp = Date.now().toString(36);
    const trackId = `track-${stamp}`;
    const clipId = `clip-${stamp}`;
    const nextTrack: StudioTrack = {
      id: trackId,
      name: `${source.name} (bounced)`,
      color: source.color,
      index: tracks.length,
      volume: 80,
      pan: 0,
      muted: false,
      solo: false,
      hidden: false,
      collapsed: false,
      groupId: null,
      chain: [],
      clipIds: [clipId],
    };
    const clip: ClipLike = {
      id: clipId,
      title: `${source.name} (bounce)`,
      start,
      duration,
      color: source.color,
      audioUrl: url,
    };
    const data = currentData() as Record<string, unknown>;
    const nextTracks = [
      ...tracks.map((candidate) =>
        candidate.id === source.id ? { ...candidate, muted: true } : candidate
      ),
      nextTrack,
    ];
    writeProjectData(
      { ...data, lanes: [...clips, clip], tracks: nextTracks },
      "bouncing the track",
      nextTracks
    );
    setSelectedTrack(trackId);
  }

  // The export toast dismisses itself; the capture keeps a manual close too.
  useEffect(() => {    if (!exportToast) return;
    const timer = window.setTimeout(() => setExportToast(null), 6000);
    return () => window.clearTimeout(timer);
  }, [exportToast]);

  /** Sample the master analyser while playing (W4.4). */
  useEffect(() => {
    if (!playing) {
      setMeter(null);
      return;
    }
    let raf = 0;
    let last = 0;
    const loop = (now: number) => {
      if (now - last > 120) {
        last = now;
        const analyser = audioRef.current?.analyser;
        if (analyser) {
          const frame = new Float32Array(analyser.fftSize);
          analyser.getFloatTimeDomainData(frame);
          setMeter(analyse(frame));
        }
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  function togglePlayback() {
    setPlaying((value) => {
      if (value) {
        void stopAudio();
        stopClicks();
        return false;
      }
      const from = !loop && playhead >= duration ? 0 : playhead;
      if (!loop && playhead >= duration) setPlayhead(0);
      scheduledThroughRef.current = from;
      void startAudio(from);
      return true;
    });
  }

  /**
   * Chain edits while the transport runs: parameter changes apply to the live nodes, a
   * change in shape (add/remove/reorder/bypass) rebuilds once so the graph stays valid.
   */
  useEffect(() => {
    if (!playing) return;
    if (!chainRuntimeRef.current.size && !chainStructureRef.current) return;
    if (chainMapStructure(chains) !== chainStructureRef.current) {
      restartAudioGuarded(playheadRef.current);
      return;
    }
    for (const [trackId, nodes] of chainRuntimeRef.current) {
      for (const entry of chains[trackId] ?? []) {
        nodes.update(entry.entryId, entry.params);
      }
    }
  }, [chains, playing]);

  /**
   * Track mix changes while playing: volume, mute and solo used to be applied only when
   * sources were scheduled, so pressing M/S mid-playback changed the button and nothing
   * else. The gain nodes already exist per track, so follow them live.
   */
  useEffect(() => {
    if (!playing) return;
    const anySolo = tracks.some((track) => track.solo);
    for (const [trackId, gain] of trackGainRef.current) {
      const track = tracks.find((candidate) => candidate.id === trackId);
      const audible = track ? !track.muted && (!anySolo || track.solo) : true;
      gain.gain.value = audible ? Math.max(0, track?.volume ?? 80) / 100 : 0;
    }
  }, [tracks, playing]);

  const barCount = Math.max(1, Math.ceil(duration / secondsPerBar));

  /** Pointer handling for clip dragging (G7/G8) and marquee selection (G6). */
  useEffect(() => {
    const computeFade = (session: { id: string; startX: number; fadeIn: number; duration: number }, clientX: number) => {
      const raw =
        session.fadeIn + ((clientX - session.startX) / barWidthRef.current) * secondsPerBarRef.current;
      return {
        id: session.id,
        fadeIn: Math.max(
          0,
          Math.min(
            session.duration,
            snapToGrid(raw, secondsPerBarRef.current, beatsPerBarRef.current)
          )
        ),
      };
    };

    const computeTrim = (
      session: { id: string; edge: "start" | "end"; startX: number; start: number; duration: number; offset: number },
      clientX: number
    ) => {
      const deltaSec = ((clientX - session.startX) / barWidthRef.current) * secondsPerBarRef.current;
      const step = secondsPerBarRef.current / beatsPerBarRef.current;
      const end = session.start + session.duration;
      if (session.edge === "end") {
        const newEnd = Math.max(
          session.start + step,
          snapToGrid(end + deltaSec, secondsPerBarRef.current, beatsPerBarRef.current)
        );
        return {
          id: session.id,
          start: session.start,
          duration: newEnd - session.start,
          offset: session.offset,
        };
      }
      // Left trim moves the start and the content offset together, so the audio under
      // the remaining clip does not shift.
      const newStart = Math.max(
        0,
        Math.min(
          end - step,
          snapToGrid(session.start + deltaSec, secondsPerBarRef.current, beatsPerBarRef.current)
        )
      );
      return {
        id: session.id,
        start: newStart,
        duration: end - newStart,
        offset: Math.max(0, session.offset + (newStart - session.start)),
      };
    };

    const move = (event: PointerEvent) => {
      const fadeSession = fadeRef.current;
      if (fadeSession) {
        const preview = computeFade(fadeSession, event.clientX);
        fadePreviewRef.current = preview;
        setFadePreview(preview);
        return;
      }
      const trimSession = trimRef.current;
      if (trimSession) {
        const next = computeTrim(trimSession, event.clientX);
        trimPreviewRef.current = next;
        setTrimPreview(next);
        return;
      }
      const session = dragRef.current;
      if (session) {
        const deltaPx = event.clientX - session.startX;
        if (isDrag(deltaPx) || drag !== null) {
          const next = { ids: session.ids, origins: session.origins, deltaPx };
          dragStateRef.current = next;
          setDrag(next);
          // Ghost drag off: every move frame reaches the engine (§22).
          if (!session.ghost && playingRef.current && dragApplyPlan(false).duringMove) {
            restartAudio(playheadRef.current, draggedLanes(next));
          }
        }
        return;
      }
      const band = marqueeRef.current;
      if (!band) return;
      if (!isDrag(event.clientX - band.startX) && !band.moved) return;
      band.moved = true;
      const x2 = event.clientX - band.originX;
      const y2 = event.clientY - band.originY;
      const left = Math.min(band.x1, x2);
      const right = Math.max(band.x1, x2);
      const top = Math.min(band.y1, y2);
      const bottom = Math.max(band.y1, y2);
      const hit: string[] = [];
      tracksRef.current.forEach((track, index) => {
        const rowTop = index * ROW_STEP;
        if (rowTop + ROW_STEP < top || rowTop > bottom) return;
        clipsRef.current
          .filter((clip) => track.clipIds.includes(clip.id))
          .forEach((clip) => {
            const clipLeft = ((clip.start ?? 0) / secondsPerBar) * barWidth;
            const clipRight = clipLeft + Math.max(20, ((clip.duration ?? 4) / secondsPerBar) * barWidth);
            if (clipRight >= left && clipLeft <= right) hit.push(clip.id);
          });
      });
      band.hit = hit;
      setMarquee({ x1: band.x1, y1: band.y1, x2, y2 });
      setSelectedIds(hit);
    };
    const up = (event: PointerEvent) => {
      const cancelled = event.type === "pointercancel";
      const fadeSession = fadeRef.current;
      if (fadeSession) {
        fadeRef.current = null;
        fadePreviewRef.current = null;
        setFadePreview(null);
        if (cancelled) return;
        // Use the release position: Chrome coalesces pointermove events, so the last
        // move can be missing and the pointerup carries the true end point.
        const preview = computeFade(fadeSession, event.clientX);
        if (Math.abs(preview.fadeIn - fadeSession.fadeIn) > 0.0001) {
          commitClipFade(preview.id, preview.fadeIn);
        }
        return;
      }
      const trimSession = trimRef.current;
      if (trimSession) {
        trimRef.current = null;
        trimPreviewRef.current = null;
        setTrimPreview(null);
        if (cancelled) return;
        const preview = computeTrim(trimSession, event.clientX);
        if (
          Math.abs(preview.start - trimSession.start) > 0.0001 ||
          Math.abs(preview.duration - trimSession.duration) > 0.0001
        ) {
          commitTrim(preview);
        }
        return;
      }
      const session = dragRef.current;
      dragRef.current = null;
      if (session) {
        // A cancel must abort the gesture: its coordinates are not the pointer's.
        if (cancelled) {
          dragStateRef.current = null;
          setDrag(null);
          return;
        }
        // Commit from the release position: the browser may coalesce the final
        // pointermove, so the last computed delta can be short of the drop.
        const finalDelta = event.clientX - session.startX;
        const current = { ids: session.ids, origins: session.origins, deltaPx: finalDelta };
        if (Math.abs(finalDelta) > 0) {
          // Ghost drag on: nothing moved audio during the gesture, so apply once now.
          const proposed = draggedLanes(current);
          commitDrag(current);
          if (session.ghost && playingRef.current && dragApplyPlan(true).onDrop) {
            restartAudio(playheadRef.current, proposed);
          }
        }
        dragStateRef.current = null;
        setDrag(null);
      }
      const band = marqueeRef.current;
      marqueeRef.current = null;
      if (band) {
        setMarquee(null);
        if (band.moved) setSelectedIds(band.hit);
      }
    };
    // Keep the freshest handlers for the single set of listeners registered below. The
    // old version re-registered on every drag frame; between removal and re-attach the
    // browser could deliver pointer moves to nobody, so a fast drag only moved once.
    pointerHandlersRef.current = { move, up };
  }, [drag, secondsPerBar, beatsPerBar, projectId]);

  /** One stable pair of window listeners for clip drag, trim, fade and marquee. */
  useEffect(() => {
    const onMove = (event: PointerEvent) => pointerHandlersRef.current?.move(event);
    const onUp = (event: PointerEvent) => pointerHandlersRef.current?.up(event);
    const onCancel = (event: PointerEvent) => {
      pointerHandlersRef.current?.up(event);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onCancel);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onCancel);
    };
  }, []);


  /** Coarse pointers get 44px hit areas without changing desktop density (G20). */
  const [touchMode, setTouchMode] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const query = window.matchMedia("(pointer: coarse)");
    setTouchMode(query.matches);
    const onChange = () => setTouchMode(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  if (authLoading) return <div className="se-shell is-loading" role="main" aria-busy="true" />;

  if (!user) {
    return (
      <div className="se-gate">
        <h1>Studio</h1>
        <p>Sign in to open a project.</p>
        <Link className="btn btn-primary" href="/login?next=/studio">Sign in</Link>
      </div>
    );
  }

  if (!projectId) {
    return (
      <div className="se-gate">
        <h1>No project selected</h1>
        <p>Choose a project from the Studio home.</p>
        <Link className="btn btn-primary" href="/studio">Open Studio home</Link>
      </div>
    );
  }

  /** Remix (S37): generate a variation from the song's style and add it to the library. */
  async function remixSong(song: WebMusicGeneration) {
    if (remixingSongId) return;
    if (!song.style?.trim()) return;
    setRemixingSongId(song.id);
    try {
      const created = await generateSong({
        mode: "advanced",
        style: song.style,
        prompt: song.style,
        title: `${song.title || "Song"} remix`,
        instrumental: song.instrumental,
        model: song.model,
      });
      const deadline = Date.now() + 180_000;
      let generation: WebMusicGeneration | null = null;
      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        const current = await fetchGeneration(created.task_id);
        if (current.status === "complete" || current.status === "ready") {
          generation = current;
          break;
        }
        if (current.status === "error" || current.status === "failed") {
          throw new Error(current.error_message || "Remix failed.");
        }
      }
      if (!generation) throw new Error("Remix timed out.");
      const remix = generation;
      setLibrarySongs((previous) => (previous ? [remix, ...previous] : [remix]));
      setExportToast("Remix generated and added to the library.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Remix failed.");
    } finally {
      setRemixingSongId(null);
    }
  }

  /**
   * S45 entry: "Create new plugin" closes the catalog and turns the Magic Bar into
   * design mode — warm tint, seeded prompt, active send, current object attached.
   */
  function openPluginDesigner() {
    const clip = selectedClip ? clips.find((item) => item.id === selectedClip) : null;
    const track = tracks.find((item) => item.id === selectedTrack) ?? tracks[0];
    setDesignContext(clip?.title || track?.name || "Studio");
    setDesignMode(true);
    setDesignRequest(null);
    setDesignBuilt(null);
    setAssistantOpen(false);
    setPromptValue(DESIGN_PROMPT);
    window.setTimeout(() => {
      const input = promptRef.current?.querySelector("input");
      input?.focus();
      input?.setSelectionRange(input.value.length, input.value.length);
    }, 0);
  }

  function exitPluginDesigner() {
    setDesignMode(false);
    setDesignContext(null);
    setDesignRequest(null);
    setDesignBuilt(null);
    setPromptValue("");
  }

  /** Design mode's send: restate the request and ask before building anything. */
  function startPluginDesign(prompt: string) {
    const result = designPlugin(prompt, customPlugins.map((plugin) => plugin.name));
    setAssistantOpen(true);
    setPendingSong(null);
    setDesignBuilt(null);
    setDesignRequest(result);
    setAssistantMessages([
      { id: `u-${Date.now()}`, role: "user", text: prompt },
      { id: `d-${Date.now()}`, role: "design", text: result.restate },
    ]);
    setPromptValue("");
  }

  /** Save the designed plugin to MY PLUGINS; it is never auto-inserted. */
  function buildDesignedPlugin() {
    if (!designRequest) return;
    const result = designRequest;
    const data = currentData() as Record<string, unknown>;
    const existing = Array.isArray(data.customPlugins) ? data.customPlugins : [];
    writeProjectData(
      { ...data, customPlugins: [...existing, result.plugin] },
      "a designed plugin"
    );
    setDesignRequest(null);
    setDesignBuilt(result);
    setAssistantMessages((current) => [
      ...current,
      { id: `r-${Date.now()}`, role: "result", text: result.completion },
    ]);
  }

  /** Return to the prompt with the original wording so the user can edit it. */
  function revisePluginDesign() {
    const original = assistantMessages.find((message) => message.role === "user")?.text;
    setDesignRequest(null);
    setPromptValue(original ?? DESIGN_PROMPT);
    window.setTimeout(() => {
      const input = promptRef.current?.querySelector("input");
      input?.focus();
      input?.setSelectionRange(0, input.value.length);
    }, 0);
  }

  /** Insert a built plugin into a track's chain (drag target or the card button). */
  function addDesignedToTrack(custom: CustomPlugin, trackId?: string) {
    const target = trackId ?? selectedTrack ?? tracks[0]?.id;
    if (!target) return;
    const current = chains[target] ?? [];
    commitChain(target, addCustomPlugin(current, custom));
    setSelectedTrack(target);
    setExportToast(`${custom.name} added to the track.`);
  }

  /** Prompt bar (S16): generate inline, then place the result at the playhead. */
  async function submitPrompt(raw: string) {
    const prompt = raw.trim();
    if (!prompt || promptBusy) return;
    if (designMode) {
      startPluginDesign(prompt);
      return;
    }
    setPromptBusy(true);
    setAssistantOpen(true);
    setPendingSong(null);
    setPromptNotice(null);
    setAssistantMessages([{ id: `u-${Date.now()}`, role: "user", text: prompt }]);
    const statusId = `s-${Date.now()}`;
    setAssistantMessages((current) => [
      ...current,
      { id: statusId, role: "status", text: "Generating…" },
    ]);
    try {
      const created = await generateSong({
        mode: "simple",
        prompt,
        model: STUDIO_MODEL_API[promptModel] ?? "V6",
      });
      const deadline = Date.now() + 180_000;
      let generation: WebMusicGeneration | null = null;
      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        const current = await fetchGeneration(created.task_id);
        if (current.status === "complete" || current.status === "ready") {
          generation = current;
          break;
        }
        if (current.status === "error" || current.status === "failed") {
          throw new Error(current.error_message || "Generation failed.");
        }
      }
      if (!generation) throw new Error("Generation timed out.");
      const finished = generation;
      setLibrarySongs((previous) => (previous ? [finished, ...previous] : [finished]));
      setPendingSong(finished);
      setAssistantMessages((current) =>
        current.map((message) =>
          message.id === statusId
            ? {
                ...message,
                role: "result",
                text: `Created ${finished.title || "a new part"}. Audition it or commit it to the track.`,
              }
            : message
        )
      );
      setPromptValue("");
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Generation failed.";
      const copy = classifyStudioError(message, "Generation failed.");
      if (copy.kind === "credits") {
        setPromptNotice({ kind: "credits", text: copy.text });
      } else if (copy.kind === "policy") {
        setPromptNotice({ kind: "moderation", text: copy.text });
      }
      setAssistantMessages((current) =>
        current.map((item) =>
          item.id === statusId ? { ...item, role: "status", text: "Generation stopped." } : item
        )
      );
    } finally {
      setPromptBusy(false);
    }
  }

  /** Insert one take (generation clip) at the playhead on the selected track. */
  function commitTake(song: WebMusicGeneration, take: { variant: string; title?: string; audio_url?: string | null; duration_seconds?: number | null }) {
    const trackId = selectedTrack ?? tracks[0]?.id;
    if (!trackId || !take.audio_url) return;
    const start = snapToGrid(playhead, secondsPerBar, beatsPerBar);
    // S29: regenerating over an existing audio clip stacks a take instead of adding a clip.
    const owner = tracks.find((track) => track.id === trackId);
    const existing = owner
      ? clips.find(
          (clip) =>
            owner.clipIds.includes(clip.id) &&
            !clip.midi &&
            clip.audioUrl &&
            Math.abs((clip.start ?? 0) - start) < 0.05
        )
      : undefined;
    if (existing) {
      const title = take.title || song.title || "Take";
      const nextTake = {
        id: `take-${song.id}-${take.variant}-${Date.now().toString(36)}`,
        title,
        audioUrl: take.audio_url,
        duration: take.duration_seconds ?? existing.duration ?? 8,
        active: true,
      };
      const prior =
        existing.takes && existing.takes.length
          ? existing.takes.map((item) => ({ ...item, active: false }))
          : [
              {
                id: `take-base-${existing.id}`,
                title: existing.title || "Original",
                audioUrl: existing.audioUrl,
                duration: existing.duration ?? 8,
                active: false,
              },
            ];
      const updated: ClipLike = {
        ...existing,
        audioUrl: nextTake.audioUrl,
        duration: nextTake.duration,
        takes: [nextTake, ...prior],
      };
      const lanes = clips.map((clip) => (clip.id === existing.id ? updated : clip));
      const data = currentData() as Record<string, unknown>;
      writeProjectData({ ...data, lanes }, "a take");
      setSelectedClip(existing.id);
      setTakeLanesOpen(true);
      setExportToast("Take added to the clip.");
      return;
    }
    insertClips([
      {
        trackId,
        clip: {
          id: `clip-${song.id}-${take.variant}-${Date.now().toString(36)}`,
          title: take.title || song.title || "Song",
          start: snapToGrid(playhead, secondsPerBar, beatsPerBar),
          duration: take.duration_seconds ?? 8,
          volume: 1,
          pan: 0,
          audioUrl: take.audio_url,
          songId: song.id,
        },
      },
    ]);
    setExportToast("Take added to the track at the playhead.");
  }

  /** Make one take active; the clip's audio mirrors it (S29). */
  function activateTake(clipId: string, takeId: string) {
    const data = currentData() as Record<string, unknown>;
    const lanes = clips.map((clip) => {
      if (clip.id !== clipId) return clip;
      const takes = (clip.takes ?? []).map((take) => ({ ...take, active: take.id === takeId }));
      const active = takes.find((take) => take.active);
      return {
        ...clip,
        takes,
        audioUrl: active?.audioUrl ?? clip.audioUrl,
        duration: active?.duration ?? clip.duration,
      };
    });
    writeProjectData({ ...data, lanes }, "the active take");
  }

  /** Audition a single take from the assistant panel. */
  function toggleTakePreview(url: string) {
    if (previewingUrl === url) {
      previewRef.current?.pause();
      previewRef.current = null;
      setPreviewingUrl(null);
      return;
    }
    previewRef.current?.pause();
    const audio = new Audio(url);
    previewRef.current = audio;
    setPreviewingUrl(url);
    setPlayingSongId(null);
    setPlayingUploadId(null);
    audio.onended = () => setPreviewingUrl((current) => (current === url ? null : current));
    void audio.play().catch(() => setPreviewingUrl((current) => (current === url ? null : current)));
  }

  const railOpen = libraryOpen || inspectorOpen;

  /** The MIDI clip open in the bottom editor, if any (notes coerced to the model). */
  const midiKey = String((currentData() as { key?: unknown }).key ?? "C");
  const midiScale = String((currentData() as { scale?: unknown }).scale ?? "off");

  const midiClipSource = midiClipId ? clips.find((clip) => clip.id === midiClipId) : undefined;
  const midiClip = midiClipSource
    ? {
        ...midiClipSource,
        midi: {
          notes: sanitizeNotes(midiClipSource.midi?.notes),
          bend: sanitizePoints(midiClipSource.midi?.bend, -1, 1),
          mod: sanitizePoints(midiClipSource.midi?.mod, 0, 1),
        },
      }
    : undefined;

  /** The audio clip open in the bottom editor, if any (S30). */
  const audioClip = audioClipId ? clips.find((clip) => clip.id === audioClipId) : undefined;

  return (
    <>
      {/* The reference gates Studio below 768 px (S65): desktop-only notice. */}
      <div className="se-desktop-gate">
        <div className="se-gate-card">
          <div className="se-gate-art" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div className="se-gate-body">
            <h1>CAMXORA Studio</h1>
            <p>
              Studio is desktop-only. Open CAMXORA on a larger screen to keep working on this
              project.
            </p>
            <Link className="se-gate-link" href="/create">
              Back to Create
            </Link>
          </div>
        </div>
      </div>
      <div
      className={`se-shell${touchMode ? " is-touch" : ""}${railOpen ? " has-rail" : ""}${
        assistantOpen ? " has-assistant" : ""
      }`}
    >
      <StudioHeader
        title={project?.title || "Untitled project"}
        projectId={projectId}
        settings={settings}
        onSettingsChange={(next) => {
          setSettings(next);
          writeStudioSettings(next);
        }}
        onRenamed={(next) => setProject((current) => (current ? { ...current, title: next } : current))}
        onShowQuickStart={() => setQuickStartToken((value) => value + 1)}
        timeSignature={timeSignature}
        onTimeSignature={(next) => {
          setTimeSignature(next);
          if (!projectId) return;
          persist(
            (expected) =>
              updateStudioProject(projectId, { time_signature: next, expectedUpdatedAt: expected }),
            "Could not save the time signature."
          );
        }}
        clock={clock(playhead)}
        barBeat={barBeat(playhead, bpm, timeSignature)}
        bpm={bpm}
        onBpmChange={setBpm}
        onBpmCommit={() => {
          if (!projectId) return;
          persist(
            (expected) => updateStudioProject(projectId, { bpm, expectedUpdatedAt: expected }),
            "Could not save the tempo."
          );
        }}
        playing={playing}
        loop={loop}
        metronome={metronome}
        canUndo={historyState.canUndo}
        canRedo={historyState.canRedo}
        saveStatus={saveStatus}
        onRetrySave={() => retryRef.current?.()}
        meter={meter}
        playbackRate={playbackRate}
        onCycleSpeed={() => setPlaybackRate((current) => (current === 1 ? 0.5 : current === 0.5 ? 2 : 1))}
        exportOpen={exportOpen}
        exporting={exporting}
        rangeReady={Boolean(timeSelection) || loopEnd > loopStart}
        onToggleExport={() => setExportOpen((open) => !open)}
        onExport={(scope) => void runExport(scope)}
        normalise={exportNormalise}
        onToggleNormalise={() => setExportNormalise((value) => !value)}
        libraryOpen={libraryOpen}
        onToggleLibrary={() => toggleLibrary()}
        onBackToStart={() => { setPlaying(false); void stopAudio(); setPlayhead(0); }}
        onStop={() => {
          // Stop halts the transport where it is; Back to start is the rewind.
          if (recording) stopRecording();
          setPlaying(false);
          void stopAudio();
          stopClicks();
        }}
        onTogglePlay={togglePlayback}
        recording={recording}
        onToggleRecord={toggleRecord}
        recordDisabled={!tracks.some((track) => track.armed)}
        recordTitle={tracks.some((track) => track.armed) ? undefined : "Arm a track first"}
        inputDeviceId={settings.inputDeviceId}
        inputDevices={inputDevices}
        inputOpen={inputOpen}
        onToggleInput={() => void toggleInputPicker()}
        onPickInput={pickInputDevice}
        countIn={settings.countIn}
        onToggleCountIn={toggleCountInSetting}
        countInBeat={countInBeat}
        onToggleLoop={toggleLoop}
        onToggleMetronome={() =>
          setMetronome((value) => {
            if (value) {
              stopClicks();
              return false;
            }
            scheduledThroughRef.current = playheadRef.current;
            return true;
          })
        }
        beat={metronome ? beatAt(playhead, bpm, beatsPerBar) : 0}
        onUndo={undo}
        onRedo={redo}
      />

      <div className={`se-body${libraryOpen ? " with-library" : ""}`} role="main">
        <h1 className="se-sr-only">{project?.title || "Studio project"}</h1>
        <StudioTrackPanel
          tracks={tracks}
          selectedTrack={selectedTrack}
          menuTrackId={menuTrackId}
          renameTrackId={renameTrackId}
          renameValue={renameValue}
          hiddenOpen={hiddenOpen}
          collapsed={tracksCollapsed}
          onToggleCollapsed={() => setTracksCollapsed((value) => !value)}
          onSelectTrack={(trackId) => {
            setMasterSelected(false);
            setSelectedTrack(trackId);
          }}
          onToggleMenu={setMenuTrackId}
          onToggleFlag={toggleTrackFlag}
          onToggleArm={toggleArm}
          onUpdateTrack={updateTrack}
          onPreviewTrack={previewTrack}
          onRenameStart={startRename}
          onRenameChange={setRenameValue}
          onRenameCommit={commitRename}
          onRenameCancel={() => setRenameTrackId(null)}
          onDuplicate={duplicateTrack}
          onBounce={(trackId) => void bounceTrack(trackId)}
          bouncingTrackId={bouncingTrack}
          onHide={hideTrack}
          onDelete={deleteTrack}
          onAddTrack={addTrack}
          onAddMidiTrack={addMidiTrack}
          masterSelected={masterSelected}
          onSelectMaster={() => {
            setMasterSelected(true);
            setMidiClipId(null);
          }}
          onDropPlugin={(trackId, payload) => {
            try {
              const parsed = sanitizeCustomPlugin(JSON.parse(payload));
              if (parsed) addDesignedToTrack(parsed, trackId);
            } catch {
              /* not one of our cards */
            }
          }}
          onAddUploadTrack={openUploadLibrary}
          onToggleHidden={() => setHiddenOpen((open) => !open)}
          onShowAllHidden={showAllHidden}
          onToggleAllCollapsed={toggleAllCollapsed}
          masterVolume={masterVolume}
          masterMuted={masterMuted}
          onMasterVolume={(value) => {
            setMasterVolume(value);
            applyMasterGain(value, masterMuted);
          }}
          onMasterCommit={() => commitMaster()}
          onToggleMasterMute={() => {
            const next = !masterMuted;
            setMasterMuted(next);
            applyMasterGain(masterVolume, next);
            commitMaster(masterVolume, next);
          }}
        />

        <StudioTimeline
          tracks={tracks}
          clips={clips}
          barWidth={barWidth}
          barCount={barCount}
          secondsPerBar={secondsPerBar}
          beatsPerBar={beatsPerBar}
          duration={duration}
          playhead={playhead}
          clock={clock}
          rowStep={ROW_STEP}
          selectedTrack={selectedTrack}
          selectedClip={selectedClip}
          selectedIds={selectedIds}
          drag={drag}
          marquee={marquee}
          loop={loop}
          loopStart={loopStart}
          loopEnd={loopEnd}
          timeSelection={timeSelection}
          markers={markers}
          onMarkerClick={seekTo}
          onMarkerRemove={removeSectionMarker}
          viewWidth={view.width}
          viewLeft={view.left}
          trimPreview={trimPreview}
          fadePreview={fadePreview}
          timelineRef={timelineRef}
          onScroll={(left, width) => setView({ left, width })}
          onLanePointerDown={handleLanePointerDown}
          onLaneDragOver={(event) => {
            if (event.dataTransfer.types.includes(SONG_DRAG_TYPE)) event.preventDefault();
          }}
          onLaneDrop={(event, trackId) => dropSongOnLane(event, trackId)}
          onRulerPointerDown={handleRulerPointerDown}
          onRulerContextMenu={handleRulerContextMenu}
          onRangeHandleDown={handleRangeHandleDown}
          onClipPointerDown={handleClipPointerDown}
          onClipDoubleClick={handleClipDoubleClick}
          onClipContextMenu={handleClipContextMenu}
          onTrimPointerDown={handleTrimPointerDown}
          onFadePointerDown={handleFadePointerDown}
          onLoopHandleDown={(event) => {
            event.stopPropagation();
            loopDragRef.current = true;
          }}
        />

        {(() => {
          const inspected = inspectorOpen
            ? clips.find((clip) => clip.id === selectedClip)
            : undefined;
          if (inspected) {
            const owner = tracks.find((track) => track.clipIds.includes(inspected.id));
            return (
              <StudioClipInfo
                width={LIBRARY_W}
                clip={inspected}
                trackName={owner?.name}
                source={clipSource}
                stems={stems}
                onRequestStems={openStemsDialog}
                onClose={() => setInspectorOpen(false)}
              />
            );
          }
          if (libraryOpen && detailSong) {
            const detailClip =
              detailSong.clips?.find((candidate) => candidate.audio_url) ?? detailSong.clips?.[0];
            const detailKey = detailClip ? `${detailSong.id}:${detailClip.variant}` : "";
            return (
              <StudioSongDetail
                width={LIBRARY_W}
                song={detailSong}
                liked={(likedKeys ?? []).includes(detailKey)}
                disliked={(dislikedKeys ?? []).includes(detailKey)}
                playing={playingSongId === detailSong.id}
                onBack={() => setDetailSong(null)}
                onClose={() => {
                  setDetailSong(null);
                  setLibraryOpen(false);
                }}
                onTogglePlay={toggleSongPreview}
                onToggleLike={(song, next) => void toggleSongLike(song, next)}
                onToggleDislike={(song, next) => void toggleSongDislike(song, next)}
                projectId={projectId}
                commentAuthor={user?.email?.split("@")[0] || "You"}
                remixing={remixingSongId === detailSong.id}
                onRemix={(song) => void remixSong(song)}
              onAddToProject={addSongToTimeline}
              onDownloadWav={(song) => void downloadSongWav(song)}
              onTrash={(song) => void trashSong(song)}
              />
            );
          }
          if (!libraryOpen) return null;
          return (
            <StudioLibrary
              ref={librarySearchRef}
              width={LIBRARY_W}
              view={libraryView}
              query={libraryQuery}
              onQuery={setLibraryQuery}
              songs={librarySongs}
              workspaces={libraryWorkspaces}
              activeWorkspaceId={libraryWorkspaceId}
              projects={libraryProjects}
              uploads={libraryUploads}
              stems={libraryStems}
              currentProjectId={projectId}
              likedKeys={likedKeys}
              playingSongId={playingSongId}
              playingUploadId={playingUploadId}
              playingStemId={playingStemId}
              projectSongIds={projectSongIds}
              error={libraryError}
              onRetry={retryLibrary}
              onOpenSong={(song) => setDetailSong(song)}
              onClose={() => setLibraryOpen(false)}
              onBack={() => setLibraryView({ kind: "root" })}
              onOpenSongs={openLibrarySongs}
              onOpenStems={() => setLibraryView({ kind: "stems" })}
              onOpenUploads={() => setLibraryView({ kind: "uploads" })}
              onOpenWorkspace={openLibraryWorkspace}
              onFilter={setLibrarySongFilter}
              onNewWorkspace={createLibraryWorkspace}
              onNewSong={() => {
                window.location.href = "/create";
              }}
              onUploadAudio={uploadLibraryAudio}
              onAddSong={addSongToTimeline}
              onTogglePlay={toggleSongPreview}
              onToggleLike={(song, nextLiked) => void toggleSongLike(song, nextLiked)}
              onToggleUploadPlay={toggleUploadPreview}
              onAddUpload={addUploadToTimeline}
              onToggleStemPlay={toggleStemPreview}
              onAddStem={addStemToTimeline}
              onOpenProject={(id) => {
                window.location.href = `/studio/editor?project=${encodeURIComponent(id)}`;
              }}
            />
          );
        })()}

        {/* Captured prompt bar (S16/S36/S38/S45): attach, prompt, model, send. */}
        <form
          className={`se-prompt${designMode ? " is-design" : ""}`}
          ref={promptRef}
          onSubmit={(event) => {
            event.preventDefault();
            void submitPrompt(promptValue);
          }}
        >
          <span className="se-prompt-badge">BETA</span>
          <div className="se-prompt-top">
            <button
              type="button"
              className="se-prompt-attach"
              aria-label="Attach a track or clip"
              aria-haspopup="menu"
              aria-expanded={attachOpen}
              onClick={() => setAttachOpen((open) => !open)}
            >
              <Icon name="fa-plus" />
            </button>
            {designMode && designContext ? (
              <span className="se-prompt-context is-plugin">
                <Icon name="fa-wave-square" />
                {designContext}
                <button type="button" aria-label="Exit plugin designer" onClick={exitPluginDesigner}>
                  <Icon name="fa-xmark" />
                </button>
              </span>
            ) : selectedTrack ? (
              <span className="se-prompt-context">
                {attachedClipId === selectedClip && attachedClipId ? (
                  <Icon name="fa-wave-square" />
                ) : null}
                {(attachedClipId === selectedClip &&
                  clips.find((clip) => clip.id === attachedClipId)?.title) ||
                  tracks.find((track) => track.id === selectedTrack)?.name ||
                  "Track"}
                <button
                  type="button"
                  aria-label="Clear track context"
                  onClick={() => {
                    setAttachedClipId(null);
                    setSelectedTrack(null);
                    setSelectedClip(null);
                  }}
                >
                  <Icon name="fa-xmark" />
                </button>
              </span>
            ) : null}
            <span className="se-prompt-tools">
              <button
                type="button"
                aria-label={assistantOpen ? "Dock prompt to the centre" : "Open conversation"}
                aria-pressed={assistantOpen}
                onClick={() => setAssistantOpen((open) => !open)}
              >
                <Icon name={assistantOpen ? "fa-up-right-and-down-left-from-center" : "fa-table-columns"} />
              </button>
              <button
                type="button"
                aria-label={designMode ? "Exit plugin designer" : "Clear prompt"}
                onClick={() => {
                  if (designMode) exitPluginDesigner();
                  else setPromptValue("");
                }}
              >
                <Icon name="fa-xmark" />
              </button>
            </span>
          </div>
          {attachOpen ? (
            <div className="se-prompt-attach-menu" role="menu" aria-label="Attach to the prompt">
              {tracks.map((track) => (
                <button
                  key={track.id}
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setAttachedClipId(null);
                    setSelectedTrack(track.id);
                    setSelectedClip(null);
                    setAttachOpen(false);
                  }}
                >
                  <Icon name="fa-layer-group" /> {track.name}
                </button>
              ))}
              {clips.slice(0, 6).map((clip) => {
                const owner = tracks.find((track) => track.clipIds.includes(clip.id));
                return (
                  <button
                    key={clip.id}
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      if (owner) setSelectedTrack(owner.id);
                      setSelectedClip(clip.id);
                      setAttachedClipId(clip.id);
                      setAttachOpen(false);
                    }}
                  >
                    <Icon name="fa-wave-square" /> {clip.title || "Clip"}
                  </button>
                );
              })}
            </div>
          ) : null}
          <div className="se-prompt-line">
            <input
              className="se-prompt-input"
              value={promptValue}
              disabled={promptBusy}
              onChange={(event) => setPromptValue(event.target.value)}
              placeholder={
                designMode
                  ? "Make me a new plugin. Here's what I have in mind:"
                  : promptBusy
                    ? "Generating…"
                    : "Describe a part to generate"
              }
              aria-label="Describe a part to generate"
            />
            {!designMode && !promptValue.trim() ? <kbd className="se-prompt-kbd">Tab</kbd> : null}
          </div>
          {modelOpen ? (
            <div className="se-model-menu" role="listbox" aria-label="Generation model">
              <div className="se-model-custom" aria-disabled="true">
                <span>Create Custom Model</span>
                <span className="se-model-credits">100 Credits</span>
              </div>
              <p className="se-model-label">All models</p>
              {(
                [
                  ["v6", "Balanced, high-fidelity generations"],
                  ["v6-wild", "Wilder variations for experiments"],
                  ["v6-mini", "Faster, lighter generations"],
                ] as const
              ).map(([value, description]) => (
                <button
                  key={value}
                  type="button"
                  role="option"
                  aria-selected={promptModel === value}
                  className={promptModel === value ? "on" : undefined}
                  onClick={() => {
                    setPromptModel(value);
                    setModelOpen(false);
                  }}
                >
                  <strong>{value}</strong>
                  <small>{description}</small>
                </button>
              ))}
            </div>
          ) : null}
          <div className="se-prompt-actions">
            <button
              type="button"
              className="se-prompt-model"
              aria-haspopup="listbox"
              aria-expanded={modelOpen}
              aria-label={`Generation model: ${promptModel}`}
              onClick={() => setModelOpen((open) => !open)}
            >
              {promptModel} <Icon name="fa-chevron-down" />
            </button>
            <button
              type="submit"
              className={`se-prompt-send${designMode && promptValue.trim() ? " is-active" : ""}`}
              aria-label={designMode ? "Design this plugin" : "Generate this part"}
              title={designMode ? "Builds a plugin, no credits spent" : "Generates with your account credits"}
              disabled={!promptValue.trim() || promptBusy}
            >
              <Icon name="fa-arrow-up" />
            </button>
          </div>
        </form>
      </div>

      {assistantOpen ? (
        <aside className="se-assistant" aria-label="Studio assistant">
          <header className="se-assistant-head">
            <p className="se-assistant-note">
              Chat is powered by AI and can make mistakes
              <button
                type="button"
                className="se-icon"
                aria-label="Close assistant"
                onClick={() => setAssistantOpen(false)}
              >
                <Icon name="fa-xmark" />
              </button>
            </p>
          </header>
          <div className="se-assistant-log">
            {promptNotice ? (
              <div className={`se-assistant-notice ${promptNotice.kind}`} role="alert">
                <strong>
                  {promptNotice.kind === "credits" ? "Not enough credits" : "That prompt was refused"}
                </strong>
                <span>
                  {promptNotice.kind === "credits"
                    ? "Your balance does not cover this generation. Top up or pick a lighter model."
                    : "The content policy blocked this request. Try rewording the prompt."}
                </span>
                {promptNotice.kind === "credits" ? (
                  <a className="se-pill on" href="/pricing">
                    View plans
                  </a>
                ) : (
                  <button
                    type="button"
                    className="se-pill on"
                    onClick={() => promptRef.current?.querySelector("input")?.focus()}
                  >
                    Edit prompt
                  </button>
                )}
                <small>{promptNotice.text}</small>
              </div>
            ) : null}
            {assistantMessages.length === 0 && !pendingSong && !designRequest && !designBuilt ? (
              <p className="se-assistant-invite">
                Describe a section or ask for ideas to start a conversation with the Studio Agent.
              </p>
            ) : null}
            {assistantMessages.map((message) => (
              <p key={message.id} className={`se-assistant-msg ${message.role}`}>
                {message.text}
              </p>
            ))}
            {designRequest ? (
              <div className="se-design-actions">
                <button type="button" className="se-pill on" onClick={buildDesignedPlugin}>
                  Build it
                </button>
                <button type="button" className="se-pill" onClick={revisePluginDesign}>
                  Change something…
                </button>
              </div>
            ) : null}
            {designBuilt ? (
              <div
                className="se-design-card"
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.setData(
                    "application/x-camxora-plugin",
                    JSON.stringify(designBuilt.plugin)
                  );
                  event.dataTransfer.effectAllowed = "copy";
                }}
                aria-label={`${designBuilt.plugin.name}, designed plugin`}
              >
                <span className="se-design-grip" aria-hidden="true">
                  <Icon name="fa-grip-vertical" />
                </span>
                <span className="se-design-body">
                  <strong>{designBuilt.plugin.name}</strong>
                  <span className="se-design-sub">{DESIGN_CARD_SUBTITLE}</span>
                </span>
                <button
                  type="button"
                  className="se-pill on"
                  onClick={() => addDesignedToTrack(designBuilt.plugin)}
                  disabled={tracks.length === 0}
                >
                  Add to track
                </button>
              </div>
            ) : null}
            {pendingSong
              ? (pendingSong.clips ?? [])
                  .filter((take) => take.audio_url)
                  .map((take, index) => (
                    <div key={`${pendingSong.id}-${take.variant}`} className="se-assistant-take">
                      <span>Take {index + 1}</span>
                      <button
                        type="button"
                        className="se-pill"
                        onClick={() => take.audio_url && toggleTakePreview(take.audio_url)}
                      >
                        {previewingUrl === take.audio_url ? "Pause" : "Audition"}
                      </button>
                      <button
                        type="button"
                        className="se-pill on"
                        onClick={() => commitTake(pendingSong, take)}
                        disabled={tracks.length === 0}
                      >
                        Commit
                      </button>
                    </div>
                  ))
              : null}
          </div>
        </aside>
      ) : null}

      <StudioOnboarding
        projectId={projectId}
        isEmpty={!loading && tracks.length === 0 && clips.length === 0}
        reopenToken={quickStartToken}
      />

      <StudioMetricsProbe />

      {/* Floating menus live outside <main>; a named region keeps them inside a
          landmark for assistive tech (axe: region rule). */}
      <div role="region" aria-label="Editor menus">
      {clipMenu
        ? (() => {
            const clip = clips.find((item) => item.id === clipMenu.clipId);
            const owner = tracks.find((track) => clip && track.clipIds.includes(clip.id));
            if (!clip) return null;
            const start = clip.start ?? 0;
            const duration = clip.duration ?? 4;
            const canSplit = playhead > start + 0.001 && playhead < start + duration - 0.001;
            const midiSelection = (
              activeClipIds().length > 0 ? activeClipIds() : [clip.id]
            )
              .map((id) => clips.find((item) => item.id === id))
              .filter((item) => Boolean(item?.midi?.notes?.length));
            const mashupSources = (selectedIds.length >= 2 ? selectedIds : [])
              .map((id) => clips.find((item) => item.id === id))
              .filter((item) => Boolean(item?.songId));
            const canMashup = mashupSources.length === 2;
            const clipStart = clip.start ?? 0;
            const clipEnd = clipStart + (clip.duration ?? 4);
            const canReplace = Boolean(
              clip.songId &&
                timeSelection &&
                timeSelection.end > timeSelection.start &&
                Math.min(timeSelection.end, clipEnd) - Math.max(timeSelection.start, clipStart) >
                  0.05
            );
            return (
              <div
                className="se-clip-menu"
                role="menu"
                aria-label="Clip options"
                style={{
                  left: Math.min(clipMenu.x, Math.max(8, window.innerWidth - 200)),
                  top: Math.min(clipMenu.y, Math.max(8, window.innerHeight - 400)),
                  // The menu grew with the Generate rows; cap it to the space below its
                  // anchor so it scrolls instead of running off-screen.
                  maxHeight: Math.max(
                    160,
                    window.innerHeight - Math.min(clipMenu.y, Math.max(8, window.innerHeight - 400)) - 8
                  ),
                }}
              >
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    copySelection();
                    setClipMenu(null);
                  }}
                >
                  <Icon name="fa-copy" /> Copy <span>Ctrl C</span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  disabled={clipboardRef.current.length === 0}
                  onClick={() => {
                    pasteSelection();
                    setClipMenu(null);
                  }}
                >
                  <Icon name="fa-paste" /> Paste <span>Ctrl V</span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    duplicateSelection();
                    setClipMenu(null);
                  }}
                >
                  <Icon name="fa-clone" /> Duplicate <span>Ctrl D</span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    deleteSelection();
                    setClipMenu(null);
                  }}
                >
                  <Icon name="fa-trash" /> Delete <span>Backspace</span>
                </button>
                <div className="se-clip-menu-sep" />
                <button
                  type="button"
                  role="menuitem"
                  disabled
                  title="Heal Edits is not built in this editor"
                >
                  <Icon name="fa-wand-magic" /> Heal Edits
                </button>
                <button
                  type="button"
                  role="menuitem"
                  disabled={!canSplit}
                  onClick={() => {
                    splitClips([clip.id], playhead);
                    setClipMenu(null);
                  }}
                >
                  <Icon name="fa-scissors" /> Split <span>Ctrl E</span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    createSectionFromClip(clip);
                    setClipMenu(null);
                  }}
                >
                  <Icon name="fa-flag" /> Create Section
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setClipRename({ id: clip.id, value: clip.title || "" });
                    setClipMenu(null);
                  }}
                >
                  <Icon name="fa-pen" /> Rename
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setClipMenu(null);
                    setLibraryOpen(false);
                    setInspectorOpen(true);
                  }}
                >
                  <Icon name="fa-info-circle" /> Clip Info
                </button>
                <div className="se-menu-sub">
                  <button
                    type="button"
                    role="menuitem"
                    aria-haspopup="true"
                    aria-expanded={clipColorOpen}
                    onClick={() => setClipColorOpen((open) => !open)}
                  >
                    <Icon name="fa-circle" /> Clip Color <Icon name="fa-chevron-right" />
                  </button>
                  {clipColorOpen ? (
                    <div className="se-clip-menu-colors" role="group" aria-label="Clip colour">
                      <button
                        type="button"
                        className="se-color-auto"
                        aria-pressed={!clip.color}
                        onClick={() => {
                          setClipColor(clip.id, "");
                          setClipMenu(null);
                        }}
                      >
                        <span className="se-color-dot" aria-hidden="true" />
                        Auto
                        {!clip.color ? <Icon name="fa-check" /> : null}
                      </button>
                      <div className="se-color-grid">
                        {CLIP_COLORS.map((color) => (
                          <button
                            key={color}
                            type="button"
                            aria-label={`Clip colour ${color}`}
                            style={{ background: color }}
                            className={clip.color === color ? "on" : undefined}
                            onClick={() => {
                              setClipColor(clip.id, color);
                              setClipMenu(null);
                            }}
                          />
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
                <div className="se-clip-menu-sep" />
                <button
                  type="button"
                  role="menuitem"
                  disabled={!clip.songId}
                  title={clip.songId ? undefined : "No source generation for this clip"}
                  onClick={() => {
                    setClipMenu(null);
                    openStemsDialog();
                  }}
                >
                  <Icon name="fa-wand-magic-sparkles" /> Get Stems
                </button>
                <div className="se-clip-menu-sep" />
                <button
                  type="button"
                  role="menuitem"
                  disabled={!clip.songId || Boolean(transformBusy)}
                  title={
                    clip.songId
                      ? "Continue this clip after itself"
                      : "No source generation for this clip"
                  }
                  onClick={() => void runTransform("extend", clip.id)}
                >
                  <Icon name="fa-arrow-right" /> Extend
                </button>
                <button
                  type="button"
                  role="menuitem"
                  disabled={!clip.songId || Boolean(transformBusy)}
                  title={
                    clip.songId
                      ? "Re-sing this clip in a new style"
                      : "No source generation for this clip"
                  }
                  onClick={() => {
                    setClipMenu(null);
                    setTransformValue("");
                    setTransformPrompt({ clipId: clip.id, kind: "cover" });
                  }}
                >
                  <Icon name="fa-music" /> Cover…
                </button>
                <button
                  type="button"
                  role="menuitem"
                  disabled={!clip.songId || Boolean(transformBusy)}
                  title={
                    clip.songId
                      ? `Clean up and re-master this clip${transformCost != null ? ` (${transformCost} credits)` : ""}`
                      : "No source generation for this clip"
                  }
                  onClick={() => void runTransform("remaster", clip.id)}
                >
                  <Icon name="fa-wand-magic" /> Remaster
                </button>
                <button
                  type="button"
                  role="menuitem"
                  disabled={!clip.songId || Boolean(transformBusy)}
                  title={
                    clip.songId
                      ? `Sing over this clip${transformCost != null ? ` (${transformCost} credits)` : ""}`
                      : "No source generation for this clip"
                  }
                  onClick={() => {
                    setClipMenu(null);
                    setTransformValue("");
                    setTransformPrompt({ clipId: clip.id, kind: "vocals" });
                  }}
                >
                  <Icon name="fa-microphone" /> Vocals…
                </button>
                <button
                  type="button"
                  role="menuitem"
                  disabled={!clip.songId || Boolean(transformBusy)}
                  title={
                    clip.songId
                      ? `Add an instrumental to this clip${transformCost != null ? ` (${transformCost} credits)` : ""}`
                      : "No source generation for this clip"
                  }
                  onClick={() => {
                    setClipMenu(null);
                    setTransformValue("");
                    setTransformPrompt({ clipId: clip.id, kind: "instrumental" });
                  }}
                >
                  <Icon name="fa-wave-square" /> Instrumental…
                </button>
                <button
                  type="button"
                  role="menuitem"
                  disabled={!canMashup || Boolean(transformBusy)}
                  title={
                    canMashup
                      ? `Combine the two selected clips${transformCost != null ? ` (${transformCost} credits)` : ""}`
                      : "Select two clips that have a source generation"
                  }
                  onClick={() => {
                    setClipMenu(null);
                    setTransformValue("");
                    setMashupIds(
                      mashupSources
                        .map((item) => item?.id)
                        .filter((id): id is string => Boolean(id))
                    );
                    setTransformPrompt({ clipId: clip.id, kind: "mashup" });
                  }}
                >
                  <Icon name="fa-shuffle" /> Mashup…
                </button>
                <button
                  type="button"
                  role="menuitem"
                  disabled={!canReplace || Boolean(transformBusy)}
                  title={
                    canReplace
                      ? `Rewrite the selected range with new lyrics${transformCost != null ? ` (${transformCost} credits)` : ""}`
                      : "Select a time range over this clip first"
                  }
                  onClick={() => {
                    setClipMenu(null);
                    setTransformValue("");
                    setTransformLyrics("");
                    setTransformPrompt({ clipId: clip.id, kind: "replace" });
                  }}
                >
                  <Icon name="fa-scissors" /> Replace…
                </button>
                <div className="se-clip-menu-sep" />
                <button
                  type="button"
                  role="menuitem"
                  disabled={!clip.audioUrl}
                  onClick={() => void downloadClipWav(clip.id)}
                >
                  <Icon name="fa-download" /> Download WAV
                </button>
                <button
                  type="button"
                  role="menuitem"
                  disabled={midiSelection.length === 0}
                  title={
                    midiSelection.length === 0
                      ? "Select a MIDI clip with notes first"
                      : "Download the selected MIDI clips as one .mid file"
                  }
                  onClick={() => downloadMidi(clip.id)}
                >
                  <Icon name="fa-music" /> Download MIDI
                </button>
                <button
                  type="button"
                  role="menuitem"
                  disabled
                  title="MIDI conversion is not built in this editor"
                >
                  <Icon name="fa-music" /> Get MIDI
                </button>
                <button
                  type="button"
                  role="menuitem"
                  disabled={!owner || (chains[owner.id] ?? []).length === 0}
                  title={
                    owner
                      ? "Remove every plugin from this clip's track"
                      : "No track owns this clip"
                  }
                  onClick={() => {
                    if (!owner) return;
                    commitChain(owner.id, []);
                    setExportToast("Track effects removed.");
                    setClipMenu(null);
                  }}
                >
                  <Icon name="fa-xmark" /> Remove FX
                </button>
              </div>
            );
          })()
        : null}

      {rangeMenu && timeSelection
        ? (() => {
            const from = clock(timeSelection.start).slice(0, 5);
            const to = clock(timeSelection.end).slice(0, 5);
            return (
              <div
                className="se-clip-menu"
                role="menu"
                aria-label="Time selection options"
                style={{
                  left: Math.min(rangeMenu.x, Math.max(8, window.innerWidth - 250)),
                  top: Math.min(rangeMenu.y, Math.max(8, window.innerHeight - 320)),
                }}
              >
                <div className="se-clip-menu-head">
                  {from} – {to}
                </div>
                <button type="button" role="menuitem" onClick={loopTimeSelection}>
                  <Icon name="fa-repeat" /> Loop selection
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => duplicateSelectedTime()}
                >
                  <Icon name="fa-clone" /> Duplicate time <span>Ctrl Shift D</span>
                </button>
                <div className="se-clip-menu-sep" />
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => deleteSelectedTime("all")}
                >
                  <Icon name="fa-trash" /> Delete time <span>Ctrl Shift ⌫</span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  disabled={!selectedTrack}
                  title={selectedTrack ? undefined : "Focus a track first"}
                  onClick={() => deleteSelectedTime("track")}
                >
                  <Icon name="fa-trash" /> Delete time on this track
                  <span>Ctrl ⌫</span>
                </button>
                <div className="se-clip-menu-sep" />
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setRangeMenu(null);
                    void runExport("range");
                  }}
                >
                  <Icon name="fa-download" /> Export selection <span>WAV</span>
                </button>
                <button type="button" role="menuitem" onClick={clearTimeSelection}>
                  <Icon name="fa-xmark" /> Clear selection <span>Esc</span>
                </button>
              </div>
            );
          })()
        : null}
      </div>

      {clipRename ? (        <div className="se-dialog-backdrop" role="dialog" aria-modal="true" aria-label="Rename clip">
          <div className="se-dialog">
            <h2>Rename clip</h2>
            <label className="se-dialog-note" htmlFor="se-clip-title">
              Clip name
            </label>
            <input
              id="se-clip-title"
              className="se-pill"
              value={clipRename.value}
              autoFocus
              aria-label="Clip name"
              onChange={(event) =>
                setClipRename((current) =>
                  current ? { ...current, value: event.target.value } : current
                )
              }
              onKeyDown={(event) => {
                if (event.key === "Enter") commitClipRename();
                if (event.key === "Escape") setClipRename(null);
              }}
            />
            <div className="se-dialog-foot">
              <button type="button" className="se-pill" onClick={() => setClipRename(null)}>
                Cancel
              </button>
              <button type="button" className="se-pill on" onClick={commitClipRename}>
                Save
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {transformPrompt
        ? (() => {
            const kind = transformPrompt.kind;
            const copy =
              kind === "cover"
                ? {
                    title: "Cover this clip",
                    label: "Style instructions",
                    aria: "Cover style",
                    placeholder: "e.g. acoustic, slow tempo, female vocal",
                    action: "Generate cover",
                  }
                : kind === "vocals"
                  ? {
                      title: "Add vocals to this clip",
                      label: "Vocal instructions",
                      aria: "Vocal instructions",
                      placeholder: "e.g. warm female lead, close harmony",
                      action: "Add vocals",
                    }
                : kind === "instrumental"
                  ? {
                      title: "Add an instrumental",
                      label: "Instrument instructions",
                      aria: "Instrument instructions",
                      placeholder: "e.g. acoustic guitar, upright bass",
                      action: "Add instrumental",
                    }
                  : kind === "mashup"
                    ? {
                        title: "Mashup two clips",
                        label: "Instructions (optional)",
                        aria: "Mashup instructions",
                        placeholder: "e.g. keep the drums, blend the vocals",
                        action: "Create mashup",
                      }
                    : {
                        title: "Replace section",
                        label: "New lyrics for the selected range",
                        aria: "New lyrics",
                        placeholder: "Write what the new section should sing…",
                        action: "Replace section",
                      };
            const submit = () => {
              const target = transformPrompt;
              setTransformPrompt(null);
              if (kind === "mashup") {
                void runMashup(mashupIds, transformValue);
                return;
              }
              if (kind === "replace") {
                void runReplaceSection(target.clipId, transformLyrics);
                return;
              }
              void runTransform(kind, target.clipId, transformValue);
            };
            return (
              <div
                className="se-dialog-backdrop"
                role="dialog"
                aria-modal="true"
                aria-label={copy.title}
              >
                <div className="se-dialog">
                  <h2>{copy.title}</h2>
                  <label className="se-dialog-note" htmlFor="se-transform-prompt">
                    {copy.label}
                  </label>
                  {kind === "replace" ? (
                    <textarea
                      id="se-transform-prompt"
                      className="se-dialog-area"
                      value={transformLyrics}
                      autoFocus
                      aria-label={copy.aria}
                      placeholder={copy.placeholder}
                      onChange={(event) => setTransformLyrics(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Escape") setTransformPrompt(null);
                      }}
                    />
                  ) : (
                    <input
                      id="se-transform-prompt"
                      className="se-pill"
                      value={transformValue}
                      autoFocus
                      aria-label={copy.aria}
                      placeholder={copy.placeholder}
                      onChange={(event) => setTransformValue(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") submit();
                        if (event.key === "Escape") setTransformPrompt(null);
                      }}
                    />
                  )}
                  {kind === "replace" ? (
                    <div className="se-dialog-note">
                      <label htmlFor="se-persona-select">Persona (optional)</label>
                      <select
                        id="se-persona-select"
                        className="se-pill"
                        value={selectedPersonaId}
                        disabled={personaBusy}
                        onChange={(event) => setSelectedPersonaId(event.target.value)}
                      >
                        <option value="">No persona</option>
                        {personas
                          .filter(
                            (persona) =>
                              persona.status === "complete" && persona.provider_persona_id
                          )
                          .map((persona) => (
                            <option key={persona.id} value={persona.provider_persona_id ?? ""}>
                              {persona.name}
                            </option>
                          ))}
                      </select>
                      <div className="se-dialog-row">
                        <input
                          className="se-pill"
                          value={personaName}
                          placeholder="New persona name"
                          maxLength={80}
                          onChange={(event) => setPersonaName(event.target.value)}
                        />
                        <button
                          type="button"
                          className="se-pill"
                          disabled={personaBusy}
                          onClick={() => void createPersonaForClip(transformPrompt.clipId)}
                        >
                          {personaBusy ? "Working..." : "Create"}
                        </button>
                      </div>
                      {personaError ? <small>{personaError}</small> : null}
                    </div>
                  ) : null}
                  {transformCost != null ? (
                    <p className="se-dialog-note">This spends {transformCost} credits.</p>
                  ) : null}
                  <div className="se-dialog-foot">
                    <button
                      type="button"
                      className="se-pill"
                      onClick={() => setTransformPrompt(null)}
                    >
                      Cancel
                    </button>
                    <button type="button" className="se-pill on" onClick={submit}>
                      {copy.action}
                    </button>
                  </div>
                </div>
              </div>
            );
          })()
        : null}

      {stemsPrompt ? (
        <div
          className="se-dialog-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Get stems"
        >
          <div className="se-dialog">
            <h2>Separate stems</h2>
            <p className="se-dialog-note">
              Choose the separation depth. This spends credits from your balance.
            </p>
            {(
              [
                ["vocal", "Vocals + instrumental", stemsPricing?.stems2],
                ["stems", "Core stems", stemsPricing?.stems2],
                ["advanced", "Full 12-stem split", stemsPricing?.stems12],
              ] as const
            ).map(([mode, label, cost]) => (
              <label key={mode} className="se-dialog-note">
                <input
                  type="radio"
                  name="stem-mode"
                  checked={stemsMode === mode}
                  onChange={() => setStemsMode(mode)}
                />{" "}
                {label}
                {cost != null ? ` (${cost} credits)` : ""}
              </label>
            ))}
            <div className="se-dialog-foot">
              <button type="button" className="se-pill" onClick={() => setStemsPrompt(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="se-pill on"
                onClick={() => void requestStems(stemsMode)}
              >
                Separate
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <ClipSourceStrip
        source={clipSource}
        stems={stems}
        onRequestStems={openStemsDialog}
      />

      {automationOpen && selectedTrack
        ? (() => {
            const track = tracks.find((candidate) => candidate.id === selectedTrack);
            if (!track) return null;
            return (
              <StudioAutomationPanel
                track={track}
                duration={duration}
                playhead={playhead}
                onChange={(points: AutomationPoint[]) =>
                  updateTrack(track.id, { volumeAutomation: points })
                }
                onClose={() => setAutomationOpen(false)}
              />
            );
          })()
        : null}

      {takeLanesOpen ? (
        <StudioTakeLanes
          takes={selectedClip ? clips.find((clip) => clip.id === selectedClip)?.takes ?? null : null}
          color={
            (() => {
              const owner = selectedClip
                ? tracks.find((track) => track.clipIds.includes(selectedClip))
                : undefined;
              return owner?.color ?? "#38bdf8";
            })()
          }
          onClose={() => setTakeLanesOpen(false)}
          onActivate={(takeId) => {
            if (selectedClip) activateTake(selectedClip, takeId);
          }}
        />
      ) : midiClip ? (
        <StudioMidiEditor
          clip={midiClip}
          barWidth={barWidth}
          secondsPerBar={secondsPerBar}
          loop={loop}
          keyName={midiKey}
          scaleName={midiScale}
          onKeyChange={(next) => {
            writeProjectData({ ...currentData(), key: next }, "the project key");
          }}
          onScaleChange={(next) => {
            writeProjectData({ ...currentData(), scale: next }, "the project scale");
          }}
          instrument={normalizeMidiInstrument(midiClip.instrument)}
          onInstrumentChange={(instrument) => setMidiInstrument(midiClip.id, instrument)}
          onImportMidi={(file) => void importMidiFile(file)}
          onToggleLoop={() => setLoop((value) => !value)}
          onChangeNotes={(notes) => setMidiNotes(midiClip.id, notes)}
          onChangeLanes={(lane, points) => setMidiLanes(midiClip.id, lane, points)}
          onClose={() => setMidiClipId(null)}
        />
      ) : audioClip ? (
        <StudioAudioEditor
          clip={audioClip}
          secondsPerBar={secondsPerBar}
          beatsPerBar={beatsPerBar}
          playhead={playhead}
          onWarp={(next) => commitWarp(audioClip.id, next)}
          onAudio={(next) => commitClipAudio(audioClip.id, next)}
          onClose={() => setAudioClipId(null)}
        />
      ) : masterSelected ? (
        <StudioMasterDock chain={masterChain} onChange={commitMasterChain} />
      ) : selectedTrack ? (
        <StudioPluginDock
          chain={chains[selectedTrack] ?? []}
          trackName={tracks.find((track) => track.id === selectedTrack)?.name}
          customPlugins={customPlugins}
          tracks={tracks.map((track) => ({ id: track.id, name: track.name }))}
          userPresets={
            Array.isArray((currentData() as { pluginPresets?: unknown }).pluginPresets)
              ? ((currentData() as { pluginPresets?: UserPreset[] }).pluginPresets ?? [])
              : []
          }
          onSavePreset={savePluginPreset}
          onDesignPlugin={openPluginDesigner}
          onChange={(next) => commitChain(selectedTrack, next)}
        />
      ) : null}

      <StudioFooter
        chain={
          masterSelected
            ? masterChain.map((entry) => entry.type ?? "")
            : (selectedTrack ? chains[selectedTrack] : [])?.map((entry) => entry.pluginId) ?? []
        }
        hasTrack={masterSelected || Boolean(selectedTrack)}
        loop={loop}
        onLoop={() => setLoop((value) => !value)}
        onZoomOut={() => zoomBy(-1)}
        onZoomFit={zoomToFit}
        onZoomIn={() => zoomBy(1)}
        onSearch={() => {
          if (!libraryOpen) toggleLibrary(true);
          setTimeout(() => librarySearchRef.current?.focus(), 60);
        }}
        onToggleLibrary={() => toggleLibrary()}
        whatsThis={settings.whatsThis}
        takeLanesOpen={takeLanesOpen}
        onToggleTakeLanes={() => {
          setTakeLanesOpen((open) => !open);
          setAutomationOpen(false);
          setMidiClipId(null);
        }}
        automationOpen={automationOpen}
        onToggleAutomation={() => {
          setAutomationOpen((open) => !open);
          setMidiClipId(null);
          setAudioClipId(null);
          setTakeLanesOpen(false);
        }}
        onWhatsThis={(next) => {
          const updated = { ...settingsRef.current, whatsThis: next };
          setSettings(updated);
          writeStudioSettings(updated);
        }}
      />

      {exportToast ? (
        <div className="se-toast" role="status">
          <span>{exportToast}</span>
          <button
            type="button"
            className="se-icon"
            aria-label="Dismiss export message"
            onClick={() => setExportToast(null)}
          >
            <Icon name="fa-xmark" />
          </button>
        </div>
      ) : null}

      {error ? <div className="se-error" role="alert">{error}</div> : null}
      {transformNotice ? (
        <div className={`se-transform-notice ${transformNotice.kind}`} role="alert">
          <strong>
            {transformNotice.kind === "credits" ? "Not enough credits" : "That edit did not run"}
          </strong>
          <span>
            {transformNotice.kind === "credits"
              ? "This edit spends credits your balance does not cover."
              : "The operation failed before anything was placed."}
          </span>
          {transformNotice.kind === "credits" ? (
            <a className="se-pill on" href="/pricing">
              View plans
            </a>
          ) : null}
          <button
            type="button"
            className="se-icon"
            aria-label="Dismiss"
            onClick={() => setTransformNotice(null)}
          >
            <Icon name="fa-xmark" />
          </button>
          <small>{transformNotice.text}</small>
        </div>
      ) : null}
      {recordError ? (
        <div className="se-error" role="alert">
          {recordError}
        </div>
      ) : null}

      {conflict ? (
        <div className="se-conflict" role="alertdialog" aria-label="Project changed elsewhere">
          <strong>This project changed in another tab.</strong>
          <span>{conflict}</span>
          <div className="se-conflict-actions">
            <button type="button" className="se-pill" onClick={() => void resolveConflictByReload()}>
              Reload theirs
            </button>
            <button type="button" className="se-pill on" onClick={resolveConflictByOverwrite}>
              Keep mine
            </button>
          </div>
        </div>
      ) : null}

      {draft ? (
        <div className="se-conflict" role="alert" aria-label="Recovered draft">
          <strong>We found {describeDraft(draft)}.</strong>
          <span>The last change did not reach the server.</span>
          <div className="se-conflict-actions">
            <button type="button" className="se-pill" onClick={discardDraft}>
              Discard
            </button>
            <button type="button" className="se-pill on" onClick={restoreDraft}>
              Restore draft
            </button>
          </div>
        </div>
      ) : null}
      {loading ? <div className="se-loading" aria-live="polite">Loading project…</div> : null}
    </div>
    </>
  );
}
