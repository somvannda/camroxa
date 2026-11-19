import { describe, expect, it } from "vitest";
import {
  API_ROW_CAP,
  countStats,
  downloadQueueRows,
  filterProgressRows,
  imageCellText,
  isActiveRow,
  localVideoState,
  metaLine,
  musicCellText,
  prepareRows,
  progressQuery,
  rangeError,
  relativeTime,
  rowKey,
  stageTimeline,
  summaryText,
  todayYmd,
  youtubeCellText,
} from "../../src/features/progress/progress-format";
import type { ProgressRow, ProgressRowMeta } from "../../src/features/progress/progress-types";

type RowOverrides = Omit<Partial<ProgressRow>, "meta"> & { meta?: Partial<ProgressRowMeta> };

function row(overrides: RowOverrides = {}): ProgressRow {
  const meta = {
    batch_id: "batch-1",
    profile_id: "profile-1",
    role: "OK",
    run_dir: "C:\\runs\\batch-1",
    expected: 10,
    saved: 10,
    download_pending: 0,
    download_ready: 10,
    bg_ready: 10,
    bg_total: 10,
    th_ready: 10,
    th_total: 10,
    bg_status: "READY",
    th_status: "READY",
    long_ready: false,
    reel_ready: false,
    pipeline_complete: false,
    updated_at: "2026-11-19T10:00:00Z",
    ...(overrides.meta ?? {}),
  };
  return {
    batch: "batch-1",
    run_date: "2026-11-19",
    channel: "Night Shift",
    album: "Night Drive",
    status: "running",
    music: "10/10",
    image: "10/10",
    converter: "",
    merge: "",
    youtube: "",
    stage: "music",
    notes: "",
    updated: "just now",
    ...overrides,
    meta,
  };
}

describe("filters", () => {
  it("rejects a To date before From", () => {
    expect(rangeError("2026-11-19", "2026-11-18")).toBe(
      "The To date must be on or after the From date.",
    );
    expect(rangeError("2026-11-19", "2026-11-19")).toBeNull();
  });

  it("caps the API limit at 100 while keeping the display limit", () => {
    expect(progressQuery("2026-11-01", "2026-11-19", 200, true)).toEqual({
      limit: API_ROW_CAP,
      active_only: true,
      from_date: "2026-11-01",
      to_date: "2026-11-19",
    });
    expect(progressQuery("2026-11-01", "2026-11-19", 25, false).limit).toBe(25);
  });

  it("deduplicates by batch + date + profile + role and sorts newest first", () => {
    const older = row({ batch: "b1", run_date: "2026-11-18" });
    const newer = row({ batch: "b2", run_date: "2026-11-19" });
    const duplicate = row({ batch: "b2", run_date: "2026-11-19", channel: "Other" });
    const prepared = prepareRows([older, newer, duplicate]);
    expect(prepared.map((entry) => entry.batch)).toEqual(["b2", "b1"]);
    expect(rowKey(prepared[0])).toBe("b2|2026-11-19|profile-1|OK");
  });

  it("applies Active, Stage and Limit on the effective rows", () => {
    const rows = [
      row({ batch: "music", stage: "music" }),
      row({ batch: "image", stage: "image" }),
      row({ batch: "export", stage: "converter" }),
      row({ batch: "done", stage: "done" }),
      row({ batch: "error", stage: "error", status: "failed" }),
    ];
    expect(filterProgressRows(rows, { activeOnly: true, stage: "all" }).map((r) => r.batch)).toEqual([
      "music",
      "image",
      "export",
      "error",
    ]);
    expect(filterProgressRows(rows, { activeOnly: false, stage: "converter" }).map((r) => r.batch)).toEqual([
      "export",
    ]);
    expect(
      filterProgressRows(rows, { activeOnly: false, stage: "all", limit: 2 }).map((r) => r.batch),
    ).toEqual(["music", "image"]);
  });

  it("hides completed local pipelines from Active only but keeps YouTube", () => {
    expect(isActiveRow(row({ stage: "youtube" }))).toBe(true);
    expect(isActiveRow(row({ stage: "done" }))).toBe(false);
    expect(isActiveRow(row({ stage: "merge", meta: { pipeline_complete: true } }))).toBe(false);
    expect(isActiveRow(row({ stage: "error", status: "failed" }))).toBe(true);
  });
});

describe("stat counts", () => {
  it("counts active, video, waiting and failed over the filtered set", () => {
    const waiting = row({ batch: "wait", stage: "image" });
    const rows = [
      waiting,
      row({ batch: "export", stage: "converter" }),
      row({ batch: "merge", stage: "merger" }),
      row({ batch: "done", stage: "done" }),
      row({ batch: "fail", stage: "error", status: "failed" }),
      row({ batch: "blocked", stage: "youtube", status: "blocked" }),
    ];
    expect(countStats(rows, true, new Set([rowKey(waiting)]))).toEqual({
      active: 4,
      video: 2,
      waiting: 1,
      failed: 2,
    });
    expect(countStats(rows, false, new Set())).toEqual({
      active: 4,
      video: 2,
      waiting: 0,
      failed: 2,
    });
  });
});

