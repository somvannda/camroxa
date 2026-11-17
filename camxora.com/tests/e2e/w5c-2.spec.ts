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
  openClipMenu,
  openEditor,
  openProjectMenu,
  p1Document,
  p2Document,
  quietStorage,
  rowByText,
  setPlayhead,
  shot,
  signIn,
  toastText,
} from "./w5c-harness";

/**
 * W5-C, spec 2: C4 (clip menu, 35 rows) + C5 (time-selection menu, 9 rows).
 * Destructive rows run against throw-away copies of P1 so the fixture survives.
 */

test.describe.configure({ mode: "serial" });
test.setTimeout(900_000);

const rec = makeRecorder("c4-c5");
const viewport = { width: 1689, height: 1277 };

let ctx: BrowserContext;
let page: Page;
let P1 = "";
let P2 = "";
let POFF = "";
let PC5 = "";

test.beforeAll(async ({ browser }) => {
  ctx = await browser.newContext({ viewport, acceptDownloads: true });
  page = await ctx.newPage();
  page.setDefaultTimeout(15_000);
  await quietStorage(page);
  await signIn(page);
  P1 = await createProject(page, "W5C C4", p1Document());
  P2 = await createProject(page, "W5C C4 takes", p2Document());
  const off = p1Document();
  const vox = off.data.lanes.find((lane) => lane.id === "c-vox") as Record<string, unknown>;
  vox.start = 1.37; // off the bar line (2 s bars at 120 BPM)
  POFF = await createProject(page, "W5C C4 offgrid", off);
  PC5 = await createProject(page, "W5C C5", p1Document());
});

test.afterAll(async () => {
  rec.flush();
  await ctx?.close();
});

