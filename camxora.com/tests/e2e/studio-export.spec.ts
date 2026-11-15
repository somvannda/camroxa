import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

import { createStudioProject } from "./studio-fixture";

/**
 * Export downloads (W4.3): the renderer and WAV encoder are unit-tested, but the menu →
 * download wiring never was. These read the actual downloaded bytes.
 */

test("full mix downloads a RIFF file and JSON exports the document", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const title = `Export ${tag}`;
  await createStudioProject(page, { title });

  // Full Song: the fixture has one 4-second clip with no audio URL, so the mix is
  // silence — but it must still be a valid, correctly sized RIFF file.
  await page.getByLabel("Export menu").click();
  const wavDownload = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "Full Song" }).click();
  const wav = await wavDownload;
  expect(wav.suggestedFilename()).toBe(`${title}.wav`);

  const wavPath = await wav.path();
  if (!wavPath) throw new Error("download has no path");
  const bytes = await readFile(wavPath);
  expect(bytes.subarray(0, 4).toString("latin1")).toBe("RIFF");
  expect(bytes.subarray(8, 12).toString("latin1")).toBe("WAVE");
  expect(bytes.subarray(12, 16).toString("latin1")).toBe("fmt ");
  // 4 s stereo 44.1 kHz 16-bit + 44-byte header (allow a little slack for rounding).
  const expected = 44 + 4 * 44100 * 2 * 2;
  expect(Math.abs(bytes.length - expected)).toBeLessThan(2000);

  // Multitrack: a single track means exactly one download.
  await page.getByLabel("Export menu").click();
  const trackDownload = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "Multitrack" }).click();
  const track = await trackDownload;
  expect(track.suggestedFilename()).toContain("Track 1");

  // Project JSON is the document itself.
  await page.getByLabel("Export menu").click();
  const jsonDownload = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "Project (JSON)" }).click();
  const json = await jsonDownload;
  const jsonPath = await json.path();
  if (!jsonPath) throw new Error("json download has no path");
  const document = JSON.parse(await readFile(jsonPath, "utf8")) as {
    title?: string;
    data?: { lanes?: unknown[]; tracks?: unknown[] };
  };
  expect(document.title).toBe(title);
  expect(document.data?.lanes).toHaveLength(1);
  expect(document.data?.tracks).toHaveLength(1);
});

test("MP3 export encodes the same render", async ({ page }) => {
  test.setTimeout(120_000);
  const tag = Math.random().toString(36).slice(2, 8);
  const title = `Mp3 ${tag}`;
  await createStudioProject(page, { title });

  await page.getByLabel("Export menu").click();
  await page.getByRole("menuitemradio", { name: "MP3" }).click();
  await expect(page.getByRole("menuitemradio", { name: "MP3" })).toHaveAttribute(
    "aria-checked",
    "true"
  );

  const download = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "Full Song" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe(`${title}.mp3`);

  const path = await file.path();
  if (!path) throw new Error("download has no path");
  const bytes = await readFile(path);
  // MPEG frame sync (0xFFEx) or an ID3 tag, and not a RIFF header.
  const head = bytes.subarray(0, 3).toString("latin1");
  expect(head === "ID3" || (bytes[0] === 0xff && (bytes[1] & 0xe0) === 0xe0)).toBe(true);
  expect(bytes.subarray(0, 4).toString("latin1")).not.toBe("RIFF");
  expect(bytes.length).toBeGreaterThan(2_000);
});

test("a project JSON round-trips back in as a new project", async ({ page }) => {
  test.setTimeout(120_000);
  const tag = Math.random().toString(36).slice(2, 8);
  const title = `Round trip ${tag}`;
  await createStudioProject(page, { title });

  const document = {
    title,
    bpm: 96,
    time_signature: "3/4",
    data: {
      lanes: [
        { id: "clip-a", title: "Verse", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav", volume: 1, pan: 0 },
      ],
      tracks: [
        {
          id: "track-a",
          name: "Track 1",
          color: "#8b5cf6",
          index: 0,
          volume: 80,
          pan: 0,
          muted: false,
          solo: false,
          hidden: false,
          groupId: null,
          chain: [],
          clipIds: ["clip-a"],
        },
      ],
    },
  };

  await page.getByLabel("Import Studio project JSON").setInputFiles({
    name: "round-trip.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(document), "utf8"),
  });

  await expect(page).toHaveURL(/\/studio\/editor\?project=/);
  await expect(page.getByRole("button", { name: `${title} (imported)` })).toBeVisible();
  await expect(page.locator(".se-clip")).toHaveCount(1);

  const saved = await page.evaluate(async () => {
    const id = new URL(window.location.href).searchParams.get("project");
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    return (await response.json()) as {
      bpm: number;
      time_signature: string;
      data: { tracks: Array<{ name: string }> };
    };
  });
  expect(saved.bpm).toBe(96);
  expect(saved.time_signature).toBe("3/4");
  expect(saved.data.tracks[0].name).toBe("Track 1");
});

test("Selected Time Range exports the loop range only", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Range ${tag}` });

  // Arming the loop with no range selects four bars (8 s at 120 BPM).
  await page.locator(".se-head").getByRole("button", { name: "Loop", exact: true }).click();

  await page.getByLabel("Export menu").click();
  const range = page.getByRole("menuitem", { name: "Selected Time Range" });
  await expect(range).toBeEnabled();
  const download = page.waitForEvent("download");
  await range.click();
  const file = await download;

  const path = await file.path();
  if (!path) throw new Error("download has no path");
  const bytes = await readFile(path);
  const expected = 44 + 8 * 44100 * 2 * 2;
  expect(Math.abs(bytes.length - expected)).toBeLessThan(3000);
});
