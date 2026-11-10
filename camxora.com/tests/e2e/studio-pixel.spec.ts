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
  expect(frame.head).toMatchObject({ height: 52, background: "rgb(7, 10, 18)" });
  expect(frame.tracks).toMatchObject({ width: 260, background: "rgb(15, 20, 31)" });
  expect(frame.foot).toMatchObject({ height: 52, background: "rgb(7, 10, 18)" });
  expect(frame.body).toMatchObject({ background: "rgb(11, 15, 25)" });
  expect(frame.shell?.color).toBe("rgb(248, 250, 252)");

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
    const sliders = Array.from(document.querySelectorAll(".se-track .se-track-slider")).map((element) => {
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
  expect(
    await page.evaluate(() => {
      const row = document.querySelector(".se-track");
      const pan = document.querySelector(".se-pan-input");
      return {
        row: row ? getComputedStyle(row).backgroundColor : null,
        pan: pan !== null,
      };
    })
  ).toEqual({ row: "rgba(0, 0, 0, 0)", pan: true });
  expect(track.sliders).toHaveLength(1);
  expect(track.sliders[0]?.x).toBe(28);
  expect(track.sliders[0]?.width).toBe(167);
  expect(track.sliders[0]?.height).toBe(25);
  expect(Math.abs((track.sliders[0]?.y ?? 0) - 126)).toBeLessThanOrEqual(1);
  const pan = await page.evaluate(() => {
    const input = document.querySelector(".se-pan-input")?.getBoundingClientRect();
    const pointer = document.querySelector(".se-pan-pointer");
    return {
      input: input ? { x: Math.round(input.x), width: Math.round(input.width) } : null,
      angle: pointer ? getComputedStyle(pointer).transform : null,
    };
  });
  expect(pan.input).toEqual({ x: 201, width: 50 });
  expect(pan.angle).not.toBe("none");

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
  expect(timeline.ruler).toMatchObject({ height: 30, background: "rgb(15, 20, 31)" });
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

  // §4 playhead: a 1 px line with a 10 px flag at the ruler's bottom edge.
  const playhead = await page.evaluate(() => {
    const flag = document.querySelector(".se-playhead-flag")?.getBoundingClientRect();
    const line = document.querySelector(".se-playhead");
    const lineBox = line?.getBoundingClientRect();
    return {
      flagX: flag ? Math.round(flag.x) : null,
      flagWidth: flag ? Math.round(flag.width) : null,
      lineX: lineBox ? Math.round(lineBox.x) : null,
      lineColor: line ? getComputedStyle(line).backgroundColor : null,
    };
  });
  expect(playhead.flagX).not.toBeNull();
  expect(Math.abs((playhead.flagX ?? 0) - (playhead.lineX ?? 0))).toBeLessThanOrEqual(5);
  expect(playhead.lineColor).toBe("rgb(76, 76, 76)");

  // §4 bottom time ruler: 22 px band #1e1e20 with dim labels.
  const timeRuler = await page.evaluate(() => {
    const band = document.querySelector(".se-ruler-time");
    const label = document.querySelector(".se-time-tick");
    return {
      height: band ? Math.round(band.getBoundingClientRect().height) : null,
      background: band ? getComputedStyle(band).backgroundColor : null,
      labelColor: label ? getComputedStyle(label).color : null,
    };
  });
  expect(timeRuler.height).toBe(22);
  expect(timeRuler.background).toBe("rgb(15, 20, 31)");
  expect(timeRuler.labelColor).toBe("rgb(139, 144, 166)");
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
  expect(info.background).toBe("rgb(19, 24, 38)");
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
  expect(info.background).toBe("rgb(19, 24, 38)");
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
  expect(info.background).toBe("rgb(19, 24, 38)");
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
  expect(info.background).toBe("rgb(19, 24, 38)");
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
    const rows = Array.from(
      element.querySelectorAll(":scope > button, :scope > .se-menu-sub > button")
    ).map((row) => {
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
  expect(info.background).toBe("rgb(19, 24, 38)");
  expect(info.rows.map((row) => row.text)).toEqual([
    "Copy Ctrl C",
    "Paste Ctrl V",
    "Duplicate Ctrl D",
    "Delete Backspace",
    "Heal Edits",
    "Split Ctrl E",
    "Rename",
    "Clip Info",
    "Clip Color",
    "Get Stems",
    "Download WAV",
    "Get MIDI",
    "Remove FX",
  ]);
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
  expect(info.background).toBe("rgb(19, 24, 38)");
  expect(info.titleSize).toBe("24px");
  expect(info.titleWeight).toBe("700");
  expect(info.actionHeight).toBe(44);
  expect(info.backdrop).toBe("rgba(0, 0, 0, 0.72)");
});

test("master strip is pinned to the captured track panel bottom", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel master" });
  const info = await page.evaluate(() => {
    const strip = document.querySelector(".se-master-strip");
    const fader = strip?.querySelector(".se-track-slider");
    if (!strip || !fader) return null;
    const stripBox = strip.getBoundingClientRect();
    const faderBox = fader.getBoundingClientRect();
    return {
      right: Math.round(stripBox.right),
      faderX: Math.round(faderBox.x),
      faderWidth: Math.round(faderBox.width),
      footerMaster: document.querySelectorAll(".se-foot .se-master").length,
      label: strip.querySelector(".se-master-label")?.textContent,
    };
  });
  // S19/S49: Main + fader pinned at the bottom of the 260 px panel, not the footer.
  expect(info).not.toBeNull();
  expect(info?.right).toBe(259);
  expect(info?.label).toBe("Main");
  expect(info?.faderX).toBe(12);
  expect(info?.faderWidth).toBe(239);
  expect(info?.footerMaster).toBe(0);
});

test("selecting a track highlights its panel row and lane", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel lane" });
  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  const info = await page.evaluate(() => {
    const row = document.querySelector(".se-track");
    const lane = document.querySelector(".se-lane");
    return {
      rowSelected: row?.classList.contains("selected") ?? false,
      laneSelected: lane?.classList.contains("selected") ?? false,
      rowBackground: row ? getComputedStyle(row).backgroundColor : null,
      laneBackground: lane ? getComputedStyle(lane).backgroundColor : null,
    };
  });
  // S25: the selected track tints both the gutter row and its lane.
  expect(info.rowSelected).toBe(true);
  expect(info.laneSelected).toBe(true);
  expect(info.rowBackground).toBe("rgb(33, 41, 59)");
  expect(info.laneBackground).toBe("rgba(255, 255, 255, 0.05)");
});

