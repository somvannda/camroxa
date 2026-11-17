import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import {
  api,
  check,
  createProject,
  createShare,
  deleteProject,
  dialog,
  emptyDocument,
  getProject,
  makeRecorder,
  openEditor,
  p1Document,
  quietStorage,
  shot,
  signIn,
} from "./w5c-harness";

/**
 * W5-C, spec 5: C12 (Studio home: My Projects, Recently Deleted — 10),
 * C13 (shared project page — 8), C14 (onboarding — 6).
 */

test.describe.configure({ mode: "serial" });
test.setTimeout(1_200_000);

const rec = makeRecorder("c12-c14");
const viewport = { width: 1689, height: 1277 };

let ctx: BrowserContext;
let page: Page;
let PHOME = "";
let PARCH = "";
let PPIN = "";
let PDEL = "";
let PSHARE = "";
let PSHARE2 = "";
const TAG = Date.now().toString(36).slice(-4).toUpperCase();
const NAME_ALPHA = `W5C Home Alpha ${TAG}`;
const NAME_PIN = `W5C Home Pinned ${TAG}`;
const NAME_ARCH = `W5C Home Archived ${TAG}`;
const NAME_DEL = `W5C Home Delete Me ${TAG}`;
let P0 = "";
let P0B = "";
let P0C = "";

test.beforeAll(async ({ browser }) => {
  ctx = await browser.newContext({ viewport });
  page = await ctx.newPage();
  page.setDefaultTimeout(15_000);
  await quietStorage(page);
  await signIn(page);
  PHOME = await createProject(page, NAME_ALPHA, p1Document());
  PARCH = await createProject(page, NAME_ARCH, p1Document());
  PPIN = await createProject(page, NAME_PIN, p1Document());
  PDEL = await createProject(page, NAME_DEL, p1Document());
  PSHARE = await createProject(page, "W5C Shared Song", p1Document());
  PSHARE2 = await createProject(page, "W5C Shared Quiet", p1Document());
  P0 = await createProject(page, "W5C Onboarding A", emptyDocument());
  P0B = await createProject(page, "W5C Onboarding B", emptyDocument());
  P0C = await createProject(page, "W5C Onboarding C", emptyDocument());
  await api(page, `/api/v3/web-music/studio/projects/${PARCH}`, {
    method: "PATCH",
    body: { archived: true },
  });
  await api(page, `/api/v3/web-music/studio/projects/${PPIN}`, {
    method: "PATCH",
    body: { pinned: true },
  });
});

test.afterAll(async () => {
  rec.flush();
  await ctx?.close();
});

