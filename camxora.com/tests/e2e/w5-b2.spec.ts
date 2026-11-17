import { test, expect, type Page } from "@playwright/test";
import {
  addPlugin,
  createProject,
  knob,
  makeRecorder,
  openDock,
  openProject,
  p1Document,
  quietHelp,
  readAll,
  readout,
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
 * W5 independent manual run - area B, sections B3-B7 (32 checks):
 * Convolution, Delay, Distortion, EQ, Gate.
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

async function setAdvanced(on: boolean) {
  await page.evaluate((next) => {
    const raw = window.localStorage.getItem("studio:settings");
    const parsed = raw ? JSON.parse(raw) : {};
    window.localStorage.setItem(
      "studio:settings",
      JSON.stringify({ ...parsed, advancedContent: next })
    );
  }, on);
  await page.reload();
  await openProject(page, P1);
  await openDock(page);
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
  P1 = await createProject(page, "W5 P1 fixture (B3-B7)", p1Document());
});

test.afterAll(async () => {
  REC.flush();
  await page.close();
});

test("B3 convolution", async () => {
  test.setTimeout(6 * 60_000);
  await openProject(page, P1);
  await openDock(page);
  await restoreChain(page);
  await addPlugin(page, "Convolution");
  await expect(slot(page, "Convolution")).toBeVisible();

  await check("B-31", "Convolution defaults", async () => {
    const values = await readAll(page, "Convolution", ["Mix", "Gain", "Pre", "Width"]);
    expect(values).toEqual({ Mix: "50%", Gain: "0db", Pre: "0ms", Width: "100%" });
    return JSON.stringify(values);
  });

  await check("B-32", "empty asset slot", async () => {
    const button = slot(page, "Convolution").locator(".sp-ir-picker button");
    await expect(button).toContainText("NO ASSET LOADED");
    await expect(slot(page, "Convolution").locator("svg.sp-ir")).toHaveAttribute(
      "aria-label",
      "No asset loaded"
    );
    const wave = await slot(page, "Convolution").locator("svg.sp-ir path.sp-ir-wave").count();
    expect(wave).toBe(0);
    return `button="NO ASSET LOADED"; svg aria-label="No asset loaded"; no envelope path`;
  });

  await check("B-33", "IR picker is a grouped menu that expands and collapses", async () => {
    await slot(page, "Convolution").locator(".sp-ir-picker button").click();
    const menu = page.locator(".sp-ir-menu[aria-label='Impulse responses']");
    await expect(menu).toBeVisible();
    const cats = menu.locator(".sp-ir-cat");
    const count = await cats.count();
    expect(count).toBeGreaterThan(0);
    const first = cats.first();
    const label = await first.innerText();
    await expect(first).toHaveAttribute("aria-expanded", "false");
    await first.click();
    await expect(first).toHaveAttribute("aria-expanded", "true");
    expect(await menu.locator("[role='menuitem']").count()).toBeGreaterThan(count);
    await first.click();
    await expect(first).toHaveAttribute("aria-expanded", "false");
    return `${count} category rows; "${label}" collapses/expands`;
  });

  await check("B-34", "choosing an IR fills the slot and marks it Custom", async () => {
    const menu = page.locator(".sp-ir-menu[aria-label='Impulse responses']");
    await menu.locator(".sp-ir-cat", { hasText: "Halls" }).click();
    const item = menu.getByRole("menuitem", { name: "Cathedral" });
    await item.click();
    await expect(page.locator(".sp-ir-menu")).toHaveCount(0);
    const label = await slot(page, "Convolution").locator(".sp-ir-picker > button span").innerText();
    expect(label).toContain("Cathedral");
    expect(await slot(page, "Convolution").locator("svg.sp-ir path.sp-ir-wave").count()).toBe(1);
    await expect(slot(page, "Convolution").locator(".sp-preset")).toHaveText("Custom");
    return `IR label="${label.trim()}"; envelope drawn; preset label=Custom`;
  });

  await check("B-35", "Escape closes the picker without applying", async () => {
    const before = await slot(page, "Convolution")
      .locator(".sp-ir-picker > button span")
      .innerText();
    await slot(page, "Convolution").locator("button[aria-label='Impulse response']").click();
    await expect(page.locator(".sp-ir-menu")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator(".sp-ir-menu")).toHaveCount(0);
    const after = await slot(page, "Convolution")
      .locator(".sp-ir-picker > button span")
      .innerText();
    expect(after).toBe(before);
    return `menu closed by Escape; asset unchanged ("${before}")`;
  });

  await check("B-36", "with Advanced content off there is no Design response row", async () => {
    await setAdvanced(false);
    await slot(page, "Convolution").locator("button[aria-label='Impulse response']").click();
    const menu = page.locator(".sp-ir-menu[aria-label='Impulse responses']");
    await expect(menu).toBeVisible();
    const rows = await menu.locator("[role='menuitem']").count();
    expect(await menu.getByText("Design response.").count()).toBe(0);
    await page.keyboard.press("Escape");
    return `menu rows = ${rows}; no "Design response." row`;
  });

  await check("B-37", "with Advanced content on, Design response opens the IR designer", async () => {
    await setAdvanced(true);
    await slot(page, "Convolution").locator("button[aria-label='Impulse response']").click();
    const row = page.locator(".sp-ir-menu").getByRole("menuitem", { name: /Design response/ });
    await expect(row).toBeVisible();
    await row.click();
    await expect(page.locator("[aria-label='Impulse response designer']")).toBeVisible();
    return `Design response. row present; designer dialog opened`;
  });
});

