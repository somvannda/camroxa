import { test, expect, type Page } from "@playwright/test";
import {
  addPlugin,
  createProject,
  makeRecorder,
  openDock,
  openProject,
  p1Document,
  quietHelp,
  readAll,
  ensurePresetMenu,
  removeSlot,
  restoreChain,
  savedProject,
  setKnob,
  shot,
  signIn,
  slot,
  waitSaved,
} from "./w5-harness";

/**
 * W5 independent manual run - area B, sections B8-B12 (46 checks):
 * Limiter, Reverb, Rhythm Gate, Stereo Utility, presets and the dirty/Update cycle.
 */

const REC = makeRecorder("b");
const VP = "1689x1277";

let P1 = "";
let P3 = "";
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

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ browser }) => {
  test.setTimeout(240_000);
  page = await browser.newPage();
  page.setDefaultTimeout(15_000);
  await quietHelp(page);
  await page.setViewportSize({ width: 1689, height: 1277 });
  page.on("pageerror", (error) => console.log("PAGEERROR", error.message));
  await signIn(page);
  P1 = await createProject(page, "W5 P1 fixture (B8-B12)", p1Document());
  const legacy = p1Document();
  (legacy.data as any).chains = {
    "t-drums": [
      {
        entryId: "legacy-chorus",
        pluginId: "chorus",
        presetId: null,
        presetName: "Default",
        dirty: false,
        params: { rate: 6, depth: 40, mix: 30 },
        assetId: null,
        bypassed: false,
        poppedOut: false,
      },
    ],
  };
  P3 = await createProject(page, "W5 legacy chorus fixture", legacy);
});

test.afterAll(async () => {
  REC.flush();
  await page.close();
});

test("B8 limiter", async () => {
  test.setTimeout(6 * 60_000);
  await openProject(page, P1);
  await openDock(page);
  await restoreChain(page);
  await addPlugin(page, "Limiter");

  await check("B-63", "Limiter defaults", async () => {
    const values = await readAll(page, "Limiter", ["Lookahead", "Pre Gain", "Attack", "Release"]);
    expect(values).toEqual({
      Lookahead: "3ms",
      "Pre Gain": "0db",
      Attack: "1ms",
      Release: "60ms",
    });
    return JSON.stringify(values);
  });

  await check("B-64", "preset Loud", async () => {
    await slot(page, "Limiter").locator(".sp-preset").click();
    await page.locator(".sp-preset-menu [role='menuitem']", { hasText: /^Loud$/ }).click();
    const values = await readAll(page, "Limiter", ["Lookahead", "Pre Gain", "Attack", "Release"]);
    expect(values).toEqual({
      Lookahead: "3ms",
      "Pre Gain": "6db",
      Attack: "1ms",
      Release: "50ms",
    });
    return JSON.stringify(values);
  });

  await check("B-65", "preset Transparent", async () => {
    await slot(page, "Limiter").locator(".sp-preset").click();
    await page
      .locator(".sp-preset-menu [role='menuitem']", { hasText: /^Transparent$/ })
      .click();
    const values = await readAll(page, "Limiter", ["Lookahead", "Pre Gain", "Attack", "Release"]);
    expect(values).toEqual({
      Lookahead: "5ms",
      "Pre Gain": "0db",
      Attack: "3ms",
      Release: "120ms",
    });
    return JSON.stringify(values);
  });

  await check("B-66", "no mode tabs and no asset slot", async () => {
    expect(await slot(page, "Limiter").locator(".sp-modes").count()).toBe(0);
    expect(await slot(page, "Limiter").locator(".sp-ir-picker").count()).toBe(0);
    expect(await slot(page, "Limiter").locator(".sp-knob-grid input[aria-label]").count()).toBe(4);
    return `0 mode tabs, 0 asset slots, 4 knobs`;
  });
});

