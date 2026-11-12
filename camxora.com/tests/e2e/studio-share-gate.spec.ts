import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Share naming gate (S12/§24.1): an unnamed project must be offered a name before the
 * share dialog, and Skip must still share without renaming.
 */

test("sharing an unnamed project hits the naming gate", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, { title: "Untitled project" });

  const openMenu = async () => {
    await page.locator(".se-project .se-chip").click();
    await page.getByRole("menuitem", { name: "Share Project" }).click();
  };

  const titleFromApi = () =>
    page.evaluate(async (id) => {
      const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
      const project = (await response.json()) as { title?: string };
      return project.title;
    }, projectId);

  // Skip: shares while leaving the name alone.
  await openMenu();
  const gate = page.getByRole("dialog", { name: "Name project before sharing" });
  await expect(gate).toBeVisible();
  await expect(gate.getByLabel("Project title")).toHaveValue("Untitled project");
  await gate.getByRole("button", { name: "Skip" }).click();

  const share = page.getByRole("dialog", { name: "Share project" });
  await expect(share).toBeVisible();
  await expect(share.getByRole("heading")).toContainText("Untitled project");
  await share.getByRole("button", { name: "Done" }).click();
  expect(await titleFromApi()).toBe("Untitled project");

  // Save: renames first, then shares under the new name.
  await openMenu();
  const gateAgain = page.getByRole("dialog", { name: "Name project before sharing" });
  await expect(gateAgain).toBeVisible();
  const named = `Named ${tag}`;
  await gateAgain.getByLabel("Project title").fill(named);
  await gateAgain.getByRole("button", { name: "Save" }).click();

  const shareAgain = page.getByRole("dialog", { name: "Share project" });
  await expect(shareAgain).toBeVisible();
  await expect(shareAgain.getByRole("heading")).toContainText(named);
  await shareAgain.getByRole("button", { name: "Done" }).click();

  await expect.poll(titleFromApi, { timeout: 15_000 }).toBe(named);
  await expect(page.locator(".se-project .se-chip")).toHaveText(named);
});
