import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Library panel (G12/G13): the drawer offers Songs, Projects and Uploads, and the
 * shared search narrows the list it is on.
 *
 * Filtering is asserted on the Projects section, which this test owns: it creates a
 * second project with a unique title, so the result does not depend on what songs or
 * uploads the sandbox account happens to hold.
 */

test("library tabs switch sections and the search filters them", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const currentTitle = `Library ${tag}`;
  const otherTitle = `Filter target ${tag}`;

  const projectId = await createStudioProject(page, { title: currentTitle });
  // A second project exists but is not the open one, so it is listed under Projects.
  await createStudioProject(page, { title: otherTitle });
  await page.goto(`/studio/editor?project=${projectId}`);
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Library", exact: true }).click();
  const library = page.getByRole("complementary", { name: "Library" });
  await expect(library).toBeVisible();

  const tabs = library.getByRole("tab");
  await expect(tabs).toHaveCount(4);
  await expect(tabs.nth(0)).toHaveText("Songs");
  await expect(tabs.nth(1)).toHaveText("Workspaces");
  await expect(tabs.nth(2)).toHaveText("Projects");
  await expect(tabs.nth(3)).toHaveText("Uploads");

  // Every section resolves to either rows or its own empty explanation.
  for (const label of ["Songs", "Workspaces", "Projects", "Uploads"]) {
    await library.getByRole("tab", { name: label }).click();
    await expect(library.getByRole("tab", { name: label })).toHaveAttribute("aria-selected", "true");
    await expect
      .poll(
        async () =>
          (await library.locator(".se-lib-row").count()) +
          (await library.locator(".se-lib-empty").count())
      )
      .toBeGreaterThan(0);
  }

  // Workspaces are real data: choose one, land on Songs filtered to it, then clear.
  await library.getByRole("tab", { name: "Workspaces" }).click();
  await expect(library.getByLabel("Show songs from every workspace")).toBeVisible();
  await library.getByLabel(/^Show songs in /).first().click();
  await expect(library.getByRole("tab", { name: "Songs" })).toHaveAttribute("aria-selected", "true");
  await expect(library.getByLabel("Clear workspace filter")).toBeVisible();
  await library.getByLabel("Clear workspace filter").click();
  await expect(library.getByLabel("Clear workspace filter")).toHaveCount(0);

  // The one project that is not open must be findable, and nothing else may match.
  await library.getByRole("tab", { name: "Projects" }).click();
  await expect(library.getByText(otherTitle)).toBeVisible({ timeout: 10_000 });
  await expect(library.getByText(currentTitle)).toHaveCount(0);

  await library.getByLabel("Search library").fill(otherTitle);
  await expect(library.locator(".se-lib-row")).toHaveCount(1);
  await expect(library.getByText(otherTitle)).toBeVisible();

  await library.getByLabel("Search library").fill("zzz-no-such-project");
  await expect(library.locator(".se-lib-row")).toHaveCount(0);

  await library.getByLabel("Search library").fill("");
  await expect(library.getByText(otherTitle)).toBeVisible();

  // Closing the drawer removes it.
  await library.getByLabel("Close library").click();
  await expect(library).toHaveCount(0);
});