test("B9 reverb", async () => {
  test.setTimeout(6 * 60_000);
  await openProject(page, P1);
  await openDock(page);

  await check("B-67", "Reverb defaults", async () => {
    const values = await readAll(page, "Reverb", [
      "Decay",
      "Mix",
      "Width",
      "Damping",
      "Predelay",
      "Low Cut",
      "High Cut",
    ]);
    expect(values).toEqual({
      Decay: "2.4s",
      Mix: "25%",
      Width: "100%",
      Damping: "40%",
      Predelay: "20ms",
      "Low Cut": "120hz",
      "High Cut": "14khz",
    });
    return JSON.stringify(values);
  });

  await check("B-68", "readout formatting: 2.4s and kHz above 1000", async () => {
    const decay = await slot(page, "Reverb").locator(".sp-knob-readout").allInnerTexts();
    expect(decay[0]).toBe("2.4s");
    expect(decay[6]).toBe("14khz");
    return `readouts = ${JSON.stringify(decay)}`;
  });

  await check("B-69", "presets Room / Hall / Plate", async () => {
    const seen: Record<string, unknown> = {};
    for (const name of ["Room", "Hall", "Plate"]) {
      await slot(page, "Reverb").locator(".sp-preset").click();
      await page
        .locator(".sp-preset-menu [role='menuitem']", { hasText: new RegExp(`^${name}$`) })
        .click();
      await expect(slot(page, "Reverb").locator(".sp-preset")).toHaveText(name);
      seen[name] = await readAll(page, "Reverb", [
        "Decay",
        "Mix",
        "Width",
        "Damping",
        "Predelay",
        "Low Cut",
        "High Cut",
      ]);
    }
    expect(seen["Room"]).toEqual({
      Decay: "1.2s",
      Mix: "18%",
      Width: "100%",
      Damping: "55%",
      Predelay: "10ms",
      "Low Cut": "120hz",
      "High Cut": "14khz",
    });
    expect(seen["Hall"]).toEqual({
      Decay: "3.2s",
      Mix: "28%",
      Width: "120%",
      Damping: "40%",
      Predelay: "25ms",
      "Low Cut": "120hz",
      "High Cut": "12khz",
    });
    expect(seen["Plate"]).toEqual({
      Decay: "1.8s",
      Mix: "22%",
      Width: "90%",
      Damping: "30%",
      Predelay: "5ms",
      "Low Cut": "150hz",
      "High Cut": "16khz",
    });
    return JSON.stringify(seen);
  });

  await check("B-70", "Decay reaches 20s in 0.1 steps and never exceeds it", async () => {
    await setKnob(page, "Reverb", "Decay", 19.94);
    expect(await (await slot(page, "Reverb").locator("input[aria-label='Decay']").getAttribute("aria-valuetext"))).toBe("19.9s");
    const input = slot(page, "Reverb").locator("input[aria-label='Decay']");
    await input.focus();
    await page.keyboard.press("End");
    expect(await input.getAttribute("aria-valuetext")).toBe("20.0s");
    await setKnob(page, "Reverb", "Decay", 25);
    expect(await input.evaluate((el) => (el as HTMLInputElement).value)).toBe("20");
    return `max readout 20.0s; setting 25 clamps to 20`;
  });

  await check("B-71", "no mode tabs: seven knobs only", async () => {
    expect(await slot(page, "Reverb").locator(".sp-modes").count()).toBe(0);
    expect(await slot(page, "Reverb").locator(".sp-knob-grid input[aria-label]").count()).toBe(7);
    return `0 mode tabs, 7 knobs`;
  });
});