test("C12 — Studio home", async () => {
  await page.goto("/studio");
  await page.locator(".studio-home").first().waitFor({ timeout: 40_000 });
  await expect(
    page.locator(".studio-card:has(.studio-card-menu-btn)").first()
  ).toBeVisible({ timeout: 60_000 });

  await check(rec, page, "C-187", async () => {
    const eyebrow = ((await page.locator(".studio-home-eyebrow").first().textContent()) ?? "").trim();
    const h1 = ((await page.locator(".studio-home-head h1").textContent()) ?? "").trim();
    const sub = (await page.locator(".studio-home-sub").first().innerText()).trim();
    const actions = (await page.locator(".studio-home-actions").innerText()).replace(/\s+/g, " ");
    expect(eyebrow).toBe("Camxora Studio");
    expect(h1).toBe("Your projects");
    expect(sub.length).toBeGreaterThan(0);
    expect(actions).toContain("Create a song");
    expect(actions).toContain("New project");
    await shot(page, "C-187-1689x1277");
    return `eyebrow "${eyebrow}", h1 "${h1}", sub "${sub}", actions "${actions.trim()}"`;
  });

  await check(rec, page, "C-188", async () => {
    const resume = page.locator(".studio-resume");
    await expect(resume).toBeVisible({ timeout: 10_000 });
    const title = (await resume.locator("h2").innerText()).trim();
    const open = resume.locator("button", { hasText: "Open project" });
    expect(await open.count()).toBe(1);
    const cards = await page.locator(".studio-card").count();
    return `resume block for "${title}" with Open project (${cards} cards in the grid)`;
  });

  await check(rec, page, "C-189", async () => {
    const search = page.locator('.studio-home-search input[aria-label="Search projects"]');
    await search.fill("Home Alpha");
    await page.waitForTimeout(600);
    const titles = (await page.locator(".studio-card:has(.studio-card-menu-btn) .studio-card-title").allInnerTexts()).map(
      (text) => text.trim()
    );
    expect(titles.length).toBeGreaterThan(0);
    for (const title of titles) expect(title).toContain("Home Alpha");
    await search.fill("zzzz-no-such-project");
    await page.waitForTimeout(400);
    const state = page.locator(".studio-home-state");
    const heading = (await state.locator("h2").innerText()).trim();
    expect(heading).toContain("No projects match “zzzz-no-such-project”");
    const clear = state.locator("button", { hasText: "Clear search" });
    expect(await clear.count()).toBe(1);
    await clear.click();
    await page.waitForTimeout(400);
    const restored = await page.locator(".studio-card").count();
    return `search filtered to "${titles[0]}"; no-match state "${heading}" + Clear search; clearing restored ${restored} cards`;
  });

  await check(rec, page, "C-190", async () => {
    // The grid is paged; narrow to the archived fixture before revealing archived cards.
    await page.locator('.studio-home-search input[aria-label="Search projects"]').fill(NAME_ARCH);
    await page.waitForTimeout(500);
    const before = await page.locator(".studio-card.is-archived").count();
    await page.locator('.studio-home-toggle input[type="checkbox"]').check();
    await expect
      .poll(async () => page.locator(".studio-card.is-archived").count(), { timeout: 15_000 })
      .toBeGreaterThan(0);
    const after = await page.locator(".studio-card.is-archived").count();
    const titles = (await page.locator(".studio-card.is-archived .studio-card-title").allInnerTexts()).map(
      (text) => text.trim()
    );
    expect(before).toBe(0);
    expect(after).toBeGreaterThan(0);
    expect(titles.join(",")).toContain(NAME_ARCH);
    await page.locator('.studio-home-toggle input[type="checkbox"]').uncheck();
    await page.waitForTimeout(600);
    await page.locator('.studio-home-search input[aria-label="Search projects"]').fill("");
    await page.waitForTimeout(400);
    return `Archived toggle revealed ${after} archived card(s): ${titles.join(", ")}`;
  });

  await check(rec, page, "C-191", async () => {
    const sort = page.locator('select[aria-label="Sort projects"]');
    const cards = async () =>
      page.locator(".studio-card:has(.studio-card-menu-btn)").evaluateAll((nodes) =>
        nodes.map((node) => ({
          title: (node.querySelector(".studio-card-title")?.textContent ?? "").trim(),
          pinned: Boolean(node.querySelector(".fa-thumbtack")),
        }))
      );
    await sort.selectOption("updated");
    await page.waitForTimeout(600);
    const updatedOrder = await cards();
    await sort.selectOption("title");
    await page.waitForTimeout(600);
    const titleOrder = await cards();
    const firstUnpinned = (list: typeof titleOrder) => list.findIndex((card) => !card.pinned);
    const lastPinned = (list: typeof titleOrder) =>
      list.reduce((last, card, index) => (card.pinned ? index : last), -1);
    // Pinned cards lead both modes.
    expect(lastPinned(titleOrder)).toBeLessThan(firstUnpinned(titleOrder));
    expect(lastPinned(updatedOrder)).toBeLessThan(firstUnpinned(updatedOrder));
    expect(titleOrder.findIndex((card) => card.title === NAME_PIN)).toBeLessThan(
      firstUnpinned(titleOrder)
    );
    // Everything after the pinned block is alphabetical under "Title".
    const rest = titleOrder.slice(firstUnpinned(titleOrder)).map((card) => card.title);
    expect(rest, `title order = ${JSON.stringify(rest.slice(0, 6))}`).toEqual(
      rest.slice().sort((a, b) => a.localeCompare(b))
    );
    await sort.selectOption("updated");
    return `pinned block leads both modes (${lastPinned(titleOrder) + 1} card(s), incl. ${NAME_PIN}); ${rest.length} others sort alphabetically under Title`;
  });

  await check(rec, page, "C-192", async () => {
    await page.locator(`button[aria-label="Actions for ${NAME_ALPHA}"]`).first().click();
    const pop = page.locator('.studio-card-menu-pop[role="menu"]').first();
    await expect(pop).toBeVisible({ timeout: 8000 });
    const rows = (await pop.locator('[role="menuitem"]').allInnerTexts()).map((text) => text.trim());
    expect(rows).toEqual(["Open", "Rename", "Duplicate", "Pin", "Archive", "Delete"]);
    await shot(page, "C-192-1689x1277");
    return `card menu = ${rows.join(" | ")}`;
  });

  await check(rec, page, "C-193", async () => {
    let pop = page.locator('.studio-card-menu-pop[role="menu"]').first();
    await pop.locator('[role="menuitem"]', { hasText: "Rename" }).click();
    const dlg = page.locator('.studio-dialog[role="dialog"]', { has: page.locator("#studio-rename-title") });
    await expect(dlg).toBeVisible({ timeout: 8000 });
    const input = dlg.locator('input[aria-label="Project title"]');
    expect(await input.inputValue()).toBe(NAME_ALPHA);
    await input.fill("");
    expect(await dlg.locator("button", { hasText: "Save" }).isDisabled()).toBe(true);
    await input.fill("W5C Home Alpha renamed");
    await page.keyboard.press("Enter");
    await expect(dlg).toHaveCount(0, { timeout: 8000 });
    await page.waitForTimeout(800);
    const titles = (await page.locator(".studio-card-title").allInnerTexts()).map((text) => text.trim());
    expect(titles.some((text) => text.includes("renamed"))).toBe(true);
    return `prefilled, Save disabled while empty, Enter saved the new title`;
  });

  await check(rec, page, "C-194", async () => {
    await page.locator('.studio-home-search input[aria-label="Search projects"]').fill(NAME_DEL);
    await page.waitForTimeout(500);
    await page.locator('button[aria-label="Actions for ' + NAME_DEL + '"]').first().click();
    let pop = page.locator('.studio-card-menu-pop[role="menu"]').first();
    await pop.locator('[role="menuitem"]', { hasText: "Delete" }).click();
    const dlg = page.locator('.studio-dialog[role="dialog"]', { has: page.locator("#studio-delete-title") });
    await expect(dlg).toBeVisible({ timeout: 8000 });
    const text = (await dlg.innerText()).replace(/\s+/g, " ").trim();
    expect(text).toContain("Recently Deleted");
    expect(text).toContain("Keep project");
    await dlg.locator("button", { hasText: "Keep project" }).click();
    await expect(dlg).toHaveCount(0, { timeout: 5000 });
    expect(await page.locator(".studio-card-title", { hasText: NAME_DEL }).count()).toBeGreaterThan(0);
    await page.locator('button[aria-label="Actions for ' + NAME_DEL + '"]').first().click();
    pop = page.locator('.studio-card-menu-pop[role="menu"]').first();
    await pop.locator('[role="menuitem"]', { hasText: "Delete" }).click();
    const again = page.locator('.studio-dialog[role="dialog"]', { has: page.locator("#studio-delete-title") });
    await again.locator("button.btn-danger", { hasText: "Delete" }).click();
    await page.waitForTimeout(1500);
    await expect(
      page.locator(".studio-card:has(.studio-card-menu-btn) .studio-card-title", { hasText: NAME_DEL })
    ).toHaveCount(0, { timeout: 15_000 });
    const remaining = await page.locator(".studio-card-title", { hasText: NAME_DEL }).count();
    expect(remaining).toBe(0);
    return `confirm dialog explains Recently Deleted; Keep project cancels; Delete removed the card`;
  });

  await check(rec, page, "C-195", async () => {
    await openEditor(page, PHOME);
    await page.locator(".se-chip").first().click();
    await page.locator('.se-project-menu [role="menuitem"]', { hasText: "Open Project" }).click();
    const dlg = dialog(page, "Open project");
    await expect(dlg).toBeVisible({ timeout: 10_000 });
    await dlg.locator('[role="tab"]', { hasText: "Recently Deleted" }).click();
    const deleted = dlg.locator('[aria-label="Restore ' + NAME_DEL + '"]');
    await expect(deleted).toBeVisible({ timeout: 15_000 });
    await deleted.click();
    await page.waitForTimeout(1200);
    await page.keyboard.press("Escape");
    const restored = await getProject(page, PDEL);
    expect(restored.id).toBe(PDEL);
    return "the home deletion is listed in the editor's Recently Deleted tab and is restorable";
  });

  await check(rec, page, "C-196", async () => {
    await page.goto("/studio");
    await page.locator(".studio-home").first().waitFor({ timeout: 30_000 });
    const dots = page.locator(".studio-sync-dot");
    const count = await dots.count();
    expect(count).toBeGreaterThan(0);
    const labels = (await dots.evaluateAll((nodes) =>
      nodes.slice(0, 5).map((node) => ({
        label: node.getAttribute("aria-label"),
        state: node.getAttribute("data-state"),
      }))
    )) as Array<{ label: string | null; state: string | null }>;
    for (const dot of labels) expect(dot.label ?? "").toMatch(/^Suno Studio: /);
    return `${count} sync dot(s); sample ${labels.map((dot) => `${dot.state}:${dot.label}`).join(" | ")}`;
  });
});

