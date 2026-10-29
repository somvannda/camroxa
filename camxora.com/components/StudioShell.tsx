"use client";

import { useEffect, useMemo, useState } from "react";

import { Icon } from "@/components/Icon";
import type { WebMusicGeneration } from "@/lib/library-api";
import { listWebMusicGenerations, studioSessionForClip } from "@/lib/web-music-api";

type Dock = "songs" | "liked" | "stems" | "uploads" | "workspaces" | "projects";

const DOCK: Array<{ id: Dock; label: string; icon: string }> = [
  { id: "songs", label: "All songs", icon: "fa-music" },
  { id: "liked", label: "Liked", icon: "fa-heart" },
  { id: "stems", label: "Stems", icon: "fa-layer-group" },
  { id: "uploads", label: "Uploads", icon: "fa-arrow-up-from-bracket" },
  { id: "workspaces", label: "Workspaces", icon: "fa-folder-tree" },
  { id: "projects", label: "Projects", icon: "fa-table-columns" },
];

const TRACK_COLORS = ["#7466F1", "#A259FF", "#2f7bf6", "#25d366", "#f59e0b"];

type TrackBlock = {
  id: string;
  title: string;
  color: string;
  offset: number;
  width: number;
};

/**
 * Studio shell in Suno's arrangement: library dock on the left, timeline in the
 * middle, details on the right, transport along the bottom. Built on Suno Studio
 * projects through the platform proxy.
 */
