"use client";

import { Icon } from "@/components/Icon";
import { StudioProjectMenu } from "@/components/studio/StudioProjectMenu";
import { STUDIO_SIGNATURES } from "@/lib/studio-signature";
import type { StudioSettings } from "@/lib/studio-settings";
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
  projectId: string | null;
  settings: StudioSettings;
  onSettingsChange: (next: StudioSettings) => void;
  onRenamed: (title: string) => void;
  onShowQuickStart: () => void;
  timeSignature: string;
  onTimeSignature: (next: string) => void;
  clock: string;
  barBeat: string;
  bpm: number;
  onBpmChange: (value: number) => void;
  onBpmCommit: () => void;

  playing: boolean;
  loop: boolean;
  metronome: boolean;
  /** 1-based beat within the bar while playing, 0 when the click is off. */
  beat: number;
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
  /** Mix/range exports are gain-matched to the menu's target when on (G11). */
  normalise: boolean;
  onToggleNormalise: () => void;

  libraryOpen: boolean;
  onToggleLibrary: () => void;

  onBackToStart: () => void;
  onStop: () => void;
  onTogglePlay: () => void;
  onToggleLoop: () => void;
  onToggleMetronome: () => void;
  onUndo: () => void;
  onRedo: () => void;
};

export function StudioHeader(props: StudioHeaderProps) {
  const {
    title,
    projectId,
    settings,
    onSettingsChange,
    onRenamed,
    onShowQuickStart,
    timeSignature,
    onTimeSignature,
    clock,
    barBeat,
    bpm,
    onBpmChange,
    onBpmCommit,
    playing,
    loop,
    metronome,
    beat,
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
    normalise,
    onToggleNormalise,
    libraryOpen,
    onToggleLibrary,
    onBackToStart,
    onStop,
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
        {projectId ? (
          <StudioProjectMenu
            projectId={projectId}
            title={title}
            settings={settings}
            onSettingsChange={onSettingsChange}
            onRenamed={onRenamed}
            onShowQuickStart={onShowQuickStart}
          />
        ) : (
          <button type="button" className="se-chip" disabled>
            {title}
            <Icon name="fa-chevron-down" />
          </button>
        )}
        <button type="button" className="se-icon" aria-label="Undo" disabled={!canUndo} onClick={onUndo} data-help="undo">
          <Icon name="fa-rotate-left" />
        </button>
        <button type="button" className="se-icon" aria-label="Redo" disabled={!canRedo} onClick={onRedo} data-help="redo">
          <Icon name="fa-rotate-right" />
        </button>
      </div>

      <div className="se-head-center">
        <button type="button" className="se-icon" onClick={onBackToStart} aria-label="Back to start" data-help="back-to-start">
          <Icon name="fa-backward-step" />
        </button>
        <button
          type="button"
          className={`se-icon${loop ? " on" : ""}`}
          onClick={onToggleLoop}
          aria-pressed={loop}
          aria-label="Loop"
          title="Loop"
          data-help="loop"
        >
          <Icon name="fa-repeat" />
        </button>
        <button type="button" className="se-icon" onClick={onStop} aria-label="Stop">
          <Icon name="fa-stop" />
        </button>
        <button
          type="button"
          className={`se-icon se-play${playing ? " on" : ""}`}
          onClick={onTogglePlay}
          aria-label={playing ? "Pause" : "Play"}
          title={playing ? "Pause" : "Play"}
          data-help="play"
        >
          <Icon name={playing ? "fa-pause" : "fa-play"} />
        </button>
        <button
          type="button"
          className={`se-icon${metronome ? " on" : ""}`}
          onClick={onToggleMetronome}
          aria-pressed={metronome}
          aria-label={metronome ? `Metronome (click track) — beat ${beat || 1}` : "Metronome (click track)"}
          title="Metronome (click track)"
          data-beat={metronome ? beat : 0}
          data-help="metronome"
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
          data-help="tempo"
          onChange={(event) => {
            const next = Number(event.target.value.replace(/\D/g, ""));
            if (Number.isFinite(next)) onBpmChange(Math.min(300, Math.max(20, next || 20)));
          }}
          onBlur={onBpmCommit}
        />
        <select
          className="se-pill se-signature"
          value={timeSignature}
          aria-label="Time signature"
          data-help="time-signature"
          onChange={(event) => onTimeSignature(event.target.value)}
        >
          {(STUDIO_SIGNATURES.includes(timeSignature as (typeof STUDIO_SIGNATURES)[number])
            ? STUDIO_SIGNATURES
            : [timeSignature, ...STUDIO_SIGNATURES]
          ).map((signature) => (
            <option key={signature} value={signature}>
              {signature}
            </option>
          ))}
        </select>
        <StudioSaveStatus status={saveStatus} onRetry={onRetrySave} />
        <span className="se-pill se-meter" aria-label="Master peak" title="Peak level at the master output" data-help="meter">
          {formatMeter(meter)}
        </span>
        <button
          type="button"
          className={`se-pill${playbackRate !== 1 ? " on" : ""}`}
          aria-label={`Audition speed ${playbackRate}×`}
          onClick={onCycleSpeed}
          data-help="speed"
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
          data-help="export"
        >
          <Icon name="fa-arrow-up-from-bracket" /> {exporting ? "Exporting…" : "Export"}
        </button>
        {exportOpen ? (
          <div className="se-export-menu" role="menu" aria-label="Export options">
            <button
              type="button"
              role="menuitemcheckbox"
              aria-checked={normalise}
              onClick={onToggleNormalise}
              title="Sets the mix peak to −1 dBFS so successive exports compare"
            >
              {normalise ? "✓ " : ""}Normalise mix to −1 dBFS
            </button>
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
          data-help="library"
        >
          <Icon name="fa-table-columns" /> Library
        </button>
      </div>
    </header>
  );
}