test("C13 — shared project page", async () => {
  const share = await createShare(page, PSHARE);
  const emptyShare = await createShare(page, PSHARE2);

  await check(rec, page, "C-197", async () => {
    const anonymous = await ctx.browser()!.newContext({ viewport });
    try {
      const guest = await anonymous.newPage();
      await guest.goto(`/studio/shared/${share.token}`);
      const card = guest.locator(".shared-studio-card");
      await expect(card).toBeVisible({ timeout: 30_000 });
      const brand = (await guest.locator(".shared-studio-brand").innerText()).trim();
      const badge = ((await guest.locator(".shared-studio-badge").textContent()) ?? "").trim();
      const title = (await card.locator("h1").innerText()).trim();
      const meta = (await card.locator(".shared-studio-title p").last().innerText()).trim();
      const duration = (await card.locator(".shared-studio-time").innerText()).trim();
      expect(brand).toContain("CAMXORA");
      expect(badge.toLowerCase()).toBe("read-only studio share");
      expect(title).toBe("W5C Shared Song");
      expect(meta).toContain("120 BPM");
      expect(meta).toContain("4/4");
      expect(meta).toMatch(/\d+ tracks?/);
      expect(duration).toMatch(/^\d+:\d{2}$/);
      await guest.screenshot({ path: `../docs/studio/reports/evidence-w5c/C-197-1689x1277.png` });
      return `signed out: brand "${brand}", badge "${badge}", "${title}", "${meta}", duration ${duration}`;
    } finally {
      await anonymous.close();
    }
  });

  await check(rec, page, "C-198", async () => {
    await page.goto(`/studio/shared/${share.token}`);
    const card = page.locator(".shared-studio-card");
    await expect(card).toBeVisible({ timeout: 30_000 });
    const rows = await page.locator(".shared-studio-track").count();
    const clips = page.locator(".shared-studio-clip");
    const clipCount = await clips.count();
    const geometry = await clips.evaluateAll((nodes) =>
      nodes.map((node) => {
        const style = (node as HTMLElement).style;
        return [style.left, style.width];
      })
    );
    const inputs = await card.locator("input, textarea, [contenteditable]").count();
    expect(rows).toBe(5);
    expect(clipCount).toBe(5);
    for (const [left, width] of geometry as string[][]) {
      expect(left.endsWith("%")).toBe(true);
      expect(width.endsWith("%")).toBe(true);
    }
    await shot(page, "C-198-1689x1277");
    return `${rows} lane rows, ${clipCount} clips positioned in % (${geometry
      .slice(0, 3)
      .map((pair) => (pair as string[]).join("/"))
      .join(", ")}); editable fields outside the comment form = ${inputs}`;
  });

  await check(rec, page, "C-199", async () => {
    await page.goto(`/studio/shared/${share.token}`);
    await page.locator(".shared-studio-card").waitFor({ timeout: 30_000 });
    await page.locator('.shared-studio-comment-form input[placeholder="Your name"]').fill("W5C Guest");
    const body = page.locator(".shared-studio-comment-form textarea");
    await body.fill("Checking the share page comments.");
    await page.locator(".shared-studio-comment-form button", { hasText: /Post comment/ }).click();
    await page.waitForTimeout(1500);
    const list = page.locator(".shared-studio-comment-list");
    const first = list.locator("article").first();
    const author = (await first.locator("header b").innerText()).trim();
    const stamp = (await first.locator("header span").innerText()).trim();
    const text = (await first.locator("p").innerText()).trim();
    const cleared = await body.inputValue();
    expect(author).toBe("W5C Guest");
    expect(stamp.length).toBeGreaterThan(0);
    expect(text).toBe("Checking the share page comments.");
    expect(cleared).toBe("");
    await shot(page, "C-199-1689x1277");
    return `comment at the top by ${author} (${stamp}); textarea cleared`;
  });

  await check(rec, page, "C-200", async () => {
    const first = page.locator(".shared-studio-comment-list article").first();
    await first.locator("button", { hasText: "Reply" }).first().click();
    const banner = page.locator(".shared-studio-reply-banner");
    await expect(banner).toBeVisible({ timeout: 8000 });
    const bannerText = (await banner.innerText()).replace(/\s+/g, " ").trim();
    expect(bannerText).toContain("Replying to W5C Guest");
    await page.locator(".shared-studio-comment-form textarea").fill("A nested reply.");
    await page.locator(".shared-studio-comment-form button", { hasText: /Post reply/ }).click();
    await page.waitForTimeout(1500);
    const nested = page.locator(".shared-studio-comment-children article").first();
    await expect(nested).toBeVisible({ timeout: 8000 });
    const nestedText = (await nested.locator("p").innerText()).trim();
    expect(nestedText).toBe("A nested reply.");
    await page.locator(".shared-studio-comment-list article").first().locator("button", { hasText: "Reply" }).first().click();
    await expect(page.locator(".shared-studio-reply-banner")).toBeVisible({ timeout: 5000 });
    await page.locator(".shared-studio-reply-banner button", { hasText: "Cancel" }).click();
    await expect(page.locator(".shared-studio-reply-banner")).toHaveCount(0);
    return `banner "${bannerText}"; the reply nested under the comment; Cancel cleared the banner`;
  });

  await check(rec, page, "C-201", async () => {
    const button = page.locator(".shared-studio-comment-form button", { hasText: /Post comment/ });
    await page.locator(".shared-studio-comment-form textarea").fill("");
    expect(await button.isDisabled()).toBe(true);
    await page.locator(".shared-studio-comment-form textarea").fill("   ");
    expect(await button.isDisabled()).toBe(true);
    return "Post is disabled for an empty or whitespace-only body";
  });

  await check(rec, page, "C-202", async () => {
    await page.goto(`/studio/shared/${emptyShare.token}`);
    await page.locator(".shared-studio-card").waitFor({ timeout: 30_000 });
    const empty = page.locator(".shared-studio-comment-empty");
    await expect(empty).toBeVisible({ timeout: 8000 });
    return `no-comments note = "${(await empty.innerText()).trim()}"`;
  });

  await check(rec, page, "C-203", async () => {
    let signedOut = "";
    const anonymous = await ctx.browser()!.newContext({ viewport });
    try {
      const guest = await anonymous.newPage();
      await guest.goto(`/studio/shared/${emptyShare.token}`);
      const footer = guest.locator(".shared-studio-footer-actions");
      await expect(footer).toBeVisible({ timeout: 30_000 });
      signedOut = (await footer.innerText()).replace(/\s+/g, " ").trim();
      expect(signedOut).toContain("Sign in to fork");
      await guest.close();
    } finally {
      await anonymous.close();
    }
    await page.goto(`/studio/shared/${emptyShare.token}`);
    const footer = page.locator(".shared-studio-footer-actions");
    await footer.waitFor({ timeout: 30_000 });
    const signedIn = (await footer.innerText()).replace(/\s+/g, " ").trim();
    expect(signedIn).toContain("Fork to Studio");
    await Promise.all([
      page.waitForURL(/\/studio\/editor\?project=/, { timeout: 40_000 }),
      footer.locator("button", { hasText: "Fork to Studio" }).click(),
    ]);
    await page.locator(".se-shell").waitFor({ timeout: 40_000 });
    await page.waitForTimeout(800);
    const chip = (await page.locator(".se-chip").first().innerText()).replace(/\s+/g, " ").trim();
    return `signed out "${signedOut}"; signed in "${signedIn}"; fork opened a copy ("${chip}")`;
  });

  await check(rec, page, "C-204", async () => {
    await page.goto("/studio/shared/not-a-real-token-w5c");
    const empty = page.locator(".shared-studio-empty");
    await expect(empty).toBeVisible({ timeout: 30_000 });
    const heading = (await empty.locator("h1").innerText()).trim();
    const message = (await empty.locator("p").innerText()).trim();
    expect(heading).toBe("Project unavailable");
    expect(message.length).toBeGreaterThan(0);
    await shot(page, "C-204-1689x1277");
    return `"${heading}": "${message}"`;
  });
});

