import { useEffect, useState } from "react";
import { Button } from "../../components/button";
import { Icon } from "../../components/icon";
import { Input } from "../../components/input";
import { classNames } from "../../lib/format";
import type {
  VizzyExportProgress,
  VizzyExportResult,
  VizzyExportSettingsInput,
} from "../../../electron/shared/types";
import { formatBytes, formatDuration } from "./vizzy-format";

const selectClass =
  "h-8 w-full rounded-control border border-border bg-surface-1 px-2 text-body-sm text-text-primary focus:border-accent focus:outline-none disabled:opacity-40";

const PRESETS: Array<{ label: string; width: number; height: number }> = [
  { label: "1080p · 1920×1080", width: 1920, height: 1080 },
  { label: "720p · 1280×720", width: 1280, height: 720 },
  { label: "480p · 854×480", width: 854, height: 480 },
  { label: "360p · 640×360", width: 640, height: 360 },
  { label: "Portrait · 1080×1920", width: 1080, height: 1920 },
];

function presetValue(width: number, height: number): string {
  const found = PRESETS.find((preset) => preset.width === width && preset.height === height);
  return found ? `${found.width}x${found.height}` : "custom";
}

export interface VizzyExportMenuProps {
  open: boolean;
  onClose: () => void;
  project: { width: number; height: number; fps: number; duration: number };
  running: boolean;
  progress: VizzyExportProgress | null;
  result: VizzyExportResult | null;
  error: string | null;
  onStart: (settings: VizzyExportSettingsInput) => void;
  onCancel: () => void;
  onReveal: (name: string) => void;
  onOpenRenders: () => void;
}

/**
 * Compact export popover on the Vizzy strip. It never renders the video: the
 * hosted editor does, the host writes `renders/<slug>-<timestamp>.<ext>` and
 * the strip shows progress and the result.
 */