test("hovering a clip explains it with the captured card", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel clip help" });
  await page.locator(".se-clip").first().hover();
  const tip = page.getByRole("tooltip");
  await expect(tip).toBeVisible();
  await expect(tip).toContainText("Clip");
  const box = await tip.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      width: Math.round(rect.width),
      radius: getComputedStyle(element).borderTopLeftRadius,
      background: getComputedStyle(element).backgroundColor,
    };
  });
  // §7.1: the per-control card is the same 256 px light surface as the intro card.
  expect(box.width).toBe(256);
  expect(box.radius).toBe("16px");
  expect(box.background).toBe("rgb(210, 208, 206)");
});

test("export toast matches the captured banner", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel toast" });
  await page.getByRole("button", { name: "Export menu" }).click();
  const downloaded = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: /Project \(JSON\)/ }).click();
  await downloaded;
  const toast = page.getByRole("status").filter({ hasText: "download started" });
  await expect(toast).toBeVisible();
  const box = await toast.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      width: Math.round(rect.width),
      left: Math.round(rect.left),
      radius: style.borderTopLeftRadius,
      background: style.backgroundColor,
      fontSize: style.fontSize,
    };
  });
  // S51: a bottom-left banner on #1c1c1e, radius 16, 888 px wide.
  expect(box.width).toBe(888);
  expect(box.left).toBe(24);
  expect(box.radius).toBe("16px");
  expect(box.background).toBe("rgb(19, 24, 38)");
  expect(box.fontSize).toBe("22px");
});

test("track panel head toggles every track's controls", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel head" });
  const head = page.locator(".se-tracks-head");
  await expect(head.locator("button")).toHaveCount(2);
  const sizes = await head.locator("button").evaluateAll((nodes) =>
    nodes.map((node) => Math.round(node.getBoundingClientRect().width))
  );
  // S16: 24 px icons at each end of the 29 px head. The right control collapses the
  // panel to a 44 px rail and brings it back.
  expect(sizes).toEqual([24, 24]);
  await head.getByRole("button", { name: "Collapse track panel" }).click();
  const panel = page.locator(".se-tracks");
  await expect(panel).toHaveClass(/is-collapsed/);
  await expect(panel).toHaveCSS("width", "44px");
  await page.getByRole("button", { name: "Expand track panel" }).click();
  await expect(panel).not.toHaveClass(/is-collapsed/);
  await expect(panel).toHaveCSS("width", "260px");
  await head.getByRole("button", { name: "Collapse all track controls" }).click();
  await expect(page.locator(".se-track .se-track-slider")).toHaveCount(0);
  await expect(page.locator(".se-pan-input")).toHaveCount(0);
  await head.getByRole("button", { name: "Expand all track controls" }).click();
  await expect(page.locator(".se-track .se-track-slider")).toHaveCount(1);
  await expect(page.locator(".se-pan-input")).toHaveCount(1);
});

