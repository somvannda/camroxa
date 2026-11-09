import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Pixel-parity gate (D-022). Targets come from
 * `docs/studio/reference/METRICS.json` and the measured frame in spec §1.
 *
 * Renders the editor at the captured viewport (1689×1277, DPR 1) and asserts the
 * global frame: header/tracks/body/footer heights and widths, row pitch, bar pitch,
 * and the captured palette. Branding and copy are the only intentional deviations.
 */

const REFERENCE_VIEWPORT = { width: 1689, height: 1277 };

test("global frame matches the captured metrics", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel gate" });

  const frame = await page.evaluate(() => {
    const rect = (selector: string) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const box = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return {
        x: Math.round(box.x),
        y: Math.round(box.y),
        width: Math.round(box.width),
        height: Math.round(box.height),
        background: style.backgroundColor,
        color: style.color,
        fontSize: style.fontSize,
      };
    };
    return {
      head: rect(".se-head"),
      tracks: rect(".se-tracks"),
      track: rect(".se-track"),
      lane: rect(".se-lane"),
      foot: rect(".se-foot"),
      body: rect(".se-body"),
      shell: rect(".se-shell"),
    };
  });

  // §1 frame.
  expect(frame.head).toMatchObject({ height: 52, background: "rgb(10, 10, 10)" });
  expect(frame.tracks).toMatchObject({ width: 260, background: "rgb(28, 28, 30)" });
  expect(frame.foot).toMatchObject({ height: 52, background: "rgb(10, 10, 10)" });
  expect(frame.body).toMatchObject({ background: "rgb(17, 17, 17)" });
  expect(frame.shell?.color).toBe("rgb(247, 244, 239)");

  // §52.1 row rhythm.
  expect(frame.track?.height).toBe(85);
  expect(frame.lane?.height).toBe(86);
  expect(frame.lane?.x).toBe(260);

  // Track header internals: name at x48 / 11 px, controls 24×24 (extend 16),
  // faders 167 px + 50 px at x28 and y132.
  const track = await page.evaluate(() => {
    const name = document.querySelector(".se-track-name")?.getBoundingClientRect();
    const buttons = Array.from(
      document.querySelectorAll(".se-track-buttons button")
    ).map((element) => {
      const rect = element.getBoundingClientRect();
      return { x: Math.round(rect.x), width: Math.round(rect.width), height: Math.round(rect.height) };
    });
    const sliders = Array.from(document.querySelectorAll(".se-track-slider")).map((element) => {
      const rect = element.getBoundingClientRect();
      return { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) };
    });
    return {
      nameX: name ? Math.round(name.x) : null,
      nameFont: document.querySelector(".se-track-name")
        ? getComputedStyle(document.querySelector(".se-track-name") as Element).fontSize
        : null,
      buttons,
      sliders,
    };
  });
  expect(track.nameX).toBe(48);
  expect(track.nameFont).toBe("11px");
  expect(track.buttons.slice(0, 3).every((button) => button.width === 24)).toBe(true);
  expect(track.buttons.slice(0, 3).every((button) => button.height === 24)).toBe(true);
  expect(track.buttons[3]?.width).toBe(16);
  expect(Math.abs((track.buttons[0]?.x ?? 0) - 162)).toBeLessThanOrEqual(6);
  expect(track.sliders).toHaveLength(2);
  expect(track.sliders[0]?.x).toBe(28);
  expect(track.sliders[0]?.width).toBe(167);
  expect(track.sliders[0]?.height).toBe(25);
  expect(Math.abs((track.sliders[0]?.y ?? 0) - 126)).toBeLessThanOrEqual(1);
  expect(track.sliders[1]).toMatchObject({ x: 201, width: 50 });

  // §4 ruler: 30 px band, first lane at y82, clip 82 px tall from y84.
  const timeline = await page.evaluate(() => {
    const rect = (selector: string) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const box = element.getBoundingClientRect();
      return {
        y: Math.round(box.y),
        height: Math.round(box.height),
        background: getComputedStyle(element).backgroundColor,
      };
    };
    return {
      ruler: rect(".se-ruler-bars"),
      lane: rect(".se-lane"),
      clip: rect(".se-clip"),
      radius: document.querySelector(".se-clip")
        ? getComputedStyle(document.querySelector(".se-clip") as Element).borderTopLeftRadius
        : null,
    };
  });
  expect(timeline.ruler).toMatchObject({ height: 30, background: "rgb(16, 16, 18)" });
  expect(timeline.lane?.y).toBe(82);
  expect(timeline.clip).toMatchObject({ y: 84, height: 82 });
  expect(timeline.radius).toBe("10px");

  // §2 header: 36 px pills on a 52 px band; project chip at x≈115, undo/redo grouped.
  const header = await page.evaluate(() => {
    const measure = (selector: string) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const box = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return {
        x: Math.round(box.x),
        y: Math.round(box.y),
        height: Math.round(box.height),
        radius: style.borderTopLeftRadius,
        background: style.backgroundColor,
      };
    };
    return {
      chip: measure(".se-chip"),
      group: measure(".se-head-group"),
      icon: measure(".se-head .se-icon"),
      transport: measure(".se-transport"),
      tempo: measure(".se-tempo"),
    };
  });
  expect(header.chip).toMatchObject({ y: 8, height: 36, radius: "999px", background: "rgb(28, 28, 30)" });
  expect(Math.abs((header.chip?.x ?? 0) - 115)).toBeLessThanOrEqual(6);
  expect(header.group).toMatchObject({ y: 8, height: 36, radius: "999px" });
  expect(header.icon?.height).toBe(36);
  expect(header.transport?.height).toBe(36);
  expect(header.tempo?.height).toBe(36);

  // §44.3 ruler pitch: adjacent bar ticks are 96 px apart at the default zoom.
  const ticks = await page.locator(".se-bar-tick").evaluateAll((nodes) =>
    nodes.slice(0, 2).map((node) => Math.round(node.getBoundingClientRect().x))
  );
  expect(ticks).toHaveLength(2);
  expect(ticks[1] - ticks[0]).toBe(96);
});