export function VizzyExportMenu({
  open,
  onClose,
  project,
  running,
  progress,
  result,
  error,
  onStart,
  onCancel,
  onReveal,
  onOpenRenders,
}: VizzyExportMenuProps) {
  const [width, setWidth] = useState("1920");
  const [height, setHeight] = useState("1080");
  const [fps, setFps] = useState("30");
  const [format, setFormat] = useState<"mp4" | "webm">("mp4");
  const [start, setStart] = useState("0");
  const [end, setEnd] = useState("");

  // Seed from the open project every time the popover is opened.
  useEffect(() => {
    if (!open) return;
    setWidth(String(project.width || 1920));
    setHeight(String(project.height || 1080));
    setFps(String(project.fps || 30));
    setFormat("mp4");
    setStart("0");
    setEnd(project.duration > 0 ? String(Number(project.duration.toFixed(2))) : "");
  }, [open, project.width, project.height, project.fps, project.duration]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === "Escape" && !running) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, running, onClose]);

  if (!open) return null;

  const widthNumber = Number(width);
  const heightNumber = Number(height);
  const startNumber = start.trim() === "" ? 0 : Number(start);
  const endNumber = end.trim() === "" ? undefined : Number(end);
  const valid =
    Number.isFinite(widthNumber) &&
    Number.isFinite(heightNumber) &&
    widthNumber >= 16 &&
    heightNumber >= 16 &&
    widthNumber <= 7680 &&
    heightNumber <= 7680 &&
    Number.isFinite(startNumber) &&
    (endNumber === undefined || (Number.isFinite(endNumber) && endNumber > startNumber));

  const submit = (): void => {
    if (!valid || running) return;
    onStart({
      width: widthNumber,
      height: heightNumber,
      fps: Number(fps),
      format,
      start: startNumber,
      end: endNumber,
    });
  };

  return (
    <div
      className="rounded-card border border-border bg-surface-1 p-3 shadow-2xl"
      role="dialog"
      aria-label="Export settings"
      data-testid="vizzy-export-menu"
    >
      <div className="-mt-1 mb-3 flex items-center justify-between">
        <span className="text-caption uppercase tracking-wide text-text-muted">Export</span>
        <button
          type="button"
          aria-label="Close export settings"
          className="flex h-6 w-6 items-center justify-center rounded-[6px] text-text-muted hover:bg-surface-hover hover:text-text-primary"
          onClick={() => {
            if (!running) onClose();
          }}
        >
          <Icon name="fa-xmark" size={13} />
        </button>
      </div>
      {running ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-body-sm font-medium text-text-primary">
              <Icon name="fa-film" size={13} className="text-accent" />
              Exporting
              <span className="ml-auto font-mono text-meta text-text-muted">
                {progress ? `${progress.percent}%` : "…"}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
              <div
                className="h-full rounded-full bg-accent transition-[width] duration-300"
                style={{ width: `${progress?.percent ?? 0}%` }}
              />
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="min-w-0 truncate text-meta text-text-muted">
                {progress ? `${progress.stage} · ${progress.done}/${progress.total}` : "Preparing"}
              </span>
              <Button variant="secondary" onClick={onCancel} data-testid="vizzy-export-cancel">
                Cancel
              </Button>
            </div>
          </div>
        ) : result ? (
          <div className="space-y-3" data-testid="vizzy-export-result">
            <div className="flex items-center gap-2 text-body-sm font-medium text-text-primary">
              <Icon name="fa-circle-check" size={13} className="text-success" />
              Render saved
            </div>
            <p className="break-all text-meta text-text-secondary">{result.name}</p>
            <p className="text-meta text-text-muted">
              {formatBytes(result.bytes)} · {formatDuration(result.durationSec)} ·{" "}
              {result.width}×{result.height}
              {result.videoCodec ? ` · ${result.videoCodec}` : ""}
            </p>
            <div className="flex items-center gap-2">
              <Button variant="primary" onClick={() => onReveal(result.name)}>
                Show file
              </Button>
              <Button variant="secondary" onClick={onOpenRenders}>
                Renders
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-body-sm font-medium text-text-primary">
              <Icon name="fa-clapperboard" size={13} className="text-text-muted" />
              Export video
            </div>

            <label className="block space-y-1">
              <span className="text-caption text-text-muted">Resolution</span>
              <select
                className={selectClass}
                value={presetValue(widthNumber, heightNumber)}
                onChange={(event) => {
                  const preset = PRESETS.find(
                    (entry) => `${entry.width}x${entry.height}` === event.target.value,
                  );
                  if (!preset) return;
                  setWidth(String(preset.width));
                  setHeight(String(preset.height));
                }}
                data-testid="vizzy-export-preset"
              >
                {PRESETS.map((preset) => (
                  <option key={preset.label} value={`${preset.width}x${preset.height}`}>
                    {preset.label}
                  </option>
                ))}
                {presetValue(widthNumber, heightNumber) === "custom" ? (
                  <option value="custom">
                    Custom · {Number.isFinite(widthNumber) ? widthNumber : "?"}×
                    {Number.isFinite(heightNumber) ? heightNumber : "?"}
                  </option>
                ) : null}
              </select>
            </label>

            <div className="grid grid-cols-2 gap-2">
              <label className="block space-y-1">
                <span className="text-caption text-text-muted">Width</span>
                <Input
                  type="number"
                  min={16}
                  max={7680}
                  step={2}
                  value={width}
                  onChange={(event) => setWidth(event.target.value)}
                  data-testid="vizzy-export-width"
                />
              </label>
              <label className="block space-y-1">
                <span className="text-caption text-text-muted">Height</span>
                <Input
                  type="number"
                  min={16}
                  max={7680}
                  step={2}
                  value={height}
                  onChange={(event) => setHeight(event.target.value)}
                  data-testid="vizzy-export-height"
                />
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="block space-y-1">
                <span className="text-caption text-text-muted">Frame rate</span>
                <select
                  className={selectClass}
                  value={fps}
                  onChange={(event) => setFps(event.target.value)}
                  data-testid="vizzy-export-fps"
                >
                  <option value="24">24 fps</option>
                  <option value="30">30 fps</option>
                  <option value="60">60 fps</option>
                </select>
              </label>
              <label className="block space-y-1">
                <span className="text-caption text-text-muted">Format</span>
                <select
                  className={selectClass}
                  value={format}
                  onChange={(event) => setFormat(event.target.value === "webm" ? "webm" : "mp4")}
                  data-testid="vizzy-export-format"
                >
                  <option value="mp4">MP4 · H.264</option>
                  <option value="webm">WebM · VP9</option>
                </select>
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="block space-y-1">
                <span className="text-caption text-text-muted">Start (s)</span>
                <Input
                  type="number"
                  min={0}
                  step={0.1}
                  value={start}
                  onChange={(event) => setStart(event.target.value)}
                  data-testid="vizzy-export-start"
                />
              </label>
              <label className="block space-y-1">
                <span className="text-caption text-text-muted">End (s)</span>
                <Input
                  type="number"
                  min={0}
                  step={0.1}
                  placeholder={project.duration > 0 ? `${project.duration}` : "Full project"}
                  value={end}
                  onChange={(event) => setEnd(event.target.value)}
                  data-testid="vizzy-export-end"
                />
              </label>
            </div>

            <p className="text-caption text-text-muted">
              Saves to the Camxora renders folder. The editor keeps its own export dialog as a
              fallback.
            </p>

            {error ? (
              <p className="text-meta text-danger" role="alert" data-testid="vizzy-export-error">
                {error}
              </p>
            ) : null}

            <Button
              variant="primary"
              className={classNames("w-full", !valid ? "opacity-40" : "")}
              onClick={submit}
              disabled={!valid}
              data-testid="vizzy-export-submit"
            >
              Export video
            </Button>
          </div>
        )}
    </div>
  );
}