test("clip info rail follows the captured anatomy", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel inspector" });
  await page.locator(".se-clip").first().click({ button: "right" });
  await page.getByRole("menuitem", { name: /Clip Info/ }).click();
  const panel = page.getByRole("complementary", { name: "Clip info" });
  await expect(panel).toBeVisible();
  const info = await panel.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const art = element.querySelector(".se-clip-art")?.getBoundingClientRect();
    const tab = element.querySelector(".se-lib-tab")?.getBoundingClientRect();
    const card = element.querySelector(".se-clip-card");
    return {
      x: Math.round(rect.x),
      width: Math.round(rect.width),
      radius: getComputedStyle(element).borderTopLeftRadius,
      background: getComputedStyle(element).backgroundColor,
      art: art ? Math.round(art.width) : null,
      tabHeight: tab ? Math.round(tab.height) : null,
      cardRadius: card ? getComputedStyle(card).borderTopLeftRadius : null,
      cardBackground: card ? getComputedStyle(card).backgroundColor : null,
    };
  });
  // S27: the inspector is the same floating 360 px rail, with a 48 px hero tile,
  // 38 px tabs and quiet #141416 section cards.
  expect(info).toMatchObject({
    x: REFERENCE_VIEWPORT.width - 368,
    width: 360,
    radius: "12px",
    background: "rgb(15, 20, 31)",
    art: 48,
    tabHeight: 38,
    cardRadius: "12px",
    cardBackground: "rgb(19, 24, 38)",
  });
});

test("song detail rail follows the captured anatomy", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel song" });
  await page.getByRole("button", { name: "Library", exact: true }).click();
  await page.getByRole("button", { name: /All Songs/ }).click();
  await page.locator(".se-lib-song").first().dblclick();
  const panel = page.getByRole("complementary", { name: "Song details" });
  await expect(panel).toBeVisible();
  const info = await panel.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const art = element.querySelector(".se-song-hero .se-clip-art")?.getBoundingClientRect();
    const tab = element.querySelector(".se-lib-tab")?.getBoundingClientRect();
    const card = element.querySelector(".se-song-section");
    return {
      x: Math.round(rect.x),
      width: Math.round(rect.width),
      radius: getComputedStyle(element).borderTopLeftRadius,
      art: art ? Math.round(art.width) : null,
      tabHeight: tab ? Math.round(tab.height) : null,
      cardBackground: card ? getComputedStyle(card).backgroundColor : null,
      cardRadius: card ? getComputedStyle(card).borderTopLeftRadius : null,
    };
  });
  const mini = panel.locator(".se-song-mini");
  await expect(mini).toBeVisible();
  expect(await mini.evaluate((element) => Math.round(element.getBoundingClientRect().height))).toBeGreaterThan(40);

  // S27/EXTRA detail: floating 360 px rail, 52 px hero, 38 px tabs, #141416 cards.
  expect(info).toMatchObject({
    x: REFERENCE_VIEWPORT.width - 368,
    width: 360,
    radius: "12px",
    art: 52,
    tabHeight: 38,
    cardBackground: "rgb(19, 24, 38)",
    cardRadius: "12px",
  });
});

test("plugin dock sits above the footer on the captured surface", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel dock" });
  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  const info = await page.evaluate(() => {
    const dock = document.querySelector(".sp-dock");
    const foot = document.querySelector(".se-foot");
    const add = document.querySelector(".sp-add-inline");
    if (!dock || !foot || !add) return null;
    const dockBox = dock.getBoundingClientRect();
    const footBox = foot.getBoundingClientRect();
    return {
      dockWidth: Math.round(dockBox.width),
      dockBottom: Math.round(dockBox.bottom),
      footTop: Math.round(footBox.top),
      background: getComputedStyle(dock).backgroundColor,
      addHeight: Math.round(add.getBoundingClientRect().height),
    };
  });
  // The captured dock is a full-width band above the footer, with a 36 px add pill.
  expect(info).not.toBeNull();
  expect(info?.dockWidth).toBe(REFERENCE_VIEWPORT.width);
  expect(info?.dockBottom).toBe(info?.footTop);
  expect(info?.background).toBe("rgb(15, 20, 31)");
  expect(info?.addHeight).toBe(36);
});

test("the convolution card loads an impulse response from the library", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel convolution" });
  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  await page.locator(".sp-add-inline").click();
  await page.getByRole("dialog", { name: "Add a track plugin" })
    .getByRole("button", { name: /^Convolution/ })
    .first()
    .click();

  const slot = page.locator(".sp-slot").first();
  await expect(slot.getByRole("button", { name: "Impulse response" })).toContainText(
    "No impulse response"
  );
  await expect(slot.getByRole("slider", { name: "Gain" })).toHaveValue("0");
  await expect(slot.locator(".sp-ir")).toHaveAttribute("aria-label", "No impulse response");

  await slot.getByRole("button", { name: "Impulse response" }).click();
  const menu = page.getByRole("menu", { name: "Impulse responses" });
  await expect(menu.getByRole("menuitem")).toHaveCount(6);
  await menu.getByRole("menuitem", { name: "Halls" }).click();
  await menu.getByRole("menuitem", { name: "New England Hall" }).click();
  await expect(menu).toHaveCount(0);
  await expect(slot.getByRole("button", { name: "Impulse response" })).toContainText(
    "Halls › New England Hall"
  );
  await expect(slot.locator(".sp-ir")).toHaveAttribute(
    "aria-label",
    "Impulse response New England Hall"
  );
});

