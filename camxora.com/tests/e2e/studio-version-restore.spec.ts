import { expect, test } from "@playwright/test";

import { createStudioProject, dragFirstClipOneBar } from "./studio-fixture";

/**
 * Version restore (W3/G28): a labelled snapshot of the original arrangement must put
 * the clip back where it was, and the result must be on the server after the reload the
 * panel performs.
 */

test("restoring a version brings the arrangement back", async ({ page }) => {
  test.setTimeout(120_000);

  const projectId = await createStudioProject(page, { title: "Restore probe" });

  // Capture the original before any edit.
  const created = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}/versions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: "Original" }),
    });
    return response.status;
  }, projectId);
  expect(created).toBe(201);

  const clip = page.locator(".se-clip").first();
  const left = () => clip.evaluate((element) => (element as HTMLElement).style.left);
  await dragFirstClipOneBar(page);
  await expect.poll(left, { timeout: 10_000 }).not.toBe("0px");
  await expect(page.getByText("Saved", { exact: true })).toBeVisible({ timeout: 15_000 });

  await page.locator(".se-project .se-chip").click();
  await page.getByRole("menuitem", { name: "Version History" }).click();
  const dialog = page.getByRole("dialog", { name: "Version history" });
  await expect(dialog.getByText("Original")).toBeVisible();

  await dialog.getByRole("button", { name: "Restore Original" }).click();

  // Restore reloads the editor with the restored document.
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await expect
    .poll(() => page.locator(".se-clip").first().evaluate((el) => (el as HTMLElement).style.left), {
      timeout: 15_000,
    })
    .toBe("0px");
  await expect(page.getByText("Saved", { exact: true })).toBeVisible({ timeout: 15_000 });

  const start = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    const project = (await response.json()) as { data?: { lanes?: Array<{ start?: number }> } };
    return project.data?.lanes?.[0]?.start ?? null;
  }, projectId);
  expect(start).toBe(0);
});
