import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Loop playback (spec §68): arming Loop selects four bars, and the transport must repeat
 * that range rather than playing through the whole project.
 *
 * The fixture project's duration is ~240 s, so a wrap inside ten seconds can only come
 * from the loop range.
 */

test("armed loop repeats the selected range", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Loop ${tag}` });

  const clock = page.getByLabel("Time", { exact: true });
  const seconds = async () => {
    const text = (await clock.innerText()).trim();
    const [minutes, rest] = text.split(":");
    return Number(minutes) * 60 + Number(rest);
  };

  await page.locator(".se-head").getByRole("button", { name: "Loop", exact: true }).click();
  await page.getByLabel("Play", { exact: true }).click();

  // Four bars at 120 BPM = 8 s. Reach the second half of the loop…
  await expect.poll(seconds, { timeout: 15_000, intervals: [200] }).toBeGreaterThan(6);
  // …then wrap back to the loop start well before the 240 s project end.
  await expect.poll(seconds, { timeout: 10_000, intervals: [100] }).toBeLessThan(4);

  await page.getByLabel("Pause", { exact: true }).click();
});

test("clicking the timeline while playing moves the playback position", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Seek ${tag}` });

  const clock = page.getByLabel("Time", { exact: true });
  const seconds = async () => {
    const text = (await clock.innerText()).trim();
    const [minutes, rest] = text.split(":");
    return Number(minutes) * 60 + Number(rest);
  };

  await page.getByLabel("Play", { exact: true }).click();
  await expect.poll(seconds, { timeout: 10_000, intervals: [200] }).toBeGreaterThan(1.5);

  // One bar = 96 px = 2 s at 120 BPM.
  await page.locator(".se-lanes").click({ position: { x: 96, y: 40 } });
  const landed = await seconds();
  expect(landed).toBeGreaterThan(1.5);
  expect(landed).toBeLessThan(3);

  // Playback continues from the new position.
  await expect.poll(seconds, { timeout: 10_000, intervals: [200] }).toBeGreaterThan(landed + 0.5);
  await page.getByLabel("Pause", { exact: true }).click();
});

test("the loop range has a flag at each end and the left flag drags", async ({ page }) => {
  test.setTimeout(120_000);
  const projectId = await createStudioProject(page, { title: "Loop flags" });

  await page.locator(".se-head").getByRole("button", { name: "Loop", exact: true }).click();
  const start = page.getByRole("button", { name: "Loop start" });
  const end = page.getByRole("button", { name: "Loop end" });
  await expect(start).toBeVisible();
  await expect(end).toBeVisible();

  const box = await start.boundingBox();
  if (!box) throw new Error("loop start flag has no box");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 90, box.y + box.height / 2, { steps: 5 });
  await page.mouse.up();

  await expect
    .poll(
      async () =>
        page.evaluate(async (id) => {
          const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
          const body = (await response.json()) as { data?: { loopStart?: number } };
          return body.data?.loopStart ?? 0;
        }, projectId),
      { timeout: 15_000 }
    )
    .toBeGreaterThan(0);
});

test("the footer Loop seeds and persists the same four bars as the header", async ({ page }) => {
  test.setTimeout(120_000);
  const projectId = await createStudioProject(page, { title: "Footer loop" });

  const saved = () =>
    page.evaluate(async (id) => {
      const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
      const body = (await response.json()) as {
        data?: { loopStart?: number; loopEnd?: number };
      };
      return { start: body.data?.loopStart ?? 0, end: body.data?.loopEnd ?? null };
    }, projectId);

  const footerLoop = page.locator("footer").getByRole("button", { name: "Loop", exact: true });
  await footerLoop.click();

  // The footer used to flip the flag alone: no band and no persisted range (W5 D-43).
  await expect(page.locator(".se-loop-band")).toHaveCount(1);
  await expect.poll(async () => (await saved()).end, { timeout: 15_000 }).toBe(8);

  await footerLoop.click();
  await expect(page.locator(".se-loop-band")).toHaveCount(0);
});
