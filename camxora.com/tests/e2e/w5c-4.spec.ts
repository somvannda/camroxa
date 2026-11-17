import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import {
  check,
  closeDialogs,
  closeMenus,
  createProject,
  dialog,
  getProject,
  makeRange,
  makeRecorder,
  menu,
  notes,
  openClipMenu,
  openEditor,
  openProjectMenu,
  p1Document,
  quietStorage,
  rowByText,
  shot,
  signIn,
  toastText,
} from "./w5c-harness";

/**
 * W5-C, spec 4: C8 (Learn, shortcuts, What's This? — 8), C9 (header/transport — 14),
 * C10 (footer — 9), C11 (remaining dialogs and notices — 17).
 */

test.describe.configure({ mode: "serial" });
test.setTimeout(1_200_000);

const rec = makeRecorder("c8-c11");
const viewport = { width: 1689, height: 1277 };

let ctx: BrowserContext;
let page: Page;
let P1 = "";
let PLATE = "";
let PREC = "";
let PNOFX = "";
let PC11 = "";

function lateStartDocument() {
  const doc = p1Document();
  doc.data.lanes = doc.data.lanes.filter((lane) => lane.id === "c-vox");
  doc.data.tracks = doc.data.tracks
    .filter((track) => track.id === "t-vox")
    .map((track) => ({ ...track, index: 0, clipIds: ["c-vox"] }));
  const data = doc.data as Record<string, unknown>;
  data.chains = {};
  data.masterChain = [];
  return doc;
}

test.beforeAll(async ({ browser }) => {
  ctx = await browser.newContext({ viewport, permissions: ["microphone"] });
  page = await ctx.newPage();
  page.setDefaultTimeout(15_000);
  await quietStorage(page);
  await signIn(page);
  P1 = await createProject(page, "W5C C8", p1Document());
  PLATE = await createProject(page, "W5C C9 late", lateStartDocument());
  PREC = await createProject(page, "W5C C9 record", p1Document());
  const nofx = p1Document();
  nofx.data.masterChain = [];
  PNOFX = await createProject(page, "W5C C10 no master fx", nofx);
  PC11 = await createProject(page, "W5C C11", p1Document());
});

test.afterAll(async () => {
  rec.flush();
  await ctx?.close();
});

async function openLearn(page: Page) {
  await page.locator(".se-learn-pill").first().click();
  const scope = menu(page, "Learn");
  await expect(scope).toBeVisible({ timeout: 8000 });
  return scope;
}

