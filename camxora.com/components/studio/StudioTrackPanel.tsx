"use client";

import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import type { StudioTrack } from "@/lib/studio-tracks";

/**
 * Track panel: the gutter list — number, name, mute/solo/arm, the per-track options
 * menu, two level sliders, Add new track, and the hidden-tracks surface (S21).
 *
 * Extracted from the shell (roadmap G15). Every action is a callback so the shell keeps
 * ownership of the document write path (and therefore undo/redo).
 */

const ROW_HEIGHT = 85;
const ROW_STEP = 86;

const TRACK_COLORS = ["#38bdf8", "#a78bfa", "#f472b6", "#fb923c", "#4ade80"];

export type StudioTrackPanelProps = {
  tracks: StudioTrack[];
  selectedTrack: string | null;
  menuTrackId: string | null;
  renameTrackId: string | null;
  renameValue: string;
  hiddenOpen: boolean;

  onSelectTrack: (trackId: string) => void;
  onToggleMenu: (trackId: string | null) => void;
  onToggleFlag: (trackId: string, flag: "muted" | "solo") => void;
  /** Arm exactly one track for recording (D-020). */
  onToggleArm: (trackId: string) => void;
  onUpdateTrack: (trackId: string, patch: Partial<StudioTrack>) => void;
  /** Live slider movement without a history entry; commit on release. */
  onPreviewTrack: (trackId: string, patch: Partial<StudioTrack>) => void;
  onRenameStart: (track: StudioTrack) => void;
  onRenameChange: (value: string) => void;
  onRenameCommit: () => void;
  onRenameCancel: () => void;
  onDuplicate: (trackId: string) => void;
  onHide: (trackId: string) => void;
  onDelete: (trackId: string) => void;
  onAddTrack: () => void;
  onAddUploadTrack: () => void;
  onToggleHidden: () => void;
  onShowAllHidden: () => void;
  /** Capture head: one control expands or collapses every visible track. */
  onToggleAllCollapsed: () => void;

  /** Master strip pinned at the panel bottom (reference F-01/F-02). */
  masterVolume: number;
  masterMuted: boolean;
  onMasterVolume: (value: number) => void;
  onMasterCommit: () => void;
  onToggleMasterMute: () => void;
};

