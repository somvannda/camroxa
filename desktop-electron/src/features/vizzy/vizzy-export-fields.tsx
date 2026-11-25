import { Input } from "../../components/input";
import { Select } from "../../components/select";
import type { VizzyExportSettingsInput } from "../../../electron/shared/types";
import {
  EXPORT_ENCODERS,
  EXPORT_FORMATS,
  EXPORT_FRAME_RATES,
  EXPORT_PRESETS,
  EXPORT_PROFILES,
  EXPORT_RESOLUTIONS,
  resolutionValue,
} from "./export-options";
import { defaultExportBitrate } from "./export-settings";

export interface ExportSettingsFieldsProps {
  value: VizzyExportSettingsInput;
  onChange: (next: VizzyExportSettingsInput) => void;
}

/**
 * The Export rail's fields, rendered as a controlled editor.
 *
 * Shared by the rail and the save-template dialog so the pipeline profile can be
 * chosen at save time instead of opening Export first.
 */
export function ExportSettingsFields({ value, onChange }: ExportSettingsFieldsProps) {
  const width = value.width ?? 1920;
  const height = value.height ?? 1080;
  const fps = value.fps ?? 30;
  const codec = value.codec === "vp8" || value.codec === "vp9" ? value.codec : "h264";
  const engine = value.engine === "webcodecs" ? "webcodecs" : "wasm";
  const bitrate = value.bitrate ?? defaultExportBitrate(height);
  const crf = value.crf ?? 20;
  const preset = value.preset ?? "veryfast";
  const profile = value.profile ?? "high";
  const audioBitrate = value.audioBitrate ?? 192;
  const x264Locked = codec !== "h264" || engine !== "wasm";

  const patch = (next: Partial<VizzyExportSettingsInput>): void => {
    onChange({ ...value, ...next });
  };

  const number = (input: string, fallback: number): number => {
    const parsed = Number(input);
    return Number.isFinite(parsed) ? Math.max(0, Math.round(parsed)) : fallback;
  };

  const changeResolution = (next: string): void => {
    const [nextWidth, nextHeight] = next.split("x").map(Number);
    if (!Number.isFinite(nextWidth) || !Number.isFinite(nextHeight)) return;
    patch({
      width: nextWidth,
      height: nextHeight,
      bitrate: defaultExportBitrate(nextHeight),
    });
  };

  return (
    <div className="space-y-2.5">
      <label className="block space-y-1">
        <span className="text-caption text-text-muted">Video encoder</span>
        <Select
          value={engine}
          options={EXPORT_ENCODERS.map((option) => ({ ...option }))}
          onValueChange={(next) => patch({ engine: next === "webcodecs" ? "webcodecs" : "wasm" })}
          data-testid="vizzy-template-export-engine"
        />
        <span className="block text-caption text-text-muted">
          Scene rendering always uses the GPU; this picks the video encoder.
        </span>
      </label>

      <label className="block space-y-1">
        <span className="text-caption text-text-muted">Resolution</span>
        <Select
          value={resolutionValue(width, height)}
          options={[
            ...EXPORT_RESOLUTIONS,
            ...(resolutionValue(width, height) === "custom"
              ? [{ value: "custom", label: `Custom · ${width}×${height}` }]
              : []),
          ]}
          onValueChange={changeResolution}
          data-testid="vizzy-template-export-resolution"
        />
      </label>

      <div className="grid grid-cols-2 gap-2">
        <label className="block space-y-1">
          <span className="text-caption text-text-muted">Frame rate</span>
          <Select
            value={String(fps)}
            options={EXPORT_FRAME_RATES.map((rate) => ({
              value: String(rate),
              label: `${rate} fps`,
            }))}
            onValueChange={(next) => patch({ fps: Number(next) || 30 })}
            data-testid="vizzy-template-export-fps"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-caption text-text-muted">Format</span>
          <Select
            value={codec}
            options={EXPORT_FORMATS}
            onValueChange={(next) =>
              patch({
                codec: next === "vp8" || next === "vp9" ? next : "h264",
                format: next === "h264" ? "mp4" : "webm",
              })
            }
            data-testid="vizzy-template-export-format"
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
            value={String(bitrate)}
            onChange={(event) => patch({ bitrate: number(event.target.value, bitrate) })}
            data-testid="vizzy-template-export-bitrate"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-caption text-text-muted">Audio (kbps)</span>
          <Input
            type="number"
            min={64}
            max={320}
            step={16}
            value={String(audioBitrate)}
            onChange={(event) => patch({ audioBitrate: number(event.target.value, audioBitrate) })}
            data-testid="vizzy-template-export-audio"
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
            value={String(crf)}
            disabled={x264Locked}
            onChange={(event) => patch({ crf: number(event.target.value, crf) })}
            data-testid="vizzy-template-export-crf"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-caption text-text-muted">Preset</span>
          <Select
            value={preset}
            options={EXPORT_PRESETS.map((option) => ({ value: option, label: option }))}
            onValueChange={(next) => patch({ preset: next })}
            disabled={x264Locked}
            data-testid="vizzy-template-export-preset"
          />
        </label>
      </div>

      <label className="block space-y-1">
        <span className="text-caption text-text-muted">Profile</span>
        <Select
          value={profile}
          options={EXPORT_PROFILES.map((option) => ({ value: option, label: option }))}
          onValueChange={(next) => patch({ profile: next })}
          disabled={x264Locked}
          data-testid="vizzy-template-export-profile"
        />
      </label>
    </div>
  );
}
