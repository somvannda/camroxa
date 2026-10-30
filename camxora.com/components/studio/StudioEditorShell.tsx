"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import { getStudioProject, updateStudioProject, type StudioProject } from "@/lib/studio-api";
import { migrateLanesToTracks, sanitizeTracks, type StudioTrack } from "@/lib/studio-tracks";
import type { PluginChainEntry } from "@/lib/studio-plugins";
import { StudioPluginDock } from "@/components/studio/StudioPluginDock";

const ROW_HEIGHT = 85;
const ROW_STEP = 86;
const PANEL_W = 260;
const LIBRARY_W = 368;
const BAR_PX = 96;

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
  const [loading, setLoading] = useState(true);
  const [selectedTrack, setSelectedTrack] = useState<string | null>(null);
  const [selectedClip, setSelectedClip] = useState<string | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loop, setLoop] = useState(false);
  const [metronome, setMetronome] = useState(false);
  const [bpm, setBpm] = useState(120);
  const [projectId, setProjectId] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setProjectId(params.get("project"));
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

  useEffect(() => {
    setLocalTracks(null);
  }, [projectId]);

  /** Persist the track list into the project document. */
  function commitTracks(next: StudioTrack[]) {
    setLocalTracks(next);
    if (!projectId) return;
    const base = (project?.data || {}) as Record<string, unknown>;
    updateStudioProject(projectId, { data: { ...base, tracks: next } }).catch(() => {
      setError("Could not save the track list.");
    });
  }

  function addTrack() {
    const next: StudioTrack = {
      id: `track-${Date.now().toString(36)}`,
      name: `Track ${tracks.length + 1}`,
      color: "#8b5cf6",
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
    if (!projectId) return;
    const base = (project?.data || {}) as Record<string, unknown>;
    updateStudioProject(projectId, { data: { ...base, chains: merged } }).catch(() => {
      setError("Could not save the plugin chain.");
    });
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
      setPlayhead((current) => {
        const next = current + delta;
        if (next >= duration) return loop ? 0 : duration;
        return next;
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, duration, loop]);

  useEffect(() => {
    if (playing && !loop && playhead >= duration) setPlaying(false);
  }, [playing, loop, playhead, duration]);

  const secondsPerBar = 240 / bpm;
  const barCount = Math.max(1, Math.ceil((duration * bpm) / 240));

  if (authLoading) return <div className="se-shell is-loading" aria-busy="true" />;

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
    <div className="se-shell">
      <header className="se-head">
        <div className="se-head-left">
          <span className="se-logo">CAMXORA</span>
          <button type="button" className="se-chip" disabled title="Project menu is not wired in the shell yet">
            {project?.title || "Untitled project"}
            <Icon name="fa-chevron-down" />
          </button>
          <button type="button" className="se-icon" disabled aria-label="Undo (not wired)"><Icon name="fa-rotate-left" /></button>
          <button type="button" className="se-icon" disabled aria-label="Redo (not wired)"><Icon name="fa-rotate-right" /></button>
        </div>

        <div className="se-head-center">
          <button type="button" className="se-icon" onClick={() => { setPlaying(false); setPlayhead(0); }} aria-label="Back to start"><Icon name="fa-backward-step" /></button>
          <button
            type="button"
            className={`se-icon${loop ? " on" : ""}`}
            onClick={() => setLoop((value) => !value)}
            aria-pressed={loop}
            aria-label="Loop"
            title="Loop"
          >
            <Icon name="fa-repeat" />
          </button>
          <button
            type="button"
            className="se-icon"
            onClick={() => { setPlaying(false); setPlayhead(0); }}
            aria-label="Stop"
          >
            <Icon name="fa-stop" />
          </button>
          <button
            type="button"
            className={`se-icon se-play${playing ? " on" : ""}`}
            onClick={() => setPlaying((value) => !value)}
            aria-label={playing ? "Pause" : "Play"}
            title={playing ? "Pause" : "Play"}
          >
            <Icon name={playing ? "fa-pause" : "fa-play"} />
          </button>
          <button
            type="button"
            className={`se-icon${metronome ? " on" : ""}`}
            onClick={() => setMetronome((value) => !value)}
            aria-pressed={metronome}
            aria-label="Metronome (visual only)"
            title="Metronome (visual only — no click audio yet)"
          >
            <Icon name="fa-bell" />
          </button>
          <span className="se-readout" aria-label="Time">{clock(playhead)}</span>
          <span className="se-readout" aria-label="Bar and beat">{barBeat(playhead, bpm)}</span>
        </div>

        <div className="se-head-right">
          <input
            className="se-pill se-bpm"
            value={bpm}
            inputMode="numeric"
            aria-label="Tempo in BPM"
            onChange={(event) => {
              const next = Number(event.target.value.replace(/\D/g, ""));
              if (Number.isFinite(next)) setBpm(Math.min(300, Math.max(20, next || 20)));
            }}
            onBlur={() => {
              if (!projectId) return;
              updateStudioProject(projectId, { bpm }).catch(() => {
                setError("Could not save the tempo.");
              });
            }}
          />
          <span className="se-pill">{project?.time_signature || "4/4"}</span>
          <button type="button" className="se-pill" disabled aria-label="Export (not wired)"><Icon name="fa-arrow-up-from-bracket" /> Export</button>
          <button
            type="button"
            className={`se-pill${libraryOpen ? " on" : ""}`}
            onClick={() => setLibraryOpen((open) => !open)}
            aria-expanded={libraryOpen}
          >
            <Icon name="fa-table-columns" /> Library
          </button>
        </div>
      </header>

      <div className={`se-body${libraryOpen ? " with-library" : ""}`}>
        <aside className="se-tracks" aria-label="Tracks">
          <div className="se-tracks-head">
            <span className="se-tracks-title">{tracks.length} track{tracks.length === 1 ? "" : "s"}</span>
          </div>

          <div className="se-track-list">
            {tracks.map((track, index) => {
              const active = selectedTrack === track.id;
              return (
                <div
                  key={track.id}
                  className={`se-track${active ? " selected" : ""}`}
                  style={{ height: ROW_HEIGHT, marginBottom: ROW_STEP - ROW_HEIGHT }}
                >
                  <span className="se-track-color" style={{ background: track.color }} aria-hidden="true" />
                  <div className="se-track-top">
                    <span className="se-track-index">{index + 1}</span>
                    <button
                      type="button"
                      className="se-track-name"
                      onClick={() => setSelectedTrack(track.id)}
                      aria-pressed={active}
                    >
                      {track.name}
                    </button>
                    <span className="se-track-buttons">
                      <button type="button" disabled aria-label={`Mute ${track.name} (not wired)`}>
                        <Icon name="fa-volume-high" />
                      </button>
                      <button type="button" disabled aria-label={`Solo ${track.name} (not wired)`}>S</button>
                      <button type="button" disabled aria-label={`Arm ${track.name} (not wired)`}>A</button>
                      <button type="button" disabled aria-label={`Options for ${track.name} (not wired)`}>
                        <Icon name="fa-chevron-down" />
                      </button>
                    </span>
                  </div>
                  <div className="se-track-sliders">
                    <div className="se-track-level" aria-hidden="true">
                      <span
                        className="se-track-level-fill"
                        style={{ width: `${track.volume}%`, background: track.color }}
                      />
                      <span className="se-track-level-handle" style={{ left: `${track.volume}%` }} />
                    </div>
                    <div className="se-track-level pan" aria-hidden="true">
                      <span className="se-track-level-handle" style={{ left: `${50 + track.pan / 2}%` }} />
                    </div>
                  </div>
                </div>
              );
            })}

            <button type="button" className="se-add-track" onClick={addTrack}>
              <Icon name="fa-plus" /> Add new track
            </button>
          </div>
        </aside>

        <div className="se-timeline">
          <div className="se-ruler-bars" aria-hidden="true">
            <div className="se-ruler-inner" style={{ width: barCount * BAR_PX }}>
              {Array.from({ length: barCount }).map((_, bar) => (
                <span key={bar} className="se-bar-tick" style={{ left: bar * BAR_PX }}>
                  {bar + 1}
                </span>
              ))}
            </div>
          </div>

          <div
            className="se-lanes"
            onPointerDown={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              const barsIn = (event.clientX - rect.left) / BAR_PX;
              setPlayhead(Math.max(0, Math.min(duration, barsIn * secondsPerBar)));
            }}
          >
            <div className="se-lanes-inner" style={{ width: barCount * BAR_PX }}>
              {tracks.map((track) => (
                <div key={track.id} className="se-lane" style={{ height: ROW_STEP }}>
                  {clips
                    .filter((clip) => track.clipIds.includes(clip.id))
                    .map((clip) => {
                      const left = ((clip.start ?? 0) / secondsPerBar) * BAR_PX;
                      const width = Math.max(20, ((clip.duration ?? 4) / secondsPerBar) * BAR_PX);
                      return (
                        <button
                          type="button"
                          key={clip.id}
                          className={`se-clip${selectedClip === clip.id ? " selected" : ""}`}
                          style={{ left, width, background: track.color }}
                          onClick={() => {
                            setSelectedTrack(track.id);
                            setSelectedClip(clip.id);
                          }}
                          aria-pressed={selectedClip === clip.id}
                        >
                          <span className="se-clip-head">{clip.title || "Clip"}</span>
                          <span className="se-clip-body" aria-hidden="true" />
                        </button>
                      );
                    })}
                </div>
              ))}

              <div className="se-playhead" style={{ left: (playhead / secondsPerBar) * BAR_PX }} aria-hidden="true" />
            </div>

            {!tracks.length ? (
              <div className="se-empty">
                <strong>Your session is empty</strong>
                <span>Add a track to start arranging.</span>
              </div>
            ) : null}
          </div>

          <div className="se-ruler-time" aria-hidden="true">
            <div className="se-ruler-inner" style={{ width: barCount * BAR_PX }}>
              {Array.from({ length: Math.ceil(duration / 30) }).map((_, index) => (
                <span key={index} className="se-time-tick" style={{ left: (index * 30 / secondsPerBar) * BAR_PX }}>
                  {clock(index * 30).slice(0, 5)}
                </span>
              ))}
            </div>
          </div>
        </div>

        {libraryOpen ? (
          <aside className="se-library" aria-label="Library" style={{ width: LIBRARY_W }}>
            <div className="se-library-head">
              <strong>Library</strong>
              <button type="button" className="se-icon" onClick={() => setLibraryOpen(false)} aria-label="Close library">
                <Icon name="fa-xmark" />
              </button>
            </div>
            <p className="se-lib-empty">Song library is not wired into this shell yet.</p>
          </aside>
        ) : null}
      </div>

      {selectedTrack ? (
        <StudioPluginDock
          chain={chains[selectedTrack] ?? []}
          trackName={tracks.find((track) => track.id === selectedTrack)?.name}
          onChange={(next) => commitChain(selectedTrack, next)}
        />
      ) : null}

      <footer className="se-foot">
        <div className="se-foot-tools">
          <button type="button" className="se-icon" disabled aria-label="Tools (not wired)"><Icon name="fa-sliders" /></button>
          <button type="button" className="se-icon" disabled aria-label="Draw (not wired)"><Icon name="fa-pen" /></button>
          <button type="button" className="se-icon" disabled aria-label="List (not wired)"><Icon name="fa-bars" /></button>
          <button type="button" className="se-icon" disabled aria-label="Microphone (not wired)"><Icon name="fa-microphone" /></button>
        </div>

        <div className="se-chain">
          {selectedTrack && chains[selectedTrack]?.length ? (
            chains[selectedTrack].map((entry) => (
              <span key={entry.entryId} className="se-chain-chip">{entry.pluginId}</span>
            ))
          ) : (
            <span className="se-foot-note">No effects on this track yet.</span>
          )}
          <button type="button" className="se-chain-add" disabled aria-label="Add effect (use the dock above)">
            <Icon name="fa-plus" />
          </button>
        </div>

        <div className="se-foot-right">
          <button type="button" className="se-icon" disabled aria-label="Projects (not wired)"><Icon name="fa-folder" /></button>
          <button type="button" className="se-icon" disabled aria-label="Search (not wired)"><Icon name="fa-magnifying-glass" /></button>
          <button type="button" className="se-icon" onClick={() => setLibraryOpen((open) => !open)} aria-label="Toggle library"><Icon name="fa-table-columns" /></button>
          <button type="button" className={`se-icon${loop ? " on" : ""}`} onClick={() => setLoop((value) => !value)} aria-label="Loop" aria-pressed={loop}><Icon name="fa-repeat" /></button>
          <Link className="se-foot-link" href={`/studio/editor/classic?project=${projectId}`}>Learn</Link>
        </div>
      </footer>

      {error ? <div className="se-error" role="alert">{error}</div> : null}
      {loading ? <div className="se-loading" aria-live="polite">Loading project…</div> : null}
    </div>
  );
}