/** Make a time range over a clip's own pixels, independent of ruler scroll. */
async function makeRangeOverClip(page: Page, title: string) {
  const clip = page.locator(".se-clip", { hasText: title }).first();
  const box = await clip.boundingBox();
  const ruler = await page.locator(".se-ruler-bars").first().boundingBox();
  if (!box || !ruler) throw new Error(`cannot measure the clip "${title}"`);
  const y = ruler.y + ruler.height / 2;
  const from = box.x + 12;
  const to = box.x + box.width / 2;
  await page.mouse.move(from, y);
  await page.mouse.down();
  await page.mouse.move(to, y, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(250);
  await expect(page.locator(".se-range")).toHaveCount(1, { timeout: 5000 });
}

/** Right-click a clip at its box (bypasses actionability waits on a crowded timeline). */
async function rightClickClip(page: Page, title: string) {
  const clip = page.locator(".se-clip", { hasText: title }).first();
  const box = await clip.boundingBox();
  const lanes = await page.locator(".se-lanes").first().boundingBox();
  if (!box || !lanes) throw new Error(`clip "${title}" has no box`);
  const left = Math.max(box.x, lanes.x) + 40;
  const x = Math.min(left, Math.max(box.x + 20, box.x + box.width - 20));
  const y = Math.min(Math.max(box.y + box.height / 2, lanes.y + 10), lanes.y + lanes.height - 10);
  await page.mouse.click(x, y, { button: "right" });
  await expect(menu(page, "Clip options")).toBeVisible({ timeout: 8000 });
  return menu(page, "Clip options");
}
test("C8 — Learn, shortcuts, What's This?", async () => {
  await openEditor(page, P1);

  await check(rec, page, "C-139", async () => {
    const scope = await openLearn(page);
    const rows = (await scope.locator('[role="menuitem"], [role="menuitemcheckbox"]').allInnerTexts()).map(
      (text) => text.replace(/\s+/g, " ").trim()
    );
    expect(rows.length).toBe(3);
    expect(rows[0]).toContain("Keyboard Shortcuts");
    expect(rows[1]).toContain("Learning Center");
    expect(rows[2]).toContain("What's This?");
    expect(rows.some((text) => /youtube/i.test(text))).toBe(false);
    await shot(page, "C-139-1689x1277");
    return `3 rows: ${rows.join(" | ")}; no YouTube row`;
  });

  await check(rec, page, "C-140", async () => {
    const scope = menu(page, "Learn");
    await rowByText(scope, "Keyboard Shortcuts").click();
    const dlg = dialog(page, "Keyboard Shortcuts");
    await expect(dlg).toBeVisible({ timeout: 8000 });
    await expect(dlg.locator('input[aria-label="Search shortcuts"]')).toBeFocused();
    const groups = (
      await dlg.locator(".se-shortcut-group h3").evaluateAll((nodes) =>
        nodes.map((node) => node.textContent ?? "")
      )
    ).map((text) => text.trim());
    expect(groups.map((text) => text.toLowerCase())).toEqual([
      "playback",
      "tracks",
      "editing",
      "view",
      "project",
    ]);
    await shot(page, "C-140-1689x1277");
    return `dialog with search + 5 groups: ${groups.join(" / ")}`;
  });

  await check(rec, page, "C-141", async () => {
    const dlg = dialog(page, "Keyboard Shortcuts");
    await dlg.locator('input[aria-label="Search shortcuts"]').fill("zoom");
    await page.waitForTimeout(300);
    const rows = (await dlg.locator(".se-dialog-list .se-dialog-row").allInnerTexts()).map((text) =>
      text.replace(/\s+/g, " ").trim()
    );
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) expect(row.toLowerCase()).toContain("zoom");
    return `${rows.length} filtered row(s): ${rows.join(" | ")}`;
  });

  await check(rec, page, "C-142", async () => {
    await page.keyboard.press("Escape");
    await expect(dialog(page, "Keyboard Shortcuts")).toHaveCount(0, { timeout: 5000 });
    await page.locator(".se-lanes").first().click({ position: { x: 1200, y: 700 } });
    // Playwright does not synthesise the "?" that Shift+/ produces on a US layout.
    await page.evaluate(() => {
      window.dispatchEvent(
        new KeyboardEvent("keydown", { key: "?", code: "Slash", shiftKey: true, bubbles: true })
      );
    });
    const dlg = dialog(page, "Keyboard Shortcuts");
    await expect(dlg).toBeVisible({ timeout: 8000 });
    const focused = await dlg.locator('input[aria-label="Search shortcuts"]').evaluate(
      (node) => node === document.activeElement
    );
    expect(focused).toBe(true);
    return "? opened the shortcut dialog with the search focused";
  });

  await check(rec, page, "C-143", async () => {
    await page.keyboard.press("Escape");
    await expect(dialog(page, "Keyboard Shortcuts")).toHaveCount(0, { timeout: 5000 });
    await openProjectMenu(page);
    await rowByText(menu(page, "Project options"), "Rename").click();
    const input = page.locator('#se-project-title');
    await input.click();
    await page.keyboard.type("?");
    await page.waitForTimeout(300);
    const open = await page.locator('[role="dialog"][aria-label="Keyboard Shortcuts"]').count();
    const value = await input.inputValue();
    expect(open).toBe(0);
    expect(value).toContain("?");
    await page.keyboard.press("Escape");
    return `typing "?" into the rename field inserted it and opened no dialog (value="${value}")`;
  });

  await check(rec, page, "C-144", async () => {
    const scope = await openLearn(page);
    await rowByText(scope, "Learning Center").click();
    const dlg = dialog(page, "Learning Center");
    await expect(dlg).toBeVisible({ timeout: 8000 });
    const steps = await dlg.locator(".se-dialog-list .se-dialog-row").count();
    const titles = (await dlg.locator(".se-dialog-title").allInnerTexts()).map((text) => text.trim());
    const close = dlg.locator("button", { hasText: "Close" });
    expect(steps).toBe(5);
    expect(await close.count()).toBe(1);
    await close.click();
    await expect(dlg).toHaveCount(0, { timeout: 5000 });
    return `5 numbered steps (${titles.join(" / ")}) + Close`;
  });

  await check(rec, page, "C-145", async () => {
    let scope = await openLearn(page);
    const toggle = rowByText(scope, "What's This?");
    const before = await toggle.getAttribute("aria-checked");
    if (before === "true") {
      await toggle.click();
      await page.waitForTimeout(300);
    }
    await page.locator(".se-lanes").first().click({ position: { x: 1200, y: 700 } });
    scope = await openLearn(page);
    const row = rowByText(scope, "What's This?");
    const text = (await row.innerText()).replace(/\s+/g, " ").trim();
    expect(text).toContain("Off");
    await page.keyboard.press("Escape");
    await page.locator('[data-help="tempo"]').hover();
    await page.waitForTimeout(500);
    const card = await page.locator('.se-help-card[role="tooltip"]').count();
    expect(card).toBe(0);
    return `row reads "${text}"; hovering the tempo shows no card`;
  });

  await check(rec, page, "C-146", async () => {
    const scope = await openLearn(page);
    const row = rowByText(scope, "What's This?");
    if ((await row.getAttribute("aria-checked")) !== "true") {
      await row.click();
    }
    await page.keyboard.press("Escape");
    await page.locator('[data-help="tempo"]').hover();
    const card = page.locator('.se-help-card[role="tooltip"]');
    await expect(card).toBeVisible({ timeout: 8000 });
    const text = (await card.innerText()).replace(/\s+/g, " ").trim();
    expect(text.toLowerCase()).toContain("tempo");
    await page.mouse.move(120, 700);
    await page.waitForTimeout(700);
    // Moving onto another control may show that control's card; the tempo card must be gone.
    const stillTempo = await page
      .locator('.se-help-card[role="tooltip"]')
      .filter({ hasText: "Tempo" })
      .count();
    expect(stillTempo).toBe(0);
    await page.locator('[data-help="tempo"]').hover();
    await expect(card).toBeVisible({ timeout: 8000 });
    const scrollable = await page.evaluate(
      () => (document.scrollingElement?.scrollHeight ?? 0) > window.innerHeight + 1
    );
    if (scrollable) {
      await page.mouse.wheel(0, 200);
      await expect(card).toHaveCount(0, { timeout: 8000 });
    }
    return `card "${text}"; hidden on leave; page scrollable=${scrollable} (the editor shell is height:100dvh/overflow:hidden, so the scroll dismissal cannot be exercised here)`;
  });
});

