import {
  applyPipelineBindings,
  type PipelineKind,
  type PipelineRunInputs,
  type PipelineTemplate,
} from "./pipeline-templates";
import { defaultExportBitrate } from "../vizzy-host/renders";

/**
 * Builds the exact render request for one pipeline run.
 *
 * The renderer (the hosted Vizzy editor) receives `projectJson`, which is the
 * saved template with the run's bindings applied. The audio is not embedded:
 * the caller loads the run track through the editor bridge, exactly as a user
 * would load it in the editor.
 */
export interface PipelineRenderPlan {
  templateId: string;
  name: string;
  kind: PipelineKind;
  projectJson: string;
  output: { width: number; height: number; fps: number };
  /** Duration to render; the audio length when the template follows the track. */
  durationSec: number;
  settings: {
    width: number;
    height: number;
    fps: number;
    codec: "h264";
    engine: "wasm" | "webcodecs";
    bitrate: number;
    crf: number;
    preset: string;
    profile: string;
    audioBitrate: number;
    start: number;
    end: number;
  };
}

export interface PipelineRun {
  /** Run track length in seconds; required for `duration.mode = "audio"`. */
  audioDurationSec: number;
  inputs?: PipelineRunInputs;
  expectedKind?: PipelineKind;
}

export function buildPipelineRenderPlan(
  template: { id?: string; projectJson: string; pipeline: PipelineTemplate },
  run: PipelineRun,
): PipelineRenderPlan {
  const { pipeline } = template;
  if (run.expectedKind && run.expectedKind !== pipeline.kind) {
    throw new Error(
      `This ${pipeline.kind} template cannot render a ${run.expectedKind} video.`,
    );
  }

  const durationSec =
    pipeline.duration.mode === "audio"
      ? run.audioDurationSec
      : pipeline.duration.seconds;
  if (!Number.isFinite(durationSec) || durationSec <= 0) {
    throw new Error("The run audio has no usable duration.");
  }

  const projectJson = applyPipelineBindings(
    template.projectJson,
    pipeline,
    run.inputs ?? {},
  );

  const { width, height, fps } = pipeline.output;
  const exported = pipeline.export;
  const exportWidth = exported?.width ?? width;
  const exportHeight = exported?.height ?? height;
  const exportFps = exported?.fps ?? fps;
  return {
    templateId: template.id ?? "",
    name: pipeline.name,
    kind: pipeline.kind,
    projectJson,
    output: { width: exportWidth, height: exportHeight, fps: exportFps },
    durationSec,
    settings: {
      width: exportWidth,
      height: exportHeight,
      fps: exportFps,
      codec: "h264",
      engine: exported?.engine === "webcodecs" ? "webcodecs" : "wasm",
      /** Mirror the Export rail saved with the template; defaults otherwise. */
      bitrate: exported?.bitrate ?? defaultExportBitrate(exportHeight),
      crf: exported?.crf ?? 20,
      preset: exported?.preset ?? "veryfast",
      profile: exported?.profile ?? "high",
      audioBitrate: exported?.audioBitrate ?? 192,
      start: 0,
      /** Pipeline renders always follow the run audio, never a saved 12 s trim. */
      end: durationSec,
    },
  };
}