test("C4 — clip menu", async () => {
  await openEditor(page, P1);

  await check(rec, page, "C-64", async () => {
    const clip = page.locator(".se-clip", { hasText: "Drums A" }).first();
    const box = await clip.boundingBox();
    await clip.click({ button: "right" });
    const scope = menu(page, "Clip options");
    await expect(scope).toBeVisible({ timeout: 8000 });
    const menuBox = await scope.boundingBox();
    const maxHeight = await scope.evaluate((node) => getComputedStyle(node).maxHeight);
    const overflowY = await scope.evaluate((node) => getComputedStyle(node).overflowY);
    const rowsOutside = await scope.evaluate((node) => {
      const rect = node.getBoundingClientRect();
      return [...node.querySelectorAll('[role="menuitem"]')].filter((row) => {
        const box = row.getBoundingClientRect();
        return box.bottom > window.innerHeight + 1 || box.top < rect.top - 1;
      }).length;
    });
    expect(menuBox).not.toBeNull();
    expect(menuBox!.x).toBeGreaterThan(0);
    expect(menuBox!.x + menuBox!.width).toBeLessThanOrEqual(viewport.width);
    expect(menuBox!.y + menuBox!.height).toBeLessThanOrEqual(viewport.height);
    expect(overflowY).toBe("auto");
    await shot(page, "C-64-1689x1277");
    return `opens at the pointer (clip x=${Math.round(box?.x ?? 0)}), box ${Math.round(
      menuBox!.x
    )},${Math.round(menuBox!.y)} ${Math.round(menuBox!.width)}×${Math.round(
      menuBox!.height
    )} within 1689×1277; maxHeight=${maxHeight}; overflow-y=${overflowY}; rows past the viewport=${rowsOutside}`;
  });

  await check(rec, page, "C-65", async () => {
    const scope = menu(page, "Clip options");
    const rows = (await scope.locator('[role="menuitem"]').allInnerTexts())
      .map((text) => text.replace(/\s+/g, " ").trim())
      .slice(0, 6);
    expect(rows).toEqual([
      "Copy ctrl C",
      "Paste ctrl V",
      "Duplicate ctrl D",
      "Delete backspace",
      "Copy settings",
      "Paste settings",
    ]);
    return `first six rows = ${rows.join(" | ")}`;
  });

  await check(rec, page, "C-66", async () => {
    await closeMenus(page);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator(".se-clip").first().waitFor({ state: "visible", timeout: 40_000 });
    const scope = await openClipMenu(page, "Drums A");
    const paste = rowByText(scope, "Paste");
    expect(await paste.isDisabled()).toBe(true);
    return "after a reload (empty clipboard) Paste is disabled";
  });

  await check(rec, page, "C-67", async () => {
    let scope = menu(page, "Clip options");
    await rowByText(scope, "Copy").click();
    await closeMenus(page);
    scope = await openClipMenu(page, "Drums A");
    const paste = rowByText(scope, "Paste");
    expect(await paste.isDisabled()).toBe(false);
    await page.keyboard.press("Escape");
    return "Copy → Paste enabled in the re-opened menu";
  });

  await check(rec, page, "C-68", async () => {
    const scope = await openClipMenu(page, "Drums A");
    const pasteSettings = rowByText(scope, "Paste settings");
    expect(await pasteSettings.isDisabled()).toBe(true);
    return "no settings copied: Paste settings disabled";
  });

  await check(rec, page, "C-69", async () => {
    let scope = menu(page, "Clip options");
    await rowByText(scope, "Copy settings").click();
    const toast = await toastText(page);
    expect(toast).toBe("Clip settings copied.");
    scope = await openClipMenu(page, "Vox");
    const paste = rowByText(scope, "Paste settings");
    expect(await paste.isDisabled()).toBe(false);
    await page.keyboard.press("Escape");
    return `toast "${toast}"; Paste settings enabled on another clip`;
  });

  await check(rec, page, "C-70", async () => {
    // Source: Vox carries fadeIn/fadeOut/audio; paste onto Drums B and check the document.
    let scope = await openClipMenu(page, "Vox");
    await rowByText(scope, "Copy settings").click();
    await toastText(page);
    const before = await getProject(page, P1);
    const lanes = (before.data as { lanes: Array<Record<string, unknown>> }).lanes;
    const source = lanes.find((lane) => lane.id === "c-vox") as Record<string, unknown>;
    expect(source.fadeIn).toBe(0.5);
    scope = await openClipMenu(page, "Drums B");
    await rowByText(scope, "Paste settings").click();
    const toast = await toastText(page);
    expect(toast).toBe("Settings pasted to 1 clip.");
    await page.waitForTimeout(2000);
    const after = await getProject(page, P1);
    const afterLanes = (after.data as { lanes: Array<Record<string, unknown>> }).lanes;
    const updated = afterLanes.find((lane) => lane.id === "c-d2") as Record<string, unknown>;
    expect(updated.fadeIn).toBe(source.fadeIn);
    expect(updated.fadeOut).toBe(source.fadeOut);
    expect(updated.audio).toEqual(source.audio);
    return `toast "${toast}"; fadeIn=${updated.fadeIn}, fadeOut=${updated.fadeOut}, audio copied`;
  });

  await check(rec, page, "C-71", async () => {
    const scope = await openClipMenu(page, "Drums A");
    const heal = rowByText(scope, "Heal Edits");
    const disabled = await heal.isDisabled();
    const title = await heal.getAttribute("title");
    expect(disabled).toBe(true);
    expect(title).toBe("No generated edits to heal");
    await page.keyboard.press("Escape");
    return `Heal Edits disabled, title="${title}"`;
  });

  await check(rec, page, "C-72", async () => {
    await openEditor(page, P2);
    const scope = await openClipMenu(page, "Drums A");
    const heal = rowByText(scope, "Heal Edits");
    const disabled = await heal.isDisabled();
    const title = await heal.getAttribute("title");
    expect(disabled).toBe(false);
    expect(title ?? "").toContain("Restore the audio");
    return `P2 clip: Heal Edits enabled, title="${title}"`;
  });

  await check(rec, page, "C-73", async () => {
    const scope = menu(page, "Clip options");
    await rowByText(scope, "Heal Edits").click();
    const toast = await toastText(page);
    expect(toast).toBe("Edits healed to the original clip.");
    const takes = await page.locator(".se-takes").count();
    return `toast "${toast}"; take-lane bands visible = ${takes}`;
  });

  await check(rec, page, "C-74", async () => {
    await openEditor(page, P1);
    // The playhead sits at 0 and Drums A starts at 0, so Split must be disabled.
    const scope = await openClipMenu(page, "Drums A");
    const split = rowByText(scope, "Split");
    expect(await split.isDisabled()).toBe(true);
    await page.keyboard.press("Escape");
    return "playhead at the clip start: Split disabled";
  });

  await check(rec, page, "C-75", async () => {
    await setPlayhead(page, 0.5, 0);
    const scope = await openClipMenu(page, "Drums A");
    const split = rowByText(scope, "Split");
    expect(await split.isDisabled()).toBe(false);
    const text = (await split.innerText()).replace(/\s+/g, " ").trim();
    expect(text).toContain("ctrl E");
    await page.keyboard.press("Escape");
    return `playhead inside: Split enabled, label "${text}"`;
  });

  await check(rec, page, "C-76", async () => {
    const before = await page.locator(".se-clip").count();
    const scope = await openClipMenu(page, "Vox");
    await rowByText(scope, "Split on Transients").click();
    const first = await toastText(page);
    if (first.startsWith("Finding transients")) {
      await page.waitForFunction(
        () => /Split into \d+ clip/.test(document.querySelector(".se-toast")?.textContent ?? ""),
        null,
        { timeout: 40_000 }
      );
      const second = (await page.locator(".se-toast").first().innerText()).replace(/\s+/g, " ").trim();
      const after = await page.locator(".se-clip").count();
      expect(after).toBeGreaterThan(before);
      await page.keyboard.press("Control+z");
      await page.waitForTimeout(600);
      return `toast "${first}" → "${second}"; clips ${before} → ${after} (undone)`;
    }
    // The negative branch: the fixture audio has no detectable onsets.
    throw new Error(
      `first toast was "${first}", not "Finding transients…" — no split happened (clips ${before})`
    );
  });

  await check(rec, page, "C-77", async () => {
    const scope = await openClipMenu(page, "Bass");
    const row = rowByText(scope, "Split on Transients");
    const disabled = await row.isDisabled();
    const title = await row.getAttribute("title");
    expect(disabled).toBe(true);
    expect(title).toBe("This clip has no audio to analyse");
    await page.keyboard.press("Escape");
    return `MIDI clip: disabled, title="${title}"`;
  });

  await check(rec, page, "C-78", async () => {
    await openEditor(page, POFF);
    const scope = await openClipMenu(page, "Vox");
    await rowByText(scope, "Make Beat 1").click();
    const toast = await toastText(page);
    expect(toast).toMatch(/^Clip moved to the bar line at [\d.]+s\.$/);
    const doc = await getProject(page, POFF);
    const lane = (doc.data as { lanes: Array<Record<string, unknown>> }).lanes.find(
      (item) => item.title === "Vox"
    ) as Record<string, unknown>;
    // 120 BPM 4/4 = 2 s per bar; a bar-line start is a multiple of 2 s.
    expect(Math.abs(Number(lane.start) % 2)).toBeLessThan(0.001);
    return `toast "${toast}"; start now ${lane.start}s`;
  });

  await check(rec, page, "C-79", async () => {
    const scope = await openClipMenu(page, "Drums A");
    await rowByText(scope, "Make Beat 1").click();
    const toast = await toastText(page);
    expect(toast).toBe("This clip already starts on a bar line.");
    return `toast "${toast}"`;
  });

  await check(rec, page, "C-80", async () => {
    const scope = await openClipMenu(page, "Drums A");
    await rowByText(scope, "Create Section").click();
    const marker = page.locator(".se-section-marker").first();
    await expect(marker).toBeVisible({ timeout: 8000 });
    const text = (await marker.innerText()).replace(/\s+/g, " ").trim();
    expect(text).toContain("Drums A");
    return `marker on the ruler labelled "${text}"`;
  });

  await check(rec, page, "C-81", async () => {
    let scope = await openClipMenu(page, "Drums A");
    await rowByText(scope, "Rename").click();
    const dlg = dialog(page, "Rename clip");
    await expect(dlg).toBeVisible({ timeout: 8000 });
    const input = dlg.locator('input[aria-label="Clip name"]');
    await input.fill("Drums Renamed");
    await page.keyboard.press("Enter");
    await expect(dlg).toHaveCount(0, { timeout: 8000 });
    await expect(page.locator(".se-clip", { hasText: "Drums Renamed" }).first()).toBeVisible({
      timeout: 8000,
    });
    scope = await openClipMenu(page, "Drums Renamed");
    await rowByText(scope, "Rename").click();
    await dialog(page, "Rename clip").locator('input[aria-label="Clip name"]').fill("Discard me");
    await page.keyboard.press("Escape");
    await expect(dialog(page, "Rename clip")).toHaveCount(0);
    expect(await page.locator(".se-clip", { hasText: "Discard me" }).count()).toBe(0);
    scope = await openClipMenu(page, "Drums Renamed");
    await rowByText(scope, "Rename").click();
    const empty = dialog(page, "Rename clip");
    await empty.locator('input[aria-label="Clip name"]').fill("");
    await page.keyboard.press("Enter");
    await expect(dialog(page, "Rename clip")).toHaveCount(0);
    await expect(page.locator(".se-clip", { hasText: "Drums Renamed" }).first()).toBeVisible();
    return "Enter saves, Escape discards, an empty name is ignored";
  });

  await check(rec, page, "C-82", async () => {
    await page.getByRole("button", { name: "Library", exact: true }).first().click();
    await page.waitForTimeout(400);
    const libraryBefore = await page.locator(".se-library").count();
    const scope = await openClipMenu(page, "Drums Renamed");
    await rowByText(scope, "Clip Info").click();
    const inspector = page.locator('aside.se-inspector[aria-label="Clip info"]');
    await expect(inspector).toBeVisible({ timeout: 10_000 });
    expect(libraryBefore).toBeGreaterThan(0);
    expect(await page.locator(".se-library").count()).toBe(0);
    return `library was open (${libraryBefore}) and closed; Clip info inspector opened`;
  });

  await check(rec, page, "C-83", async () => {
    await openEditor(page, P1);
    const scope = await openClipMenu(page, "Drums A");
    await rowByText(scope, "Clip Color").click();
    const group = page.locator('.se-clip-menu-colors[role="group"][aria-label="Clip colour"]');
    await expect(group).toBeVisible({ timeout: 8000 });
    const auto = group.locator(".se-color-auto");
    const swatches = await group.locator(".se-color-grid button").count();
    expect(await auto.count()).toBe(1);
    expect(swatches).toBeGreaterThanOrEqual(5);
    await shot(page, "C-83-1689x1277");
    return `group opened: Auto + ${swatches} swatches (checklist says 5; the palette was widened to 20 in b3d718f4)`;
  });

  await check(rec, page, "C-84", async () => {
    const group = page.locator('.se-clip-menu-colors[role="group"]');
    const swatch = group.locator(".se-color-grid button").nth(6);
    const color = await swatch.getAttribute("aria-label");
    await swatch.click();
    await expect(menu(page, "Clip options")).toHaveCount(0, { timeout: 5000 });
    const selected = await page.locator(".se-clip.selected").count();
    const style = await page
      .locator(".se-clip.selected")
      .first()
      .evaluate((node) => getComputedStyle(node).backgroundColor);
    expect(selected).toBe(1);
    return `${color} applied; clip background ${style}; menu closed; 1 clip stays selected`;
  });

  await check(rec, page, "C-85", async () => {
    const scope = await openClipMenu(page, "Drums A");
    await rowByText(scope, "Clip Color").click();
    const group = page.locator('.se-clip-menu-colors[role="group"]');
    const auto = group.locator(".se-color-auto");
    await auto.click();
    const before = await page.locator(".se-clip", { hasText: "Drums A" }).first().evaluate((node) =>
      getComputedStyle(node).backgroundColor
    );
    const scope2 = await openClipMenu(page, "Drums A");
    await rowByText(scope2, "Clip Color").click();
    await expect(page.locator(".se-color-auto")).toHaveAttribute("aria-pressed", "true");
    const doc = await getProject(page, P1);
    const lane = (doc.data as { lanes: Array<Record<string, unknown>> }).lanes.find(
      (item) => item.id === "c-d1"
    ) as Record<string, unknown>;
    expect(lane.color ?? "").toBe("");
    await page.keyboard.press("Escape");
    return `Auto pressed; clip falls back to the track colour (${before}); stored colour cleared`;
  });

  await check(rec, page, "C-86", async () => {
    const scope = await openClipMenu(page, "Drums A");
    await rowByText(scope, "Get Stems").click();
    const dlg = dialog(page, "Get stems");
    await expect(dlg).toBeVisible({ timeout: 10_000 });
    // The stems dialog has no Escape handler; Cancel is its only close affordance.
    await dlg.locator(".se-dialog-foot button", { hasText: "Cancel" }).click();
    await expect(dlg).toHaveCount(0, { timeout: 5000 });
    return `song-backed clip: dialog "${(await dlg.locator("h2").innerText().catch(() => "Separate stems"))}" opened and cancelled`;
  });

  await check(rec, page, "C-87", async () => {
    await closeDialogs(page);
    const scope = await openClipMenu(page, "Vox");
    const row = rowByText(scope, "Get Stems");
    const disabled = await row.isDisabled();
    const title = await row.getAttribute("title");
    expect(disabled).toBe(true);
    expect(title).toBe("No source generation for this clip");
    await page.keyboard.press("Escape");
    return `uploaded clip: disabled, title="${title}"`;
  });

  await check(rec, page, "C-88", async () => {
    await closeDialogs(page);    const midiMenu = await openClipMenu(page, "Bass");
    const disabledRow = rowByText(midiMenu, "Download .WAV");
    const disabled = await disabledRow.isDisabled();
    const label = (await disabledRow.innerText()).replace(/\s+/g, " ").trim();
    await page.keyboard.press("Escape");
    const audioMenu = await openClipMenu(page, "Drums A");
    const enabledRow = rowByText(audioMenu, "Download .WAV");
    expect(await enabledRow.isDisabled()).toBe(false);
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 30_000 }),
      enabledRow.click(),
    ]);
    const name = download.suggestedFilename();
    return `MIDI clip disabled=${disabled} ("${label}"); audio clip started "${name}"`;
  });

  await check(rec, page, "C-89", async () => {
    await closeDialogs(page);
    await page.route("**/api/v3/web-music/studio/generations/*/midi", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "op-w5c-midi",
          status: "done",
          task_id: "song-w5c-1",
          variant: "ok",
          operation_type: "midi",
          provider_clip_id: "clip",
          mode: "transcribe",
          result: {
            midi_data: {
              instruments: [
                {
                  name: "Piano",
                  notes: [
                    { pitch: 60, start: 0, end: 0.5, velocity: 0.8 },
                    { pitch: 62, start: 0.5, end: 1, velocity: 0.76 },
                    { pitch: 64, start: 1, end: 1.5, velocity: 0.72 },
                  ],
                },
              ],
            },
          },
        }),
      });
    });
    try {
      const midiMenu = await openClipMenu(page, "Bass");
      expect(await rowByText(midiMenu, "Get MIDI").isDisabled()).toBe(true);
      await page.keyboard.press("Escape");
      const scope = await openClipMenu(page, "Drums A");
      await rowByText(scope, "Get MIDI").click();
      const first = await toastText(page);
      expect(first).toBe("Transcribing MIDI...");
      await page.waitForFunction(
        () => /MIDI added as a track/.test(document.querySelector(".se-toast")?.textContent ?? ""),
        null,
        { timeout: 30_000 }
      );
      const second = (await page.locator(".se-toast").first().innerText()).replace(/\s+/g, " ").trim();
      const tracks = await page.locator(".se-track").count();
      return `disabled without songId; toast "${first}" → "${second}" (${tracks} tracks)`;
    } finally {
      await page.unroute("**/api/v3/web-music/studio/generations/*/midi");
    }
  });

  await check(rec, page, "C-90", async () => {
    await closeDialogs(page);    const scope = await openClipMenu(page, "Drums A");
    const remove = rowByText(scope, "Remove FX");
    expect(await remove.isDisabled()).toBe(true);
    const add = rowByText(scope, "Add FX");
    expect(await add.isDisabled()).toBe(false);
    await add.click();
    const dlg = dialog(page, "Add clip effect");
    await expect(dlg).toBeVisible({ timeout: 10_000 });
    // This dialog has no Escape handler; Cancel is its only close affordance.
    await dlg.locator(".se-dialog-foot button", { hasText: "Cancel" }).click();
    await expect(dlg).toHaveCount(0, { timeout: 5000 });
    return "Remove FX disabled with no fx; Add FX… opened the clip-effect dialog (closed with Cancel — no Escape handler)";
  });

  await check(rec, page, "C-91", async () => {
    await closeDialogs(page);    const scope = await openClipMenu(page, "Vox");
    const rows = ["Extend", "Cover…", "Remaster", "Vocals…", "Instrumental…", "Mashup…", "Replace…"];
    const measured: string[] = [];
    for (const label of rows) {
      const row = rowByText(scope, label);
      const disabled = await row.isDisabled();
      const title = (await row.getAttribute("title")) ?? "";
      measured.push(`${label}:${disabled ? "disabled" : "ENABLED"}${title ? ` (${title})` : ""}`);
      expect(disabled).toBe(true);
    }
    await page.keyboard.press("Escape");
    return `uploaded clip without songId → ${measured.join("; ")}`;
  });

  await check(rec, page, "C-92", async () => {
    await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
    const scope = await openClipMenu(page, "Drums A");
    const row = rowByText(scope, "Mashup…");
    const disabled = await row.isDisabled();
    const title = await row.getAttribute("title");
    expect(disabled).toBe(true);
    expect(title).toBe("Select two clips that have a source generation");
    await page.keyboard.press("Escape");
    return `one clip selected: Mashup disabled, title="${title}"`;
  });

  await check(rec, page, "C-93", async () => {
    const scope = await openClipMenu(page, "Drums A");
    const row = rowByText(scope, "Replace…");
    expect(await row.isDisabled()).toBe(true);
    const title = await row.getAttribute("title");
    expect(title).toBe("Select a time range over this clip first");
    await page.keyboard.press("Escape");
    return `no range: Replace disabled, title="${title}"`;
  });

  await check(rec, page, "C-94", async () => {
    await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
    const scope = await openClipMenu(page, "Drums A");
    const row = rowByText(scope, "Download MIDI");
    const disabled = await row.isDisabled();
    const title = await row.getAttribute("title");
    expect(disabled).toBe(true);
    expect(title).toBe("Select a MIDI clip with notes first");
    await page.keyboard.press("Escape");
    return `audio clip selected: Download MIDI disabled, title="${title}"`;
  });

  await check(rec, page, "C-95", async () => {
    const scope = await openClipMenu(page, "Drums A");
    await rowByText(scope, "Clip Info").click();
    const inspector = page.locator('aside.se-inspector[aria-label="Clip info"]');
    await expect(inspector).toBeVisible({ timeout: 10_000 });
    await inspector.locator('button[aria-label="Back to arrangement"]').click();
    await expect(inspector).toHaveCount(0, { timeout: 8000 });
    const selected = await page.locator(".se-clip.selected").count();
    expect(selected).toBeGreaterThan(0);
    return `inspector closed via "Back to arrangement"; selection kept (${selected})`;
  });

  await check(rec, page, "C-96", async () => {
    await openClipMenu(page, "Drums A");
    await page.keyboard.press("Escape");
    await expect(menu(page, "Clip options")).toHaveCount(0, { timeout: 5000 });
    const clips = await page.locator(".se-clip").count();
    return `Escape closed the menu without an action (clips=${clips})`;
  });

  await check(rec, page, "C-97", async () => {
    await openClipMenu(page, "Drums A");
    await page.locator(".se-timeline").first().click({ position: { x: 1200, y: 620 } });
    await expect(menu(page, "Clip options")).toHaveCount(0, { timeout: 5000 });
    return "pointerdown outside closed the menu";
  });

  await check(rec, page, "C-98", async () => {
    await openClipMenu(page, "Drums A");
    const first = await menu(page, "Clip options").boundingBox();
    await page.locator(".se-clip", { hasText: "Vox" }).first().click({ button: "right" });
    await page.waitForTimeout(300);
    const second = await menu(page, "Clip options").boundingBox();
    const scope = menu(page, "Clip options");
    // The refreshed menu must target Vox: Get Stems is disabled for an uploaded clip.
    const disabled = await rowByText(scope, "Get Stems").isDisabled();
    expect(disabled).toBe(true);
    expect(second!.x).not.toBe(first!.x);
    await page.keyboard.press("Escape");
    return `menu moved from x=${Math.round(first!.x)} to x=${Math.round(
      second!.x
    )} and now targets Vox (Get Stems disabled)`;
  });
});