test("the empty dock rail suggests the next three effects", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel ghosts" });
  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  await page.locator(".sp-add-inline").click();
  await page.getByRole("dialog", { name: "Add a track plugin" })
    .getByRole("button", { name: /^EQ/ })
    .first()
    .click();

  const rail = page.getByLabel("Add another effect");
  await expect(rail).toBeVisible();
  await expect(rail.locator(".sp-ghost")).toHaveCount(3);
  await expect(rail.getByRole("button", { name: "Add Compressor" })).toBeVisible();

  await rail.getByRole("button", { name: "Add Compressor" }).click();
  await expect(page.locator(".sp-slot")).toHaveCount(2);
  await expect(rail.locator(".sp-ghost")).toHaveCount(2);
});

test("plugin catalog dialog matches the captured surface", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel catalog" });
  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  await page.locator(".sp-add-inline").click();
  const dialog = page.getByRole("dialog", { name: "Add a track plugin" });
  await expect(dialog).toBeVisible();
  const info = await dialog.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const card = element.querySelector(".sp-catalog:not(.sp-catalog-mine) .sp-card");
    const label = Array.from(element.querySelectorAll(".sp-catalog-label")).find(
      (node) => node.textContent === "Audio effects"
    );
    return {
      width: Math.round(rect.width),
      radius: getComputedStyle(element).borderTopLeftRadius,
      background: getComputedStyle(element).backgroundColor,
      cardBackground: card ? getComputedStyle(card).backgroundColor : null,
      cardRadius: card ? getComputedStyle(card).borderTopLeftRadius : null,
      label: label?.textContent,
      labelSize: label ? getComputedStyle(label).fontSize : null,
    };
  });
  // S45: MY PLUGINS comes first with the dashed Create-new-plugin card.
  await expect(dialog.locator(".sp-catalog-mine .sp-create")).toBeVisible();
  await expect(dialog.locator(".sp-create-label")).toContainText("Create new plugin");

  // S39: 760 px dialog on #171717, #1c1c1e cards, uppercase section label.
  expect(info).toMatchObject({
    width: 760,
    radius: "16px",
    background: "rgb(23, 23, 23)",
    cardBackground: "rgb(19, 24, 38)",
    cardRadius: "12px",
    label: "Audio effects",
    labelSize: "11px",
  });

  // S39: each card opens with a device preview; ours is drawn from the plugin family.
  const previews = await dialog.locator(".sp-card-preview").evaluateAll((nodes) =>
    nodes.map((node) => Math.round(node.getBoundingClientRect().height))
  );
  expect(previews.length).toBeGreaterThan(0);
  expect(previews.every((height) => height === 88)).toBe(true);
  expect(await dialog.locator(".sp-card-preview path").count()).toBeGreaterThan(0);

  // S39: each card carries a Learn chip that explains the effect; it must not add it.
  const learn = dialog.locator(".sp-card-learn").first();
  await learn.hover();
  const tip = page.getByRole("tooltip");
  await expect(tip).toBeVisible();
  await expect(tip).toContainText("Compressor");
  await learn.click();
  await expect(dialog).toBeVisible();
  await expect(page.locator(".sp-slot")).toHaveCount(0);
});

test("clip colour opens the captured submenu", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel colour" });
  await page.locator(".se-clip").first().click({ button: "right" });
  const menu = page.getByRole("menu", { name: "Clip options" });
  await menu.getByRole("menuitem", { name: "Clip Color" }).click();
  const flyout = menu.locator(".se-clip-menu-colors");
  await expect(flyout).toBeVisible();
  const info = await flyout.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    const menuBox = element.closest(".se-clip-menu")?.getBoundingClientRect();
    return {
      width: Math.round(rect.width),
      radius: style.borderTopLeftRadius,
      background: style.backgroundColor,
      leftOfMenu: menuBox ? Math.round(rect.left - menuBox.right) : null,
      auto: element.querySelector(".se-color-auto")?.textContent?.replace(/\s+/g, " ").trim(),
      swatches: element.querySelectorAll(".se-color-grid button").length,
    };
  });
  // S28: a 196 px card to the right of the row, Auto + five swatches.
  expect(info.width).toBe(196);
  expect(info.radius).toBe("12px");
  expect(info.background).toBe("rgb(19, 24, 38)");
  expect(info.leftOfMenu).toBeGreaterThanOrEqual(3);
  expect(info.leftOfMenu).toBeLessThanOrEqual(16);
  expect(info.auto).toBe("Auto");
  expect(info.swatches).toBe(5);
});