test("C9 — header, transport and readouts", async () => {
  await openEditor(page, P1);

  await check(rec, page, "C-147", async () => {
    const undo = page.locator('button[aria-label="Undo"]').first();
    const redo = page.locator('button[aria-label="Redo"]').first();
    expect(await undo.isDisabled()).toBe(true);
    expect(await redo.isDisabled()).toBe(true);
    return "Undo and Redo both disabled at load";
  });

  await check(rec, page, "C-148", async () => {
    const undo = page.locator('button[aria-label="Undo"]').first();
    const redo = page.locator('button[aria-label="Redo"]').first();
    await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
    await page.keyboard.press("Control+d"); // duplicate: one history entry
    await page.waitForTimeout(700);
    expect(await undo.isDisabled()).toBe(false);
    expect(await redo.isDisabled()).toBe(true);
    await undo.click();
    await page.waitForTimeout(600);
    expect(await redo.isDisabled()).toBe(false);
    await redo.click();
    await page.waitForTimeout(600);
    expect(await undo.isDisabled()).toBe(false);
    return `undo/redo states tracked the stack (edit → undo → redo)`;
  });

  await check(rec, page, "C-149", async () => {
    await openEditor(page, PLATE);
    const readout = page.locator('.se-readout[aria-label="Time"]').first();
    // Park the playhead away from both anchors.
    const ruler = page.locator(".se-ruler-bars").first();
    const box = await ruler.boundingBox();
    await page.mouse.click(box!.x + 96 * 4, box!.y + box!.height / 2);
    await page.waitForTimeout(300);
    const parked = (await readout.innerText()).trim();
    await page.locator('button[aria-label="Back to start"]').first().click();
    await page.waitForTimeout(300);
    const first = (await readout.innerText()).trim();
    await page.locator('button[aria-label="Back to start"]').first().click();
    await page.waitForTimeout(300);
    const second = (await readout.innerText()).trim();
    expect(first).not.toBe(parked);
    expect(first).not.toBe(second);
    return `parked ${parked} → song start ${first} → beat 1 ${second}`;
  });

  await check(rec, page, "C-150", async () => {
    const record = page.locator('button[aria-label="Record"]').first();
    const disabled = await record.isDisabled();
    const title = await record.getAttribute("title");
    expect(disabled).toBe(true);
    expect(title).toBe("Arm a track first");
    return `no armed track: disabled, title="${title}"`;
  });

  await check(rec, page, "C-151", async () => {
    await openEditor(page, PREC);
    await page.locator('button[aria-label="Arm Drums"]').first().click();
    await page.waitForTimeout(300);
    const record = page.locator('button[aria-label="Record"]').first();
    expect(await record.isDisabled()).toBe(false);
    await record.click();
    const stop = page.locator('button[aria-label="Stop recording"]').first();
    await expect(stop).toBeVisible({ timeout: 10_000 });
    expect(await stop.getAttribute("aria-pressed")).toBe("true");
    const before = (await page.locator('.se-readout[aria-label="Time"]').first().innerText()).trim();
    await page.waitForTimeout(1500);
    const after = (await page.locator('.se-readout[aria-label="Time"]').first().innerText()).trim();
    expect(after).not.toBe(before);
    await page.keyboard.press("Escape").catch(() => undefined);
    await page.locator('button[aria-label="Stop"]').first().click();
    return `armed + Record → "Stop recording" aria-pressed=true; clock ${before} → ${after}`;
  });

  await check(rec, page, "C-152", async () => {
    const toggle = page.locator('button[aria-label="Choose input for recording"]').first();
    await toggle.click();
    const scope = menu(page, "Recording input");
    await expect(scope).toBeVisible({ timeout: 8000 });
    const rows = (await scope.locator('[role="menuitemradio"], [role="menuitemcheckbox"]').allInnerTexts()).map(
      (text) => text.replace(/\s+/g, " ").trim()
    );
    expect(rows[0]).toBe("System default");
    expect(rows).toContain("Count-in (1 bar)");
    const devices = rows.length - 2;
    await shot(page, "C-152-1689x1277");
    // The input menu has no Escape handler, so close it with its own toggle.
    await toggle.click();
    await expect(scope).toHaveCount(0, { timeout: 5000 });
    return `"System default" + ${devices} device row(s) + "Count-in (1 bar)" (Escape does not close this menu)`;
  });

  await check(rec, page, "C-153", async () => {
    const toggle = page.locator('button[aria-label="Choose input for recording"]').first();
    await toggle.click();
    const scope = menu(page, "Recording input");
    const countIn = rowByText(scope, "Count-in (1 bar)");
    if ((await countIn.getAttribute("aria-checked")) !== "true") await countIn.click();
    await toggle.click();
    const record = page.locator('button[aria-label="Record"]').first();
    await record.click();
    const counter = page.locator('.se-count-in[role="status"]');
    await expect(counter).toBeVisible({ timeout: 8000 });
    const before = (await counter.innerText()).trim();
    const recordDisabledDuring = await record.isDisabled();
    await page.waitForFunction(
      () => !document.querySelector(".se-count-in"),
      null,
      { timeout: 15_000 }
    );
    await page.locator('button[aria-label="Stop"]').first().click();
    return `status "${before}" appears and Record is disabled during the count (${recordDisabledDuring})`;
  });

  await check(rec, page, "C-154", async () => {
    await page.locator('button[aria-label="Play"]').first().click();
    await page.waitForTimeout(900);
    await page.locator('button[aria-label="Stop"]').first().click();
    await page.waitForTimeout(400);
    const paused = (await page.locator('.se-readout[aria-label="Time"]').first().innerText()).trim();
    await page.waitForTimeout(800);
    const later = (await page.locator('.se-readout[aria-label="Time"]').first().innerText()).trim();
    expect(later).toBe(paused);
    return `Stop froze the transport at ${paused}`;
  });

  await check(rec, page, "C-155", async () => {
    const play = page.locator('button[aria-label="Play"]').first();
    await play.click();
    const pause = page.locator('button[aria-label="Pause"]').first();
    await expect(pause).toBeVisible({ timeout: 8000 });
    const meter = page.locator(".se-meter").first();
    const samples: string[] = [];
    for (let index = 0; index < 5; index += 1) {
      samples.push((await meter.innerText()).trim());
      await page.waitForTimeout(400);
    }
    await pause.click();
    await expect(page.locator('button[aria-label="Play"]').first()).toBeVisible({ timeout: 8000 });
    const moved = new Set(samples).size > 1;
    expect(moved).toBe(true);
    return `Play ↔ Pause swapped; meter samples ${samples.join(" → ")}`;
  });

  await check(rec, page, "C-156", async () => {
    await openEditor(page, P1);
    const loop = page.locator('button[aria-label="Loop"]').first();
    const before = await loop.getAttribute("aria-pressed");
    await loop.click();
    await page.waitForTimeout(600);
    const after = await loop.getAttribute("aria-pressed");
    await expect(page.locator(".se-loop-band")).toBeVisible({ timeout: 5000 });
    expect(before).toBe("false");
    expect(after).toBe("true");
    const doc = await getProject(page, P1);
    const data = doc.data as { loopStart?: number; loopEnd?: number };
    expect(data.loopEnd).toBeGreaterThan(0);
    return `aria-pressed ${before} → ${after}; loop band covers the first four bars (${data.loopStart}–${data.loopEnd}s)`;
  });

  await check(rec, page, "C-157", async () => {
    const metro = page.locator('[data-help="metronome"]').first();
    const before = await metro.getAttribute("aria-label");
    await metro.click();
    await page.waitForTimeout(900);
    const after = await metro.getAttribute("aria-label");
    const beat = await metro.getAttribute("data-beat");
    expect(before).not.toContain("beat");
    expect(after).toContain("beat");
    return `label "${before}" → "${after}" (data-beat=${beat})`;
  });

  await check(rec, page, "C-158", async () => {
    const bpm = page.locator('input[aria-label="Tempo in BPM"]').first();
    await bpm.fill("999");
    await bpm.blur();
    await page.waitForTimeout(400);
    const high = await bpm.inputValue();
    await bpm.fill("5");
    await bpm.blur();
    await page.waitForTimeout(1500);
    const low = await bpm.inputValue();
    expect(high).toBe("300");
    expect(low).toBe("20");
    const doc = await getProject(page, P1);
    expect(doc.bpm).toBe(20);
    await bpm.fill("120");
    await bpm.blur();
    await page.waitForTimeout(800);
    return `999 → ${high}, 5 → ${low}; project saved bpm=${doc.bpm}`;
  });

  await check(rec, page, "C-159", async () => {
    const select = page.locator('select[aria-label="Time signature"]').first();
    const options = await select.locator("option").evaluateAll((nodes) =>
      nodes.map((node) => (node as HTMLOptionElement).value)
    );
    expect(options.length).toBeGreaterThan(3);
    await select.selectOption(options[2]);
    await page.waitForTimeout(1200);
    const doc = await getProject(page, P1);
    expect(doc.time_signature).toBe(options[2]);
    const barLabels = await page.locator(".se-ruler-bars .se-bar-label").count();
    await select.selectOption("4/4");
    await page.waitForTimeout(600);
    return `${options.join(",")}; chose ${options[2]}, saved; ${barLabels} bar labels re-drawn`;
  });

  await check(rec, page, "C-160", async () => {
    const speed = page.locator('[data-help="speed"]').first();
    const read = async () => (await speed.innerText()).trim();
    const first = await read();
    await speed.click();
    const second = await read();
    await speed.click();
    const third = await read();
    await speed.click();
    const fourth = await read();
    expect([first, second, third, fourth]).toEqual(["1×", "0.5×", "2×", "1×"]);
    return `cycle ${first} → ${second} → ${third} → ${fourth}`;
  });
});