test("library song rows use the captured anatomy", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel rows" });
  await page.getByRole("button", { name: "Library", exact: true }).click();
  await page.getByRole("button", { name: /All Songs/ }).click();
  const row = page.locator(".se-lib-song").first();
  await expect(row).toBeVisible();
  const anatomy = await row.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const art = element.querySelector(".se-lib-art")?.getBoundingClientRect();
    const title = element.querySelector(".se-lib-title");
    const chip = document.querySelector(".se-lib-tool, .se-lib-chip")?.getBoundingClientRect();
    return {
      rowHeight: Math.round(rect.height),
      art: art ? Math.round(art.width) : null,
      titleFont: title ? getComputedStyle(title).fontSize : null,
      chipHeight: chip ? Math.round(chip.height) : null,
    };
  });
  // Captured level-2 rows: 56 px art, 15 px title, 30 px filter chips.
  expect(anatomy.art).toBe(56);
  expect(anatomy.titleFont).toBe("15px");
  expect(anatomy.chipHeight).toBe(30);
  expect(anatomy.rowHeight).toBeGreaterThanOrEqual(76);
});

test("What's This card matches the captured hover card", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel help" });
  const card = page.locator(".se-help-first");
  await expect(card).toBeVisible();
  const box = await card.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    const title = element.querySelector("strong");
    const body = element.querySelector(":scope > span");
    return {
      width: Math.round(rect.width),
      bottom: Math.round(window.innerHeight - rect.bottom),
      radius: style.borderTopLeftRadius,
      padding: style.paddingTop,
      background: style.backgroundColor,
      color: style.color,
      titleSize: title ? getComputedStyle(title).fontSize : null,
      titleWeight: title ? getComputedStyle(title).fontWeight : null,
      bodySize: body ? getComputedStyle(body).fontSize : null,
      bodyLine: body ? getComputedStyle(body).lineHeight : null,
    };
  });
  // §7.1: 256 px wide, light #d2d0ce, radius 16, padding 16, 12 px/700 title.
  expect(box.width).toBe(256);
  expect(box.radius).toBe("16px");
  expect(box.padding).toBe("16px");
  expect(box.background).toBe("rgb(210, 208, 206)");
  expect(box.color).toBe("rgb(17, 17, 17)");
  expect(box.titleSize).toBe("12px");
  expect(box.titleWeight).toBe("700");
  expect(box.bodySize).toBe("12px");
  expect(box.bodyLine).toBe("16.2px");
  expect(box.bottom).toBe(64);
});

