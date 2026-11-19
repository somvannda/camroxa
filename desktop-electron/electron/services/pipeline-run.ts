import {
  applyPipelineBindings,
  type PipelineKind,
  type PipelineRunInputs,
  type PipelineTemplate,
} from "./pipeline-templates";

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
    bitrate: number;
    crf: number;
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
  return {
    templateId: template.id ?? "",
    name: pipeline.name,
    kind: pipeline.kind,
    projectJson,
    output: { width, height, fps },
    durationSec,
    settings: {
      width,
      height,
      fps,
      codec: "h264",
      /** Mbps, matching the editor exporter (`0` = CRF only). */
      bitrate: 12,
      crf: 18,
      audioBitrate: 192,
      start: 0,
      end: durationSec,
    },
  };
}
