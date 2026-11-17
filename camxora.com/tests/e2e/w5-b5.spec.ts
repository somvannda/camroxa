import { test, expect, type Page } from "@playwright/test";
import {
  addPlugin,
  createProject,
  makeRecorder,
  openCatalog,
  openDock,
  openProject,
  p1Document,
  quietHelp,
  readAll,
  restoreChain,
  savedProject,
  setRangeInput,
  selectTrack,
  setKnob,
  shot,
  signIn,
  slot,
  waitSaved,
} from "./w5-harness";

/**
 * W5 independent manual run - area B, sections B16-B19 (20 checks):
 * IR designer, wavetable designer, clip-owned FX, sends.
 */

const REC = makeRecorder("b");
const VP = "1689x1277";

let P1 = "";
let page: Page;

async function check(id: string, plan: string, fn: () => Promise<string>) {
  try {
    const evidence = await fn();
    REC.record(id, "PASS", evidence);
  } catch (error) {
    const file = await shot(page, `${id}-${VP}`);
    REC.fail(id, error instanceof Error ? error.message : String(error), `${plan} - ${file}`);
  }
}

async function setAdvanced(on: boolean, projectId = P1) {
  await page.evaluate((next) => {
    const raw = window.localStorage.getItem("studio:settings");
    const parsed = raw ? JSON.parse(raw) : {};
    window.localStorage.setItem(
      "studio:settings",
      JSON.stringify({ ...parsed, advancedContent: next })
    );
  }, on);
  await page.reload();
  await openProject(page, projectId);
}

async function openConvolutionPicker() {
  await slot(page, "Convolution").locator("button[aria-label='Impulse response']").click();
  await expect(page.locator(".sp-ir-menu[aria-label='Impulse responses']")).toBeVisible();
}

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ browser }) => {
  test.setTimeout(240_000);
  page = await browser.newPage();
  page.setDefaultTimeout(15_000);
  await quietHelp(page);
  await page.setViewportSize({ width: 1689, height: 1277 });
  page.on("pageerror", (error) => console.log("PAGEERROR", error.message));
  await signIn(page);
  P1 = await createProject(page, "W5 P1 fixture (B16-B19)", p1Document());
});

test.afterAll(async () => {
  REC.flush();
  await page.close();
});

