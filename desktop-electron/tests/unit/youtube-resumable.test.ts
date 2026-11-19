import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  DEFAULT_CHUNK_BYTES,
  DEFAULT_PLAYLIST_ENDPOINT,
  DEFAULT_UPLOAD_ENDPOINT,
  MIN_CHUNK_BYTES,
  YoutubeUploadError,
  addToPlaylist,
  chunkRange,
  parseRangeOffset,
  resolveChunkBytes,
  resolveYoutubeEndpoints,
  retryDelayMs,
  startResumableSession,
  uploadResumable,
} from "../../electron/services/youtube-resumable";

const roots: string[] = [];

function tempFile(bytes: number): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-yt-"));
  roots.push(root);
  const filePath = path.join(root, "video.mp4");
  fs.writeFileSync(filePath, Buffer.alloc(bytes, 7));
  return filePath;
}

afterEach(() => {
  for (const root of roots.splice(0)) fs.rmSync(root, { recursive: true, force: true });
});

describe("resumable chunk math", () => {
  it("slices a file into 256 KiB aligned ranges", () => {
    const size = 1024 * 1024;
    expect(chunkRange(0, size, MIN_CHUNK_BYTES)).toEqual({
      start: 0,
      end: MIN_CHUNK_BYTES - 1,
      length: MIN_CHUNK_BYTES,
      contentRange: `bytes 0-${MIN_CHUNK_BYTES - 1}/${size}`,
      final: false,
    });
    const last = chunkRange(size - 10, size, MIN_CHUNK_BYTES);
    expect(last).toMatchObject({ start: size - 10, end: size - 1, length: 10, final: true });
    expect(last.contentRange).toBe(`bytes ${size - 10}-${size - 1}/${size}`);
    expect(chunkRange(size, size, MIN_CHUNK_BYTES).length).toBe(0);
  });

  it("reads the last received byte from a 308 Range header", () => {
    expect(parseRangeOffset("bytes=0-524287", 0)).toBe(524288);
    expect(parseRangeOffset("bytes=0-0", 0)).toBe(1);
    expect(parseRangeOffset(null, 4096)).toBe(4096);
    expect(parseRangeOffset("garbage", 999)).toBe(999);
  });

  it("keeps chunks on YouTube's 256 KiB granularity", () => {
    expect(resolveChunkBytes({})).toBe(DEFAULT_CHUNK_BYTES);
    expect(resolveChunkBytes({ CAMXORA_YOUTUBE_CHUNK_BYTES: "100" })).toBe(DEFAULT_CHUNK_BYTES);
    expect(resolveChunkBytes({ CAMXORA_YOUTUBE_CHUNK_BYTES: "300000" })).toBe(MIN_CHUNK_BYTES);
    expect(resolveChunkBytes({ CAMXORA_YOUTUBE_CHUNK_BYTES: String(MIN_CHUNK_BYTES * 3) })).toBe(
      MIN_CHUNK_BYTES * 3,
    );
  });

  it("backs off 1s/2s/4s and caps at 8s", () => {
    expect([1, 2, 3, 4, 10].map(retryDelayMs)).toEqual([1000, 2000, 4000, 8000, 8000]);
  });

  it("defaults to Google endpoints and only honours explicit overrides", () => {
    expect(resolveYoutubeEndpoints({})).toEqual({
      upload: DEFAULT_UPLOAD_ENDPOINT,
      playlist: DEFAULT_PLAYLIST_ENDPOINT,
    });
    expect(
      resolveYoutubeEndpoints({
        CAMXORA_YOUTUBE_UPLOAD_URL: "http://127.0.0.1:9/upload",
        CAMXORA_YOUTUBE_PLAYLIST_URL: "http://127.0.0.1:9/playlist",
      }),
    ).toEqual({ upload: "http://127.0.0.1:9/upload", playlist: "http://127.0.0.1:9/playlist" });
    expect(DEFAULT_UPLOAD_ENDPOINT.startsWith("https://www.googleapis.com/")).toBe(true);
    expect(DEFAULT_PLAYLIST_ENDPOINT.startsWith("https://www.googleapis.com/")).toBe(true);
  });
});

