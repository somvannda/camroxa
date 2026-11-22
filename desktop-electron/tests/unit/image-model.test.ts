import { describe, expect, it } from "vitest";
import {
  basenameOrDash,
  buildFooterDetail,
  buildQueueRows,
  buildAlbumLabels,
  bytesToDataUrl,
  emptyQueueMessage,
  filterBatchesByDate,
  filterJobsByBatchIds,
  normalizeImagePrompts,
  previewCandidates,
  splitFooterDetail,
  statusTone,
  summarizeQueue,
  todayYmd,
} from "../../src/features/image/image-model";
import type {
  ChannelProfile,
  ImageJobListItem,
  MusicHistoryBatch,
} from "../../src/features/image/image-types";

function job(overrides: Partial<ImageJobListItem> & { id: string; kind: string; status: string }): ImageJobListItem {
  return {
    batch_id: "batch-1",
    song_id: "song-1",
    profile_id: "profile-1",
    channel_role: "ok",
    prompt: null,
    input_image_path: null,
    style_reference_path: null,
    output_image_path: null,
    error: null,
    created_at: "2026-11-19T08:00:00Z",
    updated_at: "2026-11-19T08:00:00Z",
    ...overrides,
  };
}

const batch: MusicHistoryBatch = {
  batch_id: "batch-1",
  status: "completed",
  song_count: 3,
  from_date: "2026-11-18",
  to_date: "2026-11-19",
  ok_album: "Night Drive",
  alt_album: "Night Drive II",
  created_at: "2026-11-18T08:00:00Z",
  updated_at: "2026-11-19T08:00:00Z",
  songs: [{ album: "Night Drive", title: "Opening" }],
};

const profile: ChannelProfile = { id: "profile-1", name: "Night Shift" };

describe("image queue model", () => {
  it("groups background and thumbnail jobs into one row", () => {
    const rows = buildQueueRows(
      [
        job({ id: "bg-1", kind: "background", status: "success", output_image_path: "C:/out/bg.png" }),
        job({ id: "th-1", kind: "thumbnail", status: "pending" }),
      ],
      [batch],
      [profile],
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].bgJob?.id).toBe("bg-1");
    expect(rows[0].thJob?.id).toBe("th-1");
    expect(rows[0].albumLabel).toBe("Night Drive");
    expect(rows[0].profileName).toBe("Night Shift");
  });

  it("keeps a separate row per role and picks the preferred job status", () => {
    const rows = buildQueueRows(
      [
        job({ id: "bg-old", kind: "background", status: "failed" }),
        job({ id: "bg-ok", kind: "background", status: "success", updated_at: "2026-11-19T09:00:00Z" }),
        job({ id: "bg-alt", kind: "background", status: "pending", channel_role: "alt" }),
      ],
      [batch],
      [profile],
    );
    expect(rows).toHaveLength(2);
    const ok = rows.find((row) => row.role === "ok");
    expect(ok?.bgJob?.id).toBe("bg-ok");
    expect(ok?.bgJobs).toHaveLength(2);
  });

  it("filters batches on inclusive boundaries", () => {
    expect(filterBatchesByDate([batch], "2026-11-19", "2026-11-19")).toHaveLength(1);
    expect(filterBatchesByDate([batch], "2026-11-18", "2026-11-18")).toHaveLength(1);
    expect(filterBatchesByDate([batch], "2026-11-20", "2026-11-21")).toHaveLength(0);
    expect(filterBatchesByDate([batch], "", "2026-11-17")).toHaveLength(0);
  });

  it("filters jobs to the matched batch ids", () => {
    const jobs = [job({ id: "a", kind: "background", status: "pending" })];
    expect(filterJobsByBatchIds(jobs, new Set(["batch-1"]))).toHaveLength(1);
    expect(filterJobsByBatchIds(jobs, new Set(["batch-2"]))).toHaveLength(0);
    expect(filterJobsByBatchIds(jobs, new Set())).toHaveLength(0);
  });

  it("summarises row and status counts", () => {
    const rows = buildQueueRows(
      [
        job({ id: "bg", kind: "background", status: "success" }),
        job({ id: "th", kind: "thumbnail", status: "failed" }),
        job({ id: "bg2", kind: "background", status: "running", channel_role: "alt" }),
        job({ id: "th2", kind: "thumbnail", status: "pending", channel_role: "alt" }),
      ],
      [batch],
      [profile],
    );
    const summary = summarizeQueue(rows);
    expect(summary).toMatchObject({ rows: 2, pending: 1, running: 1, failed: 1, ready: 1 });
    expect(summary.text).toBe("Rows 2 · Pending 1 · Running 1 · Failed 1 · Ready 1");
  });

  it("uses the legacy imagePrompt for the background but not the thumbnail", () => {
    expect(normalizeImagePrompts({ imagePrompt: "legacy" })).toEqual({
      background: "legacy",
      thumbnail: "",
    });
    expect(
      normalizeImagePrompts({ imagePrompt: "legacy", imageBackgroundPrompt: "bg", imageThumbnailPrompt: "th" }),
    ).toEqual({ background: "bg", thumbnail: "th" });
    expect(normalizeImagePrompts({ imageThumbnailPrompt: "x".repeat(20_005) }).thumbnail).toHaveLength(
      20_000,
    );
  });

  it("maps statuses to tones and labels missing files", () => {
    expect(statusTone("success")).toBe("success");
    expect(statusTone("running")).toBe("warning");
    expect(statusTone("failed")).toBe("danger");
    expect(statusTone("pending")).toBe("neutral");
    expect(basenameOrDash("C:\\renders\\night\\bg.png")).toBe("bg.png");
    expect(basenameOrDash(null)).toBe("—");
  });

  it("builds and splits the footer detail", () => {
    const rows = buildQueueRows(
      [
        job({
          id: "bg",
          kind: "background",
          status: "failed",
          error: "provider timeout",
          input_image_path: "/tmp/sample.png",
        }),
      ],
      [batch],
      [profile],
    );
    const detail = buildFooterDetail(rows[0]);
    expect(detail).toContain("3 tracks in batch");
    expect(detail).toContain("BG error: provider timeout");
    expect(detail).toContain("BG sample: sample.png");
    expect(splitFooterDetail(detail).errors).toContain("BG error: provider timeout");
  });

  it("orders preview candidates and encodes bytes", () => {
    const rows = buildQueueRows(
      [
        job({ id: "bg-a", kind: "background", status: "success", output_image_path: "/a.png" }),
        job({ id: "bg-b", kind: "background", status: "failed", output_image_path: "/b.png" }),
      ],
      [batch],
      [profile],
    );
    expect(previewCandidates(rows[0], "background")).toEqual([
      { jobId: "bg-a", path: "/a.png" },
      { jobId: "bg-b", path: "/b.png" },
    ]);
    expect(previewCandidates(null, "background")).toEqual([]);
    expect(bytesToDataUrl(new Uint8Array([1, 2]), "image/png")).toBe("data:image/png;base64,AQI=");
  });

  it("distinguishes empty states and names album labels", () => {
    expect(emptyQueueMessage(0, 0, 0)).toBe("No image jobs yet.");
    expect(emptyQueueMessage(4, 0, 0)).toBe("No batches found in the selected date range.");
    expect(emptyQueueMessage(4, 1, 0)).toBe("No image jobs yet for this date range.");
    const labels = buildAlbumLabels([
      { ...batch, status: "manual_image", ok_album: null, alt_album: null, songs: [] },
    ]);
    expect(labels.get("batch-1")?.ok).toBe("Not available");
    expect(todayYmd(new Date(2026, 10, 19))).toBe("2026-11-19");
  });
});
