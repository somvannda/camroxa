import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/** MIDI editor (S31/S64): model, panel and note editing through the real document. */

test("a MIDI track opens the captured editor and edits notes", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  await createStudioProject(page, { title: "MIDI editor" });

  await page.getByRole("button", { name: /Add new track/ }).click();
  await page.getByRole("menuitem", { name: /MIDI/ }).click();

  const panel = page.getByRole("region", { name: "MIDI editor" });
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("tab", { name: "Velocity" })).toHaveAttribute(
    "aria-selected",
    "true"
  );
  await panel.getByRole("tab", { name: "Pitch Bend" }).click();
  const bendLane = panel.getByRole("group", { name: "Pitch bend lane" });
  await bendLane.click({ position: { x: 100, y: 40 } });
  await expect(bendLane.locator("circle")).toHaveCount(1);
  await bendLane.locator("circle").first().dblclick();
  await expect(bendLane.locator("circle")).toHaveCount(0);
  await panel.getByRole("tab", { name: "Modulation" }).click();
  const modLane = panel.getByRole("group", { name: "Modulation lane" });
  await modLane.click({ position: { x: 160, y: 30 } });
  await expect(modLane.locator("circle")).toHaveCount(1);
  await panel.getByRole("tab", { name: "Velocity" }).click();
  await expect(panel.getByText("Quantize")).toBeVisible();

  // S31/S64 geometry: 44 px keys, 34 px tab strip, 36 px control bar.
  const geometry = await page.evaluate(() => ({
    keys: Math.round(document.querySelector(".se-midi-keys")?.getBoundingClientRect().width ?? 0),
    tabs: Math.round(document.querySelector(".se-midi-tabs")?.getBoundingClientRect().height ?? 0),
    controls: Math.round(
      document.querySelector(".se-midi-controls")?.getBoundingClientRect().height ?? 0
    ),
  }));
  expect(geometry).toEqual({ keys: 44, tabs: 34, controls: 36 });

  const grid = panel.locator(".se-midi-grid");

  // Click adds a note at the snapped time/pitch.
  await grid.click({ position: { x: 80, y: 120 } });
  await expect(panel.locator(".se-midi-note")).toHaveCount(1);
  const label = await panel.locator(".se-midi-note").first().getAttribute("aria-label");
  expect(label).toMatch(/Note [A-G]#?\d at/);

  // Double-click removes it.
  await panel.locator(".se-midi-note").first().dblclick();
  await expect(panel.locator(".se-midi-note")).toHaveCount(0);

  // Add one, drag it right and confirm the start moved.
  await grid.click({ position: { x: 80, y: 120 } });
  const note = panel.locator(".se-midi-note").first();
  const before = await note.getAttribute("aria-label");
  const noteBox = await note.boundingBox();
  if (!noteBox) throw new Error("no note");
  await page.mouse.move(noteBox.x + 3, noteBox.y + 4);
  await page.mouse.down();
  await page.mouse.move(noteBox.x + 60, noteBox.y + 4, { steps: 6 });
  await page.mouse.up();
  await expect(panel.locator(".se-midi-note").first()).not.toHaveAttribute(
    "aria-label",
    before ?? ""
  );

  // Focused notes transpose with the keyboard: semitone, then octave.
  const transposeNote = panel.locator(".se-midi-note").first();
  await transposeNote.focus();
  const beforePitch = await transposeNote.getAttribute("aria-label");
  await page.keyboard.press("ArrowUp");
  await expect(transposeNote).not.toHaveAttribute("aria-label", beforePitch ?? "");
  const afterSemitone = await transposeNote.getAttribute("aria-label");
  await page.keyboard.press("Shift+ArrowUp");
  await expect(transposeNote).not.toHaveAttribute("aria-label", afterSemitone ?? "");

  // Key/scale are real: non-scale rows dim and new notes snap into C major.
  await panel.getByLabel("Scale").selectOption("major");
  await expect(panel.locator(".se-midi-row.out").first()).toBeAttached();
  await grid.click({ position: { x: 140, y: 52 } });
  const snapped = await panel.locator(".se-midi-note").last().getAttribute("aria-label");
  expect(snapped).toMatch(/Note [A-G]\d at/);

  // Velocity lane drag lowers the selected note's velocity.
  const velocityBefore = Number(await panel.locator(".se-midi-note").first().getAttribute("data-velocity"));
  const bar = panel.locator(".se-midi-velocity-bar").first();
  const barBox = await bar.boundingBox();
  if (!barBox) throw new Error("no velocity bar");
  await page.mouse.move(barBox.x + 1, barBox.y + 2);
  await page.mouse.down();
  await page.mouse.move(barBox.x + 1, barBox.y + 26, { steps: 5 });
  await page.mouse.up();
  const velocityAfter = Number(await panel.locator(".se-midi-note").first().getAttribute("data-velocity"));
  expect(velocityAfter).toBeLessThan(velocityBefore);

  // The arrangement clip previews the notes.
  const midiClip = page.locator(".se-clip", { hasText: "MIDI clip" }).first();
  await expect(midiClip.locator(".se-clip-midi span").first()).toBeVisible();

  // Selecting an audio clip leaves the editor; the MIDI clip reopens it.
  await page.locator(".se-clip", { hasText: "Fixture clip" }).first().click();
  await expect(page.getByRole("region", { name: "MIDI editor" })).toHaveCount(0);
  await page.locator(".se-clip", { hasText: "MIDI clip" }).first().click();
  await panel.getByRole("button", { name: "Close MIDI editor" }).click();
  await expect(page.getByRole("region", { name: "MIDI editor" })).toHaveCount(0);
});

