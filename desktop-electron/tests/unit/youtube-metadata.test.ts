import { describe, expect, it } from "vitest";
import {
  albumFromPath,
  buildMetadata,
  buildPublishJobPayload,
  nextPublishAt,
  renderTemplate,
  sanitizeTags,
  visibilityLabel,
  youtubeInsertBody,
} from "../../electron/services/youtube-metadata";

const profile = {
  id: "profile-1",
  name: "Night Shift",
  youtubeConfig: {
    title_template: "{title} — {channel}",
    description_template: "Album {album} on {channel}",
    visibility: "public",
    category: "10",
    playlist: "PL123",
    tags: ["Night Drive", "night drive", "chill <music>"],
    ai_use: true,
    made_for_kids: false,
  },
};

const VIDEO = "C:\\runs\\2026-11-19_Night Shift\\NS-01-merged.mp4";

describe("youtube metadata", () => {
  it("derives the album from the run folder name", () => {
    expect(albumFromPath(VIDEO)).toBe("Night Shift");
    expect(albumFromPath("C:\\runs\\Night-Drive\\NS-01-merged.mp4")).toBe("Night Drive");
    expect(albumFromPath("C:\\runs\\2026-11-19_Night_Drive\\x.mp4")).toBe("Night Drive");
    expect(albumFromPath("C:\\x\\track.mp4")).toBe("x");
  });

  it("renders {title}/{album}/{channel} and collapses whitespace", () => {
    expect(renderTemplate("{title} by {channel}", { album: "Night", channel: "Shift" })).toBe(
      "Night by Shift",
    );
    expect(renderTemplate("{album}  {album}", { album: "A", channel: "C" })).toBe("A A");
    expect(renderTemplate("", { album: "A", channel: "C" })).toBe("A");
  });

  it("sanitises tags the way YouTube validates them", () => {
    expect(sanitizeTags("a, b ,, a")).toEqual(["a", "b"]);
    expect(sanitizeTags(["<bad>", "ok  tag"])).toEqual(["bad", "ok tag"]);
    expect(sanitizeTags(["x".repeat(80)])[0]).toHaveLength(60);
    const many = sanitizeTags(Array.from({ length: 40 }, (_, index) => `tag-${index}-${"y".repeat(20)}`));
    expect(many.join(",").length).toBeLessThanOrEqual(500);
    expect(sanitizeTags(undefined)).toEqual([]);
    expect(sanitizeTags({ bad: true })).toEqual([]);
  });

  it("schedules the next local occurrence in UTC", () => {
    const now = new Date(2026, 10, 19, 8, 0, 0);
    const later = new Date(nextPublishAt("09:30", now) ?? "");
    expect(later.getHours()).toBe(9);
    expect(later.getMinutes()).toBe(30);
    expect(later.getDate()).toBe(19);
    expect(nextPublishAt("09:30", now)?.endsWith("Z")).toBe(true);

    const tomorrow = new Date(nextPublishAt("07:00", now) ?? "");
    expect(tomorrow.getDate()).toBe(20);

    expect(nextPublishAt("2026-12-01T10:00:00Z", now)).toBe("2026-12-01T10:00:00Z");
    expect(nextPublishAt("not a time", now)).toBeNull();
    expect(nextPublishAt("25:00", now)).toBeNull();
    expect(nextPublishAt("", now)).toBeNull();
  });

  it("builds the YouTube metadata from the profile publication settings", () => {
    const metadata = buildMetadata({ profile, videoPath: VIDEO });
    expect(metadata.title).toBe("Night Shift — Night Shift");
    expect(metadata.description).toBe("Album Night Shift on Night Shift");
    expect(metadata.tags).toEqual(["Night Drive", "chill music"]);
    expect(metadata.visibility).toBe("public");
    expect(metadata.category).toBe("10");
    expect(metadata.playlistId).toBe("PL123");
    expect(metadata.containsSyntheticMedia).toBe(true);
    expect(metadata.madeForKids).toBe(false);
    expect(metadata.publishAt).toBeNull();
  });

  it("keeps scheduled uploads private with publishAt and defaults to private otherwise", () => {
    const scheduled = buildMetadata({
      profile: {
        ...profile,
        youtubeConfig: { ...profile.youtubeConfig, visibility: "scheduled", publish_at: "09:30" },
      },
      videoPath: VIDEO,
      now: new Date(2026, 10, 19, 8, 0, 0),
    });
    const body = youtubeInsertBody(scheduled);
    expect(scheduled.visibility).toBe("scheduled");
    expect((body.status as Record<string, unknown>).privacyStatus).toBe("private");
    expect((body.status as Record<string, unknown>).publishAt).toBe(scheduled.publishAt);
    expect(visibilityLabel(scheduled)).toContain("Scheduled");

    const unknown = buildMetadata({
      profile: { ...profile, youtubeConfig: { visibility: "everyone" } },
      videoPath: VIDEO,
    });
    expect(unknown.visibility).toBe("private");
    expect(unknown.category).toBe("10");
    expect((youtubeInsertBody(unknown).status as Record<string, unknown>).privacyStatus).toBe(
      "private",
    );
  });

  it("maps the publish-job payload without leaking anything secret", () => {
    const metadata = buildMetadata({ profile, videoPath: VIDEO });
    const payload = buildPublishJobPayload({
      profileId: "profile-1",
      batchId: "  e29f0b8e-6f35-4d4b-9b5f-0e1d2c3b4a59 ",
      role: "ok",
      metadata,
      filePath: VIDEO,
      fileSizeBytes: 1024,
    });
    expect(payload).toMatchObject({
      profile_id: "profile-1",
      platform: "youtube",
      batch_id: "e29f0b8e-6f35-4d4b-9b5f-0e1d2c3b4a59",
      role: "OK",
      title: metadata.title,
      description: metadata.description,
      tags: metadata.tags,
      privacy_status: "public",
      publish_at: null,
      made_for_kids: false,
      contains_synthetic_media: true,
      file_name: "NS-01-merged.mp4",
      file_size_bytes: 1024,
      file_path: VIDEO,
      thumbnail_path: null,
    });
    const keys = Object.keys(payload).join(" ");
    expect(keys).not.toMatch(/token|secret|email|cookie/i);
    expect(JSON.stringify(payload)).not.toContain("access_token");
  });
});
