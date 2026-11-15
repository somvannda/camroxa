import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * S09-S11 Content and Window management settings, the advanced gating they control
 * (Wavetable Designer, IR Designer), clip-level inserts (S34 "Remove FX"), the Stereo
 * Utility plugin (S21) and the captured export labels (S49).
 */

const REFERENCE_VIEWPORT = { width: 1689, height: 1277 };

async function openSettings(page: import("@playwright/test").Page) {
  await page.keyboard.press("Control+Shift+,");
  const dialog = page.getByRole("dialog", { name: "Studio settings" });
  await expect(dialog).toBeVisible();
  return dialog;
}

test("Studio Settings has the three captured panes and persists them", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  await createStudioProject(page, { title: "Settings probe" });

  let dialog = await openSettings(page);
  await expect(dialog.getByRole("checkbox", { name: "Ghost drag for arrangement moves" })).toBeChecked();

  await dialog.getByRole("button", { name: "Window management" }).click();
  await expect(dialog.getByText("Keyboard & plugin windows")).toBeVisible();
  await dialog.getByRole("radio", { name: "Windows" }).click();
  await expect(dialog.getByRole("radio", { name: "Windows" })).toHaveAttribute(
    "aria-checked",
    "true"
  );

  await dialog.getByRole("button", { name: "Content" }).click();
  const advanced = dialog.getByRole("checkbox", { name: "Advanced content features" });
  await expect(advanced).not.toBeChecked();
  await expect(dialog.getByRole("checkbox", { name: "Auto-stretch added audio" })).toBeChecked();
  await advanced.check();

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();

  await page.reload();
  await page.locator(".se-clip").first().waitFor({ state: "visible", timeout: 30_000 });
  dialog = await openSettings(page);
  await dialog.getByRole("button", { name: "Content" }).click();
  await expect(dialog.getByRole("checkbox", { name: "Advanced content features" })).toBeChecked();
  await dialog.getByRole("button", { name: "Window management" }).click();
  await expect(dialog.getByRole("radio", { name: "Windows" })).toHaveAttribute(
    "aria-checked",
    "true"
  );
});

test("advanced content gates the impulse response designer", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: "Gate probe" });

  async function addConvolution() {
    await page.getByRole("button", { name: "Track 1", exact: true }).click();
    await page
      .getByRole("region", { name: /Plugins for/ })
      .getByRole("button", { name: "Add effect", exact: true })
      .first()
      .click();
    await page
      .getByRole("dialog", { name: "Add a track plugin" })
      .getByRole("button", { name: /^Convolution/ })
      .first()
      .click();
    const slot = page.locator(".sp-slot").first();
    await slot.getByRole("button", { name: "Impulse response" }).click();
    return page.getByRole("menu", { name: "Impulse responses" });
  }

  // Off: the designer entry is hidden, not disabled (S11 copy).
  let menu = await addConvolution();
  await expect(menu.getByRole("menuitem", { name: "Design response." })).toHaveCount(0);
  await page.keyboard.press("Escape");

  await openSettings(page).then(async (dialog) => {
    await dialog.getByRole("button", { name: "Content" }).click();
    await dialog.getByRole("checkbox", { name: "Advanced content features" }).check();
    await page.keyboard.press("Escape");
  });

  menu = await addConvolution();
  await expect(menu.getByRole("menuitem", { name: "Design response." })).toBeVisible();
});