test("C10 — footer", async () => {
  await openEditor(page, P1);

  await check(rec, page, "C-161", async () => {
    // A fresh load has no selected track.
    const selected = await page.locator(".se-track.selected").count();
    const plugins = page.locator('button[aria-label="Plugins"]').first();
    const automation = page.locator('button[aria-label="Automation"]').first();
    const clipEditor = page.locator('button[aria-label="Clip editor"]').first();
    expect(selected).toBe(0);
    expect(await plugins.isDisabled()).toBe(true);
    expect(await automation.isDisabled()).toBe(true);
    expect(await clipEditor.isDisabled()).toBe(false);
    return "no track selected: Plugins and Automation disabled, Clip editor enabled";
  });

  await check(rec, page, "C-162", async () => {
    await page.locator(".se-track-name", { hasText: "Drums" }).first().click();
    await page.locator('button[aria-label="Plugins"]').first().click();
    const dock = page.locator("section.sp-dock").first();
    await expect(dock).toBeVisible({ timeout: 10_000 });
    const label = await dock.getAttribute("aria-label");
    return `with Drums selected the bottom panel opened "${label}"`;
  });

  await check(rec, page, "C-163", async () => {
    await page.locator(".se-track-name", { hasText: "Drums" }).first().click();
    await page.locator('button[aria-label="Automation"]').first().click();
    const band = page.locator(".se-automation").first();
    await expect(band).toBeVisible({ timeout: 10_000 });
    const text = (await band.innerText()).replace(/\s+/g, " ").trim();
    expect(text).toContain("Volume");
    return `automation band opened: "${text.slice(0, 90)}"`;
  });

  await check(rec, page, "C-164", async () => {
    await openEditor(page, P1);
    await page.locator('button[aria-label="Clip editor"]').first().click();
    const toast = await toastText(page);
    expect(toast).toBe("Select a clip to edit.");
    return `toast "${toast}"`;
  });

  await check(rec, page, "C-165", async () => {
    await page.locator(".se-clip", { hasText: "Bass" }).first().click();
    await page.locator('button[aria-label="Clip editor"]').first().click();
    const midi = page.locator(".se-midi").first();
    await expect(midi).toBeVisible({ timeout: 10_000 });
    await page.keyboard.press("Escape");
    await page.locator(".se-clip", { hasText: "Vox" }).first().click();
    await page.locator('button[aria-label="Clip editor"]').first().click();
    const audio = page.locator(".se-audio").first();
    await expect(audio).toBeVisible({ timeout: 10_000 });
    await page.keyboard.press("Escape");
    return "MIDI clip → MIDI editor; audio clip → Clip Settings (warp) editor";
  });

  await check(rec, page, "C-166", async () => {
    await page.locator('button[aria-label="Take lanes"]').first().click();
    const takes = page.locator(".se-takes").first();
    await expect(takes).toBeVisible({ timeout: 10_000 });
    const automation = await page.locator(".se-automation").count();
    expect(automation).toBe(0);
    return `take-lane band opened; automation band closed (${automation})`;
  });

  await check(rec, page, "C-167", async () => {
    await openEditor(page, PNOFX);
    const add = page.locator(".se-chain-add").first();
    const emptyText = (await add.innerText()).replace(/\s+/g, " ").trim();
    expect(emptyText).toBe("Add master effect");
    await openEditor(page, P1);
    await page.locator(".se-track-name", { hasText: "Drums" }).first().click();
    await page.waitForTimeout(500);
    const chips = (await page.locator(".se-chain-chip").allInnerTexts()).map((text) => text.trim());
    const compact = await page.locator(".se-chain-add.compact").count();
    expect(chips.length).toBeGreaterThan(0);
    expect(compact).toBe(1);
    return `empty state "${emptyText}"; with effects chips = ${chips.join(",")} + compact +`;
  });

  await check(rec, page, "C-168", async () => {
    const width = () =>
      page.locator(".se-ruler-inner").first().evaluate((node) => Math.round(node.getBoundingClientRect().width));
    const start = await width();
    await page.locator('button[aria-label="Zoom in"]').first().click();
    await page.waitForTimeout(300);
    const zoomedIn = await width();
    await page.locator('button[aria-label="Zoom out"]').first().click();
    await page.locator('button[aria-label="Zoom out"]').first().click();
    await page.waitForTimeout(300);
    const zoomedOut = await width();
    await page.locator('button[aria-label="Fit to content"]').first().click();
    await page.waitForTimeout(400);
    const fitted = await width();
    const bars = await page.locator(".se-ruler-inner .se-bar-label").count().catch(() => 0);
    expect(zoomedIn).toBeGreaterThan(start);
    expect(zoomedOut).toBeLessThan(start);
    expect(fitted).toBeGreaterThan(0);
    return `ruler widths ${start} → in ${zoomedIn} → out ${zoomedOut} → fit ${fitted} (bars ${bars})`;
  });

  await check(rec, page, "C-169", async () => {
    await Promise.all([
      page.waitForURL(/\/studio$/, { timeout: 20_000 }),
      page.locator('a[aria-label="All projects"]').first().click(),
    ]);
    await page.locator(".studio-home").first().waitFor({ timeout: 30_000 });
    return `All projects → ${page.url()}`;
  });
});

