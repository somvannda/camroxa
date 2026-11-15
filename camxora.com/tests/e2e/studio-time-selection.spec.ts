import { expect, test, type Page } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Time selection (N-01).
 *
 * The reference has a second selection type beside the clip selection: a range dragged
 * on the bar ruler with its own verbs (delete time, duplicate time, loop, range export).
 * At the default zoom one bar is 96 px = 2 s at 120 BPM, so bar offsets map directly to
 * pixels on the ruler.
 */

const BAR = 96;

/** Drag across the bar ruler from one bar line to another. */
async function selectRange(page: Page, fromBar: number, toBar: number): Promise<void> {
  const ruler = page.locator(".se-ruler-bars");
  const box = await ruler.boundingBox();
  if (!box) throw new Error("ruler has no box");
  const y = box.y + box.height - 8;
  const from = box.x + fromBar * BAR + 4;
  const to = box.x + toBar * BAR;
  await page.mouse.move(from, y);
  await page.mouse.down();
  await page.mouse.move(to, y, { steps: 10 });
  await page.mouse.up();
}

/** The persisted lanes, straight from the API (not the DOM). */
async function savedLanes(page: Page, projectId: string) {
  return page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    if (!response.ok) return [];
    const project = (await response.json()) as {
      data?: { lanes?: Array<{ id: string; start?: number; duration?: number }> };
    };
    return project.data?.lanes ?? [];
  }, projectId);
}

test("dragging the ruler selects a time range and Escape clears it", async ({ page }) => {
  test.setTimeout(120_000);
  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Range ${tag}` });

  await selectRange(page, 1, 3);

  const range = page.getByTestId("se-range");
  await expect(range).toBeVisible();
  const width = await range.evaluate((element) => (element as HTMLElement).style.width);
  expect(width).toBe(`${2 * BAR}px`);

  await page.keyboard.press("Escape");
  await expect(range).toHaveCount(0);
});

test("delete time ripples the later clips left and persists", async ({ page }) => {
  test.setTimeout(120_000);
  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Delete time ${tag}`,
    clips: [
      { id: "keep", title: "Keep", start: 0, duration: 2 },
      { id: "late", title: "Late", start: 4, duration: 2 },
    ],
  });

  // Select bars 2–3 (2 s → 4 s): the empty gap ahead of the late clip.
  await selectRange(page, 1, 2);
  await expect(page.getByTestId("se-range")).toBeVisible();

  await page.keyboard.press("Control+Shift+Backspace");

  await expect
    .poll(async () => (await savedLanes(page, projectId)).find((lane) => lane.id === "late")?.start, {
      timeout: 15_000,
      intervals: [250],
    })
    .toBe(2);
  const lanes = await savedLanes(page, projectId);
  expect(lanes.find((lane) => lane.id === "keep")?.start).toBe(0);
});

test("duplicate time copies the range after itself", async ({ page }) => {
  test.setTimeout(120_000);
  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Duplicate time ${tag}`,
    clips: [{ id: "source", title: "Source", start: 0, duration: 2 }],
  });

  await selectRange(page, 0, 1);
  await expect(page.getByTestId("se-range")).toBeVisible();

  await page.keyboard.press("Control+Shift+d");

  await expect
    .poll(async () => (await savedLanes(page, projectId)).length, {
      timeout: 15_000,
      intervals: [250],
    })
    .toBe(2);
  const lanes = await savedLanes(page, projectId);
  const starts = lanes.map((lane) => lane.start).sort((a, b) => (a ?? 0) - (b ?? 0));
  expect(starts).toEqual([0, 2]);
});

test("the range menu loops the selection and the export scope unlocks", async ({ page }) => {
  test.setTimeout(120_000);
  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Range menu ${tag}` });

  await selectRange(page, 1, 3);
  const ruler = page.locator(".se-ruler-bars");
  const box = await ruler.boundingBox();
  if (!box) throw new Error("ruler has no box");
  await page.mouse.click(box.x + 2 * BAR, box.y + box.height - 8, { button: "right" });

  const menu = page.getByRole("menu", { name: "Time selection options" });
  await expect(menu).toBeVisible();
  await menu.getByRole("menuitem", { name: /Loop selection/ }).click();

  await expect(page.locator(".se-head").getByRole("button", { name: "Loop", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true"
  );

  await page.getByRole("button", { name: "Export menu" }).click();
  await expect(
    page.getByRole("menuitem", { name: /Selected Time Range/ })
  ).toBeEnabled();
});

test("Shift 1 and Shift 2 double and halve the arrangement grid", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, {
    title: `Grid density ${Math.random().toString(36).slice(2, 8)}`,
  });

  const ruler = page.locator(".se-ruler-bars");
  const box = await ruler.boundingBox();
  if (!box) throw new Error("ruler has no box");
  const x = box.x + 200;
  const y = box.y + box.height / 2;

  // Shift-clicking the ruler selects exactly one grid step.
  const selectStep = async () => {
    await page.keyboard.press("Escape");
    await page.keyboard.down("Shift");
    await page.mouse.click(x, y);
    await page.keyboard.up("Shift");
  };
  const stepWidth = async () => {
    const range = page.getByTestId("se-range");
    await expect(range).toBeVisible();
    return Number.parseFloat(
      await range.evaluate((element) => (element as HTMLElement).style.width)
    );
  };

  await selectStep();
  const beats = await stepWidth();

  // SHIFT 1 halves the step, so the same click selects half the width.
  await page.keyboard.press("Shift+1");
  await selectStep();
  const eighths = await stepWidth();
  expect(eighths).toBeCloseTo(beats / 2, 0);

  // SHIFT 2 puts it back.
  await page.keyboard.press("Shift+2");
  await selectStep();
  expect(await stepWidth()).toBeCloseTo(beats, 0);
});

test("split arrangement cuts every clip at the playhead", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: `Split arrangement ${Math.random().toString(36).slice(2, 8)}` });
  await expect(page.locator(".se-clip")).toHaveCount(1);

  // A time selection is what opens the arrangement menu that owns this verb. Build it
  // first: dragging the ruler parks the playhead at the drag anchor.
  await selectRange(page, 0, 1);

  // Roll the transport so the playhead sits inside the fixture clip (0-4s).
  await page.getByLabel("Play", { exact: true }).click();
  await page.waitForTimeout(700);
  await page.getByLabel("Stop", { exact: true }).click();

  const ruler = page.locator(".se-ruler-bars");
  const box = await ruler.boundingBox();
  if (!box) throw new Error("ruler has no box");
  await page.mouse.click(box.x + 40, box.y + box.height / 2, { button: "right" });

  const menu = page.getByRole("menu", { name: "Time selection options" });
  await expect(menu).toBeVisible();
  await menu.getByRole("menuitem", { name: "Split Arrangement" }).click();

  await expect(page.locator(".se-clip")).toHaveCount(2);
  await expect(page.getByText("Arrangement split at the playhead.", { exact: true })).toBeVisible();
});