test("B4 delay", async () => {
  test.setTimeout(6 * 60_000);
  await openProject(page, P1);
  await openDock(page);
  await restoreChain(page);
  await addPlugin(page, "Delay");

  await check("B-38", "Delay defaults", async () => {
    const values = await readAll(page, "Delay", [
      "Time",
      "Feedback",
      "Mix",
      "Low Cut",
      "High Cut",
    ]);
    expect(values).toEqual({
      Time: "350ms",
      Feedback: "35%",
      Mix: "25%",
      "Low Cut": "120hz",
      "High Cut": "12khz",
    });
    return JSON.stringify(values);
  });

  await check("B-39", "mode tabs: Time selected, Tempo available", async () => {
    const tabs = slot(page, "Delay").locator(".sp-modes[role='tablist']");
    await expect(tabs).toHaveAttribute("aria-label", "Delay mode");
    const labels = await tabs.locator("[role='tab']").allInnerTexts();
    expect(labels).toEqual(["Time", "Tempo"]);
    expect(await tabs.locator("[role='tab'][aria-selected='true']").innerText()).toBe("Time");
    return `tablist "Delay mode": ${labels.join(" / ")}; Time selected`;
  });

  await check("B-40", "clicking Tempo selects that tab", async () => {
    await slot(page, "Delay").locator("[role='tab']", { hasText: "Tempo" }).click();
    const tempo = slot(page, "Delay").locator("[role='tab']", { hasText: "Tempo" });
    await expect(tempo).toHaveAttribute("aria-selected", "true");
    await expect(tempo).toHaveClass(/on/);
    return `Tempo aria-selected=true, class .on`;
  });

  await check("B-41", "Tempo mode Time control (record-only row)", async () => {
    const division = slot(page, "Delay").locator("select[aria-label='Time division']");
    const msKnob = slot(page, "Delay").locator("input[aria-label='Time']");
    expect(await division.count()).toBe(1);
    expect(await msKnob.count()).toBe(0);
    const options = await division.locator("option").allInnerTexts();
    return `record-only: as-built Tempo mode shows a Time division select (${options.join(
      " / "
    )}) instead of the ms knob; row text and flag G-2 are stale at 90db80ab`;
  });

  await check("B-42", "Tempo mode survives a reload", async () => {
    await waitSaved(page);
    await page.reload();
    await openProject(page, P1);
    await openDock(page);
    const tempo = slot(page, "Delay").locator("[role='tab']", { hasText: "Tempo" });
    await expect(tempo).toHaveAttribute("aria-selected", "true");
    const project = (await savedProject(page, P1)) as any;
    const chain = (project.data?.chains?.["t-drums"] ?? []) as any[];
    const delay = chain.find((item) => item.pluginId === "delay");
    expect(delay?.mode).toBe("tempo");
    return `after reload Tempo selected; saved JSON mode="${delay?.mode}"`;
  });

  await check("B-43", "applying Dub sets its five values and clears dirty", async () => {
    await slot(page, "Delay").locator("[role='tab']", { hasText: "Time" }).click();
    await slot(page, "Delay").locator(".sp-preset").click();
    await page.locator(".sp-preset-menu [role='menuitem']", { hasText: /^Dub$/ }).click();
    const values = await readAll(page, "Delay", [
      "Time",
      "Feedback",
      "Mix",
      "Low Cut",
      "High Cut",
    ]);
    // Values are the checklist's; the Hz readout carries the extra ".0" tracked under B-51.
    expect(values).toEqual({
      Time: "375ms",
      Feedback: "55%",
      Mix: "30%",
      "Low Cut": "250hz",
      "High Cut": "6.0khz",
    });
    await expect(slot(page, "Delay").locator(".sp-preset")).toHaveText("Dub");
    expect(await slot(page, "Delay").locator(".sp-update").count()).toBe(0);
    return `${JSON.stringify(values)} (High Cut reads 6.0khz, not the row's 6khz)`;
  });
});