test("EQ card matches the captured band editor and drags", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel curve" });
  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  await page.locator(".sp-add-inline").click();
  const dialog = page.getByRole("dialog", { name: "Add a track plugin" });
  await dialog.getByRole("button", { name: /^EQ\b/ }).first().click();

  const card = page.locator(".sp-slot-eq");
  await expect(card.locator(".sp-eq")).toBeVisible();
  // S40/S42: band selector + switch, six shapes, one handle per band, three knobs.
  await expect(card.getByLabel("EQ band")).toHaveValue("1");
  await expect(card.getByRole("switch", { name: "Band 1 enabled" })).toBeChecked();
  await expect(card.locator(".sp-eq-shapes button")).toHaveCount(6);
  await expect(card.locator(".sp-eq-handle")).toHaveCount(4);
  await expect(card.locator(".sp-knob")).toHaveCount(3);

  const gain = card.getByRole("slider", { name: "Gain" });
  const before = Number(await gain.inputValue());
  const handle = card.locator(".sp-eq-handle").first();
  const box = await handle.boundingBox();
  if (!box) throw new Error("no handle");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, box.y - 30, { steps: 5 });
  await page.mouse.up();
  expect(Number(await gain.inputValue())).toBeGreaterThan(before);

  await card.getByRole("button", { name: "High cut" }).click();
  await expect(card.getByRole("button", { name: "High cut" })).toHaveAttribute(
    "aria-pressed",
    "true"
  );
  await card.getByLabel("EQ band").selectOption("3");
  await expect(card.locator(".sp-eq-shapes button.on")).toHaveCount(1);
});

test("clip trim handles stay hidden until hover", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel trim" });
  const clip = page.locator(".se-clip").first();
  await clip.click();
  await page.mouse.move(600, 400);
  const opacity = () =>
    page.evaluate(() => {
      const trim = document.querySelector(".se-trim");
      return trim ? getComputedStyle(trim).opacity : null;
    });
  // S25: a selected clip is outlined; trim grips appear on hover, not before.
  await expect.poll(opacity).toBe("0");
  await clip.hover();
  await expect.poll(opacity).toBe("1");
});

test("history drawer sits under the header on the captured surface", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel history" });
  await page.locator(".se-chip").click();
  await page.getByRole("menuitem", { name: "Version History" }).click();
  const drawer = page.getByRole("dialog", { name: "Version history" });
  await expect(drawer).toBeVisible();
  const info = await drawer.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      width: Math.round(rect.width),
      bottom: Math.round(window.innerHeight - rect.bottom),
      radius: style.borderTopLeftRadius,
      background: style.backgroundColor,
    };
  });
  // S13: a 300 px drawer under the 52 px header, inset 8 px, on #101012.
  expect(info).toMatchObject({
    x: 8,
    y: 52,
    width: 300,
    bottom: 8,
    radius: "12px",
    background: "rgb(19, 24, 38)",
  });
});

test("popping a plugin out floats the captured card", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel popout" });
  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  await page.locator(".sp-add-inline").click();
  await page.getByRole("dialog", { name: "Add a track plugin" })
    .getByRole("button", { name: /^EQ\b/ })
    .first()
    .click();
  await page.getByRole("button", { name: "Pop out EQ" }).click();
  const slot = page.locator(".sp-slot.is-popped");
  await expect(slot).toBeVisible();
  const box = await slot.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      position: style.position,
      width: Math.round(rect.width),
      right: Math.round(window.innerWidth - rect.right),
    };
  });
  expect(box.position).toBe("fixed");
  expect(box.width).toBe(520);
  expect(box.right).toBe(24);
  await page.getByRole("button", { name: "Dock EQ" }).click();
  await expect(page.locator(".sp-slot.is-popped")).toHaveCount(0);
});

test("song row actions stay hidden until hover", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel rows" });
  await page.getByRole("button", { name: "Library", exact: true }).click();
  await page.getByRole("button", { name: /All Songs/ }).click();
  const row = page.locator(".se-lib-song").first();
  await expect(row).toBeVisible();
  const opacity = () =>
    row.evaluate((element) => {
      const actions = element.querySelector(".se-lib-song-actions");
      return actions ? getComputedStyle(actions).opacity : null;
    });
  await page.mouse.move(600, 600);
  // S53: rows show art, title, style and tags only; play/like/add arrive on hover.
  await expect.poll(opacity).toBe("0");
  await row.hover();
  await expect.poll(opacity).toBe("1");
});

