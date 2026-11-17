import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * QA C1: timeline clips used to paint nothing when the audio could not be fetched or
 * decoded, so a clip looked like a flat colour block with no hint why. The canvas now
 * always records its state, and same-origin audio must actually decode.
 */

test("timeline clips paint their waveform from real audio", async ({ page }) => {
  test.setTimeout(120_000);

  const projectId = await createStudioProject(page, {
    title: "Waveform paint",
    clips: [
      { id: "loop", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  await page.goto(`/studio/editor?project=${projectId}`);
  const canvas = page.locator(".se-clip-body canvas").first();
  await expect(canvas).toBeVisible({ timeout: 30_000 });

  // Decoding a same-origin 4 s file is the normal path: it must reach "ready", not sit
  // on the fallback baseline.
  await expect(canvas).toHaveAttribute("data-waveform", "ready", { timeout: 30_000 });
});

test("a clip whose audio cannot be decoded says so instead of staying blank", async ({ page }) => {
  test.setTimeout(120_000);

  // A cross-origin host without CORS fails exactly like this.
  await page.route("**/seed/waveform-broken.wav", (route) => route.fulfill({ status: 500 }));

  const projectId = await createStudioProject(page, {
    title: "Waveform fallback",
    clips: [
      {
        id: "loop",
        title: "Loop",
        start: 0,
        duration: 4,
        audioUrl: "/seed/waveform-broken.wav",
      },
    ],
  });

  await page.goto(`/studio/editor?project=${projectId}`);
  const canvas = page.locator(".se-clip-body canvas").first();
  await expect(canvas).toBeVisible({ timeout: 30_000 });
  await expect(canvas).toHaveAttribute("data-waveform", "fallback", { timeout: 30_000 });
});
