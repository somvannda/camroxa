import { expect, type Page } from "@playwright/test";

/**
 * Shared Studio e2e fixtures (W5.4/G13).
 *
 * Every spec builds its own project through the API from inside the page, so specs do
 * not depend on leftover projects or on signing in through the UI. They need a dev
 * server on BASE_URL with the sandbox API running; the account is the local sandbox
 * user (scripts/seed_sandbox_user.py) and must never point at production.
 */

export const EMAIL = process.env.STUDIO_SMOKE_EMAIL ?? "somvannda@gmail.com";
export const PASSWORD = process.env.STUDIO_SMOKE_PASSWORD ?? "StudioLocal!2026";

export type FixtureClip = {
  id: string;
  title?: string;
  start: number;
  duration: number;
  /** Optional audio for render/export tests (e.g. "/seed/demo-loop.wav"). */
  audioUrl?: string;
  /** Clip Settings snapshot (gain, pitch, speed, loop, reverse). */
  audio?: Record<string, unknown>;
  /** Pre-transform audio/duration, so Heal Edits can restore it. */
  sourceAudioUrl?: string | null;
  sourceDuration?: number;
  takes?: Array<{ id: string; title?: string; audioUrl?: string | null; active?: boolean }>;
  /** Optional notes, so the MIDI export path has a real clip to read. */
  midi?: {
    notes?: Array<{
      id: string;
      pitch: number;
      start: number;
      length: number;
      velocity: number;
    }>;
  };
  /** Source generation, so Studio clip operations are enabled. */
  songId?: string;
};

export type CreateProjectOptions = {
  title: string;
  clips?: FixtureClip[];
};

const DEFAULT_CLIPS: FixtureClip[] = [
  { id: "fixture-clip", title: "Fixture clip", start: 0, duration: 4 },
];

/** Sign in through the API and leave the browser holding the auth cookies. */
export async function signIn(page: Page): Promise<void> {
  await page.goto("/studio");
  const status = await page.evaluate(
    async ({ email, password }) => {
      const login = await fetch("/api/v3/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      return login.status;
    },
    { email: EMAIL, password: PASSWORD }
  );
  if (status !== 200) throw new Error(`login failed: ${status}`);
}

/**
 * Sign in through the API and create a project with one track holding the given clips.
 * Returns the project id. Call it after any `page.goto` on this origin.
 */
export async function createStudioProject(
  page: Page,
  { title, clips = DEFAULT_CLIPS }: CreateProjectOptions
): Promise<string> {
  await page.goto("/studio");
  const projectId = await page.evaluate(
    async ({ email, password, title: projectTitle, clips: lanes }) => {
      const login = await fetch("/api/v3/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (login.status !== 200) {
        throw new Error(`login failed: ${login.status} ${(await login.text()).slice(0, 300)}`);
      }

      const payload = JSON.stringify({
        title: projectTitle,
        bpm: 120,
        time_signature: "4/4",
        data: {
          lanes: lanes.map((clip) => ({
            title: clip.title ?? clip.id,
            volume: 1,
            pan: 0,
            ...clip,
          })),
          tracks: [
            {
              id: "fixture-track",
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
              clipIds: lanes.map((clip) => clip.id),
            },
          ],
        },
      });

      // A fresh CI database occasionally returns one transient 500 while the API
      // warms its pool; retry once so infrastructure noise does not fail a spec.
      let created = await fetch("/api/v3/web-music/studio/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
      });
      if (created.status >= 500) {
        await new Promise((resolve) => setTimeout(resolve, 750));
        created = await fetch("/api/v3/web-music/studio/projects", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload,
        });
      }
      if (!created.ok) {
        throw new Error(`create failed: ${created.status} ${(await created.text()).slice(0, 300)}`);
      }
      const project = (await created.json()) as { id: string };
      return project.id;
    },
    { email: EMAIL, password: PASSWORD, title, clips }
  );
  await page.goto(`/studio/editor?project=${projectId}`);
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  return projectId;
}

/** Persisted `start` of the first lane, straight from the API (not the DOM). */
export async function savedClipStart(page: Page, projectId: string): Promise<number | null> {
  return page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    if (!response.ok) return null;
    const project = (await response.json()) as { data?: { lanes?: Array<{ start?: number }> } };
    const start = project.data?.lanes?.[0]?.start;
    return typeof start === "number" ? start : null;
  }, projectId);
}

/** `left` style of the first clip, in pixels. */
export function clipLeft(page: Page): Promise<number> {
  return page
    .locator(".se-clip")
    .first()
    .evaluate((element) => Number.parseFloat((element as HTMLElement).style.left) || 0);
}

/** Drag the first clip one bar to the right (96px at the default zoom). */
export async function dragFirstClipOneBar(page: Page): Promise<void> {
  const clip = page.locator(".se-clip").first();
  const box = await clip.boundingBox();
  if (!box) throw new Error("clip has no box");
  // Grab below the header band and away from the top-left fade handle.
  await page.mouse.move(box.x + 40, box.y + 40);
  await page.mouse.down();
  await page.mouse.move(box.x + 40 + 96, box.y + 40, { steps: 8 });
  await page.mouse.up();
}