test("B16 impulse response designer", async () => {
  test.setTimeout(6 * 60_000);
  await setAdvanced(true);
  await openDock(page);
  await restoreChain(page);
  await addPlugin(page, "Convolution");
  await openConvolutionPicker();
  await page.locator(".sp-ir-menu").getByRole("menuitem", { name: /Design response/ }).click();
  const dialog = page.locator("[aria-label='Impulse response designer']");
  await expect(dialog).toBeVisible();

  await check("B-119", "the IR designer dialog opens with preview, Name, Length, Decay", async () => {
    await expect(dialog.getByRole("heading", { name: "Impulse Response Designer" })).toBeVisible();
    await expect(dialog.locator("svg.sp-ir")).toBeVisible();
    await expect(dialog.locator("#ir-name")).toBeVisible();
    await expect(dialog.locator("#ir-length")).toBeVisible();
    await expect(dialog.locator("#ir-decay")).toBeVisible();
    return `dialog with preview + #ir-name / #ir-length / #ir-decay`;
  });

  await check("B-120", "IR designer defaults", async () => {
    expect(await dialog.locator("#ir-name").inputValue()).toBe("Custom hall");
    expect(await dialog.locator("#ir-length").inputValue()).toBe("2.4");
    expect(await dialog.locator("#ir-decay").inputValue()).toBe("2.6");
    const length = await dialog.locator("label[for='ir-length']").innerText();
    expect(length).toContain("2.4s");
    return `Name="Custom hall", Length=2.4s, Decay=2.6`;
  });

  await check("B-121", "moving Length/Decay redraws the preview and keeps one decimal", async () => {
    const path = dialog.locator("svg.sp-ir path.sp-ir-wave");
    const before = await path.getAttribute("d");
    await setRangeInput(dialog.locator("#ir-length"), 3.7);
    await setRangeInput(dialog.locator("#ir-decay"), 4.2);
    const after = await path.getAttribute("d");
    expect(after).not.toBe(before);
    const labels = await dialog.locator(".se-dialog-note b").allInnerTexts();
    expect(labels).toEqual(["3.7s", "4.2"]);
    return `preview path changed; labels = ${JSON.stringify(labels)}`;
  });

  await check("B-122", "Save response closes the dialog, selects the IR and files it under Custom", async () => {
    await dialog.getByRole("button", { name: /Save response/ }).click();
    await expect(dialog).toHaveCount(0);
    const label = await slot(page, "Convolution")
      .locator(".sp-ir-picker > button span")
      .innerText();
    expect(label).toContain("Custom hall");
    await openConvolutionPicker();
    const custom = page.locator(".sp-ir-menu .sp-ir-cat", { hasText: "Custom" });
    await expect(custom).toBeVisible();
    await custom.click();
    const rows = await page.locator(".sp-ir-menu [role='menuitem']").allInnerTexts();
    expect(rows.join(" ")).toContain("Custom hall");
    await page.keyboard.press("Escape");
    return `slot label "${label.trim()}"; picker has a Custom group listing it`;
  });

  await check("B-123", "Cancel saves nothing", async () => {
    const before = await slot(page, "Convolution")
      .locator(".sp-ir-picker > button span")
      .innerText();
    await openConvolutionPicker();
    await page.locator(".sp-ir-menu").getByRole("menuitem", { name: /Design response/ }).click();
    await expect(dialog).toBeVisible();
    await dialog.locator("#ir-name").fill("Discarded response");
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toHaveCount(0);
    const after = await slot(page, "Convolution")
      .locator(".sp-ir-picker > button span")
      .innerText();
    expect(after).toBe(before);
    await openConvolutionPicker();
    const rows = await page.locator(".sp-ir-menu [role='menuitem']").allInnerTexts();
    expect(rows.join(" ")).not.toContain("Discarded response");
    await page.keyboard.press("Escape");
    return `asset unchanged ("${before}"); "Discarded response" was not added`;
  });

  await check("B-124", "the custom IR is still listed after a reload (localStorage)", async () => {
    await waitSaved(page);
    await page.reload();
    await openProject(page, P1);
    await openDock(page);
    await openConvolutionPicker();
    const custom = page.locator(".sp-ir-menu .sp-ir-cat", { hasText: "Custom" });
    await expect(custom).toBeVisible();
    await custom.click();
    const rows = await page.locator(".sp-ir-menu [role='menuitem']").allInnerTexts();
    expect(rows.join(" ")).toContain("Custom hall");
    return `after reload the Custom group still lists "Custom hall"`;
  });
});

