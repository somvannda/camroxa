import { test, expect, type Page } from "@playwright/test";
import {
  addPlugin,
  createProject,
  createProject as createProjectFn,
  makeRecorder,
  openCatalog,
  openDock,
  openProject,
  p1Document,
  quietHelp,
  removeAllSlots,
  removeSlot,
  restoreChain,
  savedProject,
  selectTrack,
  shot,
  signIn,
  slot,
  waitSaved,
} from "./w5-harness";

/**
 * W5 independent manual run - area B, sections B13-B15 (28 checks):
 * chain operations, designed plugins, master chain dock.
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

function slotLabels() {
  return page
    .locator("article.sp-slot")
    .evaluateAll((nodes) => nodes.map((node) => node.getAttribute("aria-label") ?? ""));
}

function footerChips() {
  return page.locator(".se-chain .se-chain-chip").allInnerTexts();
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
  P1 = await createProject(page, "W5 P1 fixture (B13-B15)", p1Document());
});

test.afterAll(async () => {
  REC.flush();
  await page.close();
});

test("B13 chain operations", async () => {
  test.setTimeout(10 * 60_000);
  await openProject(page, P1);
  await openDock(page);
  await restoreChain(page);

  await check("B-91", "moving slot 1 right swaps the signal order", async () => {
    await page.locator("button[aria-label='Move Compressor right']").click();
    await expect(page.locator("article.sp-slot").first()).toHaveAttribute(
      "aria-label",
      "Reverb slot 1"
    );
    expect(await slotLabels()).toEqual(["Reverb slot 1", "Compressor slot 2"]);
    await page.locator("button[aria-label='Move Compressor left']").click();
    expect(await slotLabels()).toEqual(["Compressor slot 1", "Reverb slot 2"]);
    return `swapped to Reverb/Compressor then back`;
  });

  await check("B-92", "the first slot cannot move left", async () => {
    await expect(page.locator("button[aria-label='Move Compressor left']")).toBeDisabled();
    return `Move Compressor left is disabled`;
  });

  await check("B-93", "the last slot cannot move right", async () => {
    await expect(page.locator("button[aria-label='Move Reverb right']")).toBeDisabled();
    return `Move Reverb right is disabled`;
  });

  await check("B-94", "bypass dims, disables and reports pressed", async () => {
    const chipBefore = await footerChips();
    const button = slot(page, "Compressor").locator(".sp-bypass");
    await button.click();
    await expect(button).toHaveAttribute("aria-pressed", "true");
    await expect(slot(page, "Compressor")).toHaveClass(/is-bypassed/);
    const disabled = await slot(page, "Compressor")
      .locator(".sp-knob-grid input")
      .evaluateAll((nodes) => nodes.map((n) => (n as HTMLInputElement).disabled));
    expect(disabled.every(Boolean)).toBe(true);
    expect(await footerChips()).toEqual(chipBefore);
    await button.click();
    return `aria-pressed=true, .is-bypassed, ${disabled.length} knobs disabled, footer unchanged`;
  });

  await check("B-95", "removing a slot renumbers the rest", async () => {
    await removeSlot(page, "Compressor");
    expect(await slotLabels()).toEqual(["Reverb slot 1"]);
    return `after removing Compressor the remaining slot is "Reverb slot 1"`;
  });

  await check("B-96", "removing every slot returns the empty state", async () => {
    await removeAllSlots(page);
    await expect(page.locator(".sp-empty")).toContainText("No effects on this track yet.");
    return `.sp-empty visible after removing the last slot`;
  });

  await check("B-97", "Ctrl+Z restores the removed slot with its preset and values", async () => {
    await addPlugin(page, "Compressor");
    const menu = slot(page, "Compressor").locator(".sp-preset");
    await menu.click();
    await slot(page, "Compressor")
      .locator(".sp-preset-menu [role='menuitem']", { hasText: /^Vocal$/ })
      .click();
    await page.waitForTimeout(400);
    await removeSlot(page, "Compressor");
    await expect(page.locator("article.sp-slot")).toHaveCount(0);
    await page.keyboard.press("Control+z");
    await expect(page.locator("article.sp-slot")).toHaveCount(1);
    await expect(slot(page, "Compressor").locator(".sp-preset")).toHaveText("Vocal");
    expect(
      await slot(page, "Compressor").locator("input[aria-label='Thresh']").inputValue()
    ).toBe("-20");
    return `slot restored with preset Vocal and Thresh -20`;
  });

  await check("B-98", "pop-out moves the card to a fixed bottom-right overlay", async () => {
    await restoreChain(page);
    const railBefore = await page.locator(".sp-rail").first().evaluate((el) => el.scrollWidth);
    const secondBefore = await slot(page, "Reverb").evaluate((el) =>
      Math.round(el.getBoundingClientRect().left)
    );
    await page.locator("button[aria-label='Pop out Compressor']").click();
    await expect(slot(page, "Compressor")).toHaveClass(/is-popped/);
    const box = await slot(page, "Compressor").evaluate((el) => {
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return {
        position: style.position,
        right: style.right,
        bottom: style.bottom,
        rightGap: Math.round(window.innerWidth - rect.right),
        bottomGap: Math.round(window.innerHeight - rect.bottom),
      };
    });
    expect(box.position).toBe("fixed");
    expect(box.rightGap).toBe(24);
    const secondAfter = await slot(page, "Reverb").evaluate((el) =>
      Math.round(el.getBoundingClientRect().left)
    );
    const railAfter = await page.locator(".sp-rail").first().evaluate((el) => el.scrollWidth);
    expect(secondAfter).toBe(secondBefore);
    expect(railAfter).toBe(railBefore);
    return `position=${box.position}; right gap=${box.rightGap}px bottom gap=${box.bottomGap}px; slot 2 left ${secondBefore} -> ${secondAfter}; rail ${railBefore} -> ${railAfter}`;
  });

  await check("B-99", "Dock returns the card inline and the state persists", async () => {
    await page.locator("button[aria-label='Dock Compressor']").click();
    await expect(slot(page, "Compressor")).not.toHaveClass(/is-popped/);
    await page.locator("button[aria-label='Pop out Compressor']").click();
    await waitSaved(page);
    await page.reload();
    await openProject(page, P1);
    await openDock(page);
    const popped = await slot(page, "Compressor").evaluate((el) => el.classList.contains("is-popped"));
    expect(popped).toBe(true);
    await page.locator("button[aria-label='Dock Compressor']").click();
    return `Dock works inline; poppedOut survived the reload`;
  });

  await check("B-100", "chains are per track", async () => {
    await restoreChain(page);
    await addPlugin(page, "Delay");
    await expect(page.locator("article.sp-slot")).toHaveCount(3);
    await selectTrack(page, "Bass");
    await expect(page.locator(".sp-empty")).toBeVisible();
    await selectTrack(page, "Drums");
    expect(await slotLabels()).toEqual(["Compressor slot 1", "Reverb slot 2", "Delay slot 3"]);
    return `Bass shows the empty state; Drums kept 3 slots`;
  });

  await check("B-101", "add / undo / redo and reload all agree", async () => {
    await removeSlot(page, "Delay");
    await removeAllSlots(page);
    await restoreChain(page);
    await addPlugin(page, "Delay");
    await expect(page.locator("article.sp-slot")).toHaveCount(3);
    await page.keyboard.press("Control+z");
    await expect(page.locator("article.sp-slot")).toHaveCount(2);
    await page.keyboard.press("Control+Shift+z");
    await expect(page.locator("article.sp-slot")).toHaveCount(3);
    await waitSaved(page);
    await page.reload();
    await openProject(page, P1);
    await openDock(page);
    expect(await slotLabels()).toEqual(["Compressor slot 1", "Reverb slot 2", "Delay slot 3"]);
    const project = (await savedProject(page, P1)) as any;
    const chain = (project.data?.chains?.["t-drums"] ?? []) as any[];
    expect(chain.map((entry) => entry.pluginId)).toEqual(["compressor", "reverb", "delay"]);
    return `undo -> 2, redo -> 3, reload + saved JSON = compressor/reverb/delay`;
  });

  await check("B-102", "footer chain chips reflect the selected track's chain", async () => {
    const chips = await footerChips();
    expect(chips.map((chip) => chip.trim())).toEqual(["Compressor", "Reverb", "Delay"]);
    const dataPlugins = await page
      .locator(".se-chain .se-chain-chip")
      .evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-plugin")));
    expect(dataPlugins).toEqual(["compressor", "reverb", "delay"]);
    return `footer chips = ${JSON.stringify(chips)}`;
  });
});

test("B14 designed plugins", async () => {
  test.setTimeout(10 * 60_000);
  await openProject(page, P1);
  await openDock(page);

  // Mock the credit-spending authoring agent; the UI states are what this row asserts.
  await page.route("**/api/v3/web-music/studio/projects/*/plugins/author**", async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      await new Promise((resolve) => setTimeout(resolve, 700));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: "w5-job",
          status: "pending",
          progress: [{ message: "Designing the control surface" }],
          plugin_id: null,
          plugin_version_id: null,
          descriptor: null,
          last_error: null,
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job_id: "w5-job",
        status: "ready",
        progress: [],
        plugin_id: "w5-plugin",
        plugin_version_id: "w5-v1",
        descriptor: {
          displayName: "W5 Designer",
          parameters: [
            { name: "warmth", label: "Warmth", range: { min: 0, max: 100 }, default: 40, unit: "%" },
            { name: "air", label: "Air", range: { min: 0, max: 100 }, default: 25, unit: "%" },
            { name: "focus", label: "Focus", range: { min: 100, max: 4000 }, default: 800, unit: "hz" },
          ],
        },
        last_error: null,
      }),
    });
  });

  await check("B-103", "Create new plugin turns the prompt bar into design mode", async () => {
    await openCatalog(page);
    await page.locator("button[aria-label='Plugin catalogue options']").click();
    await page.locator(".sp-ir-menu [role='menuitem']", { hasText: "Create new plugin" }).click();
    const prompt = page.locator(".se-prompt");
    await expect(prompt).toHaveClass(/is-design/);
    await expect(prompt.locator("input[aria-label='Describe a part to generate']")).toHaveAttribute(
      "placeholder",
      "Make me a new plugin. Here's what I have in mind:"
    );
    await expect(prompt.locator(".se-prompt-badge")).toHaveText("BETA");
    return `.se-prompt.is-design, seeded placeholder, BETA badge`;
  });

  await check("B-104", "submitting a design prompt restates it with two actions", async () => {
    const input = page.locator(".se-prompt input[aria-label='Describe a part to generate']");
    await input.fill("A warm tape saturator with air");
    await page.locator(".se-prompt-send").click();
    const actions = page.locator(".se-design-actions");
    await expect(actions).toBeVisible();
    await expect(actions.getByRole("button", { name: "Build it" })).toBeVisible();
    await expect(actions.getByRole("button", { name: "Change something…" })).toBeVisible();
    return `restate + Build it / Change something… visible`;
  });

  await check("B-105", "Build it reports the authoring job status", async () => {
    await page.locator(".se-design-actions button", { hasText: "Build it" }).click();
    const status = page.locator(".se-assistant-msg[role='status']");
    await expect(status).toBeVisible();
    const text = await status.innerText();
    expect(text.length).toBeGreaterThan(10);
    return `status line = "${text}"`;
  });

  await check("B-106", "the built plugin appears as a draggable designed card", async () => {
    const card = page.locator(".se-design-card");
    await expect(card).toBeVisible({ timeout: 40_000 });
    await expect(card).toHaveAttribute("aria-label", /designed plugin$/);
    await expect(card.getByRole("button", { name: "Add to track" })).toBeVisible();
    return `card aria-label = "${await card.getAttribute("aria-label")}" with Add to track`;
  });

  await check("B-107", "Add to track inserts a Custom slot on the target track", async () => {
    const before = await page.locator("article.sp-slot").count();
    await page.locator(".se-design-card").getByRole("button", { name: "Add to track" }).click();
    await expect(page.locator("article.sp-slot")).toHaveCount(before + 1);
    const designed = page.locator("article.sp-slot").last();
    await expect(designed).toContainText("W5 Designer");
    await expect(designed.locator(".sp-preset")).toHaveText("Custom");
    return `slot added to the selected track as a Custom slot with 3 designed knobs`;
  });

  await check("B-108", "the card can be dropped on a track row", async () => {
    const type = await page.locator(".se-design-card").evaluate((element) => {
      const transfer = new DataTransfer();
      element.dispatchEvent(new DragEvent("dragstart", { bubbles: true, dataTransfer: transfer }));
      return transfer.types.join(",");
    });
    expect(type).toContain("application/x-camxora-plugin");
    // A drop needs a visible track row. The designed card only exists inside the
    // assistant, and `.se-shell.has-assistant .se-tracks{display:none}` hides the rows.
    const visibleRows = await page
      .locator(".se-track")
      .evaluateAll((nodes) => nodes.filter((node) => (node as HTMLElement).offsetParent !== null).length);
    expect(visibleRows).toBeGreaterThan(0);
    const before = await page.locator("article.sp-slot").count();
    await page.locator(".se-design-card").dragTo(page.locator(".se-track").first());
    await expect(page.locator("article.sp-slot")).toHaveCount(before + 1);
    return `payload "${type}"; ${visibleRows} visible track rows; drop added a slot`;
  });

  await check("B-109", "a custom slot has no stepper and a disabled preset menu", async () => {
    const designed = page.locator("article.sp-slot").last();
    expect(await designed.locator(".sp-preset-step").count()).toBe(0);
    await expect(designed.locator(".sp-preset")).toBeDisabled();
    const knobs = await designed
      .locator(".sp-knob-grid input[aria-label]")
      .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("aria-label")));
    expect(knobs).toEqual(["Warmth", "Air", "Focus"]);
    return `0 stepper buttons, preset disabled, knobs = ${JSON.stringify(knobs)}`;
  });

  await check("B-110", "exiting design mode restores the generate prompt", async () => {
    await page.locator("button[aria-label='Exit plugin designer']").first().click();
    await expect(page.locator(".se-prompt")).not.toHaveClass(/is-design/);
    await expect(page.locator(".se-prompt-context.is-plugin")).toHaveCount(0);
    await expect(page.locator(".se-prompt input[aria-label='Describe a part to generate']")).toHaveAttribute(
      "placeholder",
      "Describe a part to generate"
    );
    return `design tint and plugin context chip cleared`;
  });
});

test("B15 master chain dock", async () => {
  test.setTimeout(8 * 60_000);
  await openProject(page, P1);

  await check("B-111", "Main swaps the bottom panel to the master chain", async () => {
    await page.locator("button.se-master-label").click();
    await expect(page.locator(".se-master-strip")).toHaveClass(/is-selected/);
    await expect(page.locator("section.sp-dock")).toHaveAttribute("aria-label", "Master chain");
    return `.se-master-strip.is-selected; section.sp-dock[aria-label="Master chain"]`;
  });

  await check("B-112", "default limiter card has five controls including Link", async () => {
    const card = page.locator("article.sp-slot.sp-limiter-card");
    await expect(card).toBeVisible();
    const labels = await card
      .locator(".sp-knob-grid input[aria-label]")
      .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("aria-label")));
    expect(labels).toEqual(["Lookahead", "Pre Gain", "Attack", "Release", "Link"]);
    const link = await card.locator("input[aria-label='Link']").getAttribute("aria-valuetext");
    expect(link).toBe("On");
    return `controls = ${labels.join(" / ")}; Link reads On`;
  });

  await check("B-113", "master limiter preset menu", async () => {
    await page.locator(".sp-limiter-card .sp-preset").click();
    const menu = page.locator(".sp-preset-menu[aria-label='Master presets']");
    await expect(menu).toBeVisible();
    const rows = await menu.locator("[role='menuitem']").allInnerTexts();
    expect(rows.map((row) => row.trim())).toEqual(["Default", "Clean", "Warm", "Loud"]);
    await page.locator("button.se-master-label").click();
    return `rows = ${JSON.stringify(rows)}`;
  });

  await check("B-114", "Add effect offers a disabled Limiter and EQ/Compressor ghosts", async () => {
    await page.locator(".sp-empty-rail .sp-add").click();
    const menu = page.locator(".sp-ir-menu[aria-label='Add master effect']");
    await expect(menu).toBeVisible();
    const row = menu.locator("[role='menuitem']");
    await expect(row).toHaveText("Limiter (already added)");
    await expect(row).toBeDisabled();
    const ghosts = await page
      .locator(".sp-empty-rail .sp-ghost")
      .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("aria-label")));
    expect(ghosts).toEqual(["Add EQ", "Add Compressor"]);
    await page.keyboard.press("Escape");
    return `menu row disabled; ghosts = ${JSON.stringify(ghosts)}`;
  });

  await check("B-115", "EQ and Compressor each render one Amount knob", async () => {
    await page.locator(".sp-empty-rail .sp-ghost[aria-label='Add EQ']").click();
    await page.locator(".sp-empty-rail .sp-ghost[aria-label='Add Compressor']").click();
    for (const name of ["EQ", "Compressor"]) {
      const card = page.locator(`article.sp-slot[aria-label='${name} slot']`);
      await expect(card).toBeVisible();
      const knobs = card.locator(".sp-knob-grid input[aria-label]");
      await expect(knobs).toHaveCount(1);
      await expect(knobs.first()).toHaveAttribute("aria-label", "Amount");
      expect(await knobs.first().getAttribute("min")).toBe("0");
      expect(await knobs.first().getAttribute("max")).toBe("100");
    }
    return `EQ slot and Compressor slot each expose one Amount knob 0-100`;
  });

  await check("B-116", "removing a master card drops its footer chip", async () => {
    const before = await footerChips();
    await page.locator("button[aria-label='Remove EQ']").click();
    await expect(page.locator("article.sp-slot[aria-label='EQ slot']")).toHaveCount(0);
    const after = await footerChips();
    expect(after.length).toBe(before.length - 1);
    return `footer chips ${JSON.stringify(before)} -> ${JSON.stringify(after)}`;
  });

  await check("B-117", "footer Add master effect selects Main and opens the panel", async () => {
    await page.locator("button.se-master-label").click();
    await page.keyboard.press("2");
    await expect(page.locator("section.sp-dock")).toHaveCount(0);
    await page.locator(".se-chain-add").click();
    await expect(page.locator(".se-master-strip")).toHaveClass(/is-selected/);
    await expect(page.locator("section.sp-dock")).toHaveAttribute("aria-label", "Master chain");
    return `footer plus selected Main and reopened the master dock`;
  });

  await check("B-118", "the master chain persists across a reload", async () => {
    await waitSaved(page);
    await page.reload();
    await openProject(page, P1);
    const project = (await savedProject(page, P1)) as any;
    const chain = (project.data?.masterChain ?? []) as any[];
    expect(chain.map((entry) => entry.type)).toEqual(["limiter", "compressor"]);
    // The footer only renders chips while a track is selected; after a reload nothing is,
    // so select Main and read the chain from the dock and the footer.
    await page.locator("button.se-master-label").click();
    await expect(page.locator("section.sp-dock")).toHaveAttribute("aria-label", "Master chain");
    const chips = await footerChips();
    expect(chips.map((chip) => chip.trim())).toEqual(["Limiter", "Compressor"]);
    return `saved masterChain = limiter/compressor; after reload + Main the dock and chips show both`;
  });
});
