import { describe, expect, it } from "vitest";
import {
  autoPipelineBatchId,
  selectAutoVideoCandidate,
  type AutoVideoSelectInput,
} from "../../electron/services/auto-video";

function baseInput(patch: Partial<AutoVideoSelectInput> = {}): AutoVideoSelectInput {
  const background: Record<"long" | "reel", string> = {
    long: "C:/runs/b1/background-16x9.png",
    reel: "C:/runs/b1/background-9x16.png",
  };
  return {
    settings: { long: true, reel: false, merge: true },
    rows: [
      {
        batch: "b1",
        run_date: "2026-11-20",
        meta: {
          batch_id: "b1",
          profile_id: "p1",
          role: "ok",
          run_dir: "C:/runs/b1",
          background_16x9_path: background.long,
          background_9x16_path: background.reel,
          expected: 2,
          saved: 2,
          download_pending: 0,
          download_ready: 2,
          updated_at: "2026-11-20T10:00:00Z",
        },
      },
    ],
    batches: [
      {
        batch_id: "b1",
        ok_album: "Night Album",
        alt_album: "Alt Album",
        songs: [
          {
            title: "First Light",
            album: "Night Album",
            output_dir_ok: "C:/runs/b1/Night Shift",
            output_dir_alt: "C:/runs/b1/Deep Focus",
            downloaded_ok: true,
            downloaded_alt: true,
          },
          {
            title: "Second Wind",
            album: "Night Album",
            output_dir_ok: "C:/runs/b1/Night Shift",
            output_dir_alt: "C:/runs/b1/Deep Focus",
            downloaded_ok: true,
            downloaded_alt: true,
          },
        ],
      },
    ],
    profiles: [
      {
        id: "p1",
        name: "Night Shift",
        video_template_id: "long-1",
        reel_template_id: "reel-1",
      },
    ],
    templates: [
      { id: "long-1", kind: "long" },
      { id: "reel-1", kind: "reel" },
    ],
    localJobs: [],
    resolveBackground: (row, branch) =>
      (branch === "long"
        ? row.meta.background_16x9_path
        : row.meta.background_9x16_path) ?? null,
    ...patch,
  };
}

