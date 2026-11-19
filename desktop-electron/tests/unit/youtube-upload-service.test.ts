import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { YoutubeUploadService } from "../../electron/services/youtube-upload";
import type { ApiRequest } from "../../electron/shared/types";

const roots: string[] = [];

function tempRoot(): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-yt-service-"));
  roots.push(root);
  return root;
}

afterEach(() => {
  for (const root of roots.splice(0)) fs.rmSync(root, { recursive: true, force: true });
});

function profile(overrides: Record<string, unknown> = {}) {
  return {
    id: "profile-1",
    name: "Night Shift",
    youtube_config: {
      visibility: "public",
      playlist: "PL-night",
      title_template: "{title} — {channel}",
      ai_use: false,
    },
    video_template_id: null,
    reel_template_id: null,
    ...overrides,
  };
}

function service(options: {
  connections?: unknown[];
  quota?: Record<string, unknown>;
  profileOverride?: Record<string, unknown>;
  videoTemplateExists?: (id: string) => boolean;
}) {
  const calls: string[] = [];
  const api = async (request: ApiRequest) => {
    calls.push(`${request.method} ${request.path}`);
    if (request.path === "/profiles") {
      return { data: [profile(options.profileOverride ?? {})] };
    }
    if (request.path === "/youtube/connections") {
      return {
        data: {
          connections: options.connections ?? [
            {
              profile_id: "profile-1",
              status: "connected",
              channel_id: "channel-1",
              channel_title: "Night Shift Radio",
            },
          ],
        },
      };
    }
    if (request.path === "/youtube/quota") {
      return { data: options.quota ?? { limit: 6, used: 0, remaining: 6 } };
    }
    if (request.path.includes("/playlists")) {
      return { data: { playlists: [{ id: "PL-night", title: "Night Drive" }] } };
    }
    throw new Error(`unexpected request ${request.method} ${request.path}`);
  };
  const instance = new YoutubeUploadService({
    api,
    batches: () => [],
    managedRoots: () => [],
    videoTemplateExists: options.videoTemplateExists ?? (() => false),
    env: {},
  });
  return { instance, calls };
}

function runFolder(fileName = "MERGED_Night Drive.mp4", bytes = 32): string {
  const runDir = path.join(tempRoot(), "2026-11-19_Night Shift");
  fs.mkdirSync(runDir, { recursive: true });
  if (fileName) fs.writeFileSync(path.join(runDir, fileName), Buffer.alloc(bytes, 3));
  return runDir;
}

function query(runDir: string | null, youtubeUrl: string | null = null) {
  return {
    key: "NS|2026-11-19|profile-1|OK",
    batchId: "e29f0b8e-6f35-4d4b-9b5f-0e1d2c3b4a59",
    profileId: "profile-1",
    role: "OK",
    runDir,
    youtubeUrl,
  };
}

describe("youtube upload availability", () => {
  it("reports a ready merged row with the channel and playlist", async () => {
    const runDir = runFolder();
    const { instance, calls } = service({});
    const availability = await instance.availability([query(runDir)]);

    expect(availability.rows).toHaveLength(1);
    expect(availability.rows[0].block).toBe("none");
    expect(availability.rows[0].mergedName).toBe("MERGED_Night Drive.mp4");
    expect(availability.rows[0].mergedBytes).toBe(32);
    expect(availability.channel?.connected).toBe(true);
    expect(availability.channel?.channelTitle).toBe("Night Shift Radio");
    expect(availability.channel?.playlistId).toBe("PL-night");
    expect(availability.channel?.playlistTitle).toBe("Night Drive");
    expect(availability.quotaRemaining).toBe(6);
    // A lookup must never mint a token or create a job.
    expect(calls.some((call) => /access-token|publish\/jobs|uploads\/report/.test(call))).toBe(false);
  });

  it("explains no merged file, no channel, quota and already-uploaded", async () => {
    const emptyRun = runFolder("", 0);
    const ready = runFolder();

    const noFile = await service({}).instance.availability([query(emptyRun)]);
    expect(noFile.rows[0].block).toBe("no-file");
    expect(noFile.rows[0].reason).toMatch(/No merged video/);

    const noChannel = await service({ connections: [] }).instance.availability([query(ready)]);
    expect(noChannel.rows[0].block).toBe("no-channel");
    expect(noChannel.rows[0].reason).toMatch(/Settings → Profiles/);

    const quota = await service({ quota: { limit: 6, used: 6, remaining: 0 } }).instance.availability([
      query(ready),
    ]);
    expect(quota.rows[0].block).toBe("quota");
    expect(quota.rows[0].reason).toMatch(/quota/i);

    const uploaded = await service({}).instance.availability([
      query(ready, "https://www.youtube.com/watch?v=x"),
    ]);
    expect(uploaded.rows[0].block).toBe("already-uploaded");
  });

  it("blocks a legacy Camxora template with the 2.0.0 policy", async () => {
    const ready = runFolder();
    const legacy = await service({
      profileOverride: { video_template_id: "legacy-camxora-template" },
      videoTemplateExists: () => false,
    }).instance.availability([query(ready)]);
    expect(legacy.rows[0].block).toBe("legacy-template");
    expect(legacy.rows[0].reason).toMatch(/2\.0\.0 does not migrate/);

    const vizzy = await service({
      profileOverride: { video_template_id: "night-drive" },
      videoTemplateExists: (id) => id === "night-drive",
    }).instance.availability([query(ready)]);
    expect(vizzy.rows[0].block).toBe("none");
  });

  it("refuses a filesystem root as the containment folder", async () => {
    const { instance } = service({});
    const root = path.parse(process.cwd()).root;
    const availability = await instance.availability([query(root)]);
    expect(availability.rows[0].block).toBe("no-file");
    expect(availability.rows[0].mergedPath).toBeNull();
  });

  it("plans the publication without uploading anything", async () => {
    const ready = runFolder();
    const { instance, calls } = service({});
    const plan = await instance.plan(query(ready));
    expect(plan.title).toBe("Night Shift — Night Shift");
    expect(plan.channelTitle).toBe("Night Shift Radio");
    expect(plan.visibility).toBe("Public");
    expect(plan.playlistId).toBe("PL-night");
    expect(plan.playlistTitle).toBe("Night Drive");
    expect(plan.mergedName).toBe("MERGED_Night Drive.mp4");
    expect(plan.containsSyntheticMedia).toBe(false);
    expect(calls.some((call) => /access-token|publish\/jobs/.test(call))).toBe(false);
  });
});
