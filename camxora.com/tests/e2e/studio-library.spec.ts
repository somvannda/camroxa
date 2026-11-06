import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Library panel (G12): the drawer offers Songs, Workspaces, Projects and Uploads, and the
 * shared search narrows the list it is on.
 *
 * The sandbox account accumulates projects from every e2e run, so the spec picks the
 * newest *other* project from the same API window the drawer uses (50) instead of
 * assuming a project it created is still inside the first page.
 */

test("library tabs switch sections and the search filters them", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const currentTitle = `Library ${tag}`;
  await createStudioProject(page, { title: currentTitle });

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

  // Projects: the open project is excluded, and the shared search narrows to the text
  // of a loaded row — read from the drawer rather than assumed, since the sandbox
  // accumulates projects from every run.
  await library.getByRole("tab", { name: "Projects" }).click();
  await expect(library.getByText(currentTitle, { exact: true })).toHaveCount(0);
  const projectsEmpty = await library.locator(".se-lib-empty").count();
  if (projectsEmpty === 0) {
    const firstTitle = (await library.locator(".se-lib-title").first().innerText()).trim();
    expect(firstTitle.length).toBeGreaterThan(0);

    await library.getByLabel("Search library").fill(firstTitle);
    await expect(library.locator(".se-lib-row").first()).toBeVisible();
    const visible = await library.locator(".se-lib-title").allInnerTexts();
    expect(visible.length).toBeGreaterThan(0);
    expect(
      visible.every((text) => text.toLowerCase().includes(firstTitle.toLowerCase()))
    ).toBe(true);

    await library.getByLabel("Search library").fill("zzz-no-such-project");
    await expect(library.locator(".se-lib-row")).toHaveCount(0);

    await library.getByLabel("Search library").fill("");
    await expect(library.getByText(firstTitle, { exact: false }).first()).toBeVisible();
  }

  // Closing the drawer removes it.
  await library.getByLabel("Close library").click();
  await expect(library).toHaveCount(0);
});