describe("auto-video candidate selection", () => {
  it("returns nothing when both video checkboxes are off", () => {
    expect(
      selectAutoVideoCandidate(baseInput({ settings: { long: false, reel: false, merge: true } })),
    ).toBeNull();
  });

  it("builds the long branch with the generated background and song metadata", () => {
    const candidate = selectAutoVideoCandidate(baseInput());
    expect(candidate).not.toBeNull();
    expect(candidate?.branch).toBe("long");
    expect(candidate?.pipelineBatchId).toBe("b1:long:p1:ok");
    expect(candidate?.templateId).toBe("long-1");
    expect(candidate?.backgroundPath).toBe("C:/runs/b1/background-16x9.png");
    expect(candidate?.merge).toBe(true);
    expect(candidate?.mergeName).toBe("Night Album1120");
    expect(candidate?.jobs).toHaveLength(2);
    expect(candidate?.jobs[0]).toMatchObject({
      branch: "long",
      audioDir: "C:/runs/b1/Night Shift",
      audioBranch: "ok",
      title: "First Light",
      artist: "Night Shift",
      album: "Night Album",
      backgroundPath: "C:/runs/b1/background-16x9.png",
    });
  });

  it("uses the alt run folder and album for the secondary side", () => {
    const input = baseInput();
    input.rows[0].meta.role = "alt";
    const candidate = selectAutoVideoCandidate(input);
    expect(candidate?.jobs[0].audioDir).toBe("C:/runs/b1/Deep Focus");
    expect(candidate?.jobs[0].audioBranch).toBe("alt");
    expect(candidate?.jobs[0].album).toBe("Alt Album");
    expect(candidate?.mergeName).toBe("Alt Album1120");
  });

  it("renders into the downloaded song folder when run_dir is missing", () => {
    const input = baseInput();
    delete input.rows[0].meta.run_dir;
    const candidate = selectAutoVideoCandidate(input);
    expect(candidate?.outputDir).toBe("C:/runs/b1/Night Shift");
  });

  it("uses the run date for the merge name and handles a missing date", () => {
    const input = baseInput();
    input.rows[0].run_date = "";
    expect(selectAutoVideoCandidate(input)?.mergeName).toBe("Night Album");
  });

  it("waits for every expected download", () => {
    const input = baseInput();
    input.rows[0].meta.saved = 1;
    expect(selectAutoVideoCandidate(input)).toBeNull();
  });

  it("waits for a pending download even when the count looks full", () => {
    const input = baseInput();
    input.rows[0].meta.download_pending = 1;
    expect(selectAutoVideoCandidate(input)).toBeNull();
  });

  it("does not start when the generated background file is missing", () => {
    const input = baseInput();
    input.resolveBackground = () => null;
    expect(selectAutoVideoCandidate(input)).toBeNull();
  });

  it("does not start when the profile has no template for the branch", () => {
    const input = baseInput();
    input.profiles[0].video_template_id = "";
    expect(selectAutoVideoCandidate(input)).toBeNull();
  });

  it("does not start when the template is not in the local catalogue", () => {
    const input = baseInput();
    input.templates = [];
    expect(selectAutoVideoCandidate(input)).toBeNull();
  });

  it("renders the reel independently when only 9:16 is checked", () => {
    const input = baseInput({ settings: { long: false, reel: true, merge: false } });
    const candidate = selectAutoVideoCandidate(input);
    expect(candidate?.branch).toBe("reel");
    expect(candidate?.pipelineBatchId).toBe("b1:reel:p1:ok");
    expect(candidate?.templateId).toBe("reel-1");
    expect(candidate?.backgroundPath).toBe("C:/runs/b1/background-9x16.png");
  });

  it("moves to the reel after the long branch is already complete", () => {
    const input = baseInput({ settings: { long: true, reel: true, merge: true } });
    input.rows[0].meta.long_ready = true;
    const candidate = selectAutoVideoCandidate(input);
    expect(candidate?.branch).toBe("reel");
  });

  it("falls back to the reel when the long background is not ready", () => {
    const input = baseInput({ settings: { long: true, reel: true, merge: true } });
    input.resolveBackground = (row, branch) =>
      branch === "reel" ? (row.meta.background_9x16_path ?? null) : null;
    const candidate = selectAutoVideoCandidate(input);
    expect(candidate?.branch).toBe("reel");
  });

  it("never restarts a finished local branch", () => {
    const input = baseInput();
    input.localJobs = [
      { batchId: "b1:long:p1:ok", branch: "long", status: "done" },
      { batchId: "b1:long:p1:ok", branch: "long", status: "done" },
    ];
    expect(selectAutoVideoCandidate(input)).toBeNull();
  });

  it("leaves a failed local branch for an explicit retry", () => {
    const input = baseInput();
    input.localJobs = [{ batchId: "b1:long:p1:ok", branch: "long", status: "failed" }];
    expect(selectAutoVideoCandidate(input)).toBeNull();
  });

  it("skips a running local branch", () => {
    const input = baseInput();
    input.localJobs = [{ batchId: "b1:long:p1:ok", branch: "long", status: "rendering" }];
    expect(selectAutoVideoCandidate(input)).toBeNull();
  });

  it("ignores a pipeline-complete row", () => {
    const input = baseInput();
    input.rows[0].meta.pipeline_complete = true;
    expect(selectAutoVideoCandidate(input)).toBeNull();
  });

  it("uses one pipeline batch id per profile and branch", () => {
    expect(autoPipelineBatchId("batch-1", "long")).toBe("batch-1:long");
    expect(autoPipelineBatchId("batch-1", "reel")).toBe("batch-1:reel");
    expect(autoPipelineBatchId("batch-1", "long", "p1", "OK")).toBe("batch-1:long:p1:OK");
    expect(autoPipelineBatchId("batch-1", "long", "p2", "ALT")).toBe("batch-1:long:p2:ALT");
  });
});
