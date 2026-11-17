import { test, expect, type Page } from "@playwright/test";
import {
  addPlugin,
  createProject,
  knob,
  makeRecorder,
  openCatalog,
  openDock,
  openProject,
  p1Document,
  p2Document,
  quietHelp,
  readAll,
  readout,
  removeSlot,
  restoreChain,
  savedProject,
  selectTrack,
  setKnob,
  shot,
  signIn,
  slot,
  waitSaved,
} from "./w5-harness";

/**
 * W5 independent manual run - area B, sections B1-B2 (30 checks).
 * Assertions are derived from docs/studio/reports/2026-11-17-manual-qa-checklist.md section B.
 */

const REC = makeRecorder("b");
const VP = "1689x1277";

let P1 = "";
let P2 = "";
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
  P1 = await createProject(page, "W5 P1 fixture", p1Document());
  P2 = await createProject(page, "W5 P2 fixture", p2Document());
});

test.afterAll(async () => {
  REC.flush();
  await page.close();
});

test("B1 dock chrome and catalogue", async () => {
  test.setTimeout(8 * 60_000);
  await openProject(page, P1);

  await selectTrack(page, "Vox");
  await expect(page.locator(".sp-empty")).toBeVisible();

  await check("B-01", "Vox has no chain", async () => {
    const text = await page.locator(".sp-empty").innerText();
    expect(text).toContain("No effects on this track yet.");
    expect(text).toContain("Add effect");
    return `.sp-empty = "${text.replace(/\n/g, " / ")}"`;
  });

  await openDock(page);

  await check("B-02", "Drums fixture chain Compressor -> Reverb", async () => {
    const labels = await page
      .locator("article.sp-slot")
      .evaluateAll((nodes) => nodes.map((node) => node.getAttribute("aria-label")));
    expect(labels).toEqual(["Compressor slot 1", "Reverb slot 2"]);
    return `.sp-slot aria-labels = ${JSON.stringify(labels)}`;
  });

  await check("B-03", "Add effect opens the catalogue", async () => {
    await openCatalog(page);
    const title = page.locator("#sp-catalog-title");
    await expect(title).toHaveText("Add a track plugin");
    const focused = await page.evaluate(() => document.activeElement?.getAttribute("aria-label"));
    expect(focused).toBe("Search plugins");
    await expect(page.locator(".sp-dialog button[aria-label='Close']")).toBeVisible();
    await expect(
      page.locator(".sp-dialog button[aria-label='Plugin catalogue options']")
    ).toBeVisible();
    return `title="Add a track plugin"; autofocus=${focused}; close + options buttons present`;
  });

  await check("B-04", "ten audio effect cards in registry order", async () => {
    const names = await page
      .locator(".sp-catalog:not(.sp-catalog-mine) .sp-card .sp-card-name")
      .evaluateAll((nodes) =>
        nodes.map((node) => (node.textContent ?? "").replace("Learn", "").trim())
      );
    expect(names).toEqual([
      "Compressor",
      "Convolution",
      "Delay",
      "Distortion",
      "EQ",
      "Gate",
      "Limiter",
      "Reverb",
      "Rhythm Gate",
      "Stereo Utility",
    ]);
    return `order = ${names.join(" / ")}`;
  });

  await check("B-05", "card anatomy: preview + 3 mini knobs + name + description", async () => {
    const card = page.locator(".sp-catalog:not(.sp-catalog-mine) .sp-card").first();
    expect(await card.locator(".sp-card-preview").count()).toBe(1);
    expect(await card.locator(".sp-card-knob").count()).toBe(3);
    expect(await card.locator(".sp-card-name").innerText()).toContain("Compressor");
    const desc = await card.locator(".sp-card-desc").innerText();
    expect(desc.startsWith("Classic dynamics compressor: threshold, ratio, and knee")).toBe(true);
    return `Compressor card: preview, 3 mini knobs, description matches the registry`;
  });

  await check("B-06", "search 'rev' -> only Reverb", async () => {
    const search = page.locator("input[aria-label='Search plugins']");
    await search.fill("rev");
    const names = await page
      .locator(".sp-catalog:not(.sp-catalog-mine) .sp-card .sp-card-name")
      .evaluateAll((nodes) => nodes.map((n) => (n.textContent ?? "").replace("Learn", "").trim()));
    expect(names).toEqual(["Reverb"]);
    return `results = ${JSON.stringify(names)}`;
  });

  await check("B-07", "'brickwall' matches Limiter by description", async () => {
    const search = page.locator("input[aria-label='Search plugins']");
    await search.fill("brickwall");
    const names = await page
      .locator(".sp-catalog:not(.sp-catalog-mine) .sp-card .sp-card-name")
      .evaluateAll((nodes) => nodes.map((n) => (n.textContent ?? "").replace("Learn", "").trim()));
    expect(names).toEqual(["Limiter"]);
    return `results = ${JSON.stringify(names)}`;
  });

  await check("B-08", "'zzzz' -> empty-state sentence", async () => {
    const search = page.locator("input[aria-label='Search plugins']");
    await search.fill("zzzz");
    const text = await page.locator(".sp-none").innerText();
    expect(text).toContain("No effects match");
    expect(text).toContain("zzzz");
    expect(await page.locator(".sp-catalog:not(.sp-catalog-mine) .sp-card").count()).toBe(0);
    return `.sp-none = "${text}", 0 cards`;
  });

  await check("B-09", "Learn chip does not add the plugin", async () => {
    const search = page.locator("input[aria-label='Search plugins']");
    await search.fill("reverb");
    const before = await page.locator("article.sp-slot").count();
    await page.locator(".sp-card-learn").first().click();
    await expect(page.locator(".sp-dialog[role='dialog']")).toBeVisible();
    expect(await page.locator("article.sp-slot").count()).toBe(before);
    return `dialog stayed open; slot count unchanged (${before})`;
  });

  await check("B-10", "catalogue options menu has one row: Create new plugin", async () => {
    await page.locator("button[aria-label='Plugin catalogue options']").click();
    const menu = page.locator(".sp-ir-menu[aria-label='Catalogue options']");
    await expect(menu).toBeVisible();
    const rows = await menu.locator("[role='menuitem']").allInnerTexts();
    expect(rows.map((r) => r.trim())).toEqual(["Create new plugin"]);
    await page.keyboard.press("Escape");
    return `rows = ${JSON.stringify(rows)}`;
  });

  await check("B-11", "My plugins: Create new plugin card with BETA badge", async () => {
    const card = page.locator(".sp-create");
    await expect(card).toBeVisible();
    await expect(card.locator(".sp-card-badge")).toHaveText("BETA");
    await expect(card.locator(".sp-card-desc")).toHaveText("Describe it in the prompt bar");
    return `card = "${(await card.innerText()).replace(/\n/g, " / ")}"`;
  });

  await check("B-12", "add Delay -> dialog closes, query resets, Delay is slot 3", async () => {
    await page.locator("input[aria-label='Search plugins']").fill("delay");
    await page.locator(".sp-card", { hasText: /^Delay/ }).first().click();
    await expect(page.locator(".sp-dialog[role='dialog']")).toHaveCount(0);
    await expect(page.locator("article.sp-slot")).toHaveCount(3);
    await expect(page.locator("article.sp-slot").nth(2)).toHaveAttribute(
      "aria-label",
      "Delay slot 3"
    );
    await openCatalog(page);
    expect(await page.locator("input[aria-label='Search plugins']").inputValue()).toBe("");
    return "slot 3 = Delay; query cleared on reopen";
  });

  await check("B-13", "the same plugin can be added twice", async () => {
    await page.locator(".sp-card", { hasText: /^Delay/ }).first().click();
    await expect(page.locator("article.sp-slot")).toHaveCount(4);
    const delaySlots = await page
      .locator("article.sp-slot")
      .evaluateAll((nodes) =>
        nodes
          .filter((n) => (n.getAttribute("aria-label") ?? "").startsWith("Delay slot"))
          .map((n) => n.getAttribute("aria-label"))
      );
    expect(delaySlots).toEqual(["Delay slot 3", "Delay slot 4"]);
    return `two independent slots: ${delaySlots.join(", ")}`;
  });

  await check("B-14", "rail add row: Add effect + up to 3 ghost suggestions", async () => {
    await removeSlot(page, "Delay", "last");
    await removeSlot(page, "Delay", "last");
    const rail = page.locator(".sp-empty-rail");
    await expect(rail.locator(".sp-add")).toHaveText(/Add effect/);
    const ghosts = await rail.locator(".sp-ghost").count();
    expect(ghosts).toBeGreaterThan(0);
    expect(ghosts).toBeLessThanOrEqual(3);
    return `ghosts = ${ghosts}, Add effect present`;
  });

  await check("B-15", "ghosts exclude plugins already in the chain", async () => {
    const present = await page
      .locator("article.sp-slot")
      .evaluateAll((nodes) =>
        nodes.map((n) => (n.getAttribute("aria-label") ?? "").replace(/ slot \d+$/, ""))
      );
    const names = await page
      .locator(".sp-ghost")
      .evaluateAll((nodes) => nodes.map((n) => (n.getAttribute("aria-label") ?? "")));
    expect(names.length).toBeGreaterThan(0);
    expect(names.length).toBeLessThanOrEqual(3);
    for (const name of names) {
      const bare = name.replace(/^Add /, "");
      expect(present).not.toContain(bare);
    }
    return `present=${JSON.stringify(present)}; ghosts=${JSON.stringify(names)}`;
  });

  await check("B-16", "clicking a ghost appends that plugin without a dialog", async () => {
    const before = await page.locator("article.sp-slot").count();
    await page.locator(".sp-ghost", { hasText: "Delay" }).first().click();
    await expect(page.locator("article.sp-slot")).toHaveCount(before + 1);
    await expect(page.locator("article.sp-slot").last()).toHaveAttribute(
      "aria-label",
      "Delay slot 3"
    );
    return "Delay appended directly (no dialog) -> slot 3";
  });

  await check("B-17", "dock accessible name", async () => {
    await expect(page.locator("section.sp-dock")).toHaveAttribute(
      "aria-label",
      "Plugins for Drums"
    );
    return `section.sp-dock[aria-label="Plugins for Drums"]`;
  });

  await check("B-18", "slot header control order", async () => {
    const order = await page
      .locator("article.sp-slot")
      .first()
      .locator(".sp-slot-head > *")
      .evaluateAll((nodes) =>
        nodes.map((node) => {
          if (node.classList.contains("sp-dot")) return "dot";
          if (node.tagName === "STRONG") return "name";
          if (node.classList.contains("sp-preset-wrap")) return "preset+stepper";
          if (node.classList.contains("sp-bypass")) return "bypass";
          if (node.classList.contains("sp-slot-tools")) return "move/popout/close";
          return node.className;
        })
      );
    expect(order).toEqual(["dot", "name", "preset+stepper", "bypass", "move/popout/close"]);
    return `header order = ${order.join(" -> ")}`;
  });

  await check("B-19", "knob readouts format label + value", async () => {
    const comp = await readAll(page, "Compressor", [
      "Thresh",
      "Ratio",
      "Knee",
      "Atk",
      "Rel",
      "Gain",
    ]);
    expect(comp).toEqual({
      Thresh: "-18db",
      Ratio: "4",
      Knee: "6db",
      Atk: "10ms",
      Rel: "120ms",
      Gain: "0db",
    });
    const labels = await slot(page, "Compressor").locator(".sp-knob-label").allInnerTexts();
    expect(labels).toContain("Thresh");
    return `Compressor readouts = ${JSON.stringify(comp)}`;
  });

  await check("B-20", "bypassed slot dims and disables every control", async () => {
    await slot(page, "Compressor").locator(".sp-bypass").click();
    await expect(slot(page, "Compressor")).toHaveClass(/is-bypassed/);
    const disabled = await slot(page, "Compressor")
      .locator("input, select, button.sp-band-toggle")
      .evaluateAll((nodes) => nodes.map((n) => (n as HTMLInputElement).disabled));
    expect(disabled.every(Boolean)).toBe(true);
    await slot(page, "Compressor").locator(".sp-bypass").click();
    return `${disabled.length} controls disabled; .is-bypassed applied and cleared`;
  });

  await check("B-21", "four slots at 1689 keep width 448 and never wrap", async () => {
    const widths = await page
      .locator("article.sp-slot")
      .evaluateAll((nodes) => nodes.map((n) => Math.round(n.getBoundingClientRect().width)));
    expect(widths.slice(0, 3)).toEqual([448, 448, 448]);
    const rail = page.locator(".sp-rail").first();
    const overflow = await rail.evaluate((el) => getComputedStyle(el).overflowX);
    expect(["auto", "scroll"]).toContain(overflow);
    const tops = await page
      .locator("article.sp-slot")
      .evaluateAll((nodes) => nodes.map((n) => Math.round(n.getBoundingClientRect().top)));
    expect(new Set(tops).size).toBe(1);
    return `widths=${widths.join(",")}; overflowX=${overflow}; single row`;
  });

  await check("B-22", "window modes: toggle / panels / windows", async () => {
    await expect(page.locator("button[aria-label='Pop out Compressor']")).toBeVisible();
    const setMode = async (mode: string) => {
      await page.evaluate((next) => {
        const raw = window.localStorage.getItem("studio:settings");
        const parsed = raw ? JSON.parse(raw) : {};
        window.localStorage.setItem(
          "studio:settings",
          JSON.stringify({ ...parsed, windowMode: next })
        );
      }, mode);
      await page.reload();
      await openProject(page, P1);
      await openDock(page);
    };
    await setMode("panels");
    expect(await page.locator(".sp-slot-tools button[aria-label^='Pop out']").count()).toBe(0);
    expect(await page.locator("article.sp-slot.is-popped").count()).toBe(0);
    await setMode("windows");
    const popped = await page.locator("article.sp-slot.is-popped").count();
    const slots = await page.locator("article.sp-slot").count();
    expect(popped).toBe(slots);
    await setMode("toggle");
    await expect(page.locator("button[aria-label='Pop out Compressor']")).toBeVisible();
    return `toggle=per-slot button; panels=0 popped; windows=${popped}/${slots} popped`;
  });
});