describe("row presentation", () => {
  it("prefers local converter/merge truth and names P7 when nothing is reported", () => {
    const local = localVideoState(
      row({ stage: "merge", meta: { long_ready: true, reel_ready: true } }),
    );
    expect(local.source).toBe("local");
    expect(local.converter).toBe("Long + reel ready");
    expect(local.merge).toBe("Completed");

    const api = localVideoState(row({ converter: "Long 2/2", merge: "" }));
    expect(api.source).toBe("api");
    expect(api.converter).toBe("Long 2/2");
    expect(api.merge).toBeNull();

    expect(localVideoState(row()).source).toBe("none");
  });

  it("keeps music and image cells honest about pending downloads and manual mode", () => {
    expect(musicCellText(row({ meta: { download_pending: 2 } }))).toEqual({
      primary: "10/10",
      secondary: "2 pending",
    });
    expect(imageCellText(row(), true).secondary).toBe("Manual mode");
    expect(imageCellText(row({ meta: { bg_status: "FAILED" } }), false).secondary).toBe(
      "Auto mode · BG failed",
    );
  });

  it("derives YouTube state from counters and keeps the link", () => {
    const uploaded = youtubeCellText(
      row({
        meta: {
          youtube_success: 1,
          youtube_status: "READY",
          youtube_url: "https://youtube.com/watch?v=1",
        },
      }),
    );
    expect(uploaded.primary).toBe("Completed");
    expect(uploaded.url).toBe("https://youtube.com/watch?v=1");
    expect(uploaded.tone).toBe("success");
    expect(youtubeCellText(row({ meta: { youtube_failed: 1 } })).primary).toBe("Failed");
  });

  it("renders a five-step timeline and marks unreported video stages as unavailable", () => {
    const steps = stageTimeline(row({ stage: "image" }), false);
    expect(steps.map((step) => step.key)).toEqual([
      "music",
      "image",
      "converter",
      "merge",
      "youtube",
    ]);
    expect(steps[0].state).toBe("passed");
    expect(steps[1].state).toBe("current");
    expect(steps[2].state).toBe("unavailable");
    expect(steps[2].detail).toBe("Pipeline integration arrives in P7");
  });

  it("names the failed stage when the row text allows it", () => {
    const steps = stageTimeline(
      row({ stage: "error", status: "failed", notes: "Merge failed: ffmpeg exited" }),
      false,
    );
    expect(steps[3].state).toBe("failed");
    expect(steps[0].state).toBe("passed");
    expect(steps[4].state).toBe("pending");
  });

  it("formats relative times from an injected clock", () => {
    const now = Date.parse("2026-11-19T10:05:00Z");
    expect(relativeTime("2026-11-19T10:04:40Z", now)).toBe("<1m ago");
    expect(relativeTime("2026-11-19T09:40:00Z", now)).toBe("25m ago");
    expect(relativeTime(null, now)).toBe("Not reported");
  });

  it("builds the summary and meta lines without inventing local output", () => {
    const rows = [row({ stage: "music" })];
    expect(summaryText({ rows, summary: "Ready", updated_at: null }, rows)).toContain(
      "Pipeline integration arrives in P7",
    );
    const withLocal = [row({ stage: "merge", meta: { long_ready: true } })];
    expect(summaryText({ rows: withLocal, summary: "Ready", updated_at: null }, withLocal)).toContain(
      "1 run report local video output",
    );
    expect(summaryText({ rows: [], summary: "No runs", updated_at: null }, [])).toBe("No runs.");
    expect(metaLine(3, 100, 2, "error", 200)).toBe(
      "3 visible rows · 100 loaded · API cap 100 · 2 pending downloads · Error",
    );
  });

  it("produces a local date string for the default range", () => {
    expect(todayYmd(new Date(2026, 10, 19, 12, 0, 0))).toBe("2026-11-19");
  });
});

describe("download queue", () => {
  it("maps batch ids to channel names and reports target progress", () => {
    const rows = downloadQueueRows(
      [
        {
          task_id: "task-1",
          batch_id: "batch-1",
          title: "Night Drive",
          track_number: 2,
          primary: {
            download_url: "https://example.test/1.mp3",
            downloaded: true,
            output_dir: "C:\\music",
            target_path: "C:\\music\\1.mp3",
          },
          secondary: {
            download_url: null,
            downloaded: false,
            output_dir: "C:\\music",
            target_path: "C:\\music\\2.mp3",
          },
        },
      ],
      [row()],
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].channel).toBe("Night Shift");
    expect(rows[0].state).toBe("Partial");
    expect(rows[0].progress).toBe("1/2 targets ready");
    expect(rows[0].revealPath).toBe("C:\\music\\1.mp3");
    expect(rows[0].hasDownloadUrl).toBe(true);
  });

  it("falls back to the batch id when no loaded row names the channel", () => {
    const [entry] = downloadQueueRows(
      [{ task_id: "task-2", batch_id: "batch-9", primary: { downloaded: false } }],
      [],
    );
    expect(entry.channel).toBe("batch-9");
    expect(entry.state).toBe("Pending");
    expect(entry.progress).toBe("0/1 target ready");
  });
});