test("Learn menu matches the captured popover", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel learn" });
  await page.getByRole("button", { name: /Learn/ }).click();
  const menu = page.getByRole("menu", { name: "Learn" });
  await expect(menu).toBeVisible();
  const info = await menu.evaluate((element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    const rows = Array.from(element.querySelectorAll(":scope > button")).map((row) => {
      const box = row.getBoundingClientRect();
      return { text: (row.textContent ?? "").replace(/\s+/g, " ").trim(), height: Math.round(box.height) };
    });
    return {
      width: Math.round(rect.width),
      radius: style.borderTopLeftRadius,
      background: style.backgroundColor,
      rows,
    };
  });
  // S13: 206 px wide, #1c1c1e, 12 px radius, 44 px rows in the captured order.
  expect(info.width).toBe(206);
  expect(info.radius).toBe("12px");
  expect(info.background).toBe("rgb(28, 28, 30)");
  expect(info.rows.map((row) => row.text)).toEqual([
    "Keyboard Shortcuts shift ?",
    "YouTube Tutorials",
    "Learning Center",
    "What's This? On",
  ]);
  expect(info.rows.every((row) => row.height === 44)).toBe(true);
});

test("track options menu matches the captured popover", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel track menu" });
  await page.getByRole("button", { name: "Options for Track 1" }).click();
  const menu = page.getByRole("menu", { name: "Track 1 options" });
  await expect(menu).toBeVisible();
  const info = await menu.evaluate((element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    const rows = Array.from(element.querySelectorAll(":scope > button")).map((row) => {
      const box = row.getBoundingClientRect();
      return { text: (row.textContent ?? "").replace(/\s+/g, " ").trim(), height: Math.round(box.height) };
    });
    return {
      width: Math.round(rect.width),
      right: Math.round(rect.right),
      radius: style.borderTopLeftRadius,
      background: style.backgroundColor,
      rows,
    };
  });
  // S19: 164 px card on #1c1c1e, 12 px radius, 33 px rows inside the 260 px panel.
  expect(info.width).toBe(164);
  expect(info.radius).toBe("12px");
  expect(info.background).toBe("rgb(28, 28, 30)");
  expect(info.right).toBeLessThanOrEqual(260);
  expect(info.rows.map((row) => row.text)).toEqual([
    "Rename track",
    "Collapse controls",
    "Duplicate",
    "Hide & Mute Track",
    "Delete",
  ]);
  expect(info.rows.every((row) => row.height === 33)).toBe(true);
});

test("add-track menu matches the captured popover", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel add menu" });
  await page.getByRole("button", { name: /Add new track/ }).click();
  const menu = page.getByRole("menu", { name: "Add a track" });
  await expect(menu).toBeVisible();
  const info = await menu.evaluate((element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    const rows = Array.from(element.querySelectorAll("button")).map((row) => {
      const box = row.getBoundingClientRect();
      const icon = row.querySelector(".se-add-icon")?.getBoundingClientRect();
      return {
        text: (row.textContent ?? "").replace(/\s+/g, " ").trim(),
        height: Math.round(box.height),
        icon: icon ? Math.round(icon.width) : null,
      };
    });
    return {
      width: Math.round(rect.width),
      radius: style.borderTopLeftRadius,
      background: style.backgroundColor,
      rows,
    };
  });
  // S20: 208 px card on #1c1c1e, 50 px rows, 24 px coloured icon squares.
  expect(info.width).toBe(208);
  expect(info.radius).toBe("12px");
  expect(info.background).toBe("rgb(28, 28, 30)");
  expect(info.rows.map((row) => row.text)).toEqual(["Audio A", "MIDI M", "Upload U"]);
  expect(info.rows.every((row) => row.height === 50)).toBe(true);
  expect(info.rows.every((row) => row.icon === 24)).toBe(true);
});

test("project menu matches the captured popover", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel project menu" });
  await page.locator(".se-chip").click();
  const menu = page.getByRole("menu", { name: "Project options" });
  await expect(menu).toBeVisible();
  const info = await menu.evaluate((element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    const rows = Array.from(element.querySelectorAll("button")).map((row) => {
      const box = row.getBoundingClientRect();
      return { text: (row.textContent ?? "").replace(/\s+/g, " ").trim(), height: Math.round(box.height) };
    });
    return {
      width: Math.round(rect.width),
      radius: style.borderTopLeftRadius,
      background: style.backgroundColor,
      rows,
    };
  });
  // S07: 212 px card on #1c1c1e, 12 px radius, 34 px icon rows.
  expect(info.width).toBe(212);
  expect(info.radius).toBe("12px");
  expect(info.background).toBe("rgb(28, 28, 30)");
  expect(info.rows).toHaveLength(9);
  expect(info.rows[0]?.text).toBe("New Project");
  expect(info.rows[7]?.text).toBe("Studio Settings ctrl shift ,");
  expect(info.rows.every((row) => row.height === 34)).toBe(true);
});