test("MIDI notes persist and reopen from the clip", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  await createStudioProject(page, { title: "MIDI persist" });

  await page.getByRole("button", { name: /Add new track/ }).click();
  await page.getByRole("menuitem", { name: /MIDI/ }).click();
  const panel = page.getByRole("region", { name: "MIDI editor" });
  const grid = panel.locator(".se-midi-grid");
  await grid.click({ position: { x: 60, y: 96 } });
  await expect(panel.locator(".se-midi-note")).toHaveCount(1);

  await expect(page.getByText("Saved", { exact: true })).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(800);
  await page.reload();
  await expect(page.locator(".se-clip")).toHaveCount(2, { timeout: 30_000 });

  await page.getByRole("button", { name: /^MIDI clip/ }).first().click();
  const reopened = page.getByRole("region", { name: "MIDI editor" });
  await expect(reopened).toBeVisible();
  await expect(reopened.locator(".se-midi-note")).toHaveCount(1);
});

test("Ctrl A plus 0 mutes the selected notes and the mute persists", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  await createStudioProject(page, { title: "MIDI mute" });

  await page.getByRole("button", { name: /Add new track/ }).click();
  await page.getByRole("menuitem", { name: /MIDI/ }).click();
  const panel = page.getByRole("region", { name: "MIDI editor" });
  const grid = panel.locator(".se-midi-grid");
  await grid.click({ position: { x: 60, y: 96 } });
  await grid.click({ position: { x: 150, y: 60 } });
  await expect(panel.locator(".se-midi-note")).toHaveCount(2);

  // Focus stays inside the panel after adding, so the panel owns the keys.
  await page.keyboard.press("Control+a");
  await expect(panel.locator(".se-midi-note.is-selected")).toHaveCount(2);
  await page.keyboard.press("0");
  await expect(panel.locator(".se-midi-note.is-disabled")).toHaveCount(2);
  await expect(panel.locator(".se-midi-note.is-disabled").first()).toHaveAttribute(
    "aria-label",
    /disabled/
  );

  await expect(page.getByText("Saved", { exact: true })).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(800);
  await page.reload();
  await expect(page.locator(".se-clip")).toHaveCount(2, { timeout: 30_000 });
  await page.getByRole("button", { name: /^MIDI clip/ }).first().click();
  const reopened = page.getByRole("region", { name: "MIDI editor" });
  await expect(reopened.locator(".se-midi-note.is-disabled")).toHaveCount(2);

  // 0 again restores them, so the toggle is not one-way.
  await page.keyboard.press("Control+a");
  await page.keyboard.press("0");
  await expect(reopened.locator(".se-midi-note.is-disabled")).toHaveCount(0);
});
