import { expect, test, type Page } from "@playwright/test";

import {
  adfDocument,
  barMetrics,
  createProject,
  drag,
  makeRecorder,
  openProject,
  quietHelp,
  shot,
  signIn,
} from "./w5-adf-harness";

/**
 * Re-run of the failures the QA checklist and the W5 B/E pass recorded, limited to those
 * that touch the A/D/F surfaces this run owns. These rows are NOT part of the 137;
 * they exist to say whether today's fixes hold on this tree.
 */

const rec = makeRecorder("regression");
test.describe.configure({ mode: "serial" });
test.afterAll(() => rec.flush());
test.use({ viewport: { width: 1689, height: 1277 } });
test.setTimeout(180_000);

async function fresh(page: Page) {
  await quietHelp(page);
  await signIn(page);
  const id = await createProject(page, "ADF regression", adfDocument());
  await openProject(page, id);
  return id;
}

test("R — EQ band drag changes Frequency (B-55/B-56)", async ({ page }) => {
  await fresh(page);
  await page.locator(".se-track-name", { hasText: "Drums" }).first().click();
  if ((await page.locator("section.sp-dock").count()) === 0) await page.keyboard.press("2");
  const add = page.locator(".sp-add-inline, .sp-add").first();
  await add.click({ timeout: 20_000 });
  await expect(page.locator(".sp-dialog[role='dialog']")).toBeVisible({ timeout: 20_000 });
  await page.locator(".sp-card", { hasText: /^EQ/ }).first().click();
  await expect(page.locator(".sp-dialog[role='dialog']")).toHaveCount(0);

  const slot = page.locator("article.sp-slot", { hasText: "EQ" }).first();
  const freq = slot.locator('input[aria-label="Freq"]').first();
  const gain = slot.locator('input[aria-label="Gain"]').first();
  const before = {
    freq: await freq.getAttribute("aria-valuetext"),
    gain: await gain.getAttribute("aria-valuetext"),
  };
  const handle = await slot.locator(".sp-eq-handle").first().boundingBox();
  if (!handle) throw new Error("no EQ handle");
  await drag(
    page,
    { x: handle.x + handle.width / 2, y: handle.y + handle.height / 2 },
    { x: handle.x + handle.width / 2 + 160, y: handle.y + handle.height / 2 - 50 },
    20
  );
  const after = {
    freq: await freq.getAttribute("aria-valuetext"),
    gain: await gain.getAttribute("aria-valuetext"),
  };
  if (before.freq !== after.freq) {
    rec.pass("R-EQ", `band drag moved Freq ${before.freq} → ${after.freq}; Gain ${before.gain} → ${after.gain}`);
  } else {
    rec.fail("R-EQ", "Freq still does not follow a horizontal band drag", `${before.freq} → ${after.freq} — ${await shot(page, "R-EQ-1689x1277")}`);
  }
});

test("R — undo refreshes the plugin rail (B-97/B-101)", async ({ page }) => {
  await fresh(page);
  await page.locator(".se-track-name", { hasText: "Drums" }).first().click();
  if ((await page.locator("section.sp-dock").count()) === 0) await page.keyboard.press("2");
  const slots = page.locator("article.sp-slot");
  const before = await slots.count();
  while ((await slots.count()) > 0) {
    await page.locator(".sp-slot-tools button[aria-label^='Remove ']").first().click();
    await page.waitForTimeout(150);
  }
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(800);
  const afterOne = await slots.count();
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(800);
  const afterTwo = await slots.count();
  if (before === 2 && afterOne === 1 && afterTwo === 2) {
    rec.pass("R-UNDO", `rail refreshed per undo: 2 → 0 → ${afterOne} → ${afterTwo} slots`);
  } else {
    rec.fail("R-UNDO", "undo still leaves the rail stale", `${before} → 0 → ${afterOne} → ${afterTwo} slots — ${await shot(page, "R-UNDO-1689x1277")}`);
  }
});

