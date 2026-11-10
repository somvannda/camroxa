import { test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

test("debug dock", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  await createStudioProject(page, { title: "Debug dock" });
  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  await page.locator(".sp-add-inline").click();
  await page.getByRole("dialog", { name: "Add a track plugin" }).getByRole("button", { name: /^Compressor/ }).first().click();
  await page.locator(".sp-add").click();
  await page.getByRole("dialog", { name: "Add a track plugin" }).getByRole("button", { name: /^EQ/ }).first().click();
  const info = await page.evaluate(() => {
    const pick = (sel: string) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height), w: Math.round(r.width) };
    };
    return {
      dock: pick(".sp-dock"),
      rail: pick(".sp-rail"),
      slot: pick(".sp-slot"),
      eq: pick(".sp-slot-eq"),
      add: pick(".sp-add"),
      body: pick(".se-body"),
    };
  });
  console.log("DOCK", JSON.stringify(info));
});
