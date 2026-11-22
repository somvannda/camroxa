import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/button";
import { Icon } from "../../components/icon";
import { Input } from "../../components/input";
import { Select } from "../../components/select";
import { classNames } from "../../lib/format";
import type {
  VizzyExportProgress,
  VizzyExportResult,
  VizzyExportSettingsInput,
} from "../../../electron/shared/types";
import { defaultExportBitrate } from "./export-settings";
import { formatBytes, formatDuration } from "./vizzy-format";

/** Same list the editor's own Export dialog exposes. */
const RESOLUTIONS: Array<{ value: string; label: string }> = [
  { value: "640x360", label: "640×360 (360p)" },
  { value: "854x480", label: "854×480 (480p)" },
  { value: "1280x720", label: "1280×720 (720p)" },
  { value: "1920x1080", label: "1920×1080 (1080p)" },
  { value: "2560x1440", label: "2560×1440 (1440p)" },
  { value: "3840x2160", label: "3840×2160 (4K)" },
  { value: "360x640", label: "360×640 (Portrait 360p)" },
  { value: "480x854", label: "480×854 (Portrait 480p)" },
  { value: "720x1280", label: "720×1280 (Portrait 720p)" },
  { value: "1080x1920", label: "1080×1920 (Portrait 1080p)" },
  { value: "1440x2560", label: "1440×2560 (Portrait 1440p)" },
  { value: "2160x3840", label: "2160×3840 (Portrait 4K)" },
  { value: "360x360", label: "360×360 (Square 360p)" },
  { value: "480x480", label: "480×480 (Square 480p)" },
  { value: "720x720", label: "720×720 (Square 720p)" },
  { value: "1080x1080", label: "1080×1080 (Square 1080p)" },
  { value: "1440x1440", label: "1440×1440 (Square 1440p)" },
  { value: "2160x2160", label: "2160×2160 (Square 4K)" },
  { value: "1080x1350", label: "1080×1350 (Portrait)" },
];

const FRAME_RATES = [24, 30, 60] as const;

const FORMATS: Array<{ value: "h264" | "vp8" | "vp9"; label: string }> = [
  { value: "h264", label: "H.264 · MP4" },
  { value: "vp9", label: "VP9 · WebM" },
  { value: "vp8", label: "VP8 · WebM" },
];

const PRESETS = [
  "ultrafast",
  "superfast",
  "veryfast",
  "faster",
  "fast",
  "medium",
  "slow",
  "slower",
  "veryslow",
] as const;

const PROFILES = ["baseline", "main", "high"] as const;

function resolutionValue(width: number, height: number): string {
  const value = `${width}x${height}`;
  return RESOLUTIONS.some((option) => option.value === value) ? value : "custom";
}

