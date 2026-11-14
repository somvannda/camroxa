import { chromium } from "playwright";

const BASE = "http://localhost:3103";
const OUT = "../docs/studio/compare";

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1689, height: 1277 }, deviceScaleFactor: 1 });
const page = await context.newPage();
await page.goto(`${BASE}/studio`);
const projectId = await page.evaluate(async () => {
  await fetch("/api/v3/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email: "somvannda@gmail.com", password: "StudioLocal!2026" }),
  });
  const created = await fetch("/api/v3/web-music/studio/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: "Empty audit", bpm: 120, time_signature: "4/4", data: { lanes: [], tracks: [] } }),
  });
  return (await created.json()).id;
});
await page.goto(`${BASE}/studio/editor?project=${projectId}`);
await page.waitForTimeout(1500);
await page.screenshot({ path: `${OUT}/ours-onboarding.png` });
// Dismiss the overlay for the empty project frame.
await page.getByRole("button", { name: /Start|Dismiss|Skip|Empty/i }).first().click().catch(() => {});
await page.getByRole("button", { name: /Close/i }).first().click().catch(() => {});
await page.keyboard.press("Escape").catch(() => {});
await page.waitForTimeout(600);
await page.screenshot({ path: `${OUT}/ours-empty-project.png` });
console.log("ok");
await browser.close();
