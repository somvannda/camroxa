import { describe, expect, it } from "vitest";
import type {
  PipelineBatchInfo,
  PipelineJobInfo,
} from "../../electron/shared/types";
import {
  pipelineBatchCounts,
  pipelineBatchLabel,
  pipelineBranchLabel,
  pipelineProgressText,
  pipelineStageText,
  pipelineStatusLabel,
  pipelineStatusTone,
  pipelineSummaryText,
} from "../../src/features/progress/video-pipeline-format";

function job(overrides: Partial<PipelineJobInfo> = {}): PipelineJobInfo {
  return {
    id: "job-1",
    batchId: "batch-1",
    branch: "long",
    templateId: "night-drive",
    templateName: "Night Drive",
    audioPath: "C:/runs/song.mp3",
    audioName: "song.mp3",
    title: "Song",
    artist: "",
    album: "",
    outputDir: "C:/runs",
    backgroundPath: "",
    status: "queued",
    stage: "queued",
    progress: 0,
    error: null,
    output: null,
    merge: false,
    createdAt: 0,
    updatedAt: 0,
    ...overrides,
  };
}

function batch(overrides: Partial<PipelineBatchInfo> = {}): PipelineBatchInfo {
  return {
    batchId: "batch-1",
    outputDir: "C:/runs",
    merge: false,
    mergedOutput: null,
    status: "running",
    error: null,
    total: 2,
    done: 0,
    failed: 0,
    cancelled: 0,
    running: true,
    createdAt: 0,
    updatedAt: 0,
    ...overrides,
  };
}

describe("video pipeline formatting", () => {
  it("labels every queue status honestly", () => {
    expect(pipelineStatusLabel("queued")).toBe("Queued");
    expect(pipelineStatusLabel("rendering")).toBe("Rendering");
    expect(pipelineStatusLabel("encoding")).toBe("Encoding");
    expect(pipelineStatusLabel("done")).toBe("Done");
    expect(pipelineStatusLabel("failed")).toBe("Failed");
    expect(pipelineStatusLabel("cancelled")).toBe("Cancelled");
    expect(pipelineStatusTone("done")).toBe("success");
    expect(pipelineStatusTone("failed")).toBe("danger");
    expect(pipelineStatusTone("rendering")).toBe("accent");
  });

  it("describes the row without inventing progress", () => {
    expect(pipelineBranchLabel(job())).toBe("Long video");
    expect(pipelineBranchLabel(job({ branch: "reel" }))).toBe("Reel");
    expect(pipelineStageText(job({ status: "queued" }))).toBe("Waiting to render");
    expect(pipelineStageText(job({ status: "done" }))).toBe("Validated");
    expect(pipelineStageText(job({ status: "rendering", stage: "rendering" }))).toBe("rendering");
    expect(pipelineProgressText(job({ status: "encoding", progress: 91.6 }))).toBe("92%");
    expect(pipelineProgressText(job({ status: "failed" }))).toBe("—");
  });

  it("counts batch rows without double counting", () => {
    expect(pipelineBatchLabel(batch())).toBe("Running");
    expect(pipelineBatchLabel(batch({ status: "merging" }))).toBe("Merging");
    expect(pipelineBatchCounts(batch({ total: 3, done: 2, failed: 1 }))).toBe("2 done · 1 failed");
    expect(pipelineBatchCounts(batch({ total: 0 }))).toBe("No renders");
  });

  it("summarises the queue", () => {
    expect(pipelineSummaryText({ jobs: [], batches: [] })).toBe("No video renders yet.");
    expect(
      pipelineSummaryText({
        jobs: [job({ status: "done" }), job({ id: "job-2", status: "failed" })],
        batches: [batch({ mergedOutput: "C:/runs/merged.mp4" })],
      }),
    ).toBe("1/2 rendered · 1 failed · 1 merged");
  });
});