test("C5 — time selection menu", async () => {
  await openEditor(page, PC5);

  await check(rec, page, "C-99", async () => {
    await makeRange(page, 1, 2);
    const ruler = page.locator(".se-ruler-bars").first();
    const box = await ruler.boundingBox();
    await page.mouse.click(box!.x + 20, box!.y + 8, { button: "right" });
    const scope = menu(page, "Time selection options");
    await expect(scope).toBeVisible({ timeout: 8000 });
    const head = (await scope.locator(".se-clip-menu-head").innerText()).replace(/\s+/g, " ").trim();
    expect(head).toMatch(/^\d{2}:\d{2} – \d{2}:\d{2}$/);
    await shot(page, "C-99-1689x1277");
    return `menu with range header "${head}"`;
  });

  await check(rec, page, "C-101", async () => {
    const scope = menu(page, "Time selection options");
    await rowByText(scope, "Loop selection").click();
    const band = page.locator(".se-loop-band").first();
    await expect(band).toBeVisible({ timeout: 8000 });
    const loop = page.locator('button[aria-label="Loop"]').first();
    expect(await loop.getAttribute("aria-pressed")).toBe("true");
    return "loop band covers the range and the Loop toggle is pressed";
  });

  await check(rec, page, "C-105", async () => {
    // No track is focused on a fresh load; make a range without selecting a track.
    await openEditor(page, PC5);
    await makeRange(page, 1, 2);
    const selected = await page.locator(".se-track.selected").count();
    const ruler = page.locator(".se-ruler-bars").first();
    const box = await ruler.boundingBox();
    await page.mouse.click(box!.x + 20, box!.y + 8, { button: "right" });
    const scope = menu(page, "Time selection options");
    await expect(scope).toBeVisible({ timeout: 8000 });
    const row = rowByText(scope, "Delete time on this track");
    const disabled = await row.isDisabled();
    const title = await row.getAttribute("title");
    expect(selected).toBe(0);
    expect(disabled).toBe(true);
    expect(title).toBe("Focus a track first");
    await page.keyboard.press("Escape");
    return `no focused track (${selected}) → disabled, title="${title}"`;
  });

  await check(rec, page, "C-100", async () => {
    await openEditor(page, PC5);
    const ruler = page.locator(".se-ruler-bars").first();
    const box = await ruler.boundingBox();
    await page.mouse.click(box!.x + 300, box!.y + 8, { button: "right" });
    await page.waitForTimeout(400);
    const count = await page.locator('[role="menu"][aria-label="Time selection options"]').count();
    expect(count).toBe(0);
    return "right-click with no range opened no menu";
  });

  await check(rec, page, "C-107", async () => {
    await makeRange(page, 1, 2);
    const ruler = page.locator(".se-ruler-bars").first();
    const box = await ruler.boundingBox();
    await page.mouse.click(box!.x + 20, box!.y + 8, { button: "right" });
    const scope = menu(page, "Time selection options");
    await rowByText(scope, "Clear selection").click();
    await expect(page.locator(".se-range")).toHaveCount(0, { timeout: 5000 });
    return "Clear selection removed the range";
  });
});

