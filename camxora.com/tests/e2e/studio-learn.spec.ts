import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Learn menu + What's This? (reference §7/§38).
 *
 * The intro card appears once per browser profile, hovering an annotated control shows
 * its explanation, and turning the feature off survives a reload (it is an editor
 * preference, not project data).
 */

test("learn explains a control, then stays off after a reload", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Learn ${tag}` });

  // First run: the intro card explains the feature.
  const intro = page.getByRole("note");
  await expect(intro).toBeVisible();
  await expect(intro).toContainText("Hover over any control");
  await intro.getByRole("button", { name: "Dismiss" }).click();
  await expect(intro).toHaveCount(0);

  // The popover keeps the captured row order.
  await page.getByRole("button", { name: "Learn", exact: true }).click();
  const menu = page.getByRole("menu", { name: "Learn" });
  await expect(menu).toBeVisible();
  await expect(menu.getByRole("menuitem")).toHaveCount(3); // + the What's This? checkbox
  await expect(menu.getByRole("menuitemcheckbox")).toHaveAttribute("aria-checked", "true");

  await menu.getByRole("menuitem", { name: /Keyboard Shortcuts/ }).click();
  const shortcuts = page.getByRole("dialog", { name: "Keyboard shortcuts" });
  await expect(shortcuts).toBeVisible();
  await expect(shortcuts).toContainText("Undo");
  await shortcuts.getByRole("button", { name: "Close" }).click();
  await expect(shortcuts).toHaveCount(0);

  // Learning Center is an in-app tour, not a dead menu row.
  await page.getByRole("button", { name: "Learn", exact: true }).click();
  await page
    .getByRole("menu", { name: "Learn" })
    .getByRole("menuitem", { name: /Learning Center/ })
    .click();
  const center = page.getByRole("dialog", { name: "Learning Center" });
  await expect(center).toBeVisible();
  await expect(center).toContainText("Start an arrangement");
  await expect(center).toContainText("Save and mirror");
  await center.getByRole("button", { name: "Close" }).click();
  await expect(center).toHaveCount(0);

  // Hovering the tempo field explains it. Move the pointer away first: a pointer that is
  // already over the control fires no new pointerover, so a repeated hover would be a
  // no-op (and the listener may attach just after the first move under load).
  await expect
    .poll(
      async () => {
        await page.mouse.move(4, 4);
        await page.getByLabel("Tempo in BPM").hover();
        return page.getByRole("tooltip").count();
      },
      { timeout: 15_000, intervals: [250] }
    )
    .toBeGreaterThan(0);
  const card = page.getByRole("tooltip");
  await expect(card).toContainText("Tempo");
  await expect(card).toContainText("BPM");

  // Turn the feature off from the menu; the card stops appearing.
  await page.getByRole("button", { name: "Learn", exact: true }).click();
  await page.getByRole("menu", { name: "Learn" }).getByRole("menuitemcheckbox").click();
  await page.getByLabel("Tempo in BPM").hover();
  await expect(page.getByRole("tooltip")).toHaveCount(0);

  // Editor preference: off stays off across a reload, and the intro does not return.
  await page.reload();
  await expect(page.locator(".se-project .se-chip")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("note")).toHaveCount(0);
  await page.getByLabel("Tempo in BPM").hover();
  await expect(page.getByRole("tooltip")).toHaveCount(0);
  await page.getByRole("button", { name: "Learn", exact: true }).click();
  await expect(
    page.getByRole("menu", { name: "Learn" }).getByRole("menuitemcheckbox")
  ).toHaveAttribute("aria-checked", "false");
});