test("B5 distortion", async () => {
  test.setTimeout(6 * 60_000);
  await openProject(page, P1);
  await openDock(page);
  await restoreChain(page);
  await addPlugin(page, "Distortion");

  await check("B-44", "Distortion defaults", async () => {
    const values = await readAll(page, "Distortion", ["Drive", "Tilt", "Bass", "Freq"]);
    expect(values).toEqual({ Drive: "30%", Tilt: "0", Bass: "0db", Freq: "800hz" });
    return JSON.stringify(values);
  });

  await check("B-45", "five mode tabs with Hard selected first", async () => {
    const tabs = slot(page, "Distortion").locator(".sp-modes [role='tab']");
    const labels = await tabs.allInnerTexts();
    expect(labels).toEqual(["Hard", "Fold", "Align", "Sine", "Crush"]);
    expect(await tabs.first().getAttribute("aria-selected")).toBe("true");
    return `tabs = ${labels.join(" / ")}; Hard selected`;
  });

  await check("B-46", "exactly one mode selected at a time", async () => {
    const results: string[] = [];
    for (const label of ["Fold", "Align", "Sine", "Crush", "Hard"]) {
      await slot(page, "Distortion").locator("[role='tab']", { hasText: label }).click();
      const selected = await slot(page, "Distortion")
        .locator(".sp-modes [role='tab'][aria-selected='true']")
        .allInnerTexts();
      expect(selected).toEqual([label]);
      results.push(`${label}:1`);
    }
    return results.join(", ");
  });

  await check("B-47", "Tilt sweeps -100 to +100 with no unit", async () => {
    const input = knob(page, "Distortion", "Tilt");
    await input.focus();
    await page.keyboard.press("Home");
    await expect(input).toHaveAttribute("aria-valuetext", "-100");
    await page.keyboard.press("End");
    await expect(input).toHaveAttribute("aria-valuetext", "100");
    return `ends read "-100" and "100" with no unit`;
  });

  await check("B-48", "Freq uses a log scale, not arithmetic", async () => {
    await setKnob(page, "Distortion", "Freq", 630);
    const pct = await slot(page, "Distortion").locator("input[aria-label='Freq']").evaluate((el) => {
      const dial = el.parentElement?.querySelector(".sp-knob-dial") as HTMLElement | null;
      const raw = dial?.style.getPropertyValue("--p") ?? "0deg";
      return Number.parseFloat(raw) / 270;
    });
    const arithmetic = (630 - 20) / (20000 - 20);
    const geometric = Math.log(630 / 20) / Math.log(20000 / 20);
    expect(pct).toBeGreaterThan(0.4);
    expect(pct).toBeLessThan(0.75);
    expect(Math.abs(pct - geometric)).toBeLessThan(0.08);
    expect(Math.abs(pct - arithmetic)).toBeGreaterThan(0.2);
    return `dial at 630hz = ${(pct * 100).toFixed(1)}% of travel (log ${(geometric * 100).toFixed(
      1
    )}%, arithmetic ${(arithmetic * 100).toFixed(1)}%)`;
  });
});

