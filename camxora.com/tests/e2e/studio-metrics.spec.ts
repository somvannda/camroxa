import { expect, test } from "@playwright/test";

/**
 * Metric parity as a test (extends W5.4).
 *
 * The probe at `?metrics=1` compares our rendered geometry against the numbers captured
 * from the reference (`docs/studio/reference/METRICS.json`). Until now it was a panel a
 * human had to read; this asserts it, so a spacing change that drifts from the capture
 * fails CI instead of relying on someone noticing.
 */

const EMAIL = process.env.STUDIO_SMOKE_EMAIL ?? "somvannda@gmail.com";
const PASSWORD = process.env.STUDIO_SMOKE_PASSWORD ?? "StudioLocal!2026";

test("metric parity holds against the captured reference", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/studio");

  const projectId = await page.evaluate(
    async ({ email, password }) => {
      const login = await fetch("/api/v3/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (login.status !== 200) throw new Error(`login failed: ${login.status}`);

      const created = await fetch("/api/v3/web-music/studio/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: "Metrics probe",
          bpm: 120,
          time_signature: "4/4",
          data: {
            lanes: [
              { id: "metric-clip", title: "Clip", start: 0, duration: 4, volume: 1, pan: 0 },
            ],
            tracks: [
              {
                id: "metric-track",
                name: "Track 1",
                color: "#38bdf8",
                index: 0,
                volume: 80,
                pan: 0,
                muted: false,
                solo: false,
                hidden: false,
                groupId: null,
                chain: [],
                clipIds: ["metric-clip"],
              },
            ],
          },
        }),
      });
      const project = await created.json();
      return project.id as string;
    },
    { email: EMAIL, password: PASSWORD }
  );

  await page.goto(`/studio/editor?project=${projectId}&metrics=1`);

  const panel = page.locator(".se-metrics");
  await expect(panel).toBeVisible({ timeout: 30_000 });

  // The summary line is the assertion: "6/6 px · N wired · M partial · K visual".
  const summary = page.locator(".se-metrics-head span");
  await expect(summary).toContainText("/");

  const head = (await summary.innerText()).trim();
  const matched = Number(head.split("/")[0]);
  const total = Number(head.split("/")[1].split(" ")[0]);
  expect(total).toBeGreaterThan(0);
  expect(matched, `metric parity drifted: ${head}`).toBe(total);

  // And every row reports a zero delta.
  const deltas = await panel.locator("tbody tr td:nth-child(4)").allInnerTexts();
  expect(deltas.map((value) => value.trim())).toEqual(deltas.map(() => "0"));
});
