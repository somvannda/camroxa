import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { buildPipelineTemplate } from "../../electron/services/pipeline-templates";
import { buildPipelineRenderPlan } from "../../electron/services/pipeline-run";

const fixture = JSON.parse(
  fs.readFileSync(path.resolve(__dirname, "../fixtures/vizzy/trap-motion.camxora-vizzy.json"), "utf8"),
);
const projectJson = JSON.stringify(fixture);

function template(kind: "long" | "reel" = "long") {
  return {
    id: "night-drive",
    projectJson,
    pipeline: buildPipelineTemplate({
      name: "Night Drive",
      snapshot: fixture,
      kind,
      createdAt: "2026-11-19T00:00:00.000Z",
    }),
  };
}

describe("pipeline render plan", () => {
  it("uses the template output and the run audio duration", () => {
    const plan = buildPipelineRenderPlan(template(), { audioDurationSec: 187.4 });
    expect(plan).toMatchObject({
      templateId: "night-drive",
      name: "Night Drive",
      kind: "long",
      output: { width: 1920, height: 1080, fps: 30 },
      durationSec: 187.4,
      settings: { width: 1920, height: 1080, fps: 30, codec: "h264", start: 0, end: 187.4 },
    });
    expect(JSON.parse(plan.projectJson).format).toBe("studio-project");
  });

  it("applies the run bindings without changing the template", () => {
    const source = template();
    const plan = buildPipelineRenderPlan(source, {
      audioDurationSec: 30,
      inputs: { backgroundUrl: "camxora-media://local/bg" },
    });
    const nodes = JSON.parse(plan.projectJson).nodes;
    const background = nodes.find(
      (node: { id: string }) => node.id === source.pipeline.bindings.background?.nodeId,
    );
    expect(background.props.imageUrl).toBe("camxora-media://local/bg");
    expect(source.projectJson).not.toContain("camxora-media://local/bg");
  });

  it("rejects a kind mismatch and an empty track", () => {
    expect(() =>
      buildPipelineRenderPlan(template("reel"), { audioDurationSec: 30, expectedKind: "long" }),
    ).toThrow(/cannot render a long video/i);
    expect(() => buildPipelineRenderPlan(template(), { audioDurationSec: 0 })).toThrow(
      /no usable duration/i,
    );
  });

  it("uses a fixed duration when the template asks for one", () => {
    const source = template();
    const fixed = { ...source, pipeline: { ...source.pipeline, duration: { mode: "fixed" as const, seconds: 18 } } };
    const plan = buildPipelineRenderPlan(fixed, { audioDurationSec: 90 });
    expect(plan.durationSec).toBe(18);
    expect(plan.settings.end).toBe(18);
  });

  it("reuses the Export settings saved with the template", () => {
    const source = template();
    const saved = {
      ...source,
      pipeline: {
        ...source.pipeline,
        output: { width: 1080, height: 1920, fps: 60 },
        export: {
          width: 1080,
          height: 1920,
          fps: 60,
          bitrate: 50,
          crf: 18,
          preset: "slow",
          profile: "main",
          audioBitrate: 256,
          engine: "wasm" as const,
          start: 0,
          end: 12,
        },
      },
    };
    const plan = buildPipelineRenderPlan(saved, { audioDurationSec: 187.4 });
    expect(plan.output).toEqual({ width: 1080, height: 1920, fps: 60 });
    expect(plan.settings).toMatchObject({
      width: 1080,
      height: 1920,
      fps: 60,
      bitrate: 50,
      crf: 18,
      preset: "slow",
      profile: "main",
      audioBitrate: 256,
      start: 0,
      end: 187.4,
    });
  });
});
