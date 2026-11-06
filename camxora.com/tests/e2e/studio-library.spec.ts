import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Library panel (G12, spec §19.1/§19.2): the drawer is two-level, like the reference.
 *
 * Level 1 is the corpus chooser — All Songs / Liked / Stems / Uploads tiles, then the
 * Workspaces and Studio Projects sections. Level 2 is the list itself, opened by a tile
 * or a workspace row, with a Back control. The shared search narrows whichever level is
 * showing.
 *
 * The sandbox account accumulates projects from every e2e run, so the spec picks the
 * newest *other* project from the same API window the drawer uses (50) instead of
 * assuming a project it created is still inside the first page.
 */

test("library is a two-level drawer with tiles, sections and search", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const currentTitle = `Library ${tag}`;
  await createStudioProject(page, { title: currentTitle });

  await page.getByRole("button", { name: "Library", exact: true }).click();
  const library = page.getByRole("complementary", { name: "Library" });
  await expect(library).toBeVisible();

  // Level 1: the four filter tiles, in the captured order. Stems stays visible but
  // disabled until a stems job has actually produced a set (B-005).
  const tiles = library.getByRole("group", { name: "Library filters" }).getByRole("button");
  await expect(tiles).toHaveCount(4);
  await expect(tiles.nth(0)).toHaveText("All Songs");
  await expect(tiles.nth(1)).toHaveText("Liked");
  await expect(tiles.nth(2)).toHaveText("Stems");
  await expect(tiles.nth(3)).toHaveText("Uploads");
  await expect(tiles.nth(2)).toBeDisabled();

  // Both level-1 sections resolve to rows or their own empty explanation.
  for (const label of ["Workspaces", "Studio projects"]) {
    const section = library.getByRole("region", { name: label });
    await expect
      .poll(
        async () =>
          (await section.locator(".se-lib-row").count()) +
          (await section.locator(".se-lib-empty").count())
      )
      .toBeGreaterThan(0);
  }

  // All Songs opens level 2 on a date-grouped list, with a way back.
  await tiles.nth(0).click();
  await expect(library.getByLabel("Back to library")).toBeVisible();
  await expect(library.getByText("All Songs", { exact: true })).toBeVisible();
  await expect
    .poll(
      async () =>
        (await library.locator(".se-lib-row").count()) +
        (await library.locator(".se-lib-empty").count())
    )
    .toBeGreaterThan(0);
  await library.getByLabel("Back to library").click();
  await expect(tiles.nth(0)).toBeVisible();

  // Workspaces are real data: opening one lands on its songs, filtered; Clear drops the
  // filter without leaving the list.
  const workspaces = library.getByRole("region", { name: "Workspaces" });
  const workspaceButtons = workspaces.getByLabel(/^Open workspace /);
  if ((await workspaceButtons.count()) > 0) {
    await workspaceButtons.first().click();
    await expect(library.getByLabel("Clear workspace filter")).toBeVisible();
    await library.getByLabel("Clear workspace filter").click();
    await expect(library.getByLabel("Clear workspace filter")).toHaveCount(0);
    await expect(library.getByLabel("Back to library")).toBeVisible();

    // Leaving via Back keeps the filter; choosing a tile clears it, because a tile
    // selects the whole corpus.
    await library.getByLabel("Back to library").click();
    await workspaces.getByLabel(/^Open workspace /).first().click();
    await expect(library.getByLabel("Clear workspace filter")).toBeVisible();
    await library.getByLabel("Back to library").click();
    await tiles.nth(0).click();
    await expect(library.getByLabel("Clear workspace filter")).toHaveCount(0);
    await library.getByLabel("Back to library").click();
  }

  // Studio Projects: the open project is excluded, and the shared search narrows to
  // the text of a loaded row — read from the drawer rather than assumed, since the
  // sandbox accumulates projects from every run.
  const projects = library.getByRole("region", { name: "Studio projects" });
  await expect(projects.getByText(currentTitle, { exact: true })).toHaveCount(0);
  const projectsEmpty = await projects.locator(".se-lib-empty").count();
  if (projectsEmpty === 0) {
    const firstTitle = (await projects.locator(".se-lib-title").first().innerText()).trim();
    expect(firstTitle.length).toBeGreaterThan(0);

    await library.getByLabel("Search library").fill(firstTitle);
    await expect(projects.locator(".se-lib-row").first()).toBeVisible();
    const visible = await projects.locator(".se-lib-title").allInnerTexts();
    expect(visible.length).toBeGreaterThan(0);
    expect(
      visible.every((text) => text.toLowerCase().includes(firstTitle.toLowerCase()))
    ).toBe(true);

    await library.getByLabel("Search library").fill("zzz-no-such-project");
    await expect(projects.locator(".se-lib-row")).toHaveCount(0);

    await library.getByLabel("Search library").fill("");
    await expect(projects.getByText(firstTitle, { exact: false }).first()).toBeVisible();
  }

  // Uploads opens its own level-2 list.
  await tiles.nth(3).click();
  await expect(library.getByText("Uploads", { exact: true })).toBeVisible();
  await expect
    .poll(
      async () =>
        (await library.locator(".se-lib-row").count()) +
        (await library.locator(".se-lib-empty").count())
    )
    .toBeGreaterThan(0);

  // Closing the drawer removes it.
  await library.getByLabel("Close library").click();
  await expect(library).toHaveCount(0);
});
