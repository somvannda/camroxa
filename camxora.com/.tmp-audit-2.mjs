// Second audit pass: capture the remaining reference states at 1689×1277.
import { chromium } from "playwright";

const BASE = "http://localhost:3103";
const OUT = "../docs/studio/compare";
const VIEWPORT = { width: 1689, height: 1277 };

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 });
const page = await context.newPage();
const shots = [];
const errors = [];
page.on("pageerror", (error) => errors.push(String(error).slice(0, 160)));

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
          { id: "a1", title: "Electric Keyboards", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav", volume: 1, pan: 0, songId: "song-1" },
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

async function shot(name) {
  try {
    await page.screenshot({ path: `${OUT}/${name}.png` });
    shots.push(name);
  } catch (error) {
    shots.push(`${name}: FAILED ${String(error).slice(0, 80)}`);
  }
}

async function openEditor() {
  await page.goto(`${BASE}/studio/editor?project=${projectId}`);
  await page.locator(".se-clip").first().waitFor({ state: "visible", timeout: 60_000 });
  await page.waitForTimeout(900);
}

await openEditor();
await page.getByRole("button", { name: "Dismiss" }).click().catch(() => {});

// S07 project menu
await page.getByRole("button", { name: /Audit states/ }).click();
await shot("ours-project-menu");
await page.keyboard.press("Escape");

// S19 track options
await page.getByRole("button", { name: "Options for Soft Piano", exact: true }).click();
await shot("ours-track-options");
await page.keyboard.press("Escape");

// S20 add track
await page.getByRole("button", { name: /Add new track/ }).click();
await shot("ours-add-track");
await page.keyboard.press("Escape");

// S22 ruler + zoom: zoom out twice
await page.getByRole("button", { name: "Zoom out" }).click();
await page.getByRole("button", { name: "Zoom out" }).click();
await shot("ours-ruler-zoom");

// S24 loop region (drag on the ruler)
const ruler = page.locator(".se-ruler-bars");
const box = await ruler.boundingBox();
if (box) {
  await page.mouse.move(box.x + 120, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + 360, box.y + box.height / 2, { steps: 8 });
  await page.mouse.up();
  await page.getByRole("button", { name: "Loop", exact: true }).first().click();
  await shot("ours-loop-region");
  await page.keyboard.press("Escape");
}

// S25 selected clip
await page.locator(".se-clip").first().click();
await shot("ours-clip-selected");

// S26 clip menu
await page.locator(".se-clip").first().click({ button: "right" });
await shot("ours-clip-menu-state");
await page.keyboard.press("Escape");

// S28 clip colour submenu
await page.locator(".se-clip").first().click({ button: "right" });
await page.getByRole("menuitem", { name: /Clip Color/ }).click();
await shot("ours-clip-color");
await page.keyboard.press("Escape");

// S29 take lanes
await page.getByRole("button", { name: "Take lanes" }).click();
await shot("ours-take-lanes");

// S31 MIDI editor
await page.locator(".se-clip").nth(3).click();
await page.getByRole("button", { name: "Clip editor" }).click();
await page.getByRole("region", { name: "MIDI editor" }).waitFor();
await shot("ours-midi-editor");
await page.getByRole("tab", { name: "Velocity" }).click();
await shot("ours-midi-velocity");

// S34 magic bar idle
await page.getByRole("button", { name: /Close|Done/i }).first().click().catch(() => {});
await page.getByRole("button", { name: "Clip editor" }).click().catch(() => {});
await shot("ours-magicbar");

// S13 learn + S14 shortcuts + S15 what's this
await page.getByRole("button", { name: /Learn/ }).click();
await shot("ours-learn-menu");
await page.getByRole("menuitem", { name: /Keyboard Shortcuts/ }).click();
await shot("ours-shortcuts");
await page.keyboard.press("Escape");
await page.keyboard.press("Escape");

// S08 versions (menu → Version History)
await page.getByRole("button", { name: /Audit states/ }).click();
await page.getByRole("menuitem", { name: /Version History/ }).click();
await page.waitForTimeout(700);
await shot("ours-version-history");
await page.keyboard.press("Escape");

// S12 share
await page.getByRole("button", { name: /Audit states/ }).click();
await page.getByRole("menuitem", { name: /Share Project/ }).click();
await page.waitForTimeout(700);
await shot("ours-share-dialog");
await page.keyboard.press("Escape");

// S53 library songs + S58 empty
await page.getByRole("button", { name: "Library", exact: true }).click();
const library = page.getByRole("complementary", { name: "Library" });
await library.getByRole("button", { name: "All Songs" }).click();
await page.waitForTimeout(900);
await shot("ours-library-songs");
await library.getByLabel("Search songs").fill("zzz-no-match");
await page.waitForTimeout(500);
await shot("ours-library-empty");

// S63/S64 narrow widths
await page.setViewportSize({ width: 1280, height: 900 });
await page.waitForTimeout(600);
await shot("ours-editor-1280-audit");
await page.setViewportSize({ width: 1024, height: 900 });
await page.waitForTimeout(600);
await shot("ours-editor-1024");

console.log(JSON.stringify({ shots, errors }, null, 2));
await browser.close();
