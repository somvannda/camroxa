import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Clip info panel (S27/§70): the right rail swaps from the library to an inspector for the
 * selected clip, showing its timing and source generation and drawing a real waveform.
 */

test("clip info shows timing, source and a decoded waveform", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Inspector ${tag}`,
    clips: [
      { id: "clip", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  // Give the clip a source generation the sandbox actually has.
  const source = await page.evaluate(async (id) => {
    const list = await fetch("/api/v3/web-music/generations?limit=1");
    const body = (await list.json()) as {
      items?: Array<{ id: string; title: string; style?: string }>;
    };
    const first = body.items?.[0];
    if (!first) return null;
    const read = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    const project = (await read.json()) as { data: { lanes: Array<Record<string, unknown>> } };
    project.data.lanes[0].songId = first.id;
    const write = await fetch(`/api/v3/web-music/studio/projects/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: project.data }),
    });
    return write.ok ? first : null;
  }, projectId);

  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });

  const clip = page.locator(".se-clip").first();
  const box = await clip.boundingBox();
  if (!box) throw new Error("clip has no box");
  await page.mouse.click(box.x + 30, box.y + 40, { button: "right" });
  await page.getByRole("menu", { name: "Clip options" }).getByRole("menuitem", { name: "Clip Info" }).click();

  const panel = page.getByRole("complementary", { name: "Clip info" });
  await expect(panel).toBeVisible();
  await expect(panel.getByText("Loop", { exact: false }).first()).toBeVisible();
  await expect(panel.getByText("0:04.00")).toBeVisible();
  await expect(panel.getByText(source ? (source as { title: string }).title : "Untitled").first()).toBeVisible();

  // The waveform is drawn from the decoded audio, so its pixels are not all transparent.
  await expect
    .poll(
      () =>
        panel.getByRole("img", { name: "Clip waveform" }).evaluate((canvas: HTMLCanvasElement) => {
          const context = canvas.getContext("2d");
          if (!context) return 0;
          const data = context.getImageData(0, 0, canvas.width, canvas.height).data;
          let painted = 0;
          for (let i = 3; i < data.length; i += 4) if (data[i] > 0) painted += 1;
          return painted;
        }),
      { timeout: 15_000, intervals: [250] }
    )
    .toBeGreaterThan(100);

  // Stems tab exposes the request; the panel closes back to the arrangement.
  await panel.getByRole("tab", { name: "Stems" }).click();
  await expect(panel.getByRole("button", { name: "Get stems" })).toBeEnabled();
  await panel.getByRole("button", { name: "Back to arrangement" }).click();
  await expect(panel).toHaveCount(0);
});

test("clip comments are anonymous notes that survive a reload", async ({ page }) => {
  test.setTimeout(120_000);
  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `Comments ${tag}`,
    clips: [
      { id: "clip", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });

  const openInspector = async () => {
    const clip = page.locator(".se-clip").first();
    const box = await clip.boundingBox();
    if (!box) throw new Error("clip has no box");
    await page.mouse.click(box.x + 30, box.y + 40, { button: "right" });
    await page
      .getByRole("menu", { name: "Clip options" })
      .getByRole("menuitem", { name: "Clip Info" })
      .click();
    return page.getByRole("complementary", { name: "Clip info" });
  };

  const panel = await openInspector();
  await expect(panel.getByText("Comments and notes")).toBeVisible();
  const input = panel.getByLabel("Write a comment");
  const note = `Tighten the low end ${tag}`;
  await input.fill(note);
  await input.press("Enter");
  await expect(panel.getByText(note)).toBeVisible({ timeout: 15_000 });

  // A reload must read the note back from the project, still without any author line.
  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  const again = await openInspector();
  await expect(again.getByText(note)).toBeVisible({ timeout: 15_000 });
  await expect(again.getByText("You", { exact: true })).toHaveCount(0);
});