test("C14 — onboarding", async () => {
  await openEditor(page, P0, { onboarding: true });

  await check(rec, page, "C-205", async () => {
    const overlay = page.locator('[role="dialog"][aria-label="How do you want to start?"]');
    await expect(overlay).toBeVisible({ timeout: 15_000 });
    const tiles = await overlay.locator(".se-onboard-tile").count();
    expect(tiles).toBe(5);
    await shot(page, "C-205-1689x1277");
    return `overlay "How do you want to start?" with ${tiles} tiles`;
  });

  await check(rec, page, "C-206", async () => {
    const overlay = page.locator('[role="dialog"][aria-label="How do you want to start?"]');
    const titles = (await overlay.locator(".se-onboard-tile strong").allInnerTexts()).map((text) =>
      text.trim()
    );
    expect(titles).toEqual([
      "Edit Your Song",
      "Upload Audio",
      "Create a song",
      "Open a project",
      "Empty Project",
    ]);
    return `tiles in order = ${titles.join(" | ")}`;
  });

  await check(rec, page, "C-207", async () => {
    const overlay = page.locator('[role="dialog"][aria-label="How do you want to start?"]');
    await overlay.locator(".se-onboard-tile", { hasText: "Edit Your Song" }).click();
    await expect(overlay).toHaveCount(0, { timeout: 8000 });
    const library = page.locator(".se-library").first();
    await expect(library).toBeVisible({ timeout: 10_000 });
    const active = (await library.locator(".se-lib-tile.on, .se-lib-tile.active").first().innerText().catch(() => "")).trim();
    const tiles = (await library.locator(".se-lib-tile").allInnerTexts()).map((text) => text.trim());
    return `overlay closed; library opened (active "${active || tiles[0]}")`;
  });

  await check(rec, page, "C-208", async () => {
    await openEditor(page, P0B, { onboarding: true });
    const overlay = page.locator('[role="dialog"][aria-label="How do you want to start?"]');
    await overlay.locator(".se-onboard-tile", { hasText: "Upload Audio" }).click();
    await expect(overlay).toHaveCount(0, { timeout: 8000 });
    const library = page.locator(".se-library").first();
    await expect(library).toBeVisible({ timeout: 10_000 });
    const text = (await library.innerText()).replace(/\s+/g, " ");
    expect(text.toLowerCase()).toContain("upload");
    return `overlay closed; library opened on Uploads (${text.slice(0, 60)}…)`;
  });

  await check(rec, page, "C-209", async () => {
    await openEditor(page, P0C, { onboarding: true });
    const overlay = page.locator('[role="dialog"][aria-label="How do you want to start?"]');
    await expect(overlay).toBeVisible({ timeout: 15_000 });
    await overlay.locator("button", { hasText: "Start empty" }).click();
    await expect(overlay).toHaveCount(0, { timeout: 8000 });
    const flag = await page.evaluate(
      (id) => window.localStorage.getItem(`studio:onboarded:${id}`),
      P0C
    );
    expect(flag).toBe("1");
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator(".se-shell").waitFor({ timeout: 40_000 });
    await page.waitForTimeout(800);
    expect(await page.locator(".se-onboard-backdrop").count()).toBe(0);
    return `Start empty closed it; studio:onboarded:${P0C.slice(0, 8)}… = "${flag}"; absent after reload`;
  });

  await check(rec, page, "C-210", async () => {
    await page.locator(".se-chip").first().click();
    await page.locator('.se-project-menu [role="menuitem"]', { hasText: "Show Quick Start again" }).click();
    const overlay = page.locator('[role="dialog"][aria-label="How do you want to start?"]');
    await expect(overlay).toBeVisible({ timeout: 10_000 });
    return "Show Quick Start again re-opened the overlay after it had been dismissed";
  });
});