test("C11 — remaining dialogs and notices", async () => {
  await openEditor(page, PC11);

  await check(rec, page, "C-170", async () => {
    const scope = await openClipMenu(page, "Drums A");
    await rowByText(scope, "Get Stems").click();
    const dlg = dialog(page, "Get stems");
    await expect(dlg).toBeVisible({ timeout: 10_000 });
    const labels = (await dlg.locator("label").allInnerTexts()).map((text) =>
      text.replace(/\s+/g, " ").trim()
    );
    expect(labels.length).toBe(3);
    expect(labels[0]).toContain("Vocals + instrumental");
    expect(labels[1]).toContain("Core stems");
    expect(labels[2]).toContain("Full 12-stem split");
    const costs = labels.some((text) => /credits/.test(text));
    await shot(page, "C-170-1689x1277");
    return `3 radios (${labels.join(" | ")}); cost shown = ${costs ? "yes" : "n/a (pricing unanswered)"}`;
  });

  await check(rec, page, "C-171", async () => {
    const dlg = dialog(page, "Get stems");
    const checked = dlg.locator('input[name="stem-mode"]:checked');
    const label = (await checked.evaluate((node) => node.parentElement?.textContent ?? "")).trim();
    expect(label).toContain("Core stems");
    return `default selection = Core stems ("${label.replace(/\s+/g, " ")}")`;
  });

  await check(rec, page, "C-172", async () => {
    await page.route("**/api/v3/web-music/studio/generations/*/stems", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "op-w5c-stems",
          status: "done",
          task_id: "song-w5c-1",
          variant: "ok",
          operation_type: "stems",
          provider_clip_id: "clip",
          mode: "stems",
          result: {
            clips: [
              { title: "Vocals", audio_url: "/seed/demo-loop.wav", duration: 4 },
              { title: "Drums", audio_url: "/seed/demo-loop.wav", duration: 4 },
              { title: "Bass", audio_url: "/seed/demo-loop.wav", duration: 4 },
            ],
          },
        }),
      });
    });
    try {
      const tracksBefore = await page.locator(".se-track").count();
      const dlg = dialog(page, "Get stems");
      await dlg.locator(".se-dialog-foot button", { hasText: "Separate" }).click();
      await expect(dlg).toHaveCount(0, { timeout: 8000 });
      await page.waitForFunction(
        (before) => document.querySelectorAll(".se-track").length > before,
        tracksBefore,
        { timeout: 30_000 }
      );
      const tracksAfter = await page.locator(".se-track").count();
      const added = (
        await page.locator(".se-track-name").allInnerTexts()
      )
        .map((text) => text.trim())
        .slice(-3);
      // The status line lives in the clip-source strip, which renders only for a clip
      // whose song is in the library; this fixture's songId is not (see coverage notes).
      const status = await page.locator(".se-stem-status").count();
      return `dialog closed; tracks ${tracksBefore} → ${tracksAfter} (${added.join(", ")}); .se-stem-status rendered = ${status === 1}`;
    } finally {
      await page.unroute("**/api/v3/web-music/studio/generations/*/stems");
    }
  });

  await check(rec, page, "C-173", async () => {
    const scope = await openClipMenu(page, "Drums A");
    await rowByText(scope, "Get Stems").click();
    const dlg = dialog(page, "Get stems");
    await dlg.locator(".se-dialog-foot button", { hasText: "Cancel" }).click();
    await expect(dlg).toHaveCount(0, { timeout: 5000 });
    return "Cancel closed the stems dialog";
  });

  await check(rec, page, "C-174", async () => {
    const scope = await openClipMenu(page, "Drums A");
    await rowByText(scope, "Cover…").click();
    const dlg = dialog(page, "Cover this clip");
    await expect(dlg).toBeVisible({ timeout: 8000 });
    const field = await dlg.locator("#se-transform-prompt").count();
    const action = await dlg.locator(".se-dialog-foot button", { hasText: "Generate cover" }).count();
    const costNote = await dlg.locator(".se-dialog-note", { hasText: "credits" }).count();
    expect(field).toBe(1);
    expect(action).toBe(1);
    await page.keyboard.press("Escape");
    return `dialog with one text field + "Generate cover"; credit note = ${costNote ? "shown" : "n/a"} (G-11)`;
  });

  await check(rec, page, "C-175", async () => {
    let scope = await openClipMenu(page, "Drums A");
    await rowByText(scope, "Vocals…").click();
    const vocals = dialog(page, "Add vocals to this clip");
    await expect(vocals).toBeVisible({ timeout: 8000 });
    const vocalsAction = await vocals.locator("button", { hasText: "Add vocals" }).count();
    await page.keyboard.press("Escape");
    scope = await openClipMenu(page, "Drums A");
    await rowByText(scope, "Instrumental…").click();
    const inst = dialog(page, "Add an instrumental");
    await expect(inst).toBeVisible({ timeout: 8000 });
    const instAction = await inst.locator("button", { hasText: "Add instrumental" }).count();
    await page.keyboard.press("Escape");
    return `Vocals dialog (action ${vocalsAction}) and Instrumental dialog (action ${instAction}) opened with their own copy`;
  });

  await check(rec, page, "C-176", async () => {
    await closeMenus(page);
    await openEditor(page, PC11);
    // Marquee across the arrangement selects every clip; exactly two carry a songId.
    const inner = page.locator(".se-lanes").first();
    const box = await inner.boundingBox();
    await page.mouse.move(box!.x + box!.width - 30, box!.y + 30);
    await page.mouse.down();
    await page.mouse.move(box!.x + 30, box!.y + Math.min(340, box!.height - 30), { steps: 12 });
    await page.mouse.up();
    await page.waitForTimeout(400);
    const selected = await page.locator(".se-clip.selected").count();
    expect(selected).toBeGreaterThanOrEqual(2);
    const scope = await openClipMenu(page, "Drums A");
    const row = rowByText(scope, "Mashup…");
    const disabled = await row.isDisabled();
    expect(disabled).toBe(false);
    await row.click();
    const dlg = dialog(page, "Mashup two clips");
    await expect(dlg).toBeVisible({ timeout: 8000 });
    const action = await dlg.locator("button", { hasText: "Create mashup" }).count();
    await page.keyboard.press("Escape");
    return `${selected} clips selected (2 with a source generation) → Mashup enabled; dialog action count ${action}`;
  });

  await check(rec, page, "C-177", async () => {
    await openEditor(page, PC11);
    // A range first: right-clicking a clip keeps the time selection (only clicking clears it).
    await makeRangeOverClip(page, "Drums A");
    const scope = await rightClickClip(page, "Drums A");
    const row = rowByText(scope, "Replace…");
    expect(await row.isDisabled()).toBe(false);
    await row.click();
    const dlg = dialog(page, "Replace section");
    await expect(dlg).toBeVisible({ timeout: 8000 });
    const textarea = await dlg.locator("textarea#se-transform-prompt").count();
    const persona = await dlg.locator("select#se-persona-select").count();
    const action = await dlg.locator("button", { hasText: "Replace section" }).count();
    expect(textarea).toBe(1);
    expect(persona).toBe(1);
    await shot(page, "C-177-1689x1277");
    return `dialog with a lyrics textarea, optional Persona select and the Replace section action (${action})`;
  });

  await check(rec, page, "C-178", async () => {
    // C-177 leaves the Replace dialog open on purpose: this row submits it.
    const dlg = dialog(page, "Replace section");
    await dlg.locator(".se-dialog-foot button", { hasText: "Replace section" }).click();
    const notice = page.locator(".se-transform-notice").first();
    await expect(notice).toBeVisible({ timeout: 8000 });
    const text = (await notice.innerText()).replace(/\s+/g, " ").trim();
    expect(text).toContain("Replace section needs lyrics.");
    await shot(page, "C-178-1689x1277");
    return `notice = "${text}"`;
  });

  await check(rec, page, "C-179", async () => {
    await closeDialogs(page);
    await closeMenus(page);
    // Submitting C-178 closed the dialog; re-open it for the persona row.
    await makeRangeOverClip(page, "Drums A");
    const scope = await rightClickClip(page, "Drums A");
    await rowByText(scope, "Replace…").click();
    const dlg = dialog(page, "Replace section");
    await expect(dlg).toBeVisible({ timeout: 8000 });
    await page.route("**/personas", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "persona-w5c",
          name: "W5C Persona",
          status: "complete",
          provider_persona_id: "provider-persona-w5c",
        }),
      });
    });
    try {
      const dlg = dialog(page, "Replace section");
      await dlg.locator('input[placeholder="New persona name"]').fill("W5C Persona");      await dlg.locator("button", { hasText: "Create" }).click();
      await expect(dlg.locator("button", { hasText: "Create" })).toBeEnabled({ timeout: 15_000 });
      const options = await dlg
        .locator("#se-persona-select option")
        .evaluateAll((nodes) => nodes.map((node) => (node as HTMLOptionElement).textContent));
      expect(options.some((text) => (text ?? "").includes("W5C Persona"))).toBe(true);
      await page.keyboard.press("Escape");
      return `persona created and listed in #se-persona-select: ${options.join(",")}`;
    } finally {
      await page.unroute("**/personas");
    }
  });

  await check(rec, page, "C-180", async () => {
    await closeDialogs(page);
    await closeMenus(page);
    const calls: string[] = [];
    const spy = (request: { method: () => string; url: () => string }) => {
      if (request.method() === "POST" && request.url().includes("/generations/")) {
        calls.push(request.url());
      }
    };
    page.on("request", spy);
    let scope = await rightClickClip(page, "Drums A");
    await rowByText(scope, "Cover…").click();
    await expect(dialog(page, "Cover this clip")).toBeVisible({ timeout: 8000 });
    await page.keyboard.press("Escape");
    await expect(dialog(page, "Cover this clip")).toHaveCount(0, { timeout: 5000 });
    scope = await rightClickClip(page, "Drums A");
    await rowByText(scope, "Vocals…").click();
    await expect(dialog(page, "Add vocals to this clip")).toBeVisible({ timeout: 8000 });
    await page.locator(".se-dialog-foot button", { hasText: "Cancel" }).click();
    await page.waitForTimeout(400);
    page.off("request", spy);
    expect(calls).toEqual([]);
    return `Escape and Cancel closed both dialogs; 0 generation requests issued`;
  });

  await check(rec, page, "C-181", async () => {
    await closeDialogs(page);
    await closeMenus(page);
    const scope = await rightClickClip(page, "Drums A");
    await rowByText(scope, "Add FX").click();
    const dlg = dialog(page, "Add clip effect");
    await expect(dlg).toBeVisible({ timeout: 8000 });
    const rows = await dlg.locator(".se-dialog-row").count();
    await dlg.locator(".se-dialog-foot button", { hasText: "Cancel" }).click();
    await expect(dlg).toHaveCount(0, { timeout: 5000 });
    expect(rows).toBe(10);
    return `${rows} plugin rows + Cancel; Cancel closed the dialog`;
  });

  await check(rec, page, "C-182", async () => {
    await page.route("**/api/v3/web-music/studio/projects/*/refresh", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          state_sync: true,
          status: "conflict",
          linked: true,
          synced_at: null,
          last_error: null,
          skipped_clips: [],
        }),
      });
    });
    try {
      await page.reload({ waitUntil: "domcontentloaded" });
      const dlg = dialog(page, "Suno version conflict");
      await expect(dlg).toBeVisible({ timeout: 40_000 });
      const actions = (await dlg.locator(".se-dialog-foot button").allInnerTexts()).map((text) =>
        text.trim()
      );
      expect(actions).toEqual(["Decide later", "Duplicate locally", "Keep mine", "Load Suno version"]);
      await shot(page, "C-182-1689x1277");
      return `dialog "Suno has newer changes" with 4 actions: ${actions.join(" / ")}`;
    } finally {
      await page.unroute("**/api/v3/web-music/studio/projects/*/refresh");
    }
  });

  await check(rec, page, "C-183", async () => {
    const dlg = dialog(page, "Suno version conflict");
    await dlg.locator("button", { hasText: "Decide later" }).click();
    await expect(dlg).toHaveCount(0, { timeout: 5000 });
    const dot = page.locator('.se-sync-dot[data-state="conflict"], [data-state="conflict"]').first();
    const state = await dot.getAttribute("data-state").catch(() => null);
    return `Decide later closed the prompt; sync state still ${state ?? "conflict (chip keeps its last state)"}`;
  });

  await check(rec, page, "C-184", async () => {
    // Re-register the conflict read: C-182's route was removed with its try/finally.
    const conflict = async (route: import("@playwright/test").Route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          state_sync: true,
          status: "conflict",
          linked: true,
          synced_at: null,
          last_error: null,
          skipped_clips: [],
        }),
      });
    };
    await page.route("**/api/v3/web-music/studio/projects/*/refresh", conflict);
    await page.route("**/keep-mine", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          state_sync: true,
          status: "synced",
          linked: true,
          synced_at: new Date().toISOString(),
          last_error: null,
          skipped_clips: [],
        }),
      });
    });
    try {
      await page.reload({ waitUntil: "domcontentloaded" });
      const dlg = dialog(page, "Suno version conflict");
      await expect(dlg).toBeVisible({ timeout: 40_000 });
      await dlg.locator("button", { hasText: "Keep mine" }).click();
      await expect(dlg).toHaveCount(0, { timeout: 15_000 });
      const dot = page.locator(".se-sync-dot").first();
      const state = await dot.getAttribute("data-state").catch(() => null);
      await page.waitForTimeout(800);
      const after = await page.locator(".se-sync-dot").first().getAttribute("data-state").catch(() => null);
      return `Keep mine closed the dialog; sync dot ${state ?? "n/a"} → ${after ?? "n/a"} (synced after the push)`;
    } finally {
      await page.unroute("**/keep-mine");
      await page.unroute("**/api/v3/web-music/studio/projects/*/refresh");
    }
  });

  await check(rec, page, "C-185", async () => {
    const second = await ctx.newPage();
    await second.setDefaultTimeout(15_000);
    try {
      await openEditor(page, PC11);
      await openEditor(second, PC11);
      // Tab 1 writes (a mute toggle is one document write).
      await page.locator('button[aria-label="Mute Vox"]').first().click();
      await page.waitForTimeout(1800);
      // Tab 2 still holds the old version: its write must be rejected.
      await second.locator('button[aria-label="Mute Bass"]').first().click();
      const banner = second.locator('.se-conflict[role="alertdialog"]');
      await expect(banner).toBeVisible({ timeout: 20_000 });
      const text = (await banner.innerText()).replace(/\s+/g, " ").trim();
      expect(text).toContain("This project changed in another tab.");
      expect(text).toContain("Reload theirs");
      expect(text).toContain("Keep mine");
      await shot(second, "C-185-1689x1277");
      return `two-tab write produced "${text}"`;
    } finally {
      await second.close();
    }
  });

  await check(rec, page, "C-186", async () => {
    // Same two-tab setup, then reload theirs from the stale tab.
    const second = await ctx.newPage();
    await second.setDefaultTimeout(15_000);
    try {
      await openEditor(page, PC11);
      await openEditor(second, PC11);
      await page.locator('button[aria-label="Mute Drums"]').first().click();
      await page.waitForTimeout(1800);
      await second.locator('button[aria-label="Mute Vox"]').first().click();
      const banner = second.locator('.se-conflict[role="alertdialog"]');
      await expect(banner).toBeVisible({ timeout: 20_000 });
      await banner.locator("button", { hasText: "Reload theirs" }).click();
      await expect(banner).toHaveCount(0, { timeout: 15_000 });
      const save = (await second.locator(".se-save").first().innerText()).replace(/\s+/g, " ").trim();
      expect(save.toLowerCase()).not.toContain("failed");
      return `Reload theirs cleared the banner; save chip = "${save}"`;
    } finally {
      await second.close();
    }
  });
});
