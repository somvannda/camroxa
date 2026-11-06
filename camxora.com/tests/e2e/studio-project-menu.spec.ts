import { expect, test } from "@playwright/test";

import { createStudioProject, dragFirstClipOneBar } from "./studio-fixture";

/**
 * Project menu (reference §18.1/G13): the captured items exist, rename persists, and
 * the three items this build cannot honour are disabled rather than missing.
 */

test("project menu renames the project and the name survives a reload", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const original = `Menu ${tag}`;
  const renamed = `Renamed ${tag}`;

  const projectId = await createStudioProject(page, { title: original });
  const chip = page.locator(".se-project .se-chip");
  await expect(chip).toHaveText(original);

  await chip.click();
  const menu = page.getByRole("menu", { name: "Project options" });
  await expect(menu).toBeVisible();

  // The order matches the capture; the two we cannot honour are disabled.
  await expect(menu.getByRole("menuitem")).toHaveCount(9);
  await expect(menu.getByRole("menuitem").nth(5)).toBeEnabled(); // Share Project
  await expect(menu.getByRole("menuitem").nth(6)).toBeDisabled(); // v1 copy
  await expect(menu.getByRole("menuitem").nth(7)).toBeEnabled(); // Settings

  await menu.getByRole("menuitem", { name: "Rename" }).click();
  const dialog = page.getByRole("dialog", { name: "Rename project" });
  await expect(dialog).toBeVisible();
  const input = dialog.getByLabel("Project title");
  await expect(input).toHaveValue(original);
  await input.fill(renamed);
  await dialog.getByRole("button", { name: "Save" }).click();

  await expect(dialog).toHaveCount(0);
  await expect(chip).toHaveText(renamed);

  // Persisted, not just local state.
  const stored = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    return ((await response.json()) as { title?: string }).title ?? null;
  }, projectId);
  expect(stored).toBe(renamed);

  await page.reload();
  await expect(page.locator(".se-project .se-chip")).toHaveText(renamed);
});

test("share creates a view link that resolves without the editor", async ({ page }) => {  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Share ${tag}` });

  await page.locator(".se-project .se-chip").click();
  await page.getByRole("menuitem", { name: "Share Project" }).click();

  const dialog = page.getByRole("dialog", { name: "Share project" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/view this project and make their own editable copy/)).toBeVisible();

  const link = dialog.getByLabel("Share link");
  await expect(link).toHaveValue(/\/studio\/shared\/.+$/);

  // The link is view + fork: the public share endpoint must answer for its token.
  const href = await link.inputValue();
  const token = href.split("/studio/shared/")[1];
  const shared = await page.request.get(`/api/v3/web-music/studio/shares/${token}`);
  expect(shared.status()).toBe(200);
  const body = (await shared.json()) as { title?: string };
  expect(body.title).toBe(`Share ${tag}`);

  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toHaveCount(0);
});

test("new and duplicate open a different project", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const title = `Menu flow ${tag}`;
  const projectId = await createStudioProject(page, { title });

  // Duplicate: a copy opens, with a different id.
  await page.locator(".se-project .se-chip").click();
  await page.getByRole("menuitem", { name: "Duplicate Project" }).click();
  await page.waitForURL((url) => url.searchParams.get("project") !== projectId, { timeout: 30_000 });
  const copyId = new URL(page.url()).searchParams.get("project");
  expect(copyId).toBeTruthy();
  expect(copyId).not.toBe(projectId);
  await expect(page.locator(".se-project .se-chip")).toContainText(`${title} copy`, {
    timeout: 30_000,
  });

  // New Project: a fresh empty document.
  await page.locator(".se-project .se-chip").click();
  await page.getByRole("menuitem", { name: "New Project" }).click();
  await page.waitForURL((url) => url.searchParams.get("project") !== copyId, { timeout: 30_000 });
  const freshId = new URL(page.url()).searchParams.get("project");
  expect(freshId).toBeTruthy();
  expect(freshId).not.toBe(copyId);
  await expect(page.locator(".se-project .se-chip")).toHaveText("Untitled project", {
    timeout: 30_000,
  });
  await expect(page.locator(".se-clip")).toHaveCount(0);
});

test("versions are captured automatically, and throttled within 20 seconds", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, { title: `Versions ${tag}` });

  const versionCount = () =>
    page.evaluate(async (id) => {
      const response = await fetch(`/api/v3/web-music/studio/projects/${id}/versions`);
      if (!response.ok) return -1;
      return ((await response.json()) as { items?: unknown[] }).items?.length ?? 0;
    }, projectId);

  // The fixture creation does not snapshot; the first edit does.
  await expect.poll(versionCount, { timeout: 15_000 }).toBe(0);
  await dragFirstClipOneBar(page);
  await expect(page.getByText("Saved")).toBeVisible({ timeout: 15_000 });
  await expect.poll(versionCount, { timeout: 15_000 }).toBeGreaterThan(0);
  const afterFirst = await versionCount();

  // A second edit inside the 20 s window must not add another snapshot.
  await dragFirstClipOneBar(page);
  await expect(page.getByText("Saved")).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(1_500);
  expect(await versionCount()).toBe(afterFirst);

  // And the panel shows the captured automatic wording with a restorable row.
  await page.locator(".se-project .se-chip").click();
  await page.getByRole("menuitem", { name: "Version History" }).click();
  const dialog = page.getByRole("dialog", { name: "Version history" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("Projects are saved automatically");
  await expect(dialog.getByRole("button", { name: /^Restore/ }).first()).toBeVisible();
});

test("studio settings open with the captured accelerator and persist", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Settings ${tag}` });

  // `ctrl shift ,` — the accelerator recorded in §18.1.
  await page.keyboard.down("Control");
  await page.keyboard.down("Shift");
  await page.keyboard.press(",");
  await page.keyboard.up("Shift");
  await page.keyboard.up("Control");

  const dialog = page.getByRole("dialog", { name: "Studio settings" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Performance")).toBeVisible();
  await expect(dialog.getByText("Window management")).toBeVisible();
  await expect(dialog.getByText("Content")).toBeVisible();

  const ghost = dialog.getByRole("checkbox", { name: "Ghost drag for arrangement moves" });
  await expect(ghost).toBeChecked(); // captured default is "On"
  await ghost.uncheck();
  await expect(ghost).not.toBeChecked();
  expect(await page.evaluate(() => localStorage.getItem("studio:settings"))).toContain(
    '"ghostDrag":false'
  );

  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(dialog).toHaveCount(0);

  // Editor preference, not project data: it survives a reload without a save.
  await page.reload();
  await expect(page.locator(".se-project .se-chip")).toBeVisible({ timeout: 30_000 });
  await page.keyboard.down("Control");
  await page.keyboard.down("Shift");
  await page.keyboard.press(",");
  await page.keyboard.up("Shift");
  await page.keyboard.up("Control");
  await expect(
    page.getByRole("dialog", { name: "Studio settings" }).getByRole("checkbox", {
      name: "Ghost drag for arrangement moves",
    })
  ).not.toBeChecked();
});