test("studio gates below 768 with the desktop notice", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel gate" });
  await page.setViewportSize({ width: 767, height: 900 });
  const gate = page.locator(".se-desktop-gate");
  await expect(gate).toBeVisible();
  await expect(page.locator(".se-shell")).toBeHidden();
  const info = await gate.evaluate((element) => {
    const card = element.querySelector(".se-gate-card")?.getBoundingClientRect();
    const link = element.querySelector(".se-gate-link");
    return {
      card: card ? Math.round(card.width) : null,
      radius: card ? getComputedStyle(element.querySelector(".se-gate-card") as Element).borderTopLeftRadius : null,
      href: link?.getAttribute("href"),
    };
  });
  // S65: a 360 px card with the desktop-only notice and Back to Create.
  expect(info.card).toBe(360);
  expect(info.radius).toBe("24px");
  expect(info.href).toBe("/create");
});

test("narrow headers keep the captured controls", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel narrow" });

  await page.setViewportSize({ width: 1024, height: 900 });
  // S64: undo/redo stay at 1024; save/meter/speed/stop/metronome do not.
  await expect(page.getByRole("button", { name: "Undo" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Stop" })).toBeHidden();
  await expect(page.locator(".se-save")).toBeHidden();
  // S64: the prompt bar stays visible, centred over the arrangement.
  const prompt = page.locator(".se-prompt");
  await expect(prompt).toBeVisible();
  const promptBox = await prompt.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return { x: Math.round(rect.x), width: Math.round(rect.width) };
  });
  expect(promptBox).toEqual({ x: 320, width: 645 });

  await page.setViewportSize({ width: 768, height: 1024 });
  // S65: no undo/redo, panel stays 260, transport and time/tempo remain.
  await expect(page.getByRole("button", { name: "Undo" })).toBeHidden();
  await expect(page.getByRole("button", { name: "Play" })).toBeVisible();
  // S65: the Magic Bar is not part of the 768 px layout.
  await expect(prompt).toBeHidden();
  const panel = await page.locator(".se-tracks").evaluate((element) =>
    Math.round(element.getBoundingClientRect().width)
  );
  expect(panel).toBe(260);
});

test("filtered library shows the captured empty state", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel empty" });
  await page.getByRole("button", { name: "Library", exact: true }).click();
  await page.getByRole("button", { name: /All Songs/ }).click();
  const library = page.getByRole("complementary", { name: "Library" });
  await library.getByLabel("Search library").fill("zzz-no-such-song");
  await expect(library.getByText("No songs found.")).toBeVisible();
  const reset = library.getByRole("button", { name: "Reset all filters" });
  await expect(reset).toBeVisible();
  const box = await reset.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      height: Math.round(rect.height),
      radius: style.borderTopLeftRadius,
      background: style.backgroundColor,
    };
  });
  // S58: centred notice with a 38 px pill Reset all filters.
  expect(box.height).toBe(38);
  expect(box.radius).toBe("999px");
  expect(box.background).toBe("rgb(19, 24, 38)");
  await reset.click();
  await expect(library.getByLabel("Search library")).toHaveValue("");
});

test("library tiles sit on the captured grid", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel tiles" });
  await page.getByRole("button", { name: "Library", exact: true }).click();
  const tiles = await page.locator(".se-lib-tile").evaluateAll((nodes) =>
    nodes.map((node) => {
      const rect = node.getBoundingClientRect();
      return {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      };
    })
  );
  // S52: 169×64 tiles, 8 px inset, 4 px gap, first row at y52.
  expect(tiles).toHaveLength(4);
  expect(tiles[0]).toMatchObject({ x: 1330, y: 97, width: 169, height: 64 });
  expect(tiles[1].x).toBe(1503);
  expect(tiles[2].y).toBe(165);
});

test("My Projects modal matches the captured layout", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel projects" });
  await page.locator(".se-chip").click();
  await page.getByRole("menuitem", { name: "Open Project" }).click();
  const dialog = page.getByRole("dialog", { name: "Open project" });
  await expect(dialog).toBeVisible();
  // The list loads after the dialog shell; wait for the New Project card.
  await expect(dialog.locator(".se-project-card.is-new")).toBeVisible();
  const info = await dialog.locator(".se-dialog").evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    const search = element.querySelector(".se-projects-search")?.getBoundingClientRect();
    return {
      width: Math.round(rect.width),
      radius: style.borderTopLeftRadius,
      background: style.backgroundColor,
      searchHeight: search ? Math.round(search.height) : null,
      newCard: Boolean(element.querySelector(".se-project-card.is-new")),
      tabs: Array.from(element.querySelectorAll(".se-projects-tabs [role=tab]")).map((tab) =>
        tab.textContent?.trim()
      ),
    };
  });
  // S04: 786 px modal, pill search, Projects/Recently Deleted tabs, New Project first.
  expect(info.width).toBe(786);
  expect(info.radius).toBe("24px");
  expect(info.background).toBe("rgb(19, 24, 38)");
  expect(info.searchHeight).toBe(40);
  expect(info.tabs).toEqual(["Projects", "Recently Deleted"]);
  expect(info.newCard).toBe(true);
});

