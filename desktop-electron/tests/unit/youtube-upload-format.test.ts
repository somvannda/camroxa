import { describe, expect, it } from "vitest";
import type { YoutubeUploadState } from "../../electron/shared/types";
import type { ProgressRow } from "../../src/features/progress/progress-types";
import {
  availabilityFor,
  confirmationLines,
  formatUploadBytes,
  formatUploadProgress,
  playlistChoices,
  uploadCandidateRows,
  uploadControl,
  uploadPhaseLabel,
  uploadRowQuery,
  uploadTone,
} from "../../src/features/progress/youtube-upload-format";

function row(overrides: Partial<ProgressRow> = {}, meta: Record<string, unknown> = {}): ProgressRow {
  return {
    batch: "NS-2601",
    run_date: "2026-11-19",
    channel: "Night Shift",
    status: "completed",
    music: "12/12",
    image: "4/4",
    converter: "Completed",
    merge: "Completed",
    youtube: "",
    stage: "done",
    notes: "",
    updated: "just now",
    ...overrides,
    meta: {
      batch_id: "e29f0b8e-6f35-4d4b-9b5f-0e1d2c3b4a59",
      profile_id: "profile-1",
      role: "OK",
      run_dir: "C:\\runs\\2026-11-19_Night Shift",
      youtube_url: null,
      ...meta,
    },
  } as ProgressRow;
}

function uploadState(overrides: Partial<YoutubeUploadState> = {}): YoutubeUploadState {
  return {
    uploadId: "upload-1",
    key: "k",
    batchId: "batch",
    profileId: "profile-1",
    phase: "uploading",
    sentBytes: 512,
    totalBytes: 1024,
    percent: 50,
    message: null,
    title: "Title",
    videoId: null,
    videoUrl: null,
    jobUid: null,
    error: null,
    startedAt: 0,
    finishedAt: null,
    ...overrides,
  };
}

const channel = {
  profileId: "profile-1",
  profileName: "Night Shift",
  connected: true,
  channelTitle: "Night Shift Radio",
  playlistId: "PL1",
  playlistTitle: "Night Drive",
  playlists: [
    { id: "PL1", title: "Night Drive" },
    { id: "PL2", title: "After Hours" },
  ],
};

describe("upload row queries", () => {
  it("builds the main-process query from a row", () => {
    expect(uploadRowQuery(row())).toEqual({
      key: "NS-2601|2026-11-19|profile-1|OK",
      batchId: "e29f0b8e-6f35-4d4b-9b5f-0e1d2c3b4a59",
      profileId: "profile-1",
      role: "OK",
      runDir: "C:\\runs\\2026-11-19_Night Shift",
      youtubeUrl: null,
    });
    expect(uploadRowQuery(row({}, { profile_id: "" }))).toBeNull();
  });

  it("only asks about rows that reached a video output", () => {
    const rows = [
      row({ stage: "music", converter: "", merge: "" }, { pipeline_complete: false, run_dir: null }),
      row({ stage: "merger" }, { pipeline_complete: false, long_ready: true }),
      row({ stage: "done" }, { pipeline_complete: true }),
    ];
    const candidates = uploadCandidateRows(rows);
    expect(candidates).toHaveLength(2);
    expect(candidates[0].stage).toBe("merger");
    expect(availabilityFor(null, "anything")).toBeUndefined();
  });
});