test("B10 rhythm gate", async () => {
  test.setTimeout(6 * 60_000);
  await openProject(page, P1);
  await openDock(page);
  await restoreChain(page);
  await addPlugin(page, "Rhythm Gate");

  await check("B-72", "Rate is a select with 1/16, 1/8, 1/4 and defaults to 1/8", async () => {
    const select = slot(page, "Rhythm Gate").locator("select.sp-choice[aria-label='Rate']");
    await expect(select).toBeVisible();
    const options = await select.locator("option").allInnerTexts();
    expect(options).toEqual(["1/16", "1/8", "1/4"]);
    expect(await select.inputValue()).toBe("1");
    return `options=${options.join(" / ")}; value=1 (1/8)`;
  });

  await check("B-73", "0-1 params render as percent", async () => {
    const values = await readAll(page, "Rhythm Gate", ["Depth", "Mix"]);
    expect(values.Depth).toBe("75%");
    expect(values.Mix).toBe("65%");
    const inputs = await slot(page, "Rhythm Gate")
      .locator(".sp-knob-grid input[aria-label]")
      .evaluateAll((nodes) =>
        nodes.map((n) => ({
          label: n.getAttribute("aria-label"),
          min: (n as HTMLInputElement).min,
          max: (n as HTMLInputElement).max,
        }))
      );
    const depth = inputs.find((entry) => entry.label === "Depth");
    expect(depth).toMatchObject({ min: "0", max: "1" });
    return `Depth=75% Mix=65% from a 0..1 model`;
  });

  await check("B-74", "attack/release defaults read 0.1 / 0.2", async () => {
    const values = await readAll(page, "Rhythm Gate", ["Atk", "Rel"]);
    expect(values).toEqual({ Atk: "0.1", Rel: "0.2" });
    return JSON.stringify(values);
  });

  await check("B-75", "Rate 1/4 persists across a reload", async () => {
    await slot(page, "Rhythm Gate").locator("select[aria-label='Rate']").selectOption("2");
    await waitSaved(page);
    await page.reload();
    await openProject(page, P1);
    await openDock(page);
    const select = slot(page, "Rhythm Gate").locator("select[aria-label='Rate']");
    expect(await select.inputValue()).toBe("2");
    const project = (await savedProject(page, P1)) as any;
    const chain = (project.data?.chains?.["t-drums"] ?? []) as any[];
    const gate = chain.find((item) => item.pluginId === "rhythmGate");
    expect(gate?.params?.rate).toBe(2);
    return `after reload Rate=1/4; saved JSON rate=2`;
  });

  await check("B-76", "a legacy 'chorus' entry renders as Rhythm Gate", async () => {
    await openProject(page, P3);
    await openDock(page);
    const labels = await page
      .locator("article.sp-slot")
      .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("aria-label")));
    expect(labels).toEqual(["Rhythm Gate slot 1"]);
    const values = await readAll(page, "Rhythm Gate", ["Rate", "Depth", "Mix"]);
    expect(values.Depth).toBe("40%");
    expect(values.Mix).toBe("30%");
    return `legacy chorus rendered as ${JSON.stringify(labels)} with migrated ${JSON.stringify(values)}`;
  });
});

