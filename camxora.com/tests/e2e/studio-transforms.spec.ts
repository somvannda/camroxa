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
  kind: "extend" | "cover" | "add-vocals" | "add-instrumental",
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

test("Replace section rewrites the selected range as a take", async ({ page }) => {
  test.setTimeout(120_000);
  await page.route("**/api/v3/web-music/studio/generations/*/replace-section", (route) =>
    route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ id: "op-replace", status: "queued" }),
    })
  );
  await page.route("**/api/v3/web-music/studio/operations/op-replace", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "op-replace",
        status: "done",
        result: { clips: [{ audio_url: "/seed/demo-loop.wav", duration_seconds: 4 }] },
      }),
    })
  );

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Replace ${tag}`,
    clips: [CLIP],
  });

  // Bars 2–3 (2 s → 4 s at the default zoom) inside the clip.
  const ruler = page.locator(".se-ruler-bars");
  const box = await ruler.boundingBox();
  if (!box) throw new Error("ruler has no box");
  const y = box.y + box.height - 8;
  await page.mouse.move(box.x + 100, y);
  await page.mouse.down();
  await page.mouse.move(box.x + 192, y, { steps: 8 });
  await page.mouse.up();
  await expect(page.getByTestId("se-range")).toBeVisible();

  await page.locator(".se-clip").first().click({ button: "right", position: { x: 20, y: 40 } });
  const item = page
    .getByRole("menu", { name: "Clip options" })
    .getByRole("menuitem", { name: /Replace/ });
  await expect(item).toBeEnabled();
  await item.click();

  const dialog = page.getByRole("dialog", { name: "Replace section" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("New lyrics").fill("A brand new verse about the river");
  await dialog.getByRole("button", { name: "Replace section" }).click();

  await expect(page.getByRole("status")).toContainText("Replaced section added as a new take");

  await expect
    .poll(
      async () => {
        const lanes = await savedLanes(page, projectId);
        return lanes.find((lane) => lane.id === "clip-a")?.takes?.[0]?.title ?? null;
      },
      { timeout: 15_000, intervals: [250] }
    )
    .toBe("Replace section");
});

test("a refused charge shows the credits card instead of a toast", async ({ page }) => {
  test.setTimeout(120_000);
  await page.route("**/api/v3/web-music/studio/generations/*/extend", (route) =>
    route.fulfill({
      status: 402,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "INSUFFICIENT_CREDITS", message: "Insufficient credits for this operation." },
      }),
    })
  );

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Refused ${tag}`, clips: [CLIP] });

  await page.locator(".se-clip").first().click({ button: "right" });
  await page
    .getByRole("menu", { name: "Clip options" })
    .getByRole("menuitem", { name: "Extend" })
    .click();

  const notice = page.getByRole("alert").filter({ hasText: "Not enough credits" });
  await expect(notice).toBeVisible();
  await expect(notice.getByRole("link", { name: "View plans" })).toBeVisible();
  // Nothing was placed, and the paid action did not leave a spinner behind.
  await expect(page.locator(".se-clip")).toHaveCount(1);
});

test("Mashup combines the two selected clips on a new track", async ({ page }) => {  test.setTimeout(120_000);
  await page.route("**/api/v3/web-music/studio/mashup", (route) =>
    route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ id: "op-mash", status: "queued" }),
    })
  );
  await page.route("**/api/v3/web-music/studio/operations/op-mash", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "op-mash",
        status: "done",
        result: { clips: [{ audio_url: "/seed/demo-loop.wav", duration_seconds: 4 }] },
      }),
    })
  );

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Mashup ${tag}`,
    clips: [
      { ...CLIP, id: "clip-a", title: "First", start: 0, duration: 2 },
      { ...CLIP, id: "clip-b", title: "Second", start: 2, duration: 2 },
    ],
  });

  // Marquee both clips (the lane starts empty past the second clip).
  const lane = page.locator(".se-lanes");
  const box = await lane.boundingBox();
  if (!box) throw new Error("lanes have no box");
  await page.mouse.move(box.x + 300, box.y + 40);
  await page.mouse.down();
  await page.mouse.move(box.x + 8, box.y + 40, { steps: 10 });
  await page.mouse.up();
  await expect(page.locator(".se-clip.selected")).toHaveCount(2);

  await page.locator(".se-clip").first().click({ button: "right" });
  const menu = page.getByRole("menu", { name: "Clip options" });
  const mashup = menu.getByRole("menuitem", { name: /Mashup/ });
  await expect(mashup).toBeEnabled();
  await mashup.click();

  const dialog = page.getByRole("dialog", { name: "Mashup two clips" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Mashup instructions").fill("keep the drums, blend the vocals");
  await dialog.getByRole("button", { name: "Create mashup" }).click();

  await expect(page.getByRole("status")).toContainText("Mashup added as a new track");

  const document = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    return (await response.json()) as {
      data: {
        tracks: Array<{ name: string; clipIds: string[] }>;
        lanes: Array<{ id: string; title?: string; start?: number; audioUrl?: string | null }>;
      };
    };
  }, projectId);

  await expect
    .poll(async () => document.data.tracks.length, { timeout: 15_000, intervals: [250] })
    .toBeGreaterThanOrEqual(2);
  const mashupTrack = document.data.tracks.find((track) => track.name === "Mashup");
  expect(mashupTrack).toBeTruthy();
});

test("Add vocals shows the credit price and lands as a take", async ({ page }) => {
  test.setTimeout(120_000);
  await mockOperation(page, "add-vocals", "/seed/demo-loop.wav");
  await page.route("**/api/v3/web-music/studio/pricing", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ edit: 7, stems_2: 12, stems_12: 60 }),
    })
  );

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Vocals ${tag}`,
    clips: [CLIP],
  });

  await page.locator(".se-clip").first().click({ button: "right" });
  await page
    .getByRole("menu", { name: "Clip options" })
    .getByRole("menuitem", { name: /Vocals/ })
    .click();

  const dialog = page.getByRole("dialog", { name: "Add vocals to this clip" });
  await expect(dialog).toBeVisible();
  // The price comes from the pricing endpoint, never a hard-coded constant.
  await expect(dialog).toContainText("This spends 7 credits");
  await dialog.getByLabel("Vocal instructions").fill("warm female lead");
  await dialog.getByRole("button", { name: "Add vocals" }).click();

  await expect(page.getByRole("status")).toContainText("Add vocals added as a new take");

  await expect
    .poll(
      async () => {
        const lanes = await savedLanes(page, projectId);
        return lanes.find((lane) => lane.id === "clip-a")?.takes?.[0]?.title ?? null;
      },
      { timeout: 15_000, intervals: [250] }
    )
    .toBe("Add vocals");
});