describe("upload control state", () => {
  const base = {
    channel,
    blockedByOther: false,
    lookupError: null,
  };

  it("enables the action only for a ready row with a connected channel", () => {
    const control = uploadControl({
      ...base,
      row: { key: "k", profileId: "profile-1", mergedPath: "C:\\a.mp4", mergedName: "a.mp4", mergedBytes: 10, block: "none", reason: null },
      upload: undefined,
    });
    expect(control.canUpload).toBe(true);
    expect(control.reason).toBeNull();
    expect(control.playlistLabel).toBe("Night Drive");
  });

  it("explains every disabled state", () => {
    const cases = ["no-file", "no-channel", "quota", "legacy-template", "already-uploaded"];
    for (const [block] of cases) {
      const control = uploadControl({
        ...base,
        row: {
          key: "k",
          profileId: "profile-1",
          mergedPath: null,
          mergedName: null,
          mergedBytes: null,
          block: block as "no-file",
          reason: `reason for ${block}`,
        },
        upload: undefined,
      });
      expect(control.canUpload).toBe(false);
      expect(control.reason).toBe(`reason for ${block}`);
    }
  });

  it("disables while another row uploads and while a lookup failed", () => {
    const busy = uploadControl({
      ...base,
      blockedByOther: true,
      row: { key: "k", profileId: "profile-1", mergedPath: "C:\\a.mp4", mergedName: "a.mp4", mergedBytes: 1, block: "none", reason: null },
      upload: undefined,
    });
    expect(busy.canUpload).toBe(false);
    expect(String(busy.reason)).toContain("Another YouTube upload");

    const broken = uploadControl({
      ...base,
      lookupError: "offline",
      row: undefined,
      upload: undefined,
    });
    expect(broken.canUpload).toBe(false);
    expect(String(broken.reason)).toContain("offline");
  });

  it("offers cancel while uploading and retry after a failure", () => {
    const uploading = uploadControl({
      ...base,
      row: { key: "k", profileId: "profile-1", mergedPath: "C:\\a.mp4", mergedName: "a.mp4", mergedBytes: 1, block: "none", reason: null },
      upload: uploadState({ phase: "uploading" }),
    });
    expect(uploading.uploading).toBe(true);
    expect(uploading.canCancel).toBe(true);
    expect(uploading.canUpload).toBe(false);

    const failed = uploadControl({
      ...base,
      row: { key: "k", profileId: "profile-1", mergedPath: "C:\\a.mp4", mergedName: "a.mp4", mergedBytes: 1, block: "none", reason: null },
      upload: uploadState({ phase: "failed", error: "YouTube refused it", finishedAt: 1 }),
    });
    expect(failed.canRetry).toBe(true);
    expect(failed.canCancel).toBe(false);
  });

  it("does not offer a second upload for a video that just published", () => {
    const control = uploadControl({
      ...base,
      row: { key: "k", profileId: "profile-1", mergedPath: "C:\\a.mp4", mergedName: "a.mp4", mergedBytes: 1, block: "none", reason: null },
      upload: uploadState({ phase: "done", videoUrl: "https://www.youtube.com/watch?v=x", percent: 100 }),
    });
    expect(control.canUpload).toBe(false);
    expect(control.canRetry).toBe(false);
    expect(String(control.reason)).toContain("already on YouTube");
  });

  it("labels phases, tones and sizes for the panel", () => {
    expect(formatUploadBytes(0)).toBe("0 MB");
    expect(formatUploadBytes(2048)).toBe("2 KB");
    expect(formatUploadBytes(5 * 1024 * 1024)).toBe("5.0 MB");
    expect(formatUploadBytes(2 * 1024 * 1024 * 1024)).toBe("2.00 GB");
    expect(formatUploadProgress(uploadState())).toBe("50% · 1 KB of 1 KB");
    expect(uploadTone(uploadState())).toBe("accent");
    expect(uploadTone(uploadState({ phase: "done" }))).toBe("success");
    expect(uploadTone(uploadState({ phase: "failed" }))).toBe("danger");
    expect(uploadPhaseLabel(undefined)).toBe("Not started");
    expect(uploadPhaseLabel(uploadState({ phase: "cancelled" }))).toBe("Cancelled");
  });
});

describe("confirmation copy", () => {
  it("lists the channel, title, visibility, file, playlist and disclosure", () => {
    const lines = confirmationLines({
      channelTitle: "Night Shift Radio",
      profileName: "Night Shift",
      title: "Night Drive",
      visibility: "Scheduled · 2026-11-20T09:30:00Z",
      mergedName: "NS-01-merged.mp4",
      mergedBytes: 4096,
      playlistTitle: "Night Drive",
      containsSyntheticMedia: true,
      madeForKids: false,
    });
    expect(lines.map((line) => line.label)).toEqual([
      "Channel",
      "Title",
      "Visibility",
      "File",
      "Playlist",
      "Disclosure",
    ]);
    expect(lines[0].value).toBe("Night Shift Radio (Night Shift)");
    expect(lines[2].value).toContain("Scheduled");
    expect(lines[3].value).toContain("4 KB");
    expect(lines[5].value).toBe("AI-generated content disclosed");
  });

  it("offers the profile playlist, the channel playlists and no-playlist", () => {
    expect(playlistChoices(channel, "PL1")).toEqual([
      { value: "PL1", label: "Night Drive (profile default)" },
      { value: "PL2", label: "After Hours" },
      { value: "none", label: "No playlist" },
    ]);
    expect(playlistChoices(null, null)).toEqual([{ value: "none", label: "No playlist" }]);
  });
});