test("B11 stereo utility", async () => {
  test.setTimeout(6 * 60_000);
  await openProject(page, P1);
  await openDock(page);
  await restoreChain(page);
  await removeSlot(page, "Reverb");
  await addPlugin(page, "Stereo Utility");

  await check("B-77", "Stereo Utility defaults", async () => {
    const values = await readAll(page, "Stereo Utility", ["Level", "Width", "Pan", "Bass Mono"]);
    expect(values).toEqual({ Level: "0db", Width: "150%", Pan: "0", "Bass Mono": "120hz" });
    return JSON.stringify(values);
  });

  await check("B-78", "tier order: Level/Width/Pan primary, Bass Mono last", async () => {
    const order = await slot(page, "Stereo Utility")
      .locator(".sp-knob-grid input[aria-label]")
      .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("aria-label")));
    expect(order).toEqual(["Level", "Width", "Pan", "Bass Mono"]);
    return `DOM order = ${order.join(" / ")}`;
  });

  await check("B-79", "Width reaches 200%", async () => {
    await setKnob(page, "Stereo Utility", "Width", 200);
    expect(await slot(page, "Stereo Utility").locator("input[aria-label='Width']").getAttribute("aria-valuetext")).toBe("200%");
    return `readout = 200%`;
  });

  await check("B-80", "Pan shows signed values without a unit", async () => {
    await setKnob(page, "Stereo Utility", "Pan", -100);
    const low = await slot(page, "Stereo Utility").locator("input[aria-label='Pan']").getAttribute("aria-valuetext");
    await setKnob(page, "Stereo Utility", "Pan", 100);
    const high = await slot(page, "Stereo Utility").locator("input[aria-label='Pan']").getAttribute("aria-valuetext");
    expect(low).toBe("-100");
    expect(high).toBe("100");
    return `-100 / 100, no unit`;
  });

  await check("B-81", "no starter presets: only Clear, Save, Default", async () => {
    await slot(page, "Stereo Utility").locator(".sp-preset").click();
    const menu = slot(page, "Stereo Utility").locator(".sp-preset-menu");
    const rows = await menu.locator("[role='menuitem']").allInnerTexts();
    expect(rows.map((row) => row.trim())).toEqual([
      "Clear all settings",
      "Save preset\u2026",
      "Default",
    ]);
    await page.keyboard.press("Escape");
    return `rows = ${JSON.stringify(rows)}`;
  });
});

