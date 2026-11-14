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

  // Level 1: the four filter tiles, in the captured order. Stems is enabled now
  // that completed stem sets exist (G12).
  const tiles = library.getByRole("group", { name: "Library filters" }).getByRole("button");
  await expect(tiles).toHaveCount(4);
  await expect(tiles.nth(0)).toHaveText("All Songs");
  await expect(tiles.nth(1)).toHaveText("Liked");
  await expect(tiles.nth(2)).toHaveText("Stems");
  await expect(tiles.nth(3)).toHaveText("Uploads");
  await expect(tiles.nth(2)).toBeEnabled();

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
  await expect(library.getByText("Library", { exact: true })).toBeVisible();
  await expect
    .poll(
      async () =>
        (await library.locator(".se-lib-row").count()) +
        (await library.locator(".se-lib-empty").count()) +
        (await library.locator(".se-lib-empty-state").count())
    )
    .toBeGreaterThan(0);

  // Rows carry the reference's row actions: Play, Like and a way to place the clip.
  if ((await library.locator(".se-lib-song").count()) > 0) {
    const row = library.locator(".se-lib-song").first();
    await expect(row.locator("button[aria-label^='Play ']")).toBeVisible();
    await expect(row.locator("button[aria-label*='Like ']").first()).toBeVisible();
  }
  await library.getByLabel("Back to library").click();
  await expect(tiles.nth(0)).toBeVisible();

  // Workspaces are real data: opening one lands on its songs, filtered; Clear drops the
  // filter without leaving the list.
  const workspaces = library.getByRole("region", { name: "Workspaces" });
  const workspaceButtons = workspaces.getByRole("button", { name: /^Open / });
  if ((await workspaceButtons.count()) > 0) {
    await workspaceButtons.first().click();
    await expect(library.getByLabel("Clear workspace filter")).toBeVisible();
    await library.getByLabel("Clear workspace filter").click();
    await expect(library.getByLabel("Clear workspace filter")).toHaveCount(0);
    await expect(library.getByLabel("Back to library")).toBeVisible();

    // Leaving via Back keeps the filter; choosing a tile clears it, because a tile
    // selects the whole corpus.
    await library.getByLabel("Back to library").click();
    await workspaces.getByRole("button", { name: /^Open / }).first().click();
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
  await expect(library.getByLabel("Back to library")).toBeVisible();
  await expect
    .poll(
      async () =>
        (await library.locator(".se-lib-row").count()) +
        (await library.locator(".se-lib-empty").count())
    )
    .toBeGreaterThan(0);

  // Closing the drawer removes it.
  await page.getByRole("button", { name: "Library", exact: true }).click();
  await expect(library).toHaveCount(0);
});

test("level-2 toolbar filters the corpus and opens the generator", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: `Toolbar ${Math.random().toString(36).slice(2, 6)}` });

  await page.getByRole("button", { name: "Library", exact: true }).click();
  const library = page.getByRole("complementary", { name: "Library" });
  await library.getByRole("button", { name: "All Songs" }).click();

  // The captured toolbar: filter / New / thumbs-up / In Project / Stems.
  await expect(library.getByRole("button", { name: "Filter songs" })).toBeVisible();
  await expect(library.getByLabel("Liked only")).toBeVisible();
  await expect(library.getByRole("button", { name: "Stems" })).toBeEnabled();
  await expect(library.locator(".se-library-head strong")).toHaveText("Library");

  await library.getByRole("button", { name: "In Project" }).click();
  await expect(library.getByRole("button", { name: "In Project" })).toHaveAttribute(
    "aria-pressed",
    "true"
  );
  await expect
    .poll(
      async () =>
        (await library.locator(".se-lib-row").count()) +
        (await library.locator(".se-lib-empty").count()) +
        (await library.locator(".se-lib-empty-state").count())
    )
    .toBeGreaterThan(0);

  await library.getByRole("button", { name: "In Project" }).click();
  await expect(library.getByRole("button", { name: "In Project" })).toHaveAttribute(
    "aria-pressed",
    "false"
  );

  // The funnel opens the captured filter menu.
  await library.getByRole("button", { name: "Filter songs" }).click();
  const filterMenu = library.getByRole("menu", { name: "Filter songs" });
  await expect(filterMenu.getByRole("menuitemradio")).toHaveCount(3);
  await filterMenu.getByRole("menuitemradio", { name: "Liked" }).click();
  await expect(library.getByLabel("Liked only")).toHaveAttribute("aria-pressed", "true");
  await library.getByLabel("Liked only").click();

  // + New leaves the editor for the generator.
  await library.getByRole("button", { name: "New" }).click();
  await page.waitForURL(/\/create/);
});

test("adding a library song places a clip on the lane", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: `Add ${Math.random().toString(36).slice(2, 6)}` });

  await page.getByRole("button", { name: "Library", exact: true }).click();
  const library = page.getByRole("complementary", { name: "Library" });
  await library.getByRole("button", { name: "All Songs" }).click();

  const rows = library.locator(".se-lib-song");
  await expect.poll(async () => rows.count()).toBeGreaterThan(0);

  // The drag payload is covered by the component test; native HTML5 drag initiation is
  // unreliable in headless CI, so this spec exercises the same insert path with Add.
  const before = await page.locator(".se-clip").count();
  const add = rows.first().getByRole("button", { name: "Add" });
  await expect(add).toBeEnabled();
  await add.click();
  await expect(page.locator(".se-clip")).toHaveCount(before + 1);
});