test("prompt bar matches the capture and generates inline", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel prompt" });
  const bar = page.getByRole("form");
  const prompt = page.getByLabel("Describe a part to generate");
  await expect(prompt).toBeVisible();
  const info = await page.evaluate(() => {
    const element = document.querySelector(".se-prompt");
    const body = document.querySelector(".se-body");
    if (!element || !body) return null;
    const rect = element.getBoundingClientRect();
    const bodyBox = body.getBoundingClientRect();
    return {
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      left: Math.round(rect.x),
      centered: Math.round(rect.x + rect.width / 2 - (bodyBox.x + bodyBox.width / 2)),
      bottomGap: Math.round(bodyBox.bottom - rect.bottom),
      radius: getComputedStyle(element).borderTopLeftRadius,
      background: getComputedStyle(element).backgroundColor,
    };
  });
  // S16/S38: a 645 x 97 card after the 260 px panel, 16 px above the body bottom.
  expect(info).toMatchObject({
    width: 645,
    height: 97,
    left: 652,
    centered: 130,
    bottomGap: 16,
    radius: "16px",
    background: "rgb(19, 24, 38)",
  });
  await expect(page.getByRole("button", { name: "Generate this part" })).toBeDisabled();

  // Model picker (S38): three models, selecting one changes the request.
  await page.getByRole("button", { name: "Generation model" }).click();
  const models = page.getByRole("listbox", { name: "Generation model" });
  await expect(models).toBeVisible();
  await expect(models.getByRole("option")).toHaveCount(3);
  await models.getByRole("option", { name: /v6-mini/ }).click();
  await expect(models).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Generation model" })).toContainText("v6-mini");

  // S37: the selected track shows as a removable context chip in the prompt bar.
  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  const chip = page.locator(".se-prompt-context");
  await expect(chip).toHaveText(/Track 1/);
  await chip.getByRole("button", { name: "Clear track context" }).click();
  await expect(chip).toHaveCount(0);

  // Generation is inline: mock the API, then the result lands on the track.
  const captured: { model?: unknown } = {};
  await page.route("**/api/v3/web-music/generate", (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    captured.model = body.model;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ task_id: "gen-test", status: "queued", title: "Generated demo", style: "pop" }),
    });
  });
  await page.route("**/api/v3/web-music/generations/gen-test", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "gen-test",
        title: "Generated demo",
        style: "pop",
        status: "complete",
        clips: [
          {
            variant: "v1",
            title: "Generated demo",
            audio_url: "/seed/demo-loop.wav",
            download_url: "/seed/demo-loop.wav",
            duration_seconds: 4,
          },
          {
            variant: "v2",
            title: "Generated demo alt",
            audio_url: "/seed/demo-loop.wav",
            download_url: "/seed/demo-loop.wav",
            duration_seconds: 4,
          },
        ],
      }),
    })
  );
  await prompt.fill("A warm eight-bar drum loop");
  await page.getByRole("button", { name: "Generate this part" }).click();

  // S37: the take arrives in the assistant panel; commit places it on the track.
  const assistant = page.getByRole("complementary", { name: "Studio assistant" });
  await expect(assistant).toBeVisible();
  // S37: the assistant replaces the track panel and shifts the arrangement right.
  await expect(page.locator(".se-tracks")).toBeHidden();
  expect(
    await page.locator(".se-lane").first().evaluate((element) => Math.round(element.getBoundingClientRect().x))
  ).toBe(392);
  // S37: the composer moves into the assistant column.
  expect(
    await page.locator(".se-prompt").evaluate((element) => Math.round(element.getBoundingClientRect().x))
  ).toBe(24);
  await expect(assistant.getByText(/Created Generated demo/)).toBeVisible({ timeout: 20_000 });
  expect(captured.model).toBe("V6_MINI");
  await expect(page.locator(".se-clip", { hasText: "Generated demo" })).toHaveCount(0);
  await expect(assistant.getByText("Take 1")).toBeVisible();
  await expect(assistant.getByText("Take 2")).toBeVisible();
  await assistant.locator(".se-assistant-take").nth(1).getByRole("button", { name: "Commit" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Take added" })).toBeVisible();
  await expect(page.locator(".se-clip", { hasText: "Generated demo alt" })).toHaveCount(1);

  await assistant.getByRole("button", { name: "Close assistant" }).click();
  await expect(page.locator(".se-tracks")).toBeVisible();
});