test("clip context menu matches the captured popover", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel clip menu" });
  await page.locator(".se-clip").first().click({ button: "right" });
  const menu = page.getByRole("menu", { name: "Clip options" });
  await expect(menu).toBeVisible();
  const info = await menu.evaluate((element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    const rows = Array.from(element.querySelectorAll(":scope > button")).map((row) => {
      const box = row.getBoundingClientRect();
      const hint = row.querySelector("span");
      return {
        text: (row.textContent ?? "").replace(/\s+/g, " ").trim(),
        height: Math.round(box.height),
        hintSize: hint ? getComputedStyle(hint).fontSize : null,
      };
    });
    return {
      width: Math.round(rect.width),
      radius: style.borderTopLeftRadius,
      background: style.backgroundColor,
      rows,
    };
  });
  // S26: 158 px card on #1c1c1e, 12 px radius, 38 px icon rows, 11 px hints.
  expect(info.width).toBe(158);
  expect(info.radius).toBe("12px");
  expect(info.background).toBe("rgb(28, 28, 30)");
  expect(info.rows[0]?.text).toBe("Copy Ctrl C");
  expect(info.rows[0]?.hintSize).toBe("11px");
  expect(info.rows.every((row) => row.height === 38)).toBe(true);
});

test("share dialog matches the captured surface", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel share" });
  await page.locator(".se-chip").click();
  await page.getByRole("menuitem", { name: /Share Project/ }).click();
  const dialog = page.locator(".se-dialog");
  await expect(dialog).toBeVisible();
  const info = await dialog.evaluate((element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    const title = element.querySelector("h2");
    const button = element.querySelector(".se-dialog-foot .se-pill.on");
    return {
      width: Math.round(rect.width),
      radius: style.borderTopLeftRadius,
      padding: style.paddingTop,
      background: style.backgroundColor,
      titleSize: title ? getComputedStyle(title).fontSize : null,
      titleWeight: title ? getComputedStyle(title).fontWeight : null,
      actionHeight: button ? Math.round(button.getBoundingClientRect().height) : null,
      backdrop: getComputedStyle(element.parentElement as Element).backgroundColor,
    };
  });
  // S12: 480 px dialog on #1c1c1e, radius 24, padding 32, 24 px/700 title,
  // 44 px pill actions over a dimmed editor.
  expect(info.width).toBe(480);
  expect(info.radius).toBe("24px");
  expect(info.padding).toBe("32px");
  expect(info.background).toBe("rgb(28, 28, 30)");
  expect(info.titleSize).toBe("24px");
  expect(info.titleWeight).toBe("700");
  expect(info.actionHeight).toBe(44);
  expect(info.backdrop).toBe("rgba(0, 0, 0, 0.72)");
});

test("library rail is a 360 px floating card inset 8 px", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel rail" });
  await page.getByRole("button", { name: "Library", exact: true }).click();
  const library = page.getByRole("complementary", { name: "Library" });
  await expect(library).toBeVisible();
  const box = await library.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      width: Math.round(rect.width),
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      bottom: Math.round(rect.bottom),
      radius: style.borderTopLeftRadius,
      background: style.backgroundColor,
    };
  });
  // §19.1: floating card pinned 8 px from the top/right/bottom, 360 px wide.
  expect(box).toMatchObject({
    width: 360,
    x: REFERENCE_VIEWPORT.width - 368,
    y: 8,
    bottom: REFERENCE_VIEWPORT.height - 8,
    radius: "12px",
    background: "rgb(16, 16, 18)",
  });

  // The shell shrinks while the rail is open: header and footer stop at the card edge.
  const edges = await page.evaluate(() => {
    const right = (selector: string) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      return Math.round(element.getBoundingClientRect().right);
    };
    const last = (selector: string) => {
      const nodes = document.querySelectorAll(selector);
      const element = nodes[nodes.length - 1];
      return element ? Math.round(element.getBoundingClientRect().right) : null;
    };
    return {
      head: right(".se-head"),
      foot: right(".se-foot"),
      timeline: right(".se-body"),
      lastFoot: last(".se-foot .se-icon"),
    };
  });
  expect(edges.head).toBe(REFERENCE_VIEWPORT.width);
  expect(edges.timeline).toBe(REFERENCE_VIEWPORT.width);
  expect(edges.lastFoot).toBeLessThan(REFERENCE_VIEWPORT.width - 360);
});
