import { expect, test } from "@playwright/test";
import path from "node:path";

import { createStudioProject, signIn } from "./studio-fixture";

/**
 * Accessibility as a test (W5.5), not a one-off audit.
 *
 * Injects the axe-core bundle into the real pages and asserts zero violations on both
 * Studio routes. The audit that produced the G14 fixes was manual; this keeps it true.
 */

const AXE_PATH = path.join(process.cwd(), "node_modules", "axe-core", "axe.min.js");

async function audit(page: import("@playwright/test").Page) {
  await page.addScriptTag({ path: AXE_PATH });
  return page.evaluate(async () => {
    const axe = (window as unknown as { axe: { run: (ctx: Document) => Promise<{ violations: Array<{ id: string; impact: string | null; nodes: unknown[] }> }> } }).axe;
    const result = await axe.run(document);
    return result.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      // Targets make a failure actionable without re-running the audit by hand.
      nodes: (violation.nodes as Array<{ target: unknown; failureSummary?: string }>).map((node) => ({
        target: node.target,
        summary: node.failureSummary,
      })),
    }));
  });
}

test("studio home has no axe violations", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.reload();
  // The shared chrome provides <main>; StudioHome is the page content inside it.
  await expect(page.getByRole("heading", { level: 1, name: "Your projects" })).toBeVisible({
    timeout: 30_000,
  });

  expect(await audit(page)).toEqual([]);
});

test("studio editor has no axe violations", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: "A11y probe" });

  expect(await audit(page)).toEqual([]);

  // The Learn popover is a fifth surface; audit it while open.
  await page.getByRole("button", { name: "Learn", exact: true }).click();
  await expect(page.getByRole("menu", { name: "Learn" })).toBeVisible();
  expect(await audit(page)).toEqual([]);
});

test("library drawer has no axe violations", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: "A11y library probe" });
  await page.getByRole("button", { name: "Library", exact: true }).click();
  await expect(page.getByRole("complementary", { name: "Library" })).toBeVisible();

  expect(await audit(page)).toEqual([]);
});

test("the clip editor and range menu have no axe violations", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, {
    title: "A11y clip editor probe",
    clips: [
      { id: "loop", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  // Clip Settings (S30/§81) is a dense control surface: audit it while open.
  await page.locator(".se-clip").first().dblclick();
  await expect(page.getByRole("region", { name: "Clip settings" })).toBeVisible();
  await page.getByRole("radio", { name: "On Beat" }).click();
  await expect(page.locator(".se-warp-head").first()).toBeVisible();
  expect(await audit(page)).toEqual([]);

  // The time-selection menu (N-01).
  const ruler = page.locator(".se-ruler-bars");
  const box = await ruler.boundingBox();
  if (!box) throw new Error("ruler has no box");
  await page.mouse.move(box.x + 100, box.y + box.height - 8);
  await page.mouse.down();
  await page.mouse.move(box.x + 292, box.y + box.height - 8, { steps: 8 });
  await page.mouse.up();
  await page.mouse.click(box.x + 200, box.y + box.height - 8, { button: "right" });
  await expect(page.getByRole("menu", { name: "Time selection options" })).toBeVisible();
  expect(await audit(page)).toEqual([]);
});
