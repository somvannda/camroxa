"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import { fetchGenerations, type WebMusicGeneration } from "@/lib/library-api";

type Lane = {
  id: string;
  title: string;
  color: string;
  muted: boolean;
  solo: boolean;
  volume: number;
  pan: number;
  left: number;
  width: number;
};

const colors = ["#7c3aed", "#0ea5e9", "#22c55e", "#f59e0b", "#ec4899"];

function buildLanes(items: WebMusicGeneration[]): Lane[] {
  return items.slice(0, 5).map((item, index) => ({
    id: item.id,
    title: item.title || "Untitled",
    color: colors[index % colors.length],
    muted: false,
    solo: false,
    volume: 80,
    pan: 0,
    left: 4 + index * 3,
    width: 58 - index * 4,
  }));
}

export function StudioEditorView() {
  const { user, loading: authLoading } = useAuth();
  const [items, setItems] = useState<WebMusicGeneration[]>([]);
  const [lanes, setLanes] = useState<Lane[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [playhead, setPlayhead] = useState(18);
  const [bpm, setBpm] = useState(90);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    if (authLoading || !user) return;
    let active = true;
    fetchGenerations(20)
      .then((next) => {
        if (!active) return;
        setItems(next);
        setLanes(buildLanes(next));
        setSelected(next[0] ? buildLanes(next)[0].id : null);
      })
      .catch(() => {
        if (active) setItems([]);
      });
    return () => {
      active = false;
    };
  }, [authLoading, user]);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setPlayhead((value) => (value >= 100 ? 0 : value + 0.2));
    }, 120);
    return () => window.clearInterval(timer);
  }, [playing]);

  const active = lanes.find((lane) => lane.id === selected) ?? lanes[0] ?? null;

  function updateLane(patch: Partial<Lane>) {
    if (!active) return;
    setLanes((current) => current.map((lane) => (lane.id === active.id ? { ...lane, ...patch } : lane)));
  }

  function removeLane(id: string) {
    setLanes((current) => current.filter((lane) => lane.id !== id));
    if (selected === id) setSelected(null);
  }

  if (authLoading) {
    return <p className="fine" style={{ textAlign: "left" }}>Loading studio…</p>;
  }

  if (!user) {
    return (
      <div className="page">
        <div className="invite-signin panel">
          <span className="invite-hero-icon"><Icon name="fa-table-columns" /></span>
          <h1>Studio</h1>
          <p>Sign in to open your tracks in the Camxora Studio editor.</p>
          <Link className="btn btn-primary" href="/login?next=/studio/editor">Sign in</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page studio-editor-page">
      <div className="studio-editor-head">
        <div>
          <div className="eyebrow">Studio</div>
          <h1>Untitled session</h1>
          <span>Saved locally · {lanes.length} tracks</span>
        </div>
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/create">Create a track</Link>
          <button className="btn btn-primary" type="button" disabled title="Render engine not connected yet">
            <Icon name="fa-download" /> Export
          </button>
        </div>
      </div>

      <div className="studio-toolbar">
        <button className="studio-icon-btn" type="button" aria-label="Undo"><Icon name="fa-rotate-left" /></button>
        <button className="studio-icon-btn" type="button" aria-label="Redo"><Icon name="fa-rotate-right" /></button>
        <span className="studio-toolbar-divider" />
        <button className="studio-icon-btn" type="button" aria-label="Cut"><Icon name="fa-scissors" /></button>
        <button className="studio-icon-btn" type="button" aria-label="Trim"><Icon name="fa-crop" /></button>
        <span className="studio-toolbar-divider" />
        <label className="studio-bpm">BPM <input type="number" min={40} max={220} value={bpm} onChange={(event) => setBpm(Number(event.target.value))} /></label>
        <label className="studio-zoom">Zoom <input type="range" min="0.6" max="1.8" step="0.1" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label>
        <span className="studio-toolbar-spacer" />
        <span className="studio-time">{`00:${String(Math.floor(playhead / 5)).padStart(2, "0")}:${String(Math.floor((playhead % 5) * 12)).padStart(2, "0")}`}</span>
      </div>

      <div className="studio-work">
        <aside className="studio-library">
          <div className="sec-head"><h2>Library</h2><Link href="/library">All</Link></div>
          {!items.length ? (
            <div className="studio-library-empty">
              <Icon name="fa-music" />
              <p>No generated tracks yet.</p>
              <Link className="btn btn-ghost" href="/create">Create one</Link>
            </div>
          ) : (
            <div className="studio-library-list">
              {items.map((item) => {
                const added = lanes.some((lane) => lane.id === item.id);
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`studio-lib-item${added ? " added" : ""}`}
                    onClick={() => {
                      if (added) return;
                      setLanes((current) => [
                        ...current,
                        {
                          id: item.id,
                          title: item.title || "Untitled",
                          color: colors[current.length % colors.length],
                          muted: false,
                          solo: false,
                          volume: 80,
                          pan: 0,
                          left: 4 + current.length * 3,
                          width: 58 - current.length * 4,
                        },
                      ]);
                    }}
                  >
                    <span className="studio-lib-icon"><Icon name="fa-music" /></span>
                    <span><b>{item.title || "Untitled"}</b><small>{item.style || "Camxora"}</small></span>
                    <Icon name={added ? "fa-check" : "fa-plus"} />
                  </button>
                );
              })}
            </div>
          )}
        </aside>

        <section className="studio-timeline">
          <div className="studio-ruler">
            {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((bar) => <span key={bar}>{bar + 1}</span>)}
          </div>
          <div className="studio-lanes" style={{ "--studio-zoom": zoom } as React.CSSProperties}>
            {lanes.map((lane, index) => (
              <div className="studio-lane" key={lane.id}>
                <button className="studio-lane-head" type="button" onClick={() => setSelected(lane.id)}>
                  <span className="studio-lane-dot" style={{ background: lane.color }} />
                  <b>{lane.title}</b>
                  <small>{index + 1}</small>
                </button>
                <div className="studio-lane-track">
                  <button
                    className="studio-clip"
                    type="button"
                    style={{ left: `${lane.left}%`, width: `${lane.width}%`, borderColor: lane.color }}
                    onClick={() => setSelected(lane.id)}
                  >
                    <span style={{ background: lane.color }} />
                    <b>{lane.title}</b>
                    <i />
                  </button>
                </div>
                <div className="studio-lane-controls">
                  <button type="button" className={lane.muted ? "on" : ""} onClick={() => updateLane({ muted: !lane.muted })}>M</button>
                  <button type="button" className={lane.solo ? "on" : ""} onClick={() => updateLane({ solo: !lane.solo })}>S</button>
                  <button type="button" aria-label={`Remove ${lane.title}`} onClick={() => removeLane(lane.id)}><Icon name="fa-xmark" /></button>
                </div>
              </div>
            ))}
            {!lanes.length ? (
              <div className="studio-timeline-empty">
                <Icon name="fa-table-columns" />
                <h3>Your session is empty</h3>
                <p>Add a generated track from the library to start arranging.</p>
              </div>
            ) : null}
            <div className="studio-playhead" style={{ left: `${playhead}%` }} />
          </div>
        </section>

        <aside className="studio-inspector">
          <div className="sec-head"><h2>Inspector</h2></div>
          {!active ? (
            <p className="fine" style={{ textAlign: "left" }}>Select a track to edit.</p>
          ) : (
            <>
              <div className="studio-inspector-title">
                <span style={{ background: active.color }} />
                <div><b>{active.title}</b><small>Audio track</small></div>
              </div>
              <label className="studio-slider">Volume <b>{active.volume}%</b>
                <input type="range" min="0" max="100" value={active.volume} onChange={(event) => updateLane({ volume: Number(event.target.value) })} />
              </label>
              <label className="studio-slider">Pan <b>{active.pan === 0 ? "C" : active.pan > 0 ? `R${active.pan}` : `L${Math.abs(active.pan)}`}</b>
                <input type="range" min="-50" max="50" value={active.pan} onChange={(event) => updateLane({ pan: Number(event.target.value) })} />
              </label>
              <div className="studio-inspector-actions">
                <button className={active.muted ? "on" : ""} type="button" onClick={() => updateLane({ muted: !active.muted })}>Mute</button>
                <button className={active.solo ? "on" : ""} type="button" onClick={() => updateLane({ solo: !active.solo })}>Solo</button>
              </div>
              <div className="studio-inspector-note">
                <Icon name="fa-circle-info" /> Editing is preview-only. Export needs the render engine.
              </div>
            </>
          )}
        </aside>
      </div>

      <div className="studio-transport">
        <span className="studio-transport-left"><Icon name="fa-wave-square" /> {bpm} BPM · 4/4</span>
        <div className="studio-transport-center">
          <button type="button" aria-label="Go to start" onClick={() => setPlayhead(0)}><Icon name="fa-backward-step" /></button>
          <button className="play" type="button" aria-label={playing ? "Pause" : "Play"} onClick={() => setPlaying((value) => !value)}>
            <Icon name={playing ? "fa-pause" : "fa-play"} />
          </button>
          <button type="button" aria-label="Go to end" onClick={() => setPlayhead(100)}><Icon name="fa-forward-step" /></button>
        </div>
        <span className="studio-transport-right"><Icon name="fa-volume-high" /> Master</span>
      </div>
    </div>
  );
}
