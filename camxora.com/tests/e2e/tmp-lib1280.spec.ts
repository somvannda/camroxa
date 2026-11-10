import { test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

test("shot library 1280", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: "Lib 1280" });
  await page.getByRole("button", { name: "Library", exact: true }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: "test-results/shot-lib-1280.png" });
  const info = await page.getByRole("button", { name: "Library", exact: true }).evaluate((el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return { x: r.x, y: r.y, w: r.width, h: r.height, display: s.display, z: s.zIndex };
  });
  console.log("LIBBTN", JSON.stringify(info));
});