test("B2 compressor", async () => {
  test.setTimeout(6 * 60_000);
  await openProject(page, P1);
  await openDock(page);
  await restoreChain(page);

  await check("B-23", "six defaults on a fresh Compressor", async () => {
    const values = await readAll(page, "Compressor", [
      "Thresh",
      "Ratio",
      "Knee",
      "Atk",
      "Rel",
      "Gain",
    ]);
    expect(values).toEqual({
      Thresh: "-18db",
      Ratio: "4",
      Knee: "6db",
      Atk: "10ms",
      Rel: "120ms",
      Gain: "0db",
    });
    return JSON.stringify(values);
  });

  await check("B-24", "primary five first, Gain (secondary) last", async () => {
    const order = await slot(page, "Compressor")
      .locator(".sp-knob-grid input[aria-label]")
      .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("aria-label")));
    expect(order).toEqual(["Thresh", "Ratio", "Knee", "Atk", "Rel", "Gain"]);
    return `DOM order = ${order.join(" / ")}`;
  });

  await check("B-25", "Thresh clamps at -60 and 0", async () => {
    const input = knob(page, "Compressor", "Thresh");
    await input.focus();
    await page.keyboard.press("Home");
    await expect(input).toHaveAttribute("aria-valuetext", "-60db");
    const low = await input.inputValue();
    await page.keyboard.press("End");
    await expect(input).toHaveAttribute("aria-valuetext", "0db");
    const high = await input.inputValue();
    await setKnob(page, "Compressor", "Thresh", -200);
    const clamped = await input.inputValue();
    expect(clamped).toBe("-60");
    await setKnob(page, "Compressor", "Thresh", -18);
    return `min=${low} (-60db), max=${high} (0db), -200 clamps to ${clamped}`;
  });

  await check("B-26", "Ratio shows 1 and 20 with no NaN", async () => {
    await setKnob(page, "Compressor", "Ratio", 1);
    expect(await readout(page, "Compressor", "Ratio")).toBe("1");
    await setKnob(page, "Compressor", "Ratio", 20);
    expect(await readout(page, "Compressor", "Ratio")).toBe("20");
    expect(await readout(page, "Compressor", "Ratio")).not.toContain("NaN");
    return `1 -> "1", 20 -> "20"`;
  });

  await check("B-27", "transfer curve follows Thresh without reflow", async () => {
    const svg = page.locator("svg[aria-label='Compressor transfer curve']");
    const before = await svg.locator("path.sp-comp-line").getAttribute("d");
    const dotBefore = await svg.locator("circle.sp-comp-dot").getAttribute("cx");
    const box = await svg.boundingBox();
    await setKnob(page, "Compressor", "Thresh", -40);
    const after = await svg.locator("path.sp-comp-line").getAttribute("d");
    const dotAfter = await svg.locator("circle.sp-comp-dot").getAttribute("cx");
    expect(after).not.toBe(before);
    expect(dotAfter).not.toBe(dotBefore);
    const boxAfter = await svg.boundingBox();
    expect(Math.round(boxAfter!.width)).toBe(Math.round(box!.width));
    await setKnob(page, "Compressor", "Thresh", -18);
    return `path + dot moved; width stable at ${Math.round(box!.width)}px`;
  });

  await check("B-28", "Sidechain menu lists None and every track x Pre/Post", async () => {
    await page.locator("button[aria-label='Sidechain']").click();
    const menu = page.locator(".sp-sidechain-menu[aria-label='Sidechain routing']");
    await expect(menu).toBeVisible();
    const rows = await menu.locator("[role='menuitem']").allInnerTexts();
    expect(rows[0]).toBe("None");
    const expected: string[] = [];
    for (const name of ["Drums", "Bass", "Vox", "Scratch"]) {
      expected.push(`${name} \u2014 Pre-fx`, `${name} \u2014 Post-fader`);
    }
    expect(rows.slice(1)).toEqual(expected);
    const on = await menu.locator("[role='menuitem'].on").allInnerTexts();
    expect(on).toEqual(["None"]);
    return `${rows.length} rows; current = ${JSON.stringify(on)}`;
  });

  await check("B-29", "picking Bass - Post-fader updates the button and closes the menu", async () => {
    await page
      .locator(".sp-sidechain-menu [role='menuitem']", {
        hasText: `Bass \u2014 Post-fader`,
      })
      .click();
    await expect(page.locator(".sp-sidechain-menu")).toHaveCount(0);
    const label = await page.locator(".sp-sidechain button span").first().innerText();
    expect(label).toBe(`Bass \u2014 Post-fader`);
    return `button label = "${label}"`;
  });

  await check("B-30", "Sidechain back to None clears the routing", async () => {
    await page.locator("button[aria-label='Sidechain']").click();
    await page.locator(".sp-sidechain-menu [role='menuitem']", { hasText: /^None$/ }).click();
    const label = await page.locator(".sp-sidechain button span").first().innerText();
    expect(label).toBe("None");
    await waitSaved(page);
    const project = (await savedProject(page, P1)) as any;
    const chain = (project.data?.chains?.["t-drums"] ?? []) as any[];
    const comp = chain.find((item) => item.pluginId === "compressor");
    expect(comp?.sidechain ?? null).toBeNull();
    return `label="None"; saved JSON sidechain=${JSON.stringify(comp?.sidechain ?? null)}`;
  });
});