test("prompt dock matches S36 and toggles the conversation", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel dock" });

  // S16/S38 anatomy: attach, tools, input line with Tab, model + send.
  const bar = page.locator(".se-prompt");
  await expect(bar.locator(".se-prompt-attach")).toBeVisible();
  await expect(bar.locator(".se-prompt-kbd")).toHaveText("Tab");
  await expect(bar.locator(".se-prompt-actions .se-prompt-model")).toBeVisible();

  // S36: the panel glyph undocks the bar into the bottom-left conversation dock.
  await page.getByRole("button", { name: "Open conversation" }).click();
  const assistant = page.getByRole("complementary", { name: "Studio assistant" });
  await expect(assistant).toBeVisible();
  await expect(
    assistant.getByText(/Describe a section or ask for ideas to start a conversation/)
  ).toBeVisible();
  const dock = await bar.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      x: Math.round(rect.x),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      bottomGap: Math.round(window.innerHeight - rect.bottom),
    };
  });
  expect(dock.x).toBe(24);
  expect(dock.width).toBe(328);
  expect(dock.height).toBeGreaterThan(90);
  // S36: the dock floats above the assistant column's lower edge (bottom 101).
  expect(dock.bottomGap).toBe(101);
  // S37: the assistant column is 360 px at x=8 and the arrangement starts at 392.
  expect(
    await assistant.evaluate((element) => Math.round(element.getBoundingClientRect().width))
  ).toBe(360);
  await expect(page.locator(".se-tracks")).toBeHidden();
  expect(
    await page.locator(".se-lane").first().evaluate((element) => Math.round(element.getBoundingClientRect().x))
  ).toBe(392);

  // The expand glyph returns it to the centre and closes the conversation.
  await page.getByRole("button", { name: "Dock prompt to the centre" }).click();
  await expect(assistant).toHaveCount(0);
  expect(
    await bar.evaluate((element) => Math.round(element.getBoundingClientRect().width))
  ).toBe(645);

  // Attach menu: a clip becomes the prompt's context chip and clears again.
  await page.getByRole("button", { name: "Attach a track or clip" }).click();
  const attach = page.getByRole("menu", { name: "Attach to the prompt" });
  await expect(attach).toBeVisible();
  await attach.getByRole("menuitem", { name: /Fixture clip/ }).click();
  await expect(page.locator(".se-prompt-context")).toHaveText(/Fixture clip/);
  await page.getByRole("button", { name: "Clear track context" }).click();
  await expect(page.locator(".se-prompt-context")).toHaveCount(0);
});

test("muting a track swaps the speaker icon, not just the hover colour", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel mute" });

  const mute = page.getByRole("button", { name: "Mute Track 1" });
  await expect(mute.locator(".icon")).toHaveClass(/fa-volume-high/);
  await mute.click();
  await expect(mute).toHaveAttribute("aria-pressed", "true");
  await expect(mute.locator(".icon")).toHaveClass(/fa-volume-xmark/);
  await mute.click();
  await expect(mute.locator(".icon")).toHaveClass(/fa-volume-high/);
});

test("save errors float below the ruler instead of being clipped", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel error" });
  await page.route("**/api/v3/web-music/studio/projects/*", (route) =>
    route.request().method() === "PATCH"
      ? route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ error: { message: "nope" } }),
        })
      : route.continue()
  );

  await page.getByRole("button", { name: "Mute Track 1" }).click();
  const alert = page.locator(".se-error");
  await expect(alert).toBeVisible();
  const info = await alert.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const ruler = document.querySelector(".se-ruler-bars")?.getBoundingClientRect();
    return {
      top: Math.round(rect.top),
      zIndex: getComputedStyle(element).zIndex,
      rulerBottom: ruler ? Math.round(ruler.bottom) : null,
    };
  });
  expect(info.top).toBeGreaterThanOrEqual(info.rulerBottom ?? 0);
  expect(info.zIndex).toBe("90");
});

test("plugin cards offer the captured preset menu", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel presets" });
  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  await page.locator(".sp-add-inline").click();
  await page.getByRole("dialog", { name: "Add a track plugin" })
    .getByRole("button", { name: /^Compressor/ })
    .first()
    .click();

  const slot = page.locator(".sp-slot").first();
  await slot.getByRole("button", { name: "Default" }).click();
  const menu = page.getByRole("menu", { name: "Compressor presets" });
  await expect(menu).toBeVisible();
  await expect(menu.getByRole("menuitem")).toHaveText(["Default", "Vocal", "Drum Bus", "Gentle"]);

  await menu.getByRole("menuitem", { name: "Vocal" }).click();
  await expect(slot.getByRole("slider", { name: "Thresh" })).toHaveValue("-20");
  await expect(slot.getByRole("button", { name: "Vocal" })).toBeVisible();
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
    background: "rgb(15, 20, 31)",
  });

  // The header/footer span the full width; the rail floats over them (S52).
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
  expect(edges.lastFoot).toBeGreaterThan(REFERENCE_VIEWPORT.width - 360);
});