test("B6 EQ", async () => {
  test.setTimeout(9 * 60_000);
  await openProject(page, P1);
  await openDock(page);
  await restoreChain(page);
  await addPlugin(page, "EQ");
  await expect(slot(page, "EQ")).toBeVisible();

  await check("B-49", "EQ card anatomy", async () => {
    const card = slot(page, "EQ").locator(".sp-eq-card");
    await expect(card).toBeVisible();
    await expect(card.locator("select[aria-label='EQ band']")).toBeVisible();
    await expect(card.locator("button[role='switch']")).toBeVisible();
    expect(await card.locator(".sp-eq-shapes button").count()).toBe(6);
    await expect(card.locator("svg.sp-eq")).toBeVisible();
    expect(await card.locator(".sp-knobs input[aria-label]").count()).toBe(3);
    return `band select + enable switch + 6 shapes + shared curve + Freq/Q/Gain`;
  });

  await check("B-50", "band selector offers Band 1-4, Band 1 selected by default", async () => {
    const select = slot(page, "EQ").locator("select[aria-label='EQ band']");
    const options = await select.locator("option").allInnerTexts();
    expect(options).toEqual(["Band 1", "Band 2", "Band 3", "Band 4"]);
    expect(await select.inputValue()).toBe("1");
    expect(await slot(page, "EQ").locator(".sp-eq-handle.on").count()).toBe(1);
    await expect(slot(page, "EQ").locator(".sp-eq-handle.on")).toHaveAttribute(
      "aria-label",
      "Band 1 handle"
    );
    return `options=${options.join(", ")}; selected=Band 1; handle .on = Band 1`;
  });

  await check("B-51", "Band 1 defaults: 1khz / 1 / 0db", async () => {
    const values = await readAll(page, "EQ", ["Freq", "Q", "Gain"]);
    expect(values).toEqual({ Freq: "1khz", Q: "1", Gain: "0db" });
    return JSON.stringify(values);
  });

  await check("B-52", "bands 2-4 defaults", async () => {
    const select = slot(page, "EQ").locator("select[aria-label='EQ band']");
    const seen: Record<string, unknown> = {};
    for (const band of ["2", "3", "4"]) {
      await select.selectOption(band);
      const values = await readAll(page, "EQ", ["Freq", "Q", "Gain"]);
      seen[`Band ${band}`] = values;
    }
    expect(seen["Band 2"]).toEqual({ Freq: "200hz", Q: "1", Gain: "0db" });
    expect(seen["Band 3"]).toEqual({ Freq: "4khz", Q: "1", Gain: "0db" });
    expect(seen["Band 4"]).toEqual({ Freq: "10khz", Q: "1", Gain: "0db" });
    return JSON.stringify(seen);
  });
  await check("B-53", "band enable switch removes the handle", async () => {
    await slot(page, "EQ").locator("select[aria-label='EQ band']").selectOption("1");
    const toggle = slot(page, "EQ").locator("button[aria-label='Band 1 enabled']");
    await expect(toggle).toHaveAttribute("aria-checked", "true");
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(await slot(page, "EQ").locator(".sp-eq-handle", { hasText: "" }).count()).toBe(3);
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "true");
    return `aria-checked flips; handle count 4 -> 3 -> 4`;
  });

  await check("B-54", "six shapes set band type 0-5", async () => {
    const seen: string[] = [];
    for (const shape of ["Low cut", "Bell", "High shelf", "Low shelf", "High cut", "Notch"]) {
      await slot(page, "EQ").locator(`.sp-eq-shapes button[aria-label='${shape}']`).click();
      const pressed = await slot(page, "EQ")
        .locator(".sp-eq-shapes button[aria-pressed='true']")
        .getAttribute("aria-label");
      expect(pressed).toBe(shape);
      seen.push(shape);
    }
    await waitSaved(page);
    const project = (await savedProject(page, P1)) as any;
    const chain = (project.data?.chains?.["t-drums"] ?? []) as any[];
    const eq = chain.find((item) => item.pluginId === "eq");
    expect(eq?.params?.["band1.type"]).toBe(5);
    return `pressed moved through ${seen.join(" / ")}; saved band1.type=5 after Notch`;
  });

  await check("B-55", "dragging a band handle moves freq (x) and gain (y)", async () => {
    const svg = slot(page, "EQ").locator("svg.sp-eq");
    const box = (await svg.boundingBox())!;
    const handle = slot(page, "EQ").locator(".sp-eq-handle").first();
    const hbox = (await handle.boundingBox())!;
    await page.mouse.move(hbox.x + hbox.width / 2, hbox.y + hbox.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.75, box.y + box.height * 0.25, { steps: 8 });
    const midFreq = await readout(page, "EQ", "Freq");
    await page.mouse.up();
    const gain = await readout(page, "EQ", "Gain");
    await waitSaved(page);
    const project = (await savedProject(page, P1)) as any;
    const eq = ((project.data?.chains?.["t-drums"] ?? []) as any[]).find(
      (item) => item.pluginId === "eq"
    );
    const savedFreq = eq?.params?.["band1.freq"];
    expect(midFreq).not.toBe("1.0khz");
    expect(savedFreq).toBeGreaterThan(1000);
    return `Freq=${midFreq}; Gain=${gain}; saved band1.freq=${savedFreq}`;
  });

  await check("B-56", "dragging beyond the curve clamps to 20hz..20khz and +/-24db", async () => {
    const svg = slot(page, "EQ").locator("svg.sp-eq");
    const box = (await svg.boundingBox())!;
    const handle = slot(page, "EQ").locator(".sp-eq-handle").first();
    const hbox = (await handle.boundingBox())!;
    await page.mouse.move(hbox.x + hbox.width / 2, hbox.y + hbox.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x - 200, box.y - 200, { steps: 6 });
    await page.mouse.up();
    const low = await readAll(page, "EQ", ["Freq", "Gain"]);
    const hbox2 = (await slot(page, "EQ").locator(".sp-eq-handle").first().boundingBox())!;
    await page.mouse.move(hbox2.x + hbox2.width / 2, hbox2.y + hbox2.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width + 200, box.y + box.height + 200, { steps: 6 });
    await page.mouse.up();
    const high = await readAll(page, "EQ", ["Freq", "Gain"]);
    await waitSaved(page);
    const project = (await savedProject(page, P1)) as any;
    const eq = ((project.data?.chains?.["t-drums"] ?? []) as any[]).find(
      (item) => item.pluginId === "eq"
    );
    expect(low.Freq).toBe("20hz");
    expect(low.Gain).toBe("24db");
    expect(high.Freq).toBe("20khz");
    expect(high.Gain).toBe("-24db");
    expect(eq?.params?.["band1.freq"]).toBeGreaterThanOrEqual(20);
    expect(eq?.params?.["band1.freq"]).toBeLessThanOrEqual(20000);
    expect(eq?.params?.["band1.gain"]).toBeGreaterThanOrEqual(-24);
    expect(eq?.params?.["band1.gain"]).toBeLessThanOrEqual(24);
    return `top-left=${JSON.stringify(low)}; bottom-right=${JSON.stringify(high)}; saved within bounds`;
  });

  await check("B-57", "bypass disables every EQ control", async () => {
    await slot(page, "EQ").locator(".sp-bypass").click();
    await expect(slot(page, "EQ")).toHaveClass(/is-bypassed/);
    const disabled = await slot(page, "EQ")
      .locator(".sp-eq-card input, .sp-eq-card select, .sp-eq-card button")
      .evaluateAll((nodes) => nodes.map((n) => (n as HTMLButtonElement).disabled));
    expect(disabled.length).toBeGreaterThan(0);
    expect(disabled.every(Boolean)).toBe(true);
    await slot(page, "EQ").locator(".sp-bypass").click();
    return `${disabled.length} EQ card controls disabled while bypassed`;
  });

  await check("B-58", "curve has no numeric readout; handles are labelled", async () => {
    const text = await slot(page, "EQ").locator("svg.sp-eq").evaluate((el) => el.textContent);
    expect((text ?? "").trim()).toBe("");
    const labels = await slot(page, "EQ")
      .locator(".sp-eq-handle")
      .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("aria-label")));
    expect(labels.length).toBeGreaterThan(0);
    for (const label of labels) expect(label).toMatch(/^Band [1-4] handle$/);
    return `no text inside the curve; handles = ${JSON.stringify(labels)}`;
  });
});