describe("resumable session", () => {
  it("opens the session with the metadata body and content length", async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const sessionUrl = await startResumableSession({
      accessToken: "test-token",
      body: { snippet: { title: "T" } },
      sizeBytes: 4096,
      endpoint: "https://upload.example/videos",
      fetchImpl: (async (url: string, init: RequestInit) => {
        calls.push({ url, init });
        return new Response("", { status: 200, headers: { location: "https://session.example/1" } });
      }) as typeof fetch,
    });
    expect(sessionUrl).toBe("https://session.example/1");
    const url = new URL(calls[0].url);
    expect(url.searchParams.get("uploadType")).toBe("resumable");
    expect(url.searchParams.get("part")).toBe("snippet,status");
    const headers = calls[0].init.headers as Record<string, string>;
    expect(headers["X-Upload-Content-Length"]).toBe("4096");
    expect(headers.Authorization).toBe("Bearer test-token");
    expect(calls[0].init.body).toBe(JSON.stringify({ snippet: { title: "T" } }));
  });

  it("surfaces a missing session URL without echoing the token", async () => {
    await expect(
      startResumableSession({
        accessToken: "secret-token",
        body: {},
        sizeBytes: 1,
        fetchImpl: (async () => new Response("", { status: 200 })) as typeof fetch,
      }),
    ).rejects.toMatchObject({ code: "YOUTUBE_SESSION" });
    const message = await (async () => {
      try {
        await startResumableSession({
          accessToken: "secret-token",
          body: {},
          sizeBytes: 1,
          fetchImpl: (async () => new Response("", { status: 200 })) as typeof fetch,
        });
        return "";
      } catch (cause) {
        return cause instanceof Error ? cause.message : String(cause);
      }
    })();
    expect(message).not.toContain("secret-token");
  });

  it("maps quota and auth refusals to readable reasons", async () => {
    const quota = await startResumableSession({
      accessToken: "t",
      body: {},
      sizeBytes: 1,
      fetchImpl: (async () =>
        new Response('{"error":{"errors":[{"reason":"uploadLimitExceeded"}]}}', {
          status: 403,
        })) as typeof fetch,
    }).catch((error: unknown) => error as YoutubeUploadError);
    expect(quota).toBeInstanceOf(YoutubeUploadError);
    expect((quota as YoutubeUploadError).code).toBe("YOUTUBE_QUOTA");

    const auth = await startResumableSession({
      accessToken: "t",
      body: {},
      sizeBytes: 1,
      fetchImpl: (async () => new Response("", { status: 401 })) as typeof fetch,
    }).catch((error: unknown) => error as YoutubeUploadError);
    expect((auth as YoutubeUploadError).code).toBe("YOUTUBE_AUTH");
    expect((auth as YoutubeUploadError).message).toMatch(/Reconnect the channel/);
  });
});

