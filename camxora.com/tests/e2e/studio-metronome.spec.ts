import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Metronome click track (reference H-09).
 *
 * Sound cannot be heard in CI, so this counts scheduled oscillators: the click graph is
 * the only place the editor creates a bare oscillator. It also asserts the beat readout
 * moves, which is the visual half of the same clock.
 */

test("the metronome schedules clicks on the beat", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Click ${tag}` });

  // Count oscillators from before the app boots, so the audio engine is not yet warm.
  await page.addInitScript(() => {
    (window as unknown as { __clicks: number }).__clicks = 0;
    const proto = AudioContext.prototype as AudioContext & { createOscillator: () => OscillatorNode };
    const original = proto.createOscillator;
    proto.createOscillator = function patched(this: AudioContext) {
      (window as unknown as { __clicks: number }).__clicks += 1;
      return original.call(this);
    };
  });
  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });

  const metronome = page.getByRole("button", { name: /^Metronome/ });
  await metronome.click();
  await expect(metronome).toHaveAttribute("aria-pressed", "true");

  await page.keyboard.press("Space");
  await expect(page.getByLabel("Pause", { exact: true })).toBeVisible();

  // 120 BPM = a click every 500 ms; two seconds proves more than one scheduled.
  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __clicks: number }).__clicks), {
      timeout: 6000,
    })
    .toBeGreaterThan(2);

  const beat = await metronome.getAttribute("data-beat");
  expect(Number(beat)).toBeGreaterThanOrEqual(1);
  await expect
    .poll(() => metronome.getAttribute("data-beat"), { timeout: 4000 })
    .not.toBe(beat);

  // Stopping the transport stops the click source count from climbing.
  await page.keyboard.press("Space");
  const afterStop = await page.evaluate(() => (window as unknown as { __clicks: number }).__clicks);
  await page.waitForTimeout(700);
  const later = await page.evaluate(() => (window as unknown as { __clicks: number }).__clicks);
  expect(later - afterStop).toBeLessThanOrEqual(1); // at most the in-flight lookahead click
});
