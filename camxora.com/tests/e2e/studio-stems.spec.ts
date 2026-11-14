import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Stems tab with a provider-shaped result (B-005). The separation itself runs on Suno and
 * needs a funded, session-valid account; this covers the path we own end to end: the list
 * projection, the row actions and placing a stem on a lane.
 */

const STEMS = {
  items: [
    {
      clip_id: "stem-vocals",
      operation_id: "op-stems",
      task_id: "song-1",
      title: "Vocals",
      stem_type: "vocals",
      audio_url: "/seed/demo-loop.wav",
      duration_seconds: 4,
      created_at: new Date().toISOString(),
    },
    {
      clip_id: "stem-drums",
      operation_id: "op-stems",
      task_id: "song-1",
      title: "Drums",
      stem_type: "drums",
      audio_url: "/seed/transients.wav",
      duration_seconds: 4,
      created_at: new Date().toISOString(),
    },
  ],
};

test("the Stems tab lists a separated result and places a stem", async ({ page }) => {
  test.setTimeout(120_000);
  const projectId = await createStudioProject(page, { title: "Stems probe" });

  // Stems are provider output; the projection shape is fixed by the platform route.
  await page.route("**/api/v3/web-music/studio/stems*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(STEMS),
    })
  );

  await page.getByRole("button", { name: "Library", exact: true }).click();
  const library = page.getByRole("complementary", { name: "Library" });
  await library.getByRole("button", { name: "Stems" }).first().click();

  await expect(library.getByText(/vocals/i).first()).toBeVisible();
  await expect(library.getByText(/drums/i).first()).toBeVisible();

  await library.getByLabel("Add vocals").click();
  await expect
    .poll(
      async () =>
        page.evaluate(async (id) => {
          const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
          const project = (await response.json()) as {
            data?: { lanes?: Array<{ title?: string }> };
          };
          return (project.data?.lanes ?? []).map((lane) => lane.title);
        }, projectId),
      { timeout: 15_000, intervals: [250] }
    )
    .toContain("vocals");
});