export function StudioTrackPanel(props: StudioTrackPanelProps) {
  const {
    tracks,
    selectedTrack,
    menuTrackId,
    renameTrackId,
    renameValue,
    hiddenOpen,
    onSelectTrack,
    onToggleMenu,
    onToggleFlag,
    onToggleArm,
    onUpdateTrack,
    onPreviewTrack,
    onRenameStart,
    onRenameChange,
    onRenameCommit,
    onRenameCancel,
    onDuplicate,
    onHide,
    onDelete,
    onAddTrack,
    onAddUploadTrack,
    onToggleHidden,
    onShowAllHidden,
    onToggleAllCollapsed,
    masterVolume,
    masterMuted,
    onMasterVolume,
    onMasterCommit,
    onToggleMasterMute,
  } = props;

  const visible = tracks.filter((track) => !track.hidden);
  const allCollapsed =
    visible.length > 0 && visible.every((track) => track.collapsed);
  const hiddenTracks = tracks.filter((track) => track.hidden);

  // Add-track menu (§8.3). Local state: nothing outside this panel depends on it.
  const [addOpen, setAddOpen] = useState(false);
  const addRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!addOpen) return;
    const onPointer = (event: PointerEvent) => {
      if (addRef.current && !addRef.current.contains(event.target as Node)) setAddOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setAddOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [addOpen]);

  return (
    <aside className="se-tracks" aria-label="Tracks">
      <div className="se-tracks-head">
        <button
          type="button"
          className="se-icon"
          aria-label={allCollapsed ? "Expand all track controls" : "Collapse all track controls"}
          title={allCollapsed ? "Expand all track controls" : "Collapse all track controls"}
          onClick={onToggleAllCollapsed}
        >
          <Icon name="fa-bars" />
        </button>
        <span className="se-sr-only">
          {tracks.length} track{tracks.length === 1 ? "" : "s"}
        </span>
        <button
          type="button"
          className="se-icon"
          aria-label="Collapse track panel"
          title="Panel collapse is not built in this editor"
          disabled
        >
          <Icon name="fa-angles-right" />
        </button>
      </div>

      <div className="se-track-list">
        {visible.map((track, index) => {
          const active = selectedTrack === track.id;
          return (
            <div
              key={track.id}
              className={`se-track${active ? " selected" : ""}`}
              style={{ height: ROW_HEIGHT, marginBottom: ROW_STEP - ROW_HEIGHT }}
            >
              {menuTrackId === track.id ? (
                <div className="se-track-menu" role="menu" aria-label={`${track.name} options`}>
                  <button type="button" role="menuitem" onClick={() => onRenameStart(track)}>
                    <Icon name="fa-pen" /> Rename track
                  </button>
                  <div className="se-track-menu-colors" role="group" aria-label="Track colour">
                    <span className="se-track-menu-label">Color</span>
                    {TRACK_COLORS.map((color) => (
                      <button
                        key={color}
                        type="button"
                        aria-label={`Use ${color}`}
                        style={{ background: color }}
                        className={track.color === color ? "on" : undefined}
                        onClick={() => {
                          onUpdateTrack(track.id, { color });
                          onToggleMenu(null);
                        }}
                      />
                    ))}
                  </div>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      onUpdateTrack(track.id, { collapsed: !track.collapsed });
                      onToggleMenu(null);
                    }}
                  >
                    <Icon name="fa-thumbtack" />
                    {track.collapsed ? "Expand controls" : "Collapse controls"}
                  </button>
                  <button type="button" role="menuitem" onClick={() => onDuplicate(track.id)}>
                    <Icon name="fa-copy" /> Duplicate
                  </button>
                  <button type="button" role="menuitem" onClick={() => onHide(track.id)}>
                    <Icon name="fa-eye-slash" /> Hide &amp; Mute Track
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className="danger"
                    onClick={() => onDelete(track.id)}
                  >
                    <Icon name="fa-trash" /> Delete
                  </button>
                </div>
              ) : null}

              <span className="se-track-color" style={{ background: track.color }} aria-hidden="true" />

              <div className="se-track-top">
                <span className="se-track-index">{index + 1}</span>
                {renameTrackId === track.id ? (
                  <input
                    className="se-track-rename"
                    value={renameValue}
                    autoFocus
                    onChange={(event) => onRenameChange(event.target.value)}
                    onBlur={onRenameCommit}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") onRenameCommit();
                      if (event.key === "Escape") onRenameCancel();
                    }}
                    aria-label="Track name"
                  />
                ) : (
                  <button
                    type="button"
                    className="se-track-name"
                    onClick={() => onSelectTrack(track.id)}
                    aria-pressed={active}
                  >
                    {track.name}
                  </button>
                )}

                <span className="se-track-buttons">
                <button
                  type="button"
                  aria-label={`Mute ${track.name}`}
                  aria-pressed={track.muted}
                  className={track.muted ? "on" : undefined}
                  onClick={() => onToggleFlag(track.id, "muted")}
                  data-help="track-mute"
                >
                  <Icon name="fa-volume-high" />
                </button>
                <button
                  type="button"
                  aria-label={`Solo ${track.name}`}
                  aria-pressed={track.solo}
                  className={track.solo ? "on" : undefined}
                  onClick={() => onToggleFlag(track.id, "solo")}
                  data-help="track-solo"
                >
                  S
                </button>
                <button
                  type="button"
                  aria-label={`${track.armed ? "Disarm" : "Arm"} ${track.name}`}
                  aria-pressed={Boolean(track.armed)}
                  className={track.armed ? "on" : undefined}
                  onClick={() => onToggleArm(track.id)}
                  data-help="track-arm"
                >
                  A
                </button>
                <button
                  type="button"
                  aria-label={`Options for ${track.name}`}
                  aria-haspopup="menu"
                  aria-expanded={menuTrackId === track.id}
                  onClick={() => onToggleMenu(menuTrackId === track.id ? null : track.id)}
                >
                  <Icon name="fa-chevron-down" />
                </button>
              </span>
              </div>

              {track.collapsed ? null : (
                <div className="se-track-sliders">
                  <input
                    type="range"
                    className="se-track-slider"
                    min={0}
                    max={100}
                    step={1}
                    value={track.volume}
                    aria-label={`Volume ${track.name}`}
                    data-help="track-volume"
                    onChange={(event) =>
                      onPreviewTrack(track.id, { volume: Number(event.target.value) })
                    }
                    onPointerUp={() => onUpdateTrack(track.id, { volume: track.volume })}
                    onKeyUp={() => onUpdateTrack(track.id, { volume: track.volume })}
                    onBlur={() => onUpdateTrack(track.id, { volume: track.volume })}
                  />
                  <input
                    type="range"
                    className="se-track-slider pan"
                    min={-100}
                    max={100}
                    step={1}
                    value={track.pan}
                    aria-label={`Pan ${track.name}`}
                    onChange={(event) =>
                      onPreviewTrack(track.id, { pan: Number(event.target.value) })
                    }
                    onPointerUp={() => onUpdateTrack(track.id, { pan: track.pan })}
                    onKeyUp={() => onUpdateTrack(track.id, { pan: track.pan })}
                    onBlur={() => onUpdateTrack(track.id, { pan: track.pan })}
                  />
                </div>
              )}
            </div>
          );
        })}

        <div className="se-add-wrap" ref={addRef}>
          <button
            type="button"
            className="se-add-track"
            aria-haspopup="menu"
            aria-expanded={addOpen}
            onClick={() => setAddOpen((value) => !value)}
          >
            <Icon name="fa-plus" /> Add new track
          </button>
          {addOpen ? (
            <div className="se-add-menu" role="menu" aria-label="Add a track">
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setAddOpen(false);
                  onAddTrack();
                }}
              >
                <span className="se-add-icon" data-tone="audio">
                  <Icon name="fa-music" />
                </span>
                Audio <span className="se-add-key">A</span>
              </button>
              <button
                type="button"
                role="menuitem"
                disabled
                title="MIDI tracks are not built in this editor"
              >
                <span className="se-add-icon" data-tone="midi">
                  <Icon name="fa-table-columns" />
                </span>
                MIDI <span className="se-add-key">M</span>
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setAddOpen(false);
                  onAddUploadTrack();
                }}
              >
                <span className="se-add-icon" data-tone="upload">
                  <Icon name="fa-arrow-up-from-bracket" />
                </span>
                Upload <span className="se-add-key">U</span>
              </button>
            </div>
          ) : null}
        </div>

        {hiddenTracks.length > 0 ? (
          <div className="se-hidden-wrap">
            <button
              type="button"
              className="se-hidden-pill"
              aria-label={`${hiddenTracks.length} hidden track${hiddenTracks.length === 1 ? "" : "s"}`}
              aria-expanded={hiddenOpen}
              onClick={onToggleHidden}
            >
              {hiddenTracks.length}
            </button>
            {hiddenOpen ? (
              <div className="se-hidden-pop" role="dialog" aria-label="Hidden tracks">
                <div className="se-hidden-head">
                  <strong>Hidden tracks</strong>
                  <button
                    type="button"
                    className="se-icon"
                    aria-label="Close hidden tracks"
                    onClick={onToggleHidden}
                  >
                    <Icon name="fa-xmark" />
                  </button>
                </div>
                {hiddenTracks.map((track) => (
                  <div key={track.id} className="se-hidden-row">
                    <span className="se-track-color" style={{ background: track.color }} aria-hidden="true" />
                    <span>{track.name}</span>
                    <button
                      type="button"
                      className="se-pill"
                      onClick={() => onUpdateTrack(track.id, { hidden: false })}
                    >
                      Show
                    </button>
                    <button
                      type="button"
                      className="se-pill"
                      onClick={() => onUpdateTrack(track.id, { muted: !track.muted })}
                    >
                      {track.muted ? "Unmute" : "Mute"}
                    </button>
                  </div>
                ))}
                <button type="button" className="se-pill on" onClick={onShowAllHidden}>
                  Show All Hidden Tracks
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="se-master-strip" data-help="master">
        <div className="se-master-head">
          <span className="se-master-label">Main</span>
          <button
            type="button"
            className={`se-icon${masterMuted ? " on" : ""}`}
            aria-pressed={masterMuted}
            aria-label="Mute main"
            onClick={onToggleMasterMute}
          >
            <Icon name={masterMuted ? "fa-volume-xmark" : "fa-volume-high"} />
          </button>
        </div>
        <input
          type="range"
          className="se-track-slider"
          min={0}
          max={100}
          step={1}
          value={masterVolume}
          aria-label="Master volume"
          onChange={(event) => onMasterVolume(Number(event.target.value))}
          onPointerUp={onMasterCommit}
          onKeyUp={onMasterCommit}
          onBlur={onMasterCommit}
        />
      </div>
    </aside>
  );
}
