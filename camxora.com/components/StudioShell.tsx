"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { Icon } from "@/components/Icon";
import type { WebMusicGeneration } from "@/lib/library-api";
import {
  getStudioSession,
  listWebMusicGenerations,
  studioSessionForClip,
} from "@/lib/web-music-api";

const BARS = 24;
const COLORS = ["#7466F1", "#A259FF", "#2f7bf6", "#25d366", "#f59e0b"];

type Track = {
  id: string;
  name: string;
  color: string;
  clipIds: string[];
  muted: boolean;
  solo: boolean;
  volume: number;
};

function clock(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

/**
 * Suno's project view: track panel on the left, bar-numbered timeline in the
 * middle, prompt bar along the bottom, transport in the header.
 */
export function StudioShell() {
  const params = useSearchParams();
  const projectParam = params.get("project");

  const [songs, setSongs] = useState<WebMusicGeneration[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [selectedTrack, setSelectedTrack] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("Untitled Project");
  const [projectId, setProjectId] = useState<string | null>(projectParam);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [activeUrl, setActiveUrl] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const timer = useRef<number | null>(null);

  useEffect(() => {
    let active = true;
    listWebMusicGenerations(50)
      .then((page) => {
        if (active) setSongs(page.items);
      })
      .catch(() => {
        if (active) setError("Could not load your songs");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!projectParam) return;
    let active = true;
    setProjectId(projectParam);
    getStudioSession(projectParam)
      .then((session) => {
        if (!active) return;
        const title = (session as { title?: string }).title;
        if (title) setProjectName(title);
      })
      .catch(() => {
        /* older project or a signed-out pool: keep the id we have */
      });
    return () => {
      active = false;
    };
  }, [projectParam]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) void audio.play().catch(() => setPlaying(false));
    else audio.pause();
  }, [playing, activeUrl]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTime = () => setSeconds(audio.currentTime);
    const onEnd = () => setPlaying(false);
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("ended", onEnd);
    return () => {
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("ended", onEnd);
    };
  }, []);

  const readySongs = useMemo(
    () => songs.filter((song) => String(song.status).toUpperCase() === "SUCCESS"),
    [songs]
  );
  const positionPercent = (seconds / 30) * 100;
  const bar = Math.max(1, Math.floor(seconds / 1.25) + 1);

  function addTrack(name = "Audio Track") {
    const track: Track = {
      id: `${Date.now()}-${tracks.length}`,
      name,
      color: COLORS[tracks.length % COLORS.length],
      clipIds: [],
      muted: false,
      solo: false,
      volume: 80,
    };
    setTracks((current) => [...current, track]);
    setSelectedTrack(track.id);
  }

  async function addSongToTrack(song: WebMusicGeneration, trackId: string) {
    setBusy(true);
    setError("");
    try {
      const clip = song.clips?.find((item) => item.ready) ?? song.clips?.[0];
      const variant = clip?.variant === "alt" ? "alt" : "ok";
      const session = await studioSessionForClip(song.id, variant);
      if (!projectId) setProjectId(session.project_id);
      setActiveUrl(
        clip?.audio_url ||
          `/api/v3/web-music/generations/${song.id}/stream/${variant}`
      );
      setTracks((current) =>
        current.map((track) =>
          track.id === trackId
            ? { ...track, clipIds: [...track.clipIds, song.id] }
            : track
        )
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not open this song");
    } finally {
      setBusy(false);
    }
  }

  async function addSongToTimeline(song: WebMusicGeneration) {
    setBusy(true);
    setError("");
    try {
      const clip = song.clips?.find((item) => item.ready) ?? song.clips?.[0];
      const variant = clip?.variant === "alt" ? "alt" : "ok";
      const session = await studioSessionForClip(song.id, variant);
      if (!projectId) setProjectId(session.project_id);
      setActiveUrl(
        clip?.audio_url ||
          `/api/v3/web-music/generations/${song.id}/stream/${variant}`
      );
      setTracks((current) => {
        const target = current.find((track) => track.id === selectedTrack) ?? current[0];
        if (target) {
          return current.map((track) =>
            track.id === target.id
              ? { ...track, clipIds: [...track.clipIds, song.id] }
              : track
          );
        }
        return [
          {
            id: `${Date.now()}-0`,
            name: "Audio Track",
            color: COLORS[0],
            clipIds: [song.id],
            muted: false,
            solo: false,
            volume: 80,
          },
        ];
      });
      if (!tracks.length) setSelectedTrack(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not open this song");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stv">
      <audio ref={audioRef} src={activeUrl} preload="metadata" />
      <header className="stv-top">
        <span className="st-chrome-project">{projectName}</span>
        <span className="st-chrome-dots">···</span>
        <span style={{ flex: 1 }} />
        <div className="stv-transport">
          <button type="button" className="stv-icon" aria-label="Go to start" onClick={() => setSeconds(0)}>
            <Icon name="fa-backward-step" />
          </button>
          <button
            type="button"
            className="stv-icon"
            aria-label={playing ? "Pause" : "Play"}
            onClick={() => setPlaying((value) => !value)}
          >
            <Icon name={playing ? "fa-pause" : "fa-play"} />
          </button>
          <button type="button" className="stv-icon" aria-label="Metronome">
            <Icon name="fa-hourglass-half" />
          </button>
          <span className="stv-clock">{clock(seconds)}</span>
          <span className="stv-bars">{String(bar).padStart(3, "0")}.1.1</span>
        </div>
        <span style={{ flex: 1 }} />
        <span className="stv-bpm">120 BPM</span>
        <span className="stv-sig">4/4</span>
        <button type="button" className="s-btn s-btn-ghost" disabled={!tracks.length}>
          <Icon name="fa-arrow-up-from-bracket" /> Export
        </button>
        <button
          type="button"
          className="s-btn s-btn-ghost"
          onClick={() => setLibraryOpen((value) => !value)}
        >
          <Icon name="fa-folder-open" /> Library
        </button>
      </header>

      <div className="stv-body">
        <aside className="stv-tracks">
          {tracks.map((track, index) => (
            <div
              key={track.id}
              className={`stv-track${selectedTrack === track.id ? " on" : ""}`}
              onClick={() => setSelectedTrack(track.id)}
            >
              <div className="stv-track-top">
                <span className="stv-track-num">{index + 1}</span>
                <b>{track.name}</b>
                <span style={{ flex: 1 }} />
                <button
                  type="button"
                  className={`stv-pill${track.solo ? " on" : ""}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    setTracks((current) =>
                      current.map((item) =>
                        item.id === track.id ? { ...item, solo: !item.solo } : item
                      )
                    );
                  }}
                >
                  S
                </button>
                <button
                  type="button"
                  className={`stv-pill${track.muted ? " on" : ""}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    setTracks((current) =>
                      current.map((item) =>
                        item.id === track.id ? { ...item, muted: !item.muted } : item
                      )
                    );
                  }}
                >
                  M
                </button>
                <button type="button" className="stv-pill" aria-label="Record arm">
                  <Icon name="fa-circle" />
                </button>
              </div>
              <div className="stv-fader">
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={track.volume}
                  aria-label={`${track.name} volume`}
                  onChange={(event) =>
                    setTracks((current) =>
                      current.map((item) =>
                        item.id === track.id
                          ? { ...item, volume: Number(event.target.value) }
                          : item
                      )
                    )
                  }
                />
                <span className="stv-track-fx"><Icon name="fa-sliders" /></span>
              </div>
            </div>
          ))}
          <button type="button" className="stv-add-track" onClick={() => addTrack()}>
            <Icon name="fa-plus" /> Add new track
          </button>
        </aside>

        <main className="stv-canvas">
          <div className="stv-ruler">
            {Array.from({ length: BARS }).map((_, index) => (
              <span key={index} style={{ width: `${100 / BARS}%` }}>
                {index + 1}
              </span>
            ))}
          </div>
          <div className="stv-grid">
            {Array.from({ length: BARS }).map((_, index) => (
              <span key={index} style={{ left: `${(index / BARS) * 100}%` }} />
            ))}
            {tracks.map((track, index) => (
              <div
                className="stv-lane"
                key={track.id}
                style={{ top: index * 58 }}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  const songId = event.dataTransfer.getData("text/song");
                  const song = songs.find((item) => item.id === songId);
                  if (song) void addSongToTrack(song, track.id);
                }}
              >
                {track.clipIds.map((clipId, clipIndex) => {
                  const song = songs.find((item) => item.id === clipId);
                  return (
                    <span
                      key={`${clipId}-${clipIndex}`}
                      className="stv-clip"
                      style={{
                        left: `${clipIndex * 18}%`,
                        width: "16%",
                        background: `linear-gradient(90deg, ${track.color}dd, ${track.color}77)`,
                      }}
                    >
                      {song?.title || "Clip"}
                    </span>
                  );
                })}
              </div>
            ))}
            <div className="stv-playhead" style={{ left: `${positionPercent}%` }} />
            {!tracks.length ? (
              <div className="stv-empty">
                <Icon name="fa-music" />
                <b>Add a track, then drop a song on it</b>
                <p className="s-note">Use “Add new track” on the left, then Library.</p>
              </div>
            ) : null}
          </div>
        </main>

        {libraryOpen ? (
          <aside className="stv-library">
            <div className="stv-library-head">
              <b>Library</b>
              <button
                type="button"
                className="stv-icon"
                aria-label="Close library"
                onClick={() => setLibraryOpen(false)}
              >
                <Icon name="fa-xmark" />
              </button>
            </div>
            <div className="stv-library-list">
              {readySongs.length ? (
                readySongs.map((song) => (
                  <button
                    key={song.id}
                    type="button"
                    className="stv-library-row"
                    draggable
                    onDragStart={(event) => {
                      event.dataTransfer.setData("text/song", song.id);
                      event.dataTransfer.effectAllowed = "copy";
                    }}
                    disabled={busy}
                    onClick={() => void addSongToTimeline(song)}
                  >
                    <span
                      className="stv-art"
                      style={
                        song.clips?.[0]?.image_url
                          ? { backgroundImage: `url(${song.clips[0].image_url})` }
                          : undefined
                      }
                    />
                    <span className="stv-library-body">
                      <b>{song.title}</b>
                      <small>{song.style || "—"}</small>
                    </span>
                    <Icon name="fa-plus" />
                  </button>
                ))
              ) : (
                <p className="s-note">No finished songs yet.</p>
              )}
            </div>
          </aside>
        ) : null}
      </div>

      <footer className="stv-bottom">
        <div className="stv-master">
          <span className="stv-master-label">Main</span>
          <input type="range" min={0} max={100} defaultValue={80} aria-label="Master volume" />
          <Icon name="fa-volume-high" />
        </div>
        <div className="stv-prompt">
          <button type="button" className="stv-icon" aria-label="Add">
            <Icon name="fa-plus" />
          </button>
          <input
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Select a spot on the timeline and ask me to add a part"
            aria-label="Ask Studio to add a part"
          />
          <span className="stv-model">V6</span>
          <button
            type="button"
            className="stv-icon"
            aria-label="Send"
            disabled={!prompt.trim()}
            onClick={() => setPrompt("")}
          >
            <Icon name="fa-arrow-up" />
          </button>
        </div>
        <div className="stv-tools">
          <span className="s-note">Zoom</span>
          <input
            type="range"
            min={0.5}
            max={2}
            step={0.1}
            value={zoom}
            aria-label="Zoom"
            onChange={(event) => setZoom(Number(event.target.value))}
          />
          {busy ? <span className="s-note">Opening…</span> : null}
          {error ? <span className="s-error">{error}</span> : null}
        </div>
      </footer>
    </div>
  );
}
