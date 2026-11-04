"use client";

import { Icon } from "@/components/Icon";
import { StudioSaveStatus, type SaveStatus } from "@/components/studio/StudioSaveStatus";
import { formatMeter, type MeterReading } from "@/lib/studio-meter";

/**
 * Editor header: identity, transport, tempo, and the readouts/actions that belong to
 * the whole session (save state, master meter, audition speed, export, library).
 *
 * Extracted from the shell (roadmap G15) with an explicit prop contract, so the
 * transport can be reviewed and eventually tested without loading 1,800 lines.
 */

export type StudioHeaderProps = {
  title: string;
  timeSignature: string;
  clock: string;
  barBeat: string;
  bpm: number;
  onBpmChange: (value: number) => void;
  onBpmCommit: () => void;

  playing: boolean;
  loop: boolean;
  metronome: boolean;
  canUndo: boolean;
  canRedo: boolean;

  saveStatus: SaveStatus;
  onRetrySave: () => void;
  meter: MeterReading | null;
  playbackRate: number;
  onCycleSpeed: () => void;

  exportOpen: boolean;
  exporting: boolean;
  rangeReady: boolean;
  onToggleExport: () => void;
  onExport: (scope: "mix" | "tracks" | "range" | "json") => void;

  libraryOpen: boolean;
  onToggleLibrary: () => void;

  onBackToStart: () => void;
  onTogglePlay: () => void;
  onToggleLoop: () => void;
  onToggleMetronome: () => void;
  onUndo: () => void;
  onRedo: () => void;
};

export function StudioHeader(props: StudioHeaderProps) {
  const {
    title,
    timeSignature,
    clock,
    barBeat,
    bpm,
    onBpmChange,
    onBpmCommit,
    playing,
    loop,
    metronome,
    canUndo,
    canRedo,
    saveStatus,
    onRetrySave,
    meter,
    playbackRate,
    onCycleSpeed,
    exportOpen,
    exporting,
    rangeReady,
    onToggleExport,
    onExport,
    libraryOpen,
    onToggleLibrary,
    onBackToStart,
    onTogglePlay,
    onToggleLoop,
    onToggleMetronome,
    onUndo,
    onRedo,
  } = props;

  return (
    <header className="se-head">
      <div className="se-head-left">
        <span className="se-logo">CAMXORA</span>
        <button type="button" className="se-chip" disabled title="Project menu is not wired in the shell yet">
          {title}
          <Icon name="fa-chevron-down" />
        </button>
        <button type="button" className="se-icon" aria-label="Undo" disabled={!canUndo} onClick={onUndo}>
          <Icon name="fa-rotate-left" />
        </button>
        <button type="button" className="se-icon" aria-label="Redo" disabled={!canRedo} onClick={onRedo}>
          <Icon name="fa-rotate-right" />
        </button>
      </div>

      <div className="se-head-center">
        <button type="button" className="se-icon" onClick={onBackToStart} aria-label="Back to start">
          <Icon name="fa-backward-step" />
        </button>
        <button
          type="button"
          className={`se-icon${loop ? " on" : ""}`}
          onClick={onToggleLoop}
          aria-pressed={loop}
          aria-label="Loop"
          title="Loop"
        >
          <Icon name="fa-repeat" />
        </button>
        <button type="button" className="se-icon" onClick={onBackToStart} aria-label="Stop">
          <Icon name="fa-stop" />
        </button>
        <button
          type="button"
          className={`se-icon se-play${playing ? " on" : ""}`}
          onClick={onTogglePlay}
          aria-label={playing ? "Pause" : "Play"}
          title={playing ? "Pause" : "Play"}
        >
          <Icon name={playing ? "fa-pause" : "fa-play"} />
        </button>
        <button
          type="button"
          className={`se-icon${metronome ? " on" : ""}`}
          onClick={onToggleMetronome}
          aria-pressed={metronome}
          aria-label="Metronome (visual only)"
          title="Metronome (visual only — no click audio yet)"
        >
          <Icon name="fa-bell" />
        </button>
        <span className="se-readout" aria-label="Time">{clock}</span>
        <span className="se-readout" aria-label="Bar and beat">{barBeat}</span>
      </div>

      <div className="se-head-right">
        <input
          className="se-pill se-bpm"
          value={bpm}
          inputMode="numeric"
          aria-label="Tempo in BPM"
          onChange={(event) => {
            const next = Number(event.target.value.replace(/\D/g, ""));
            if (Number.isFinite(next)) onBpmChange(Math.min(300, Math.max(20, next || 20)));
          }}
          onBlur={onBpmCommit}
        />
        <span className="se-pill">{timeSignature}</span>
        <StudioSaveStatus status={saveStatus} onRetry={onRetrySave} />
        <span className="se-pill se-meter" aria-label="Master peak" title="Peak level at the master output">
          {formatMeter(meter)}
        </span>
        <button
          type="button"
          className={`se-pill${playbackRate !== 1 ? " on" : ""}`}
          aria-label={`Audition speed ${playbackRate}×`}
          onClick={onCycleSpeed}
        >
          {playbackRate}×
        </button>
        <button
          type="button"
          className={`se-pill${exportOpen ? " on" : ""}`}
          aria-label="Export menu"
          aria-expanded={exportOpen}
          onClick={onToggleExport}
          disabled={exporting}
        >
          <Icon name="fa-arrow-up-from-bracket" /> {exporting ? "Exporting…" : "Export"}
        </button>
        {exportOpen ? (
          <div className="se-export-menu" role="menu" aria-label="Export options">
            <button type="button" role="menuitem" onClick={() => onExport("mix")}>
              Full mix (WAV)
            </button>
            <button type="button" role="menuitem" onClick={() => onExport("tracks")}>
              One file per track
            </button>
            <button type="button" role="menuitem" disabled={!rangeReady} onClick={() => onExport("range")}>
              Selected time range (WAV)
            </button>
            <button type="button" role="menuitem" onClick={() => onExport("json")}>
              Project (JSON)
            </button>
          </div>
        ) : null}
        <button
          type="button"
          className={`se-pill${libraryOpen ? " on" : ""}`}
          onClick={onToggleLibrary}
          aria-expanded={libraryOpen}
        >
          <Icon name="fa-table-columns" /> Library
        </button>
      </div>
    </header>
  );
}