export function StudioShell() {
  const [songs, setSongs] = useState<WebMusicGeneration[]>([]);
  const [dock, setDock] = useState<Dock>("songs");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<WebMusicGeneration | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("Untitled Project");
  const [tracks, setTracks] = useState<TrackBlock[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [zoom, setZoom] = useState(1);
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);

  useEffect(() => {
    let active = true;
    listWebMusicGenerations(50)
      .then((page) => {
        if (active) setSongs(page.items);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Could not load songs");
      });
    return () => {
      active = false;
    };
  }, []);

  const visibleSongs = useMemo(() => {
    const term = search.trim().toLowerCase();
    const ready = songs.filter((song) => String(song.status).toUpperCase() === "SUCCESS");
    if (!term) return ready;
    return ready.filter((song) =>
      `${song.title} ${song.style ?? ""}`.toLowerCase().includes(term)
    );
  }, [songs, search]);

  async function openSong(song: WebMusicGeneration) {
    setSelected(song);
    setBusy(true);
    setError("");
    try {
      const clip = song.clips?.find((item) => item.ready) ?? song.clips?.[0];
      const variant = clip?.variant === "alt" ? "alt" : "ok";
      const session = await studioSessionForClip(song.id, variant);
      if (!projectId) {
        setProjectId(session.project_id);
        setProjectName(song.title || "Untitled Project");
      }
      setTracks((current) =>
        current.some((item) => item.id === song.id)
          ? current
          : [
              ...current,
              {
                id: song.id,
                title: clip?.title || song.title || "Clip",
                color: TRACK_COLORS[current.length % TRACK_COLORS.length],
                offset: Math.min(78, current.length * 6),
                width: 18,
              },
            ]
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not open the project");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="st-shell">
      <header className="st-top">
        <strong>CAMXORA Studio</strong>
        <span className="st-dot">·</span>
        <span className="st-project">{projectId ? projectName : "No project yet"}</span>
        {projectId ? <code className="st-pid">{projectId.slice(0, 8)}</code> : null}
        <span style={{ flex: 1 }} />
        <button
          type="button"
          className="s-btn s-btn-ghost"
          onClick={() => {
            setTracks([]);
            setProjectId(null);
            setSelected(null);
            setProjectName("Untitled Project");
          }}
        >
          <Icon name="fa-plus" /> New project
        </button>
        <button type="button" className="s-btn s-btn-primary" disabled={!tracks.length}>
          <Icon name="fa-download" /> Export
        </button>
      </header>

      <div className="st-body">
        <aside className="st-dock">
          <div className="st-dock-tabs">
            {DOCK.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`st-dock-tab${dock === item.id ? " on" : ""}`}
                onClick={() => setDock(item.id)}
                title={item.label}
              >
                <Icon name={item.icon} />
              </button>
            ))}
          </div>
          <div className="st-dock-panel">
            <div className="st-dock-title">{DOCK.find((d) => d.id === dock)?.label}</div>
            {dock === "songs" ? (
              <input
                className="s-input"
                placeholder="Search your songs"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            ) : null}
            <div className="st-list">
              {dock === "songs" && visibleSongs.length ? (
                visibleSongs.map((song) => (
                  <button
                    key={song.id}
                    type="button"
                    className={`st-item${selected?.id === song.id ? " on" : ""}`}
                    onClick={() => void openSong(song)}
                  >
                    <span
                      className="st-thumb"
                      style={
                        song.clips?.[0]?.image_url
                          ? { backgroundImage: `url(${song.clips[0].image_url})` }
                          : undefined
                      }
                    />
                    <span className="st-item-body">
                      <b>{song.title}</b>
                      <small>{song.style || "—"}</small>
                    </span>
                  </button>
                ))
              ) : dock === "songs" ? (
                <p className="s-note">No finished songs yet.</p>
              ) : (
                <p className="s-note">
                  {DOCK.find((d) => d.id === dock)?.label} is coming with the next
                  milestone.
                </p>
              )}
            </div>
          </div>
        </aside>

        <main className="st-canvas">
          <div className="st-ruler">
            {Array.from({ length: 16 }).map((_, index) => (
              <span key={index}>{index * 15}s</span>
            ))}
          </div>
          <div className="st-timeline">
            {tracks.length ? (
              tracks.map((track, index) => (
                <div className="st-track" key={track.id}>
                  <div className="st-track-head">
                    <span className="st-track-dot" style={{ background: track.color }} />
                    <b>{track.title}</b>
                    <span style={{ flex: 1 }} />
                    <button type="button" className="s-btn s-btn-icon sm" aria-label="Mute">
                      <Icon name="fa-volume-xmark" />
                    </button>
                    <button type="button" className="s-btn s-btn-icon sm" aria-label="Solo">
                      <Icon name="fa-headphones" />
                    </button>
                  </div>
                  <div className="st-lane">
                    <span
                      className="st-clip"
                      style={{
                        left: `${track.offset}%`,
                        width: `${track.width}%`,
                        background: `linear-gradient(90deg, ${track.color}cc, ${track.color}66)`,
                      }}
                    >
                      {track.title}
                    </span>
                  </div>
                  <span className="st-track-index">{index + 1}</span>
                </div>
              ))
            ) : (
              <div className="st-empty">
                <Icon name="fa-music" />
                <b>Add a clip to the timeline</b>
                <p className="s-note">
                  Pick a song in the library on the left. It opens its Suno Studio
                  project and drops onto a track.
                </p>
              </div>
            )}
            <div
              className="st-playhead"
              style={{ left: `${Math.min(98, position * zoom)}%` }}
            />
          </div>
        </main>

        <aside className="st-details">
          <div className="st-dock-title">Details</div>
          {selected ? (
            <>
              <b className="st-details-title">{selected.title}</b>
              <p className="s-note">{selected.style || "No style"}</p>
              <div className="st-detail-row">
                <span>Model</span>
                <b>{selected.model_label || selected.model || "V6"}</b>
              </div>
              <div className="st-detail-row">
                <span>Project</span>
                <b>{projectId ? projectId.slice(0, 8) : "—"}</b>
              </div>
              <div className="st-detail-row">
                <span>Clips</span>
                <b>{tracks.length}</b>
              </div>
              <div className="st-dock-title" style={{ marginTop: 16 }}>
                Lyrics
              </div>
              <pre className="st-lyrics">{selected.lyrics || "Instrumental"}</pre>
            </>
          ) : (
            <p className="s-note">Select a clip to see its details and lyrics.</p>
          )}
        </aside>
      </div>

      <footer className="st-transport">
        <button
          type="button"
          className="s-btn s-btn-icon"
          aria-label="Play"
          onClick={() => setPlaying((value) => !value)}
        >
          <Icon name={playing ? "fa-pause" : "fa-play"} />
        </button>
        <span className="st-time">0:00 / {tracks.length ? "3:00" : "0:00"}</span>
        <input
          type="range"
          min={0}
          max={100}
          value={position}
          aria-label="Playhead"
          onChange={(event) => setPosition(Number(event.target.value))}
          style={{ flex: 1 }}
        />
        <span className="s-note">Zoom</span>
        <input
          type="range"
          min={0.5}
          max={2}
          step={0.1}
          value={zoom}
          aria-label="Zoom"
          onChange={(event) => setZoom(Number(event.target.value))}
          style={{ width: 120 }}
        />
        {busy ? <span className="s-note">Opening project…</span> : null}
        {error ? <span className="s-error">{error}</span> : null}
      </footer>
    </div>
  );
}