test("B12 presets and the dirty/Update cycle", async () => {
  test.setTimeout(8 * 60_000);
  await openProject(page, P1);
  await openDock(page);
  await restoreChain(page);
  await slot(page, "Compressor").locator(".sp-preset").click();
  await page.locator(".sp-preset-menu [role='menuitem']", { hasText: /^Vocal$/ }).click();
  await expect(slot(page, "Compressor").locator(".sp-preset")).toHaveText("Vocal");

  await check("B-82", "moving a knob marks the preset Custom and shows Update", async () => {
    await setKnob(page, "Compressor", "Knee", 9);
    await expect(slot(page, "Compressor").locator(".sp-preset")).toHaveText("Custom");
    await expect(slot(page, "Compressor").locator(".sp-update")).toBeVisible();
    return `label=Custom; Update button visible`;
  });

  await check("B-83", "Update returns to the previous preset and keeps the values", async () => {
    await slot(page, "Compressor").locator(".sp-update").click();
    await expect(slot(page, "Compressor").locator(".sp-preset")).toHaveText("Vocal");
    expect(await slot(page, "Compressor").locator(".sp-update").count()).toBe(0);
    expect(await slot(page, "Compressor").locator("input[aria-label='Knee']").inputValue()).toBe(
      "9"
    );
    return `label=Vocal; Update gone; Knee stayed 9db`;
  });

  await check("B-84", "Compressor preset menu row order", async () => {
    const menu = await ensurePresetMenu(page, "Compressor");
    const rows = await menu.locator("[role='menuitem']").allInnerTexts();
    expect(rows.map((row) => row.trim())).toEqual([
      "Clear all settings",
      "Save preset\u2026",
      "Default",
      "Vocal",
      "Drum Bus",
      "Gentle",
    ]);
    expect(await menu.locator("[role='menuitem'].danger").innerText()).toBe("Clear all settings");
    return `rows = ${JSON.stringify(rows)}`;
  });

  await check("B-85", "the < > stepper cycles Default -> presets -> wraps", async () => {
    const labels: string[] = [];
    for (let index = 0; index < 5; index += 1) {
      labels.push(await slot(page, "Compressor").locator(".sp-preset").innerText());
      await slot(page, "Compressor").locator("button[aria-label='Next Compressor preset']").click();
    }
    const unique = new Set(labels);
    expect(unique.size).toBeGreaterThanOrEqual(4);
    expect(labels[labels.length - 1]).toBe(labels[0]);
    return `walked ${labels.join(" -> ")}`;
  });

  await check("B-86", "Default restores the defaults and marks the row", async () => {
    const menu = await ensurePresetMenu(page, "Compressor");
    await menu.locator("[role='menuitem']", { hasText: /^Default$/ }).click();
    const values = await readAll(page, "Compressor", ["Thresh", "Knee", "Gain"]);
    expect(values).toEqual({ Thresh: "-18db", Knee: "6db", Gain: "0db" });
    const reopened = await ensurePresetMenu(page, "Compressor");
    await expect(reopened.locator("[role='menuitem']", { hasText: /^Default$/ })).toHaveClass(
      /on/
    );
    return JSON.stringify(values);
  });

  await check("B-87", "Clear all settings applies defaults and names the preset Custom", async () => {
    await setKnob(page, "Compressor", "Thresh", -40);
    const menu = await ensurePresetMenu(page, "Compressor");
    await menu.locator("[role='menuitem'].danger").click();
    await expect(slot(page, "Compressor").locator(".sp-preset")).toHaveText("Custom");
    expect(await slot(page, "Compressor").locator(".sp-update").count()).toBe(0);
    expect(
      await slot(page, "Compressor").locator("input[aria-label='Thresh']").inputValue()
    ).toBe("-18");
    return `label=Custom, no Update, Thresh back to -18`;
  });

  await check("B-88", "Save preset adds a toast, a menu row and a stepper stop", async () => {
    await setKnob(page, "Compressor", "Ratio", 7.5);
    const menu = await ensurePresetMenu(page, "Compressor");
    await menu.locator("[role='menuitem']", { hasText: "Save preset" }).click();
    const field = page.locator(".sp-preset-save input[aria-label='Preset name']");
    await field.fill("W5 preset");
    await field.press("Enter");
    const toast = await page.locator(".se-toast").innerText();
    expect(toast.replace(/[\u201c\u201d]/g, '"')).toBe('Preset "W5 preset" saved.');
    const reopened = await ensurePresetMenu(page, "Compressor");
    const rows = await reopened.locator("[role='menuitem']").allInnerTexts();
    expect(rows.map((row) => row.trim())).toContain("W5 preset");
    await slot(page, "Compressor")
      .locator("button[aria-label='Previous Compressor preset']")
      .click();
    expect(await slot(page, "Compressor").locator(".sp-preset").innerText()).toBe("W5 preset");
    return `toast "${toast}"; menu + stepper include "W5 preset"; Ratio 7.5 kept`;
  });

  await check("B-89", "Escape in Save preset\u2026 closes the field without saving", async () => {
    const menu = await ensurePresetMenu(page, "Compressor");
    await menu.locator("[role='menuitem']", { hasText: "Save preset" }).click();
    await page.locator(".sp-preset-save input[aria-label='Preset name']").fill("Discard me");
    await page.keyboard.press("Escape");
    expect(await page.locator(".sp-preset-save").count()).toBe(0);
    const rows = await page.locator(".sp-preset-menu [role='menuitem']").allInnerTexts();
    expect(rows.map((row) => row.trim())).not.toContain("Discard me");
    return `inline field closed; "Discard me" absent from the menu`;
  });

  await check("B-90", "the user preset persists across a reload", async () => {
    await waitSaved(page);
    await page.reload();
    await openProject(page, P1);
    await openDock(page);
    const menu = await ensurePresetMenu(page, "Compressor");
    const rows = await menu.locator("[role='menuitem']").allInnerTexts();
    expect(rows.map((row) => row.trim())).toContain("W5 preset");
    await menu.locator("[role='menuitem']", { hasText: /^W5 preset$/ }).click();
    expect(await slot(page, "Compressor").locator("input[aria-label='Ratio']").inputValue()).toBe(
      "7.5"
    );
    const project = (await savedProject(page, P1)) as any;
    const presets = (project.data?.pluginPresets ?? []) as any[];
    expect(presets.some((preset) => preset.name === "W5 preset")).toBe(true);
    return `after reload the preset is listed and applies Ratio 7.5; stored in pluginPresets`;
  });
});

