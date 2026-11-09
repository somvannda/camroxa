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

  // Track header internals: name at x48 / 11 px, controls 28×32 (extend 16×32).
  const track = await page.evaluate(() => {
    const name = document.querySelector(".se-track-name")?.getBoundingClientRect();
    const buttons = Array.from(
      document.querySelectorAll(".se-track-buttons button")
    ).map((element) => {
      const rect = element.getBoundingClientRect();
      return { x: Math.round(rect.x), width: Math.round(rect.width), height: Math.round(rect.height) };
    });
    return {
      nameX: name ? Math.round(name.x) : null,
      nameFont: document.querySelector(".se-track-name")
        ? getComputedStyle(document.querySelector(".se-track-name") as Element).fontSize
        : null,
      buttons,
    };
  });
  expect(track.nameX).toBe(48);
  expect(track.nameFont).toBe("11px");
  expect(track.buttons.slice(0, 3).every((button) => button.height === 32)).toBe(true);
  expect(track.buttons.slice(0, 3).every((button) => button.width === 28)).toBe(true);
  expect(track.buttons[3]?.width).toBe(16);
  expect(Math.abs((track.buttons[0]?.x ?? 0) - 150)).toBeLessThanOrEqual(2);

  // §44.3 ruler pitch: adjacent bar ticks are 96 px apart at the default zoom.
  const ticks = await page.locator(".se-bar-tick").evaluateAll((nodes) =>
    nodes.slice(0, 2).map((node) => Math.round(node.getBoundingClientRect().x))
  );
  expect(ticks).toHaveLength(2);
  expect(ticks[1] - ticks[0]).toBe(96);
});

test("library rail is 360 px and uses the panel surface", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Pixel rail" });
  await page.getByRole("button", { name: "Library", exact: true }).click();
  const library = page.getByRole("complementary", { name: "Library" });
  await expect(library).toBeVisible();
  const box = await library.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      width: Math.round(rect.width),
      x: Math.round(rect.x),
      background: getComputedStyle(element).backgroundColor,
    };
  });
  // §19.1: panel pinned right at 360 px, surface #101012.
  expect(box.width).toBe(360);
  expect(box.x + box.width).toBe(REFERENCE_VIEWPORT.width);
  expect(box.background).toBe("rgb(16, 16, 18)");
});
