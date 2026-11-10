import { test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

test("debug header buttons", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: "Debug head" });
  console.log("viewport", page.viewportSize());
  const before = await page.locator(".se-head button").evaluateAll((nodes) =>
    nodes.map((n) => ({ text: (n.textContent || "").trim(), aria: n.getAttribute("aria-label"), help: n.getAttribute("data-help"), display: getComputedStyle(n).display }))
  );
  console.log("before", JSON.stringify(before));
  await page.getByRole("button", { name: "Library", exact: true }).click();
  const after = await page.locator(".se-head button").evaluateAll((nodes) =>
    nodes.map((n) => ({ text: (n.textContent || "").trim(), aria: n.getAttribute("aria-label"), help: n.getAttribute("data-help"), display: getComputedStyle(n).display }))
  );
  console.log("after", JSON.stringify(after));
  console.log("count", await page.getByRole("button", { name: "Library", exact: true }).count());
});
