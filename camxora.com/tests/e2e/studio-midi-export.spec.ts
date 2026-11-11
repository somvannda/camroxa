import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * MIDI download (N-05).
 *
 * The captured strings are "Download MIDI" and "Download the selected MIDI clips as a
 * MIDI file", so one selection becomes one Standard MIDI File. The encoder is unit
 * tested; this reads the downloaded bytes.
 */

test("the clip menu downloads the selected MIDI clip as a .mid file", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `Midi ${tag}`,
    clips: [
      {
        id: "midi",
        title: "Keys",
        start: 0,
        duration: 4,
        midi: {
          notes: [
            { id: "n1", pitch: 60, start: 0.5, length: 0.5, velocity: 100 },
            { id: "n2", pitch: 64, start: 1, length: 0.5, velocity: 90 },
          ],
        },
      },
    ],
  });

  await page.locator(".se-clip").first().click({ button: "right" });
  const menu = page.getByRole("menu", { name: "Clip options" });
  await expect(menu).toBeVisible();
  const row = menu.getByRole("menuitem", { name: /Download MIDI/ });
  await expect(row).toBeEnabled();

  const download = page.waitForEvent("download");
  await row.click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/- MIDI\.mid$/);

  const path = await file.path();
  if (!path) throw new Error("midi download has no path");
  const bytes = await readFile(path);

  expect(bytes.subarray(0, 4).toString("latin1")).toBe("MThd");
  expect(bytes.readUInt32BE(4)).toBe(6);
  expect(bytes[8]).toBe(0); // format 0
  expect(bytes.readUInt16BE(10)).toBe(1); // one track
  expect(bytes.readUInt16BE(12)).toBe(480); // PPQ
  expect(bytes.subarray(14, 18).toString("latin1")).toBe("MTrk");

  // Tempo meta (500,000 µs at 120 BPM) and both note-ons are in the track.
  const track = bytes.subarray(22);
  expect(track.includes(Buffer.from([0xff, 0x51, 0x03]))).toBe(true);
  expect(track.includes(Buffer.from([0x90, 60, 100]))).toBe(true);
  expect(track.includes(Buffer.from([0x90, 64, 90]))).toBe(true);
  expect(track.includes(Buffer.from([0xff, 0x2f, 0x00]))).toBe(true);
});

test("an audio clip has no MIDI to download", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `No midi ${tag}`,
    clips: [
      { id: "audio", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  await page.locator(".se-clip").first().click({ button: "right" });
  await expect(
    page.getByRole("menu", { name: "Clip options" }).getByRole("menuitem", { name: /Download MIDI/ })
  ).toBeDisabled();
});
