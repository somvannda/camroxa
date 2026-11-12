import { describe, expect, it } from "vitest";

import { placeUploadInProject, uploadTitle } from "@/lib/studio-upload-place";

const upload = {
  filename: "demo-loop.wav",
  url: "https://cdn.example/demo-loop.wav",
  durationSeconds: 4,
};

describe("uploadTitle", () => {
  it("drops the extension and falls back for empty names", () => {
    expect(uploadTitle("demo-loop.wav")).toBe("demo-loop");
    expect(uploadTitle("take 2.final.mp3")).toBe("take 2.final");
    expect(uploadTitle(".wav")).toBe("Upload");
  });
});

describe("placeUploadInProject", () => {
  it("appends the upload after the last clip on the first track", () => {
    const data = {
      lanes: [
        { id: "a", start: 0, duration: 2 },
        { id: "b", start: 4, duration: 2 },
      ],
      tracks: [
        { id: "t1", name: "Drums", clipIds: ["a"] },
        { id: "t2", name: "Bass", clipIds: ["b"] },
      ],
    };

    const result = placeUploadInProject(data, upload, "s1");

    expect(result.trackId).toBe("t1");
    expect(result.start).toBe(2);
    const clip = (result.data.lanes as Array<Record<string, unknown>>).at(-1);
    expect(clip).toMatchObject({
      id: "clip-s1",
      title: "demo-loop",
      start: 2,
      duration: 4,
      audioUrl: upload.url,
    });
    const tracks = result.data.tracks as Array<{ id: string; clipIds: string[] }>;
    expect(tracks[0].clipIds).toEqual(["a", "clip-s1"]);
    // Other tracks are untouched.
    expect(tracks[1].clipIds).toEqual(["b"]);
  });

  it("creates an Uploads track for an empty project", () => {
    const result = placeUploadInProject({}, upload, "s2");

    expect(result.start).toBe(0);
    const tracks = result.data.tracks as Array<{ id: string; name: string; clipIds: string[] }>;
    expect(tracks).toHaveLength(1);
    expect(tracks[0].name).toBe("Uploads");
    expect(tracks[0].clipIds).toEqual(["clip-s2"]);
    expect(result.data.lanes).toHaveLength(1);
  });

  it("uses a sensible duration when the upload carries none", () => {
    const result = placeUploadInProject({}, { filename: "x.wav", url: "/x.wav" }, "s3");
    const clip = (result.data.lanes as Array<Record<string, unknown>>)[0];
    expect(clip.duration).toBe(4);
  });

  it("keeps existing project settings", () => {
    const data = { loopStart: 1, loopEnd: 5, masterVolume: 70, lanes: [], tracks: [] };
    const result = placeUploadInProject(data, upload, "s4");
    expect(result.data).toMatchObject({ loopStart: 1, loopEnd: 5, masterVolume: 70 });
  });
});