export interface VizzyExportMenuProps {
  open: boolean;
  onClose: () => void;
  project: { width: number; height: number; fps: number; duration: number };
  /** Last selected settings; reopening the rail restores them. */
  savedSettings?: VizzyExportSettingsInput | null;
  onSettingsChange?: (settings: VizzyExportSettingsInput) => void;
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
 * Export rail for the hosted editor.
 *
 * This is a one-to-one mirror of the editor's own Export dialog: same encoder,
 * resolution list, frame rates, formats, bitrate/CRF/preset/profile/audio
 * fields, start/end range and estimated size. Only the destination differs —
 * the host writes the validated file into Camxora's managed `renders/` folder.
 */
export function VizzyExportMenu({
  open,
  onClose,
  project,
  savedSettings,
  onSettingsChange,
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
  const [fps, setFps] = useState("60");
  const [codec, setCodec] = useState<"h264" | "vp8" | "vp9">("h264");
  const [engine, setEngine] = useState<"wasm" | "webcodecs">("wasm");
  const [bitrate, setBitrate] = useState("25");
  const [crf, setCrf] = useState("20");
  const [preset, setPreset] = useState<string>("veryfast");
  const [profile, setProfile] = useState<string>("high");
  const [audioBitrate, setAudioBitrate] = useState("192");
  const [start, setStart] = useState("0");
  const [end, setEnd] = useState("");
  const savedRef = useRef<VizzyExportSettingsInput | null>(savedSettings ?? null);
  const changeRef = useRef(onSettingsChange);
  savedRef.current = savedSettings ?? null;
  changeRef.current = onSettingsChange;

  // Seed exactly like the editor's Export dialog when it opens, but restore the
  // user's last selection when this rail is reopened.
  useEffect(() => {
    if (!open) return;
    const saved = savedRef.current;
    const nextWidth = saved?.width ?? (project.width || 1920);
    const nextHeight = saved?.height ?? (project.height || 1080);
    setWidth(String(nextWidth));
    setHeight(String(nextHeight));
    setFps(String(saved?.fps ?? 60));
    setCodec(saved?.codec === "vp8" || saved?.codec === "vp9" ? saved.codec : "h264");
    setEngine(saved?.engine === "webcodecs" ? "webcodecs" : "wasm");
    setBitrate(String(saved?.bitrate ?? defaultExportBitrate(nextHeight)));
    setCrf(String(saved?.crf ?? 20));
    setPreset(saved?.preset ?? "veryfast");
    setProfile(saved?.profile ?? "high");
    setAudioBitrate(String(saved?.audioBitrate ?? 192));
    setStart(String(saved?.start ?? 0));
    setEnd(
      String(
        saved?.end ??
          (project.duration > 0 ? Number(project.duration.toFixed(2)) : ""),
      ),
    );
  }, [open, project.width, project.height, project.duration]);

  // Keep the template store in step with the fields the user is looking at.
  useEffect(() => {
    if (!open) return;
    const widthNumber = Number(width) || 0;
    const heightNumber = Number(height) || 0;
    const startNumber = start.trim() === "" ? 0 : Number(start);
    const endNumber = end.trim() === "" ? undefined : Number(end);
    changeRef.current?.({
      width: widthNumber,
      height: heightNumber,
      fps: Number(fps) || 30,
      format: codec === "h264" ? "mp4" : "webm",
      codec,
      engine,
      bitrate: Math.max(0, Number(bitrate) || 0),
      crf: Number(crf) || 20,
      preset,
      profile,
      audioBitrate: Number(audioBitrate) || 192,
      start: Number.isFinite(startNumber) ? startNumber : 0,
      end: Number.isFinite(endNumber) ? endNumber : undefined,
    });
  }, [
    open,
    width,
    height,
    fps,
    codec,
    engine,
    bitrate,
    crf,
    preset,
    profile,
    audioBitrate,
    start,
    end,
  ]);

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

  const software = engine === "wasm";
  const h264 = codec === "h264";
  const codecLocked = !h264 || !software;

  const format = h264 ? "mp4" : "webm";
  const from = Math.max(0, Number(start) || 0);
  const to = Math.max(from, Number(end) || from);
  const videoMbps = Math.max(0, Number(bitrate) || 0) || (h264 ? 6 : 4);
  const audioMbps = (Number(audioBitrate) || 192) / 1000;
  const frames = Math.max(1, Math.round((to - from) * (Number(fps) || 60)));
  const estimate = `≈ ${((to - from) * (videoMbps + audioMbps) / 8).toFixed(1)} MB · ${frames} frames`;

  const submit = (): void => {
    if (!valid || running) return;
    onStart({
      width: Math.round(widthNumber),
      height: Math.round(heightNumber),
      fps: Number(fps) || 60,
      format,
      codec,
      engine,
      bitrate: Math.max(0, Number(bitrate) || 0),
      crf: Number(crf) || 20,
      preset,
      profile,
      audioBitrate: Number(audioBitrate) || 192,
      start: startNumber,
      end: endNumber,
    });
  };

  const changeResolution = (value: string): void => {
    const [nextWidth, nextHeight] = value.split("x").map(Number);
    if (!Number.isFinite(nextWidth) || !Number.isFinite(nextHeight)) return;
    setWidth(String(nextWidth));
    setHeight(String(nextHeight));
    setBitrate(String(defaultExportBitrate(nextHeight)));
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
        <div className="space-y-2.5">
          <label className="block space-y-1">
            <span className="text-caption text-text-muted">Encoder</span>
            <Select
              value={engine}
              options={[
                { value: "wasm", label: "WebAssembly (x264)" },
                { value: "webcodecs", label: "WebCodecs (Experimental)" },
              ]}
              onValueChange={(value) => setEngine(value === "webcodecs" ? "webcodecs" : "wasm")}
              data-testid="vizzy-export-engine"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-caption text-text-muted">Resolution</span>
            <Select
              value={resolutionValue(widthNumber, heightNumber)}
              options={[
                ...RESOLUTIONS,
                ...(resolutionValue(widthNumber, heightNumber) === "custom"
                  ? [{ value: "custom", label: `Custom · ${width}×${height}` }]
                  : []),
              ]}
              onValueChange={changeResolution}
              data-testid="vizzy-export-preset"
            />
          </label>

          <div className="grid grid-cols-2 gap-2">
            <label className="block space-y-1">
              <span className="text-caption text-text-muted">Frame rate</span>
              <Select
                value={fps}
                options={FRAME_RATES.map((value) => ({
                  value: String(value),
                  label: `${value} fps`,
                }))}
                onValueChange={setFps}
                data-testid="vizzy-export-fps"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-caption text-text-muted">Format</span>
              <Select
                value={codec}
                options={FORMATS}
                onValueChange={(value) =>
                  setCodec(value === "vp8" || value === "vp9" ? value : "h264")
                }
                data-testid="vizzy-export-format"
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <label className="block space-y-1">
              <span className="text-caption text-text-muted">Bitrate (Mbps)</span>
              <Input
                type="number"
                min={0}
                max={200}
                step={1}
                value={bitrate}
                onChange={(event) => setBitrate(event.target.value)}
                data-testid="vizzy-export-bitrate"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-caption text-text-muted">Audio (kbps)</span>
              <Input
                type="number"
                min={64}
                max={320}
                step={16}
                value={audioBitrate}
                onChange={(event) => setAudioBitrate(event.target.value)}
                data-testid="vizzy-export-audio-bitrate"
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <label className="block space-y-1">
              <span className="text-caption text-text-muted">CRF</span>
              <Input
                type="number"
                min={0}
                max={51}
                step={1}
                value={crf}
                disabled={codecLocked}
                onChange={(event) => setCrf(event.target.value)}
                data-testid="vizzy-export-crf"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-caption text-text-muted">Preset</span>
              <Select
                value={preset}
                options={PRESETS.map((value) => ({ value, label: value }))}
                onValueChange={setPreset}
                disabled={codecLocked}
                data-testid="vizzy-export-preset-name"
              />
            </label>
          </div>

          <label className="block space-y-1">
            <span className="text-caption text-text-muted">Profile</span>
            <Select
              value={profile}
              options={PROFILES.map((value) => ({ value, label: value }))}
              onValueChange={setProfile}
              disabled={codecLocked}
              data-testid="vizzy-export-profile"
            />
          </label>

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

          <p className="text-caption text-text-muted" data-testid="vizzy-export-estimate">
            {estimate}
          </p>
          <p className="text-caption text-text-muted">
            Same encoder settings as the Vizzy Export dialog. The validated file is saved to
            Camxora’s renders folder.
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