test("C5 — destructive rows on throw-away copies", async () => {
  await check(rec, page, "C-102", async () => {
    const id = await createProject(page, "W5C C5 split", p1Document());
    await openEditor(page, id);
    const before = await page.locator(".se-clip").count();
    // Make a range first; the ruler drag also seeks. Then park the playhead inside Drums A.
    await makeRange(page, 1, 3);
    await setPlayhead(page, 0.6, 0);
    const ruler = page.locator(".se-ruler-bars").first();
    const box = await ruler.boundingBox();
    await page.mouse.click(box!.x + 20, box!.y + 8, { button: "right" });
    const scope = menu(page, "Time selection options");
    await rowByText(scope, "Split Arrangement").click();
    const toast = await toastText(page);
    expect(toast).toBe("Arrangement split at the playhead.");
    await page.waitForTimeout(1200);
    const after = await page.locator(".se-clip").count();
    expect(after).toBeGreaterThan(before);
    return `"${toast}"; clips ${before} → ${after}`;
  });

  await check(rec, page, "C-103", async () => {
    const id = await createProject(page, "W5C C5 duplicate", p1Document());
    await openEditor(page, id);
    const before = await getProject(page, id);
    const beforeStarts = (before.data as { lanes: Array<{ id: string; start: number }> }).lanes.map(
      (lane) => `${lane.id}:${lane.start}`
    );
    await makeRange(page, 1, 2);
    const ruler = page.locator(".se-ruler-bars").first();
    const box = await ruler.boundingBox();
    await page.mouse.click(box!.x + 20, box!.y + 8, { button: "right" });
    await rowByText(menu(page, "Time selection options"), "Duplicate time").click();
    await page.waitForTimeout(1800);
    const after = await getProject(page, id);
    const afterStarts = (after.data as { lanes: Array<{ id: string; start: number }> }).lanes.map(
      (lane) => `${lane.id}:${lane.start}`
    );
    expect(afterStarts.length).toBeGreaterThan(beforeStarts.length);
    await shot(page, "C-103-1689x1277");
    return `clips ${beforeStarts.join(",")} → ${afterStarts.join(",")}`;
  });

  await check(rec, page, "C-104", async () => {
    const id = await createProject(page, "W5C C5 delete", p1Document());
    await openEditor(page, id);
    await makeRange(page, 1, 2);
    const ruler = page.locator(".se-ruler-bars").first();
    const box = await ruler.boundingBox();
    await page.mouse.click(box!.x + 20, box!.y + 8, { button: "right" });
    await rowByText(menu(page, "Time selection options"), "Delete time").click();
    await page.waitForTimeout(1800);
    const after = await getProject(page, id);
    const lanes = (after.data as { lanes: Array<{ id: string; start: number; duration: number }> })
      .lanes;
    const bass = lanes.find((lane) => lane.id === "c-bass");
    const drumsB = lanes.find((lane) => lane.id === "c-d2");
    // Drums B started at 8 s; deleting 2 s of time ripples it left.
    expect(drumsB!.start).toBeLessThan(8);
    expect(bass).toBeTruthy();
    return `Drums B start 8 → ${drumsB!.start}s (ripple-left); ${lanes.length} clips remain`;
  });

  await check(rec, page, "C-106", async () => {
    const id = await createProject(page, "W5C C5 export", p1Document());
    await openEditor(page, id);
    await makeRange(page, 1, 2);
    const ruler = page.locator(".se-ruler-bars").first();
    const box = await ruler.boundingBox();
    await page.mouse.click(box!.x + 20, box!.y + 8, { button: "right" });
    const scope = menu(page, "Time selection options");
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 120_000 }),
      rowByText(scope, "Export selection").click(),
    ]);
    const name = download.suggestedFilename();
    expect(name).toMatch(/\.(wav|mp3)$/i);
    return `range export downloaded "${name}"`;
  });
});