test("double-clicking a song opens its detail rail and Back returns to the list", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: `Detail ${Math.random().toString(36).slice(2, 6)}` });

  await page.getByRole("button", { name: "Library", exact: true }).click();
  const library = page.getByRole("complementary", { name: "Library" });
  await library.getByRole("button", { name: "All Songs" }).click();
  const rows = library.locator(".se-lib-song");
  await expect.poll(async () => rows.count()).toBeGreaterThan(0);

  await rows.first().dblclick();
  const detail = page.getByRole("complementary", { name: "Song details" });
  await expect(detail).toBeVisible();
  await expect(detail.getByRole("tab", { name: "Info" })).toHaveAttribute(
    "aria-selected",
    "true"
  );
  await expect(detail.getByRole("tab", { name: "Stems" })).toBeVisible();

  // More is a real menu now (D-027), not a disabled placeholder.
  await detail.getByRole("button", { name: "More song options" }).click();
  const menu = detail.getByRole("menu", { name: "Song options" });
  await expect(menu.getByRole("menuitem")).toHaveCount(3);
  await expect(menu.getByRole("menuitem", { name: /Download WAV/ })).toBeEnabled();
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);

  await detail.getByLabel("Back to library").click();
  await expect(page.getByRole("complementary", { name: "Library" })).toBeVisible();
});


test("stems view lists completed stems and adds one to the timeline", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: `Stems ${Math.random().toString(36).slice(2, 6)}` });
  await page.route("**/api/v3/web-music/studio/stems*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            clip_id: "stem-vocals",
            operation_id: "op-1",
            task_id: "task-1",
            title: "(Vocals)",
            stem_type: "Vocals",
            audio_url: "/seed/demo-loop.wav",
            duration_seconds: 12,
            created_at: "2026-11-10T07:00:00Z",
          },
          {
            clip_id: "stem-inst",
            operation_id: "op-1",
            task_id: "task-1",
            title: "(Instrumental)",
            stem_type: "Instrumental",
            audio_url: "/seed/demo-loop.wav",
            duration_seconds: 12,
            created_at: "2026-11-10T07:00:00Z",
          },
        ],
      }),
    })
  );

  await page.getByRole("button", { name: "Library", exact: true }).click();
  const library = page.getByRole("complementary", { name: "Library" });
  await library.getByRole("group", { name: "Library filters" }).getByRole("button", { name: "Stems" }).click();
  await expect(library.getByText("Vocals", { exact: true })).toBeVisible();
  await expect(library.getByText("Instrumental", { exact: true })).toBeVisible();

  const before = await page.locator(".se-clip").count();
  await library.getByRole("button", { name: "Add Vocals" }).click();
  await expect(page.locator(".se-clip")).toHaveCount(before + 1);
  await expect(page.locator(".se-clip", { hasText: "Vocals" })).toHaveCount(1);
});

test("library upload adds audio to the Uploads list", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: `Upload ${Math.random().toString(36).slice(2, 6)}` });

  await page.getByRole("button", { name: "Library", exact: true }).click();
  const library = page.getByRole("complementary", { name: "Library" });
  await library.getByRole("group", { name: "Library filters" }).getByRole("button", { name: "Uploads" }).click();

  await library.getByLabel("Choose audio file").setInputFiles("public/seed/demo-loop.wav");

  // Importing needs streaming storage. When the API has a bucket the new file appears
  // in the Uploads list; without one the backend refuses and the panel must surface the
  // reason. Both outcomes are accepted so the spec runs on either stack. The sandbox DB
  // keeps uploads between runs, so wait for the outcome rather than for "a row exists".
  const refused = library.getByRole("alert").first();
  const outcome = await expect
    .poll(
      async () => {
        if ((await library.getByRole("alert").count()) > 0) return "refused";
        const adds = library.getByLabel("Add demo-loop.wav");
        const count = await adds.count();
        for (let index = 0; index < count; index += 1) {
          if (await adds.nth(index).isEnabled()) return "imported";
        }
        return "pending";
      },
      { timeout: 20_000, intervals: [250] }
    )
    .not.toBe("pending");

  if (outcome === "refused") {
    await expect(refused).toContainText(/not configured|Upload failed/i);
  } else {
    await expect(library.getByLabel("Back to library")).toBeVisible();
  }
});

test("remix generates a variation from the song style", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: `Remix ${Math.random().toString(36).slice(2, 6)}` });
  await page.getByRole("button", { name: "Library", exact: true }).click();
  const library = page.getByRole("complementary", { name: "Library" });
  await library.getByRole("button", { name: "All Songs" }).click();
  const first = library.locator(".se-lib-song").first();
  await expect(first).toBeVisible();
  await first.dblclick();

  await page.route("**/api/v3/web-music/generate", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ task_id: "remix-test", status: "queued", title: "Remix", style: "pop" }),
    })
  );
  await page.route("**/api/v3/web-music/generations/remix-test", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "remix-test",
        title: "Remix result",
        style: "pop",
        status: "complete",
        clips: [
          {
            variant: "v1",
            title: "Remix result",
            audio_url: "/seed/demo-loop.wav",
            download_url: "/seed/demo-loop.wav",
            duration_seconds: 4,
          },
        ],
      }),
    })
  );

  const detail = page.getByRole("complementary", { name: "Song details" });
  await detail.getByRole("button", { name: "Remix" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Remix generated" })
  ).toBeVisible({ timeout: 20_000 });
});