test("B17 wavetable designer", async () => {
  test.setTimeout(8 * 60_000);
  await setAdvanced(false);
  const openMidi = async () => {
    await page.locator(".se-clip", { hasText: "Bass" }).first().dblclick();
    await expect(page.locator(".se-midi")).toBeVisible({ timeout: 20_000 });
  };

  await check("B-125", "no Design wavetable button while Advanced content is off", async () => {
    await openMidi();
    expect(await page.locator(".se-midi-design").count()).toBe(0);
    return `MIDI editor open, .se-midi-design absent`;
  });

  await check("B-126", "Advanced content on reveals Design wavetable", async () => {
    await setAdvanced(true);
    await openMidi();
    await expect(page.locator(".se-midi-design")).toBeVisible();
    return `.se-midi-design visible`;
  });

  await check("B-127", "the designer dialog lists presets and every partial", async () => {
    await page.locator(".se-midi-design").click();
    const dialog = page.locator("[aria-label='Wavetable designer']");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { name: "Wavetable Designer" })).toBeVisible();
    await expect(dialog.locator(".se-wavetable-presets")).toBeVisible();
    const partials = await dialog
      .locator(".se-wavetable-partials input[aria-label^='Partial ']")
      .count();
    expect(partials).toBeGreaterThanOrEqual(4);
    return `${partials} partial sliders + presets group`;
  });

  await check("B-128", "a shape preset snaps every partial and redraws the preview", async () => {
    const dialog = page.locator("[aria-label='Wavetable designer']");
    const preview = dialog.locator(".se-wavetable-preview path");
    const before = await preview.getAttribute("d");
    const preset = dialog.locator(".se-wavetable-presets button").nth(1);
    const name = await preset.innerText();
    await preset.click();
    const after = await preview.getAttribute("d");
    expect(after).not.toBe(before);
    const values = await dialog
      .locator(".se-wavetable-partials input")
      .evaluateAll((nodes) => nodes.map((n) => (n as HTMLInputElement).value));
    expect(new Set(values).size).toBeGreaterThan(1);
    return `preset "${name}" redrew the preview; partials = ${JSON.stringify(values.slice(0, 5))}`;
  });

  await check("B-129", "partial 1 at 0 flattens the wave; at 100 it is a sine", async () => {
    const dialog = page.locator("[aria-label='Wavetable designer']");
    // Isolate partial 1: zero every other partial first (the shipped presets are all
    // multi-partial shapes, so "flattens" is only true of a single-partial wave).
    for (let index = 2; index <= 16; index += 1) {
      await setRangeInput(dialog.locator(`input[aria-label='Partial ${index}']`), 0);
    }
    const preview = dialog.locator(".se-wavetable-preview path");
    const partial = dialog.locator("input[aria-label='Partial 1']");
    await setRangeInput(partial, 0);
    const flat = await preview.getAttribute("d");
    expect(flat).toContain("L1 50");
    await setRangeInput(partial, 100);
    const sine = await preview.getAttribute("d");
    expect(sine).not.toBe(flat);
    expect(sine).not.toContain("L1 50");
    return `partial 0 -> flat line; partial 100 -> single sine`;
  });

  await check("B-130", "saving names the wavetable and adds it to the instrument select", async () => {
    const dialog = page.locator("[aria-label='Wavetable designer']");
    await dialog.locator("input[aria-label='Wavetable name']").fill("W5 table");
    await dialog.getByRole("button", { name: /Save wavetable/ }).click();
    await expect(dialog).toHaveCount(0);
    const toast = await page.locator(".se-toast").innerText();
    expect(toast.replace(/[\u201c\u201d]/g, '"')).toBe('Wavetable "W5 table" saved.');
    const select = page.locator("select[aria-label='MIDI instrument']");
    const options = await select.locator("option").allInnerTexts();
    expect(options.join(" ")).toContain("W5 table");
    return `toast "${toast}"; instrument options = ${JSON.stringify(options)}`;
  });
});

test("B18 clip-owned effects", async () => {
  test.setTimeout(6 * 60_000);
  await openProject(page, P1);
  await openDock(page);
  await restoreChain(page);
  const clip = page.locator(".se-clip", { hasText: "Drums A" }).first();

  await check("B-131", "clip menu Add FX opens a dialog listing all ten plugins", async () => {
    await clip.click({ button: "right" });
    await expect(page.locator(".se-clip-menu[role='menu']")).toBeVisible();
    await page.locator(".se-clip-menu [role='menuitem']", { hasText: "Add FX" }).click();
    const dialog = page.locator("[role='dialog'][aria-label='Add clip effect']");
    await expect(dialog).toBeVisible();
    const rows = await dialog.locator(".se-dialog-row .se-dialog-title").allInnerTexts();
    expect(rows.length).toBe(10);
    await expect(dialog.getByRole("button", { name: "Cancel" })).toBeVisible();
    return `10 plugin rows + Cancel`;
  });

  await check("B-132", "choosing Compressor adds it and closes the dialog", async () => {
    const dialog = page.locator("[role='dialog'][aria-label='Add clip effect']");
    await dialog.locator(".se-dialog-row", { hasText: /^Compressor$/ }).click();
    await expect(dialog).toHaveCount(0);
    await expect(page.locator(".se-toast")).toContainText("Compressor added to the clip.");
    await waitSaved(page);
    const project = (await savedProject(page, P1)) as any;
    const lane = (project.data?.lanes ?? []).find((item: any) => item.id === "c-d1");
    expect((lane?.fx ?? []).length).toBe(1);
    expect(lane?.fx?.[0]?.pluginId).toBe("compressor");
    return `toast shown; saved clip.fx = [compressor]`;
  });

  await check("B-133", "Remove FX becomes enabled once the clip has effects", async () => {
    await clip.click({ button: "right" });
    const row = page.locator(".se-clip-menu [role='menuitem']", { hasText: "Remove FX" });
    await expect(row).toBeEnabled();
    await page.keyboard.press("Escape");
    return `Remove FX enabled for a clip with fx`;
  });

  await check("B-134", "Remove FX clears the clip effects", async () => {
    await clip.click({ button: "right" });
    await page.locator(".se-clip-menu [role='menuitem']", { hasText: "Remove FX" }).click();
    await expect(page.locator(".se-toast")).toContainText("Clip effects removed.");
    await waitSaved(page);
    const project = (await savedProject(page, P1)) as any;
    const lane = (project.data?.lanes ?? []).find((item: any) => item.id === "c-d1");
    expect((lane?.fx ?? []).length).toBe(0);
    await clip.click({ button: "right" });
    const row = page.locator(".se-clip-menu [role='menuitem']", { hasText: "Remove FX" });
    await expect(row).toBeDisabled();
    await expect(
      page.locator(".se-clip-menu [role='menuitem']", { hasText: "Add FX" })
    ).toBeEnabled();
    await page.keyboard.press("Escape");
    return `fx cleared; Remove FX disabled again and Add FX available`;
  });
});