test("clip inserts are added and removed from the clip menu", async ({ page }) => {
  test.setTimeout(120_000);
  const projectId = await createStudioProject(page, {
    title: "Clip FX probe",
    clips: [
      { id: "clip-a", title: "Verse", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  await page.locator(".se-clip").first().click({ button: "right" });
  await page.getByRole("menuitem", { name: /Add FX/ }).click();
  const dialog = page.getByRole("dialog", { name: "Add clip effect" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "EQ" }).click();
  await expect(page.getByRole("status")).toContainText("EQ added to the clip.");

  await expect
    .poll(
      async () =>
        page.evaluate(async (id) => {
          const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
          const project = (await response.json()) as {
            data?: { lanes?: Array<{ id: string; fx?: Array<{ pluginId: string }> }> };
          };
          const clip = project.data?.lanes?.find((lane) => lane.id === "clip-a");
          return clip?.fx?.map((entry) => entry.pluginId) ?? [];
        }, projectId),
      { timeout: 15_000, intervals: [250] }
    )
    .toEqual(["eq"]);

  await page.locator(".se-clip").first().click({ button: "right" });
  const remove = page.getByRole("menuitem", { name: /Remove FX/ });
  await expect(remove).toBeEnabled();
  await remove.click();
  await expect(page.getByRole("status")).toContainText("Clip effects removed.");

  await expect
    .poll(
      async () =>
        page.evaluate(async (id) => {
          const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
          const project = (await response.json()) as {
            data?: { lanes?: Array<{ id: string; fx?: unknown[] }> };
          };
          return project.data?.lanes?.find((lane) => lane.id === "clip-a")?.fx?.length ?? -1;
        }, projectId),
      { timeout: 15_000, intervals: [250] }
    )
    .toBe(0);
});

test("Stereo Utility is in the catalog and lands in the chain", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: "Stereo probe" });

  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  await page
    .getByRole("region", { name: /Plugins for/ })
    .getByRole("button", { name: "Add effect", exact: true })
    .first()
    .click();
  const catalog = page.getByRole("dialog", { name: "Add a track plugin" });
  await catalog.getByLabel("Search plugins").fill("stereo");
  await catalog.getByRole("button", { name: /^Stereo Utility/ }).click();

  const slot = page.getByRole("article", { name: "Stereo Utility slot 1" });
  await expect(slot).toBeVisible();
  await expect(slot.getByRole("slider", { name: "Width" })).toBeVisible();
});

test("the preset stepper auditions presets without opening the menu", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: "Preset stepper probe" });

  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  await page
    .getByRole("region", { name: /Plugins for/ })
    .getByRole("button", { name: "Add effect", exact: true })
    .first()
    .click();
  await page
    .getByRole("dialog", { name: "Add a track plugin" })
    .getByRole("button", { name: /^Compressor/ })
    .first()
    .click();

  const slot = page.getByRole("article", { name: "Compressor slot 1" });
  const preset = slot.locator(".sp-preset");
  await expect(preset).toHaveText("Default");
  await slot.getByRole("button", { name: "Next Compressor preset" }).click();
  await expect(preset).toHaveText("Vocal");
  await slot.getByRole("button", { name: "Previous Compressor preset" }).click();
  await expect(preset).toHaveText("Default");
});

test("export menu keeps the captured scopes", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: "Export label probe" });

  await page.getByRole("button", { name: "Export menu" }).click();
  const menu = page.getByRole("menu", { name: "Export options" });
  await expect(menu.getByRole("menuitem", { name: "Full Song" })).toBeVisible();
  await expect(menu.getByRole("menuitem", { name: "Selected Time Range" })).toBeDisabled();
  await expect(menu.getByRole("menuitem", { name: "Multitrack" })).toBeVisible();
});

test("the wavetable designer saves an instrument for the MIDI clip", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
  const projectId = await createStudioProject(page, {
    title: "Wavetable probe",
    clips: [
      {
        id: "clip-a",
        title: "Keys",
        start: 0,
        duration: 4,
        midi: { notes: [{ id: "n1", pitch: 60, start: 0, length: 1, velocity: 100 }] },
      },
    ],
  });

  await page.locator(".se-clip").first().click();
  await page.getByRole("button", { name: "Clip editor" }).click();
  const panel = page.getByRole("region", { name: "MIDI editor" });
  await expect(panel).toBeVisible();
  // Advanced content is off by default: the entry is hidden, not disabled.
  await expect(panel.getByRole("button", { name: "Design a wavetable" })).toHaveCount(0);

  const dialog = await openSettings(page);
  await dialog.getByRole("button", { name: "Content" }).click();
  await dialog.getByRole("checkbox", { name: "Advanced content features" }).check();
  await page.keyboard.press("Escape");

  await expect(panel.getByRole("button", { name: "Design a wavetable" })).toBeVisible();
  await panel.getByRole("button", { name: "Design a wavetable" }).click();

  const designer = page.getByRole("dialog", { name: "Wavetable designer" });
  await expect(designer).toBeVisible();
  await designer.getByRole("button", { name: "Square" }).click();
  await designer.getByLabel("Wavetable name").fill("Glass pad");
  await designer.getByRole("button", { name: /Save wavetable/ }).click();

  await expect(page.getByRole("status")).toContainText("Glass pad");
  await expect(panel.getByLabel("MIDI instrument")).toHaveValue(/^wavetable:/);
  await expect(panel.getByRole("option", { name: "Glass pad" })).toHaveCount(1);

  await expect
    .poll(
      async () =>
        page.evaluate(async (id) => {
          const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
          const project = (await response.json()) as {
            data?: {
              wavetables?: Array<{ name: string }>;
              lanes?: Array<{ id: string; instrument?: string }>;
            };
          };
          const table = project.data?.wavetables?.[0]?.name ?? null;
          const clip = project.data?.lanes?.find((lane) => lane.id === "clip-a");
          return { table, instrument: clip?.instrument ?? null };
        }, projectId),
      { timeout: 15_000, intervals: [250] }
    )
    .toMatchObject({ table: "Glass pad", instrument: expect.stringMatching(/^wavetable:/) });
});