describe("resumable upload", () => {
  it("resumes from the 308 Range, retries a 503, and finishes with the video id", async () => {
    const filePath = tempFile(MIN_CHUNK_BYTES * 3 + 100);
    const size = fs.statSync(filePath).size;
    const ranges: string[] = [];
    const sleeps: number[] = [];
    let put = 0;

    const result = await uploadResumable({
      sessionUrl: "https://session.example/u",
      filePath,
      chunkBytes: MIN_CHUNK_BYTES,
      sleepImpl: async (ms) => {
        sleeps.push(ms);
      },
      fetchImpl: (async (_url: string, init: RequestInit) => {
        const headers = init.headers as Record<string, string>;
        ranges.push(headers["Content-Range"] ?? "");
        if (ranges.length === 1) {
          // Probe: YouTube already holds the first chunk.
          return new Response("", { status: 308, headers: { range: `bytes=0-${MIN_CHUNK_BYTES - 1}` } });
        }
        put += 1;
        if (put === 2) return new Response("busy", { status: 503 });
        if (put === 4) return new Response(JSON.stringify({ id: "vid-1" }), { status: 200 });
        const match = /^bytes (\d+)-(\d+)\/(\d+)$/.exec(headers["Content-Range"] ?? "");
        const end = match ? Number(match[2]) : 0;
        return new Response("", { status: 308, headers: { range: `bytes=0-${end}` } });
      }) as typeof fetch,
    });

    expect(result.videoId).toBe("vid-1");
    expect(sleeps).toEqual([1000]);
    expect(ranges[0]).toBe(`bytes */${size}`);
    expect(ranges[1]).toBe(`bytes ${MIN_CHUNK_BYTES}-${MIN_CHUNK_BYTES * 2 - 1}/${size}`);
    // The 503 retried the same chunk instead of skipping it.
    expect(ranges[3]).toBe(ranges[2]);
    expect(ranges[2]).toBe(`bytes ${MIN_CHUNK_BYTES * 2}-${MIN_CHUNK_BYTES * 3 - 1}/${size}`);
    expect(ranges.at(-1)).toBe(`bytes ${MIN_CHUNK_BYTES * 3}-${size - 1}/${size}`);
  });

  it("reports byte progress for every chunk", async () => {
    const filePath = tempFile(MIN_CHUNK_BYTES * 2 + 10);
    const size = fs.statSync(filePath).size;
    const progress: number[] = [];
    let chunk = 0;
    await uploadResumable({
      sessionUrl: "https://session.example/u",
      filePath,
      chunkBytes: MIN_CHUNK_BYTES,
      onProgress: (event) => progress.push(event.sentBytes),
      fetchImpl: (async (_url: string, init: RequestInit) => {
        if (!init.body) return new Response("", { status: 308 });
        chunk += 1;
        if (chunk === 3) return new Response(JSON.stringify({ id: "vid-2" }), { status: 201 });
        const match = /^bytes (\d+)-(\d+)\/(\d+)$/.exec((init.headers as Record<string, string>)["Content-Range"] ?? "");
        return new Response("", {
          status: 308,
          headers: { range: `bytes=0-${match ? match[2] : 0}` },
        });
      }) as typeof fetch,
    });
    expect(progress[0]).toBe(0);
    expect(progress).toContain(MIN_CHUNK_BYTES);
    expect(progress.at(-1)).toBe(size);
  });

  it("cancels before sending a chunk and never touches the file", async () => {
    const filePath = tempFile(MIN_CHUNK_BYTES * 2);
    const before = fs.readFileSync(filePath);
    let requests = 0;
    const error = await uploadResumable({
      sessionUrl: "https://session.example/u",
      filePath,
      chunkBytes: MIN_CHUNK_BYTES,
      isCancelled: () => true,
      fetchImpl: (async () => {
        requests += 1;
        return new Response("", { status: 308 });
      }) as typeof fetch,
    }).catch((cause: unknown) => cause as YoutubeUploadError);
    expect((error as YoutubeUploadError).code).toBe("YOUTUBE_CANCELLED");
    expect(requests).toBe(0);
    expect(fs.readFileSync(filePath).equals(before)).toBe(true);
    expect(fs.existsSync(filePath)).toBe(true);
  });

  it("fails with a readable reason when a chunk keeps failing", async () => {
    const filePath = tempFile(MIN_CHUNK_BYTES + 10);
    let put = 0;
    const error = await uploadResumable({
      sessionUrl: "https://session.example/u",
      filePath,
      chunkBytes: MIN_CHUNK_BYTES,
      sleepImpl: async () => undefined,
      fetchImpl: (async (_url: string, init: RequestInit) => {
        if (!init.body) return new Response("", { status: 308 });
        put += 1;
        return new Response("nope", { status: 500 });
      }) as typeof fetch,
    }).catch((cause: unknown) => cause as YoutubeUploadError);
    expect((error as YoutubeUploadError).code).toBe("YOUTUBE_NETWORK");
    expect((error as YoutubeUploadError).retryable).toBe(true);
    expect(put).toBe(3);
    expect(fs.existsSync(filePath)).toBe(true);
  });

  it("treats an already-complete session as success", async () => {
    const filePath = tempFile(10);
    const result = await uploadResumable({
      sessionUrl: "https://session.example/u",
      filePath,
      fetchImpl: (async () => new Response(JSON.stringify({ id: "vid-3" }), { status: 200 })) as typeof fetch,
    });
    expect(result.videoId).toBe("vid-3");
  });
});

describe("playlist insertion", () => {
  it("posts the video as a playlist item and keeps upload failures readable", async () => {
    const calls: RequestInit[] = [];
    await addToPlaylist({
      accessToken: "t",
      playlistId: "PL1",
      videoId: "vid-1",
      endpoint: "https://api.example/playlistItems",
      fetchImpl: (async (_url: string, init: RequestInit) => {
        calls.push(init);
        return new Response("{}", { status: 200 });
      }) as typeof fetch,
    });
    expect(JSON.parse(String(calls[0].body))).toEqual({
      snippet: {
        playlistId: "PL1",
        resourceId: { kind: "youtube#video", videoId: "vid-1" },
      },
    });

    const error = await addToPlaylist({
      accessToken: "t",
      playlistId: "PL1",
      videoId: "vid-1",
      fetchImpl: (async () => new Response("", { status: 404 })) as typeof fetch,
    }).catch((cause: unknown) => cause as YoutubeUploadError);
    expect((error as YoutubeUploadError).message).toMatch(/video uploaded/i);
  });
});
