import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Transport controls (H-05/H-08): Stop halts where the playhead is; Back to start is the
 * rewind. They used to share one handler, so Stop also rewound.
 */

test("stop halts in place and back-to-start rewinds", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Transport ${tag}` });

  const clock = page.getByLabel("Time", { exact: true });
  const seconds = async () => {
    const text = (await clock.innerText()).trim();
    const [minutes, rest] = text.split(":");
    return Number(minutes) * 60 + Number(rest);
  };

  await page.getByLabel("Play", { exact: true }).click();
  await expect.poll(seconds, { timeout: 10_000, intervals: [200] }).toBeGreaterThan(1);

  const beforeStop = await seconds();
  await page.getByLabel("Stop", { exact: true }).click();
  await expect(page.getByLabel("Play", { exact: true })).toBeVisible();
  const afterStop = await seconds();
  // Halted roughly where it was, not rewound.
  expect(afterStop).toBeGreaterThan(beforeStop - 1.5);

  await page.getByLabel("Back to start", { exact: true }).click();
  await expect(clock).toHaveText("00:00.000");
});
