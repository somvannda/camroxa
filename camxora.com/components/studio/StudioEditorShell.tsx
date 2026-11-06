"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import { getStudioProject, StudioConflictError, updateStudioProject, type StudioProject } from "@/lib/studio-api";
import { autoSnapshotStudioProject } from "@/lib/studio-api";
import { getStudioOperation, requestStudioStems } from "@/lib/studio-api";
import { listStudioProjects, listStudioUploads, type StudioUpload } from "@/lib/studio-api";
import { listWebMusicWorkspaces, type WebMusicWorkspace } from "@/lib/web-music-api";
import { StudioLibrary, type StudioLibraryTab } from "@/components/studio/StudioLibrary";
import { fetchGenerations, type WebMusicGeneration } from "@/lib/library-api";
import { colorForTrackName, migrateLanesToTracks, sanitizeTracks, type StudioTrack } from "@/lib/studio-tracks";
import { dragToStart, isDrag, snapToGrid } from "@/lib/studio-snap";
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
import { clearDraft, describeDraft, loadDraft, saveDraft, type StudioDraft } from "@/lib/studio-draft";
import type { PluginChainEntry } from "@/lib/studio-plugins";
import { StudioPluginDock } from "@/components/studio/StudioPluginDock";
import { StudioSaveStatus, type SaveStatus } from "@/components/studio/StudioSaveStatus";
import { StudioHeader } from "@/components/studio/StudioHeader";
import { StudioFooter } from "@/components/studio/StudioFooter";
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
const LIBRARY_W = 368;
const ZOOM_LEVELS = [48, 64, 96, 144, 192];

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
};

function clock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

