// Third audit pass: one fresh editor load per state, so no leftover overlay can block.
import { chromium } from "playwright";

const BASE = "http://localhost:3103";
const OUT = "../docs/studio/compare";
const VIEWPORT = { width: 1689, height: 1277 };

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 });
const page = await context.newPage();
const done = [];
const failed = [];

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
    body: JSON.stringify({
      title: "Audit states",
      bpm: 120,
      time_signature: "4/4",
      data: {
        lanes: [
          { id: "a1", title: "Electric Keyboards", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav", volume: 1, pan: 0 },
          { id: "a2", title: "Soft Piano", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav", volume: 1, pan: 0 },
          { id: "a3", title: "Bass Line", start: 8, duration: 4, audioUrl: "/seed/demo-loop.wav", volume: 1, pan: 0 },
          {
            id: "a4",
            title: "MIDI Keys",
            start: 4,
            duration: 4,
            volume: 1,
            pan: 0,
            midi: { notes: [{ id: "n1", pitch: 60, start: 0, length: 1, velocity: 100 }] },
          },
        ],
        tracks: [
          { id: "t1", name: "Electric Keyboards", color: "#8b5cf6", index: 0, volume: 80, pan: 0, muted: false, solo: false, hidden: false, groupId: null, chain: [], clipIds: ["a1"] },
          { id: "t2", name: "Soft Piano", color: "#a78bfa", index: 1, volume: 80, pan: 0, muted: false, solo: false, hidden: false, groupId: null, chain: [], clipIds: ["a2"] },
          { id: "t3", name: "Bass Line", color: "#2563eb", index: 2, volume: 80, pan: 0, muted: false, solo: false, hidden: false, groupId: null, chain: [], clipIds: ["a3"] },
          { id: "t4", name: "MIDI Keys", color: "#38bdf8", index: 3, volume: 80, pan: 0, muted: false, solo: false, hidden: false, groupId: null, chain: [], clipIds: ["a4"] },
        ],
      },
    }),
  });
  return (await created.json()).id;
});

async function fresh() {
  await page.goto(`${BASE}/studio/editor?project=${projectId}`);
  await page.locator(".se-clip").first().waitFor({ state: "visible", timeout: 60_000 });
  await page.waitForTimeout(900);
  await page.getByRole("button", { name: "Dismiss" }).click().catch(() => {});
  await page.waitForTimeout(200);
}

async function capture(name, steps) {
  try {
    await fresh();
    await steps();
    await page.screenshot({ path: `${OUT}/${name}.png` });
    done.push(name);
  } catch (error) {
    failed.push(`${name}: ${String(error).slice(0, 120)}`);
  }
}

await capture("ours-project-menu", async () => {
  await page.getByRole("button", { name: /Audit states/ }).click();
});

await capture("ours-track-options", async () => {
  await page.getByRole("button", { name: "Options for Soft Piano", exact: true }).click();
});

await capture("ours-add-track", async () => {
  await page.getByRole("button", { name: /Add new track/ }).click();
});

await capture("ours-ruler-zoom", async () => {
  await page.getByRole("button", { name: "Zoom out" }).click();
  await page.getByRole("button", { name: "Zoom out" }).click();
  await page.waitForTimeout(300);
});

await capture("ours-loop-region", async () => {
  const ruler = page.locator(".se-ruler-bars");
  const box = await ruler.boundingBox();
  if (!box) throw new Error("no ruler");
  await page.mouse.move(box.x + 120, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + 360, box.y + box.height / 2, { steps: 8 });
  await page.mouse.up();
  await page.getByRole("button", { name: "Loop", exact: true }).first().click();
  await page.waitForTimeout(300);
});

await capture("ours-clip-selected", async () => {
  await page.locator(".se-clip").first().click();
});

await capture("ours-clip-menu-state", async () => {
  await page.locator(".se-clip").first().click({ button: "right" });
});

await capture("ours-clip-color", async () => {
  await page.locator(".se-clip").first().click({ button: "right" });
  await page.getByRole("menuitem", { name: /Clip Color/ }).click();
  await page.waitForTimeout(300);
});

await capture("ours-take-lanes", async () => {
  await page.getByRole("button", { name: "Take lanes" }).click();
  await page.waitForTimeout(400);
});

await capture("ours-midi-editor", async () => {
  await page.locator(".se-clip").nth(3).click();
  await page.getByRole("button", { name: "Clip editor" }).click();
  await page.getByRole("region", { name: "MIDI editor" }).waitFor();
});

await capture("ours-midi-velocity", async () => {
  await page.locator(".se-clip").nth(3).click();
  await page.getByRole("button", { name: "Clip editor" }).click();
  await page.getByRole("region", { name: "MIDI editor" }).waitFor();
  await page.getByRole("tab", { name: "Velocity" }).click();
});

await capture("ours-learn-menu", async () => {
  await page.getByRole("button", { name: /Learn/ }).click();
});

await capture("ours-shortcuts", async () => {
  await page.getByRole("button", { name: /Learn/ }).click();
  await page.getByRole("menuitem", { name: /Keyboard Shortcuts/ }).click();
  await page.waitForTimeout(300);
});

await capture("ours-version-history", async () => {
  await page.getByRole("button", { name: /Audit states/ }).click();
  await page.getByRole("menuitem", { name: /Version History/ }).click();
  await page.waitForTimeout(700);
});

await capture("ours-share-dialog", async () => {
  await page.getByRole("button", { name: /Audit states/ }).click();
  await page.getByRole("menuitem", { name: /Share Project/ }).click();
  await page.waitForTimeout(700);
});

await capture("ours-library-songs", async () => {
  await page.getByRole("button", { name: "Library", exact: true }).click();
  await page.getByRole("complementary", { name: "Library" }).getByRole("button", { name: "All Songs" }).click();
  await page.waitForTimeout(900);
});

await capture("ours-library-empty", async () => {
  await page.getByRole("button", { name: "Library", exact: true }).click();
  await page.getByRole("complementary", { name: "Library" }).getByRole("button", { name: "All Songs" }).click();
  await page.waitForTimeout(700);
  await page.getByRole("complementary", { name: "Library" }).getByLabel("Search library").fill("zzz-no-match");
  await page.waitForTimeout(500);
});

await capture("ours-editor-1280-audit", async () => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.waitForTimeout(700);
});

await capture("ours-editor-1024", async () => {
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.waitForTimeout(700);
});

console.log(JSON.stringify({ done, failed }, null, 2));
await browser.close();
