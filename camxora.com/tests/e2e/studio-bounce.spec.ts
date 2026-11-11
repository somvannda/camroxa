import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Track bounce (N-06).
 *
 * The reference reports "Exporting on track #" and renders a mixdown; ours bounces one
 * track through its own effect chain and hands back a WAV, ignoring the other tracks'
 * solo state so a soloed-out track is never silent.
 */

test("the track menu bounces that track to a RIFF mixdown", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `Bounce ${tag}`,
    clips: [
      { id: "loop", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  await page.getByLabel("Options for Track 1").click();
  const download = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "Bounce track" }).click();

  const wav = await download;
  expect(wav.suggestedFilename()).toContain("(bounce).wav");

  const path = await wav.path();
  if (!path) throw new Error("bounce download has no path");
  const bytes = await readFile(path);
  expect(bytes.subarray(0, 4).toString("latin1")).toBe("RIFF");
  expect(bytes.subarray(8, 12).toString("latin1")).toBe("WAVE");
  // 4 s stereo 44.1 kHz 16-bit plus the 44-byte header.
  const expected = 44 + 4 * 44100 * 2 * 2;
  expect(Math.abs(bytes.length - expected)).toBeLessThan(2000);

  await expect(page.getByRole("status")).toContainText("Bounce on Track 1 downloaded");
});

test("bounce places a bounced track when storage accepts the render", async ({ page }) => {
  test.setTimeout(120_000);

  // The sandbox API has no upload storage (B-007), so this proves the in-place path
  // against a stubbed upload response; the render itself is real.
  await page.route("**/api/v3/web-music/studio/uploads", (route) =>
    route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        id: "bounce-upload",
        filename: "bounce.wav",
        content_type: "audio/wav",
        size_bytes: 1024,
        duration_seconds: 4,
        url: "/seed/demo-loop.wav",
      }),
    })
  );

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Bounce place ${tag}`,
    clips: [
      { id: "loop", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  await page.getByLabel("Options for Track 1").click();
  await page.getByRole("menuitem", { name: "Bounce track" }).click();

  await expect(
    page.locator(".se-tracks").getByText("Track 1 (bounced)", { exact: true })
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText("added as a new track");

  const readDocument = () =>
    page.evaluate(async (id) => {
      const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
      return (await response.json()) as {
        data: {
          tracks: Array<{ id: string; name: string; muted: boolean; clipIds: string[] }>;
          lanes: Array<{ id: string; audioUrl?: string | null; start?: number }>;
        };
      };
    }, projectId);

  // The write is asynchronous; wait for the document rather than the DOM.
  await expect.poll(async () => (await readDocument()).data.tracks.length, {
    timeout: 15_000,
    intervals: [250],
  }).toBe(2);
  const document = await readDocument();

  expect(document.data.tracks).toHaveLength(2);
  // The source is muted, the render sits on its own track at the same span.
  expect(document.data.tracks[0].muted).toBe(true);
  expect(document.data.tracks[1].name).toBe("Track 1 (bounced)");
  const bouncedClip = document.data.lanes.find(
    (lane) => lane.id === document.data.tracks[1].clipIds[0]
  );
  expect(bouncedClip?.audioUrl).toBe("/seed/demo-loop.wav");
  expect(bouncedClip?.start).toBe(0);
});

const uploadProxy = process.env.STUDIO_UPLOAD_PROXY_URL;

/**
 * Optional integration check for B-007: when STUDIO_UPLOAD_PROXY_URL points at a
 * storage-backed platform API (moto/S3 from B-006), the browser's upload is proxied
 * there, so the bounce really lands in a bucket and the placed clip points at it.
 * Skipped by default because the sandbox API has no storage.
 */
test("bounce stores the render in the bucket when uploads are configured", async ({ page }) => {
  test.skip(!uploadProxy, "set STUDIO_UPLOAD_PROXY_URL to a storage-backed API");
  test.setTimeout(120_000);

  await page.route("**/api/v3/web-music/studio/uploads", async (route) => {
    const response = await route.fetch({
      url: `${uploadProxy}/api/v3/web-music/studio/uploads`,
    });
    await route.fulfill({ response });
  });

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Bounce bucket ${tag}`,
    clips: [
      { id: "loop", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  await page.getByLabel("Options for Track 1").click();
  await page.getByRole("menuitem", { name: "Bounce track" }).click();

  await expect(page.getByRole("status")).toContainText("added as a new track");

  await expect
    .poll(
      async () =>
        page.evaluate(async (id) => {
          const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
          const project = (await response.json()) as {
            data?: {
              tracks?: Array<{ name: string; clipIds: string[] }>;
              lanes?: Array<{ id: string; audioUrl?: string | null }>;
            };
          };
          const bounced = project.data?.tracks?.find((track) =>
            track.name.endsWith("(bounced)")
          );
          if (!bounced) return null;
          return project.data?.lanes?.find((lane) => lane.id === bounced.clipIds[0])?.audioUrl;
        }, projectId),
      { timeout: 15_000, intervals: [250] }
    )
    .toContain("9000");
});

test("a track with no clips cannot be bounced", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Empty bounce ${tag}` });

  // Clear the fixture clip, leaving the track in place with nothing to render.
  await page.locator(".se-clip").first().click();
  await page.keyboard.press("Backspace");
  await expect(page.locator(".se-clip")).toHaveCount(0);

  await page.getByLabel("Options for Track 1").click();
  await expect(page.getByRole("menuitem", { name: "Bounce track" })).toBeDisabled();
});