function barBeat(seconds: number, bpm: number): string {
  const beats = (seconds * bpm) / 60;
  const bar = Math.floor(beats / 4) + 1;
  const beat = Math.floor(beats % 4) + 1;
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
  const [conflict, setConflict] = useState<string | null>(null);
  /** A draft recovered from storage after a failed or offline write (W2.3). */
  const [draft, setDraft] = useState<StudioDraft | null>(null);
  const projectRef = useRef<StudioProject | null>(null);
  /** Server version of the document, kept in sync without waiting for a render. */
  const projectVersionRef = useRef<string | null>(null);
  /** Library panel data (G12): songs, workspaces, other projects and uploads. */
  const [libraryTab, setLibraryTab] = useState<StudioLibraryTab>("songs");
  const [librarySongs, setLibrarySongs] = useState<WebMusicGeneration[] | null>(null);
  const [libraryWorkspaces, setLibraryWorkspaces] = useState<WebMusicWorkspace[] | null>(null);
  /** Workspace the Songs tab is filtered to; null means every song. */
  const [libraryWorkspaceId, setLibraryWorkspaceId] = useState<string | null>(null);
  const [libraryProjects, setLibraryProjects] = useState<StudioProject[] | null>(null);
  const [libraryUploads, setLibraryUploads] = useState<StudioUpload[] | null>(null);
  const [libraryQuery, setLibraryQuery] = useState("");
  const librarySearchRef = useRef<HTMLInputElement | null>(null);
  /** Source generation of the selected clip, when it came from the library (G16). */
  const [clipSource, setClipSource] = useState<WebMusicGeneration | null>(null);
  /** Stem separation request state for the selected clip (W4.2). */
  const [stems, setStems] = useState<{ status: string; message?: string } | null>(null);
  /** Active clip drag: every selected clip's origin plus the latest pointer delta. */
  const [drag, setDrag] = useState<{
    ids: string[];
    origins: Record<string, number>;
    deltaPx: number;
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
    setSelectedIds([]);
    setSelectedClip(null);
    setPlayhead(Math.max(0, Math.min(duration, (x / barWidth) * secondsPerBar)));
  }

  /** Press on a clip: select it (or keep the group) and start a drag session (G7/G8). */
  function handleClipPointerDown(
    event: React.PointerEvent<HTMLButtonElement>,
    clip: ClipLike,
    trackId: string
  ) {
    event.stopPropagation();
    setSelectedTrack(trackId);
    setSelectedClip(clip.id);
    const group = selectedIds.includes(clip.id) ? selectedIds : [clip.id];
    setSelectedIds(group);
    const origins: Record<string, number> = {};
    group.forEach((id) => {
      const found = clips.find((candidate) => candidate.id === id);
      if (found) origins[id] = found.start ?? 0;
    });
    dragRef.current = { startX: event.clientX, ids: group, origins, ghost: settingsRef.current.ghostDrag };
  }
  const [exporting, setExporting] = useState(false);
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
  const [selectedClip, setSelectedClip] = useState<string | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loop, setLoop] = useState(false);
  /** Loop / export range in seconds (spec §68). */
  const [loopStart, setLoopStart] = useState(0);
  const [loopEnd, setLoopEnd] = useState(0);
  const loopDragRef = useRef(false);
  const [metronome, setMetronome] = useState(false);
  const [bpm, setBpm] = useState(120);
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

  /** Load the library panel's lists the first time it opens (G12). */
  useEffect(() => {
    if (!libraryOpen || !user) return;
    let active = true;
    if (librarySongs === null) {
      fetchGenerations(20, libraryWorkspaceId)
        .then((items) => {
          if (active) setLibrarySongs(items);
        })
        .catch(() => {
          if (active) setLibrarySongs([]);
        });
    }
    if (libraryWorkspaces === null) {
      listWebMusicWorkspaces()
        .then((result) => {
          if (active) setLibraryWorkspaces(result.items ?? []);
        })
        .catch(() => {
          if (active) setLibraryWorkspaces([]);
        });
    }
    if (libraryProjects === null) {
      listStudioProjects(20, 0, false)
        .then((result) => {
          if (active) setLibraryProjects(result.items ?? []);
        })
        .catch(() => {
          if (active) setLibraryProjects([]);
        });
    }
    if (libraryUploads === null) {
      listStudioUploads(50)
        .then((result) => {
          if (active) setLibraryUploads(result.items ?? []);
        })
        .catch(() => {
          if (active) setLibraryUploads([]);
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
  ]);

  /** Choose a workspace: the Songs tab reloads filtered to it (spec §19.1). */
  function selectLibraryWorkspace(workspaceId: string | null) {
    setLibraryWorkspaceId(workspaceId);
    setLibrarySongs(null);
    setLibraryTab("songs");
  }

  /** Add-track ▸ Upload (§8.3) lands on the library's Uploads tab. */
  function openUploadLibrary() {
    setLibraryTab("uploads");
    setLibraryOpen(true);
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
          start: snapToGrid(playhead, secondsPerBar, 4),
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
          start: snapToGrid(playhead, secondsPerBar, 4),
          duration: upload.duration_seconds ?? 8,
          volume: 1,
          pan: 0,
          audioUrl: upload.url,
          uploadId: upload.id,
        } as ClipLike & { audioUrl?: string | null; uploadId?: string },
      },
    ]);
  }

  /** Apply a recovered draft locally and try to write it (W2.3). */
  function restoreDraft() {
    if (!projectId || !draft) return;
    const data = (draft.data || {}) as StudioProject["data"];
    setProject((current) => (current ? { ...current, data } : current));
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
  function writeProjectData(
    next: Record<string, unknown>,
    label: string,
    nextTracks?: StudioTrack[] | null
  ) {
    const current = (project?.data || {}) as Record<string, unknown>;
    const history = historyRef.current;
    history.undo.push({ data: current, label });
    if (history.undo.length > HISTORY_LIMIT) history.undo.shift();
    history.redo = [];
    syncHistory();
    setProject((prev) => (prev ? { ...prev, data: next } : prev));
    if (nextTracks !== undefined) setLocalTracks(nextTracks);
    if (!projectId) return;
    persist(
      (expected) => updateStudioProject(projectId, { data: next, expectedUpdatedAt: expected }),
      `Could not save ${label}.`
    );
  }

  function applyHistoryEntry(entry: { data: unknown; label: string }, to: "undo" | "redo") {
    if (!projectId) return;
    const current = (project?.data || {}) as Record<string, unknown>;
    const history = historyRef.current;
    const opposite = to === "undo" ? history.redo : history.undo;
    opposite.push({ data: current, label: entry.label });
    const data = entry.data as Record<string, unknown>;
    setProject((prev) => (prev ? { ...prev, data } : prev));
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
      // Keep the edit burst so a reload does not lose it (W2.3).
      if (projectId) saveDraft(projectId, projectRef.current?.data ?? null);
      setSaveStatus("error");
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
    const goOnline = () => setSaveStatus((current) => (current === "offline" ? "saved" : current));
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
  }, []);

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
    const data = (project?.data || {}) as { loopStart?: unknown; loopEnd?: unknown };
    if (typeof data.loopStart === "number") setLoopStart(data.loopStart);
    if (typeof data.loopEnd === "number") setLoopEnd(data.loopEnd);
  }, [project?.id, project?.data]);

  /** Persist the loop range — the same document field the reference uses. */
  function commitLoopRange(start: number, end: number) {
    const data = (project?.data || {}) as Record<string, unknown>;
    writeProjectData({ ...data, loopStart: start, loopEnd: end }, "the loop range");
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
      setLoopEnd(Math.max(loopStart + secondsPerBar / 4, snapToGrid(seconds, secondsPerBar, 4)));
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
    setBarWidth(ZOOM_LEVELS[2]);
  }

  /** Track menu actions (spec §65). All persist through the history-aware write path. */
  function updateTrack(trackId: string, patch: Partial<StudioTrack>) {
    commitTracks(tracks.map((track) => (track.id === trackId ? { ...track, ...patch } : track)));
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
    const data = (project?.data || {}) as Record<string, unknown>;
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
    const data = (project?.data || {}) as Record<string, unknown>;
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
  async function requestStems() {
    const clip = clips.find((candidate) => candidate.id === selectedClip);
    const songId = (clip as { songId?: string } | undefined)?.songId;
    if (!songId) return;
    setStems({ status: "queued" });
    try {
      const operation = await requestStudioStems({
        taskId: songId,
        variant: "ok",
        mode: "stems",
        projectId,
      });
      setStems({ status: operation.status });

      const deadline = Date.now() + 120_000;
      let current = operation;
      while (Date.now() < deadline) {
        if (current.status === "done" && current.result?.clips?.length) break;
        if (current.status === "error" || current.status === "failed") {
          setStems({ status: "error", message: current.error_message ?? "Stem separation failed." });
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
      const data = (project?.data || {}) as Record<string, unknown>;
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
      setStems({
        status: "error",
        message: cause instanceof Error ? cause.message : "Could not start stem separation.",
      });
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
    const base = (project?.data || {}) as Record<string, unknown>;
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
      groupId: null,
      chain: [],
      clipIds: [],
    };
    commitTracks([...tracks, next]);
    setSelectedTrack(next.id);
  }

  const derivedChains = useMemo<Record<string, PluginChainEntry[]>>(() => {
    const data = (project?.data || {}) as { chains?: unknown };
    return (data.chains as Record<string, PluginChainEntry[]>) || {};
  }, [project]);

  const [localChains, setLocalChains] = useState<Record<string, PluginChainEntry[]> | null>(null);
  const chains = localChains ?? derivedChains;

  useEffect(() => {
    setLocalChains(null);
  }, [projectId]);

  /** Persist one track's plugin chain into the project document. */
  function commitChain(trackId: string, next: PluginChainEntry[]) {
    const merged = { ...chains, [trackId]: next };
    setLocalChains(merged);
    const base = (project?.data || {}) as Record<string, unknown>;
    writeProjectData({ ...base, chains: merged }, "the plugin chain");
  }

  /** Persist new start positions for one or more clips (drag result). */
  function commitClipStarts(next: Record<string, number>) {
    if (!projectId) return;
    const data = (project?.data || {}) as Record<string, unknown>;
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
    const data = (project?.data || {}) as Record<string, unknown>;
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
    const target = snapToGrid(playhead, secondsPerBar, 4);
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

    const data = (project?.data || {}) as Record<string, unknown>;
    writeProjectData({ ...data, lanes: remaining, tracks: nextTracks }, "deleting clips", nextTracks);
  }

  /** After a delete, move real DOM focus to the surviving clip. */
  useEffect(() => {
    if (!focusPendingRef.current) return;
    focusPendingRef.current = false;
    const element = document.querySelector<HTMLElement>(".se-clip.selected");
    element?.focus();
  }, [selectedIds]);

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

      // BACKSPACE / DELETE remove the selection (spec §36).
      if (event.key === "Backspace" || event.key === "Delete") {
        if (activeClipIds().length === 0) return;
        event.preventDefault();
        deleteSelection();
        return;
      }

      // Unmodified keys (spec §11): Space transport, Home/End, and the add-track
      // accelerators A (audio) / U (uploads). M has no meaning here — MIDI tracks are
      // not built — so it is deliberately unbound rather than adding an audio track.
      if (!event.metaKey && !event.ctrlKey && !event.altKey) {
        if (document.querySelector('[role="dialog"]')) return;
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
          setPlayhead(duration);
          return;
        }
        const plain = event.key.toLowerCase();
        if (plain === "a") {
          event.preventDefault();
          addTrack();
          return;
        }
        if (plain === "u") {
          event.preventDefault();
          openUploadLibrary();
          return;
        }
      }

      if (!(event.metaKey || event.ctrlKey) || event.altKey) return;
      const key = event.key.toLowerCase();
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
    const lanes = Array.isArray((project?.data || {}).lanes)
      ? ((project?.data || {}) as { lanes: ClipLike[] }).lanes
      : clipsRef.current;
    return lanes.map((clip) => {
      const origin = current.origins[clip.id];
      if (origin === undefined) return clip;
      const start = dragToStart(origin, current.deltaPx, barWidth, secondsPerBar, 4);
      return Math.abs(start - origin) > 0.0001 ? { ...clip, start } : clip;
    });
  }

  function commitDrag(current: { ids: string[]; origins: Record<string, number>; deltaPx: number }) {
    const next: Record<string, number> = {};
    for (const id of current.ids) {
      const origin = current.origins[id];
      if (origin === undefined) continue;
      const start = dragToStart(origin, current.deltaPx, barWidth, secondsPerBar, 4);
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
      let next = current + delta * rateRef.current;
      if (next >= durationRef.current) next = loop ? 0 : durationRef.current;
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
  const audioRef = useRef<{ ctx: AudioContext; sources: AudioBufferSourceNode[]; analyser?: AnalyserNode } | null>(null);
  /** Decoded buffers keyed by URL, so a restart (ghost-drag apply) does not refetch. */
  const bufferCacheRef = useRef<Map<string, AudioBuffer>>(new Map());
  /** Latest values for pointer handlers that outlive the render they were made in. */
  const playheadRef = useRef(playhead);
  playheadRef.current = playhead;
  const playingRef = useRef(playing);
  playingRef.current = playing;
  const metronomeRef = useRef(metronome);
  metronomeRef.current = metronome;
  const bpmRef = useRef(bpm);
  bpmRef.current = bpm;
  const rateRef = useRef(playbackRate);
  rateRef.current = playbackRate;
  const durationRef = useRef(0);
  durationRef.current = duration;
  /** Song time up to which metronome clicks have already been scheduled. */
  const scheduledThroughRef = useRef(0);
  /** Clicks already scheduled, so switching the metronome off can silence them. */
  const clickNodesRef = useRef<OscillatorNode[]>([]);

  async function stopAudio() {
    const engine = audioRef.current;
    if (!engine) return;
    engine.sources.forEach((source) => {
      try {
        source.stop();
      } catch {
        /* already stopped */
      }
    });
    engine.sources = [];
  }

  /** Stop and re-schedule from `from` with a specific arrangement (drag apply, §22). */
  function restartAudio(from: number, arrangement: ClipLike[]) {
    void (async () => {
      await stopAudio();
      await startAudio(from, arrangement);
    })();
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
    for (const click of clicksBetween(start, until, bpmRef.current)) {
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
    master.gain.value = 0.85;

    // Master chain (W4.1): the bus is a real node graph, not a hard-coded gain.
    const masterChain = ((): MasterChainEntry[] => {
      const data = (project?.data || {}) as { masterChain?: unknown };
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
    audioRef.current = { ctx: context, sources: [], analyser };

    for (const clip of arrangement) {
      const url = (clip as { audioUrl?: string | null }).audioUrl;
      const buffer = url ? bufferCacheRef.current.get(url) : undefined;
      if (!buffer) continue;
      const start = clip.start ?? 0;
      const duration = clip.duration ?? buffer.duration;
      if (start + duration <= from) continue;
      const track = tracks.find((item) => item.clipIds.includes(clip.id));
      // Solo wins over mute, and any solo silences everything not soloed (G21).
      const anySolo = tracks.some((item) => item.solo);
      if (track?.muted) continue;
      if (anySolo && !track?.solo) continue;

      const when = now + Math.max(0, start - from) / playbackRate;
      const offset = Math.max(0, from - start);
      const source = context.createBufferSource();
      source.buffer = buffer;
      // Audition speed (G17): playbackRate scales both the scheduling offset and
      // how long the buffer takes to play, so clips stay in sync with each other.
      source.playbackRate.value = playbackRate;
      const gain = context.createGain();
      gain.gain.value = (track?.volume ?? 80) / 100;
      source.connect(gain).connect(master);
      source.start(when, offset, Math.max(0.05, duration - offset));
      audioRef.current?.sources.push(source);
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
      return;
    }
    setExporting(true);
    try {
      const buffers = await decodeClips();
      const exportClips: ExportClip[] = clips.map((clip) => ({
        id: clip.id,
        start: clip.start,
        duration: clip.duration,
        audioUrl: (clip as { audioUrl?: string | null }).audioUrl ?? null,
      }));
      const exportTracks: ExportTrack[] = tracks.map((track) => ({
        id: track.id,
        name: track.name,
        volume: track.volume,
        muted: track.muted,
        clipIds: track.clipIds,
      }));
      const chain = ((project.data || {}) as { masterChain?: MasterChainEntry[] }).masterChain;
      // Mix/range only: per-track files must keep their relative balance (G11).
      const normalise = exportNormalise ? EXPORT_TARGET_PEAK_DB : null;

      if (scope === "mix") {
        const wav = await renderMix(buffers, exportClips, exportTracks, { chain, normalise });
        download(wav, `${project.title || "mix"}.wav`, "audio/wav");
      } else if (scope === "range") {
        // Exports exactly the loop range, the reference's "Selected Time Range" (§87).
        const wav = await renderMix(buffers, exportClips, exportTracks, {
          chain,
          normalise,
          from: loopStart,
          to: loopEnd,
        });
        download(wav, `${project.title || "mix"} — selection.wav`, "audio/wav");
      } else {
        for (const track of exportTracks) {
          const wav = await renderMix(buffers, exportClips, exportTracks, {
            chain,
            clipIds: new Set(track.clipIds),
          });
          const label = (track.name || track.id).replace(/[\\/:*?"<>|]/g, "-");
          download(wav, `${project.title || "project"} — ${label}.wav`, "audio/wav");
        }
      }
    } catch {
      setError("Export failed. Check that the clips still have audio.");
    } finally {
      setExporting(false);
    }
  }

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

  const secondsPerBar = 240 / bpm;
  const barCount = Math.max(1, Math.ceil((duration * bpm) / 240));

  /** Pointer handling for clip dragging (G7/G8) and marquee selection (G6). */
  useEffect(() => {
    const move = (event: PointerEvent) => {
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
    const up = () => {
      const session = dragRef.current;
      dragRef.current = null;
      if (session) {
        // Commit from a ref, not from inside a state updater: React double-invokes
        // updaters, which fired the save twice and turned the second into a 409.
        const current = dragStateRef.current;
        if (current && Math.abs(current.deltaPx) > 0) {
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
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
    };
  }, [drag, secondsPerBar]);


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

  return (
    <div className={`se-shell${touchMode ? " is-touch" : ""}`}>
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
        timeSignature={project?.time_signature || "4/4"}
        clock={clock(playhead)}
        barBeat={barBeat(playhead, bpm)}
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
        rangeReady={loopEnd > loopStart}
        onToggleExport={() => setExportOpen((open) => !open)}
        onExport={(scope) => void runExport(scope)}
        normalise={exportNormalise}
        onToggleNormalise={() => setExportNormalise((value) => !value)}
        libraryOpen={libraryOpen}
        onToggleLibrary={() => setLibraryOpen((open) => !open)}
        onBackToStart={() => { setPlaying(false); void stopAudio(); setPlayhead(0); }}
        onTogglePlay={togglePlayback}
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
        beat={metronome ? beatAt(playhead, bpm) : 0}
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
          onSelectTrack={setSelectedTrack}
          onToggleMenu={setMenuTrackId}
          onToggleFlag={toggleTrackFlag}
          onUpdateTrack={updateTrack}
          onRenameStart={startRename}
          onRenameChange={setRenameValue}
          onRenameCommit={commitRename}
          onRenameCancel={() => setRenameTrackId(null)}
          onDuplicate={duplicateTrack}
          onHide={hideTrack}
          onDelete={deleteTrack}
          onAddTrack={addTrack}
          onAddUploadTrack={openUploadLibrary}
          onToggleHidden={() => setHiddenOpen((open) => !open)}
          onShowAllHidden={showAllHidden}
        />

        <StudioTimeline
          tracks={tracks}
          clips={clips}
          barWidth={barWidth}
          barCount={barCount}
          secondsPerBar={secondsPerBar}
          duration={duration}
          playhead={playhead}
          clock={clock}
          rowStep={ROW_STEP}
          selectedClip={selectedClip}
          selectedIds={selectedIds}
          drag={drag}
          marquee={marquee}
          loop={loop}
          loopStart={loopStart}
          loopEnd={loopEnd}
          viewWidth={view.width}
          viewLeft={view.left}
          timelineRef={timelineRef}
          onScroll={(left, width) => setView({ left, width })}
          onLanePointerDown={handleLanePointerDown}
          onClipPointerDown={handleClipPointerDown}
          onLoopHandleDown={(event) => {
            event.stopPropagation();
            loopDragRef.current = true;
          }}
        />

        {libraryOpen ? (
          <StudioLibrary
            ref={librarySearchRef}
            width={LIBRARY_W}
            tab={libraryTab}
            onTab={setLibraryTab}
            query={libraryQuery}
            onQuery={setLibraryQuery}
            songs={librarySongs}
            workspaces={libraryWorkspaces}
            activeWorkspaceId={libraryWorkspaceId}
            projects={libraryProjects}
            uploads={libraryUploads}
            currentProjectId={projectId}
            onClose={() => setLibraryOpen(false)}
            onAddSong={addSongToTimeline}
            onSelectWorkspace={selectLibraryWorkspace}
            onAddUpload={addUploadToTimeline}
            onOpenProject={(id) => {
              window.location.href = `/studio/editor?project=${encodeURIComponent(id)}`;
            }}
          />
        ) : null}
      </div>

      <StudioOnboarding
        projectId={projectId}
        isEmpty={!loading && tracks.length === 0 && clips.length === 0}
        reopenToken={quickStartToken}
      />

      <StudioMetricsProbe />

      <ClipSourceStrip
        source={clipSource}
        stems={stems}
        onRequestStems={() => void requestStems()}
      />

      {selectedTrack ? (
        <StudioPluginDock
          chain={chains[selectedTrack] ?? []}
          trackName={tracks.find((track) => track.id === selectedTrack)?.name}
          onChange={(next) => commitChain(selectedTrack, next)}
        />
      ) : null}

      <StudioFooter
        chain={(selectedTrack ? chains[selectedTrack] : [])?.map((entry) => entry.pluginId) ?? []}
        hasTrack={Boolean(selectedTrack)}
        loop={loop}
        onLoop={() => setLoop((value) => !value)}
        onZoomOut={() => zoomBy(-1)}
        onZoomFit={zoomToFit}
        onZoomIn={() => zoomBy(1)}
        onSearch={() => {
          setLibraryOpen(true);
          setTimeout(() => librarySearchRef.current?.focus(), 60);
        }}
        onToggleLibrary={() => setLibraryOpen((open) => !open)}
        whatsThis={settings.whatsThis}
        onWhatsThis={(next) => {
          const updated = { ...settingsRef.current, whatsThis: next };
          setSettings(updated);
          writeStudioSettings(updated);
        }}
      />

      {error ? <div className="se-error" role="alert">{error}</div> : null}

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
  );
}
