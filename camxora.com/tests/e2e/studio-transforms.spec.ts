import { expect, test, type Page } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Clip transforms (D-033): Extend continues a clip after itself, Cover and Remaster land
 * as new takes. The operations are paid and provider-backed, so both are exercised with
 * mocked operation endpoints; the placement and persistence are real.
 */

const CLIP = {
  id: "clip-a",
  title: "Verse",
  start: 0,
  duration: 4,
  audioUrl: "/seed/demo-loop.wav",
  songId: "song-1",
};

async function mockOperation(
  page: Page,
  kind: "extend" | "cover" | "remaster",
  resultUrl: string
): Promise<void> {
  const operationId = `op-${kind}`;
  await page.route(`**/api/v3/web-music/studio/generations/*/${kind}`, (route) =>
    route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ id: operationId, status: "queued" }),
    })
  );
  await page.route(`**/api/v3/web-music/studio/operations/${operationId}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: operationId,
        status: "done",
        result: { clips: [{ audio_url: resultUrl, duration_seconds: 4 }] },
      }),
    })
  );
}

async function savedLanes(page: Page, projectId: string) {
  return page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    const project = (await response.json()) as {
      data?: {
        lanes?: Array<{
          id: string;
          title?: string;
          start?: number;
          audioUrl?: string | null;
          takes?: Array<{ title?: string; audioUrl?: string | null; active?: boolean }>;
        }>;
      };
    };
    return project.data?.lanes ?? [];
  }, projectId);
}

test("Extend places the continuation after the clip", async ({ page }) => {
  test.setTimeout(120_000);
  await mockOperation(page, "extend", "/seed/demo-loop.wav");

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Extend ${tag}`,
    clips: [CLIP],
  });

  await page.locator(".se-clip").first().click({ button: "right" });
  const menu = page.getByRole("menu", { name: "Clip options" });
  await expect(menu.getByRole("menuitem", { name: "Extend" })).toBeEnabled();
  await menu.getByRole("menuitem", { name: "Extend" }).click();

  await expect(page.getByRole("status")).toContainText("Extension added");
  await expect
    .poll(async () => (await savedLanes(page, projectId)).length, {
      timeout: 15_000,
      intervals: [250],
    })
    .toBe(2);

  const lanes = await savedLanes(page, projectId);
  const extension = lanes.find((lane) => lane.id !== "clip-a");
  expect(extension).toMatchObject({
    title: "Verse (extended)",
    start: 4,
    audioUrl: "/seed/demo-loop.wav",
  });
});

test("Cover lands as a new take on the source clip", async ({ page }) => {
  test.setTimeout(120_000);
  await mockOperation(page, "cover", "/seed/demo-loop.wav");

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Cover ${tag}`,
    clips: [CLIP],
  });

  await page.locator(".se-clip").first().click({ button: "right" });
  await page.getByRole("menu", { name: "Clip options" })
    .getByRole("menuitem", { name: /Cover/ })
    .click();

  const dialog = page.getByRole("dialog", { name: "Cover this clip" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Cover style").fill("acoustic, slower");
  await dialog.getByRole("button", { name: "Generate cover" }).click();

  await expect(page.getByRole("status")).toContainText("Cover added as a new take");

  await expect
    .poll(
      async () => {
        const lanes = await savedLanes(page, projectId);
        return lanes.find((lane) => lane.id === "clip-a")?.takes?.length ?? 0;
      },
      { timeout: 15_000, intervals: [250] }
    )
    .toBe(1);

  const lanes = await savedLanes(page, projectId);
  const take = lanes.find((lane) => lane.id === "clip-a")?.takes?.[0];
  expect(take).toMatchObject({ title: "Cover", audioUrl: "/seed/demo-loop.wav", active: true });
});