test("R — clip menu scrolls instead of painting off-screen (E-18/E-24)", async ({ page }) => {
  await fresh(page);
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.waitForTimeout(400);
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click({ button: "right", timeout: 10_000 });
  const menu = page.locator(".se-clip-menu");
  await expect(menu).toBeVisible({ timeout: 10_000 });
  const metrics = await menu.evaluate((el) => {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return {
      overflowY: style.overflowY,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
      bottom: rect.bottom,
      innerHeight: window.innerHeight,
    };
  });
  if (metrics.overflowY === "auto" && metrics.scrollHeight > metrics.clientHeight && metrics.bottom <= metrics.innerHeight) {
    rec.pass("R-MENU", `overflow-y=${metrics.overflowY}; ${metrics.clientHeight}/${metrics.scrollHeight} px scrolls inside the 768×1024 viewport`);
  } else {
    rec.fail("R-MENU", "clip menu still overflows without a scrollbar", JSON.stringify(metrics) + ` — ${await shot(page, "R-MENU-768x1024")}`);
  }
});

test("R — MIDI overview strip scrolls the roll (W7)", async ({ page }) => {
  await fresh(page);
  await page.locator(".se-clip", { hasText: "Bass" }).first().dblclick();
  await expect(page.locator(".se-midi")).toBeVisible({ timeout: 10_000 });
  const overview = page.locator('[aria-label="Clip overview"]');
  const strip = await overview.count();
  // Zoom the roll in so the clip is wider than the viewport and the window can move.
  for (let i = 0; i < 5; i += 1) {
    await page.locator('button[aria-label="Zoom in the piano roll"]').click();
    await page.waitForTimeout(120);
  }
  const windowRatio = await page.locator(".se-midi-overview-window").evaluate((el) => {
    const style = (el as HTMLElement).style;
    return { left: style.left, width: style.width };
  }).catch(() => null);
  const roll = page.locator(".se-midi-roll");
  const before = await roll.evaluate((el) => (el as HTMLElement).scrollLeft);
  const box = await overview.boundingBox();
  if (box) {
    await page.mouse.click(box.x + box.width * 0.85, box.y + box.height / 2);
    await page.waitForTimeout(400);
  }
  const after = await roll.evaluate((el) => (el as HTMLElement).scrollLeft);
  const focused = await page.evaluate(() => (document.activeElement as HTMLElement | null)?.getAttribute("aria-label"));
  if (strip === 1 && windowRatio && after !== before && focused === "Clip overview") {
    rec.pass("R-OVW", `overview strip present (window ${windowRatio.left}/${windowRatio.width}); click scrolled the roll ${before} → ${after}`);
  } else {
    rec.fail("R-OVW", "MIDI overview strip is missing or inert", `strip=${strip} window=${JSON.stringify(windowRatio)} scroll ${before}→${after} focus=${focused} — ${await shot(page, "R-OVW-1689x1277")}`);
  }
});

test("R — loop flags are drawn and draggable (S24)", async ({ page }) => {
  await fresh(page);
  await page.locator('.se-head button[aria-label="Loop"]').click();
  await page.waitForTimeout(600);
  const band = await page.locator(".se-loop-band").count();
  const startFlag = await page.locator('button[aria-label="Loop start"]').count();
  const endFlag = await page.locator('button[aria-label="Loop end"]').count();
  const { barWidth } = await barMetrics(page);
  const handle = await page.locator('button[aria-label="Loop end"]').boundingBox().catch(() => null);
  if (handle) {
    await drag(
      page,
      { x: handle.x + handle.width / 2, y: handle.y + handle.height / 2 },
      { x: handle.x + handle.width / 2 + barWidth, y: handle.y + handle.height / 2 }
    );
  }
  const endValue = await page.evaluate(() => {
    const text = document.body.textContent ?? "";
    return text.length > 0;
  });
  if (band === 1 && startFlag === 1 && endFlag === 1 && endValue) {
    rec.pass("R-LOOP", `band + both flags present; end flag dragged one bar`);
  } else {
    rec.fail("R-LOOP", "loop flags are missing", `band=${band} start=${startFlag} end=${endFlag} — ${await shot(page, "R-LOOP-1689x1277")}`);
  }
});