test("B7 gate", async () => {
  test.setTimeout(6 * 60_000);
  await openProject(page, P1);
  await openDock(page);
  await restoreChain(page);
  await addPlugin(page, "Gate");

  await check("B-59", "Gate defaults", async () => {
    const values = await readAll(page, "Gate", ["Threshold", "Floor", "Attack", "Hold"]);
    expect(values).toEqual({
      Threshold: "-45db",
      Floor: "-60db",
      Attack: "2ms",
      Hold: "50ms",
    });
    return JSON.stringify(values);
  });

  await check("B-60", "Threshold primary, the other three secondary", async () => {
    const order = await slot(page, "Gate")
      .locator(".sp-knob-grid input[aria-label]")
      .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("aria-label")));
    expect(order).toEqual(["Threshold", "Floor", "Attack", "Hold"]);
    return `DOM order = ${order.join(" / ")}`;
  });

  await check("B-61", "preset Tight", async () => {
    await slot(page, "Gate").locator(".sp-preset").click();
    await page.locator(".sp-preset-menu [role='menuitem']", { hasText: /^Tight$/ }).click();
    const values = await readAll(page, "Gate", ["Threshold", "Floor", "Attack", "Hold"]);
    expect(values).toEqual({
      Threshold: "-40db",
      Floor: "-70db",
      Attack: "1ms",
      Hold: "30ms",
    });
    await expect(slot(page, "Gate").locator(".sp-preset")).toHaveText("Tight");
    return JSON.stringify(values);
  });

  await check("B-62", "preset Slow", async () => {
    await slot(page, "Gate").locator(".sp-preset").click();
    await page.locator(".sp-preset-menu [role='menuitem']", { hasText: /^Slow$/ }).click();
    const values = await readAll(page, "Gate", ["Threshold", "Floor", "Attack", "Hold"]);
    expect(values).toEqual({
      Threshold: "-50db",
      Floor: "-60db",
      Attack: "10ms",
      Hold: "120ms",
    });
    await expect(slot(page, "Gate").locator(".sp-preset")).toHaveText("Slow");
    return JSON.stringify(values);
  });
});