test("B19 sends and routing surfaces", async () => {
  test.setTimeout(6 * 60_000);
  await openProject(page, P1);
  await openDock(page);

  await check("B-135", "Sends group with two 0-100 sliders at zero", async () => {
    const group = page.locator(".sp-sends[role='group'][aria-label='Sends']");
    await expect(group).toBeVisible();
    const sliders = group.locator("input[type='range']");
    await expect(sliders).toHaveCount(2);
    for (const index of [0, 1]) {
      const slider = sliders.nth(index);
      expect(await slider.getAttribute("min")).toBe("0");
      expect(await slider.getAttribute("max")).toBe("100");
      expect(await slider.inputValue()).toBe("0");
    }
    const labels = await group.locator(".sp-send > span").allInnerTexts();
    expect(labels).toEqual(["Delay", "Reverb"]);
    return `Delay + Reverb sliders, 0..100, both 0`;
  });

  await check("B-136", "raising the Delay send persists on the track", async () => {
    const slider = page.locator(".sp-sends input[aria-label='Delay send']");
    await setRangeInput(slider, 42);
    await expect(slider).toHaveValue("42");
    await waitSaved(page);
    let project = (await savedProject(page, P1)) as any;
    let track = (project.data?.tracks ?? []).find((item: any) => item.id === "t-drums");
    expect(track?.sends?.delay).toBe(42);
    await page.reload();
    await openProject(page, P1);
    await openDock(page);
    expect(await page.locator(".sp-sends input[aria-label='Delay send']").inputValue()).toBe("42");
    return `saved tracks[t-drums].sends.delay = 42; slider 42 after reload`;
  });

  await check("B-137", "sends sit outside the plugin rail", async () => {
    const outside = await page.locator(".sp-rail .sp-sends").count();
    expect(outside).toBe(0);
    expect(await page.locator("section.sp-dock > .sp-sends").count()).toBe(1);
    return `.sp-sends is a sibling of .sp-rail, not part of the chain list`;
  });

  await check("B-138", "playback with a chain and a send moves the master meter", async () => {
    await page.locator("button[aria-label='Play']").click();
    const readings: string[] = [];
    for (let index = 0; index < 10; index += 1) {
      await page.waitForTimeout(600);
      readings.push((await page.locator(".se-meter").innerText()).trim());
    }
    await page.locator("button[aria-label='Pause']").click().catch(() => undefined);
    const live = readings.filter((value) => value !== "-" && value !== "-inf dB pk");
    expect(live.length).toBeGreaterThan(0);
    return `meter samples = ${JSON.stringify(readings.slice(0, 6))}`;
  });
});

