import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { StudioLearn } from "@/components/studio/StudioLearn";

/**
 * Learn menu + What's This? (reference §7/§38). The captured part is the four-row
 * popover and the global hover help; the shortcut list is our own content.
 */

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(cleanup);

function renderLearn(overrides: Partial<Parameters<typeof StudioLearn>[0]> = {}) {
  const onWhatsThis = vi.fn();
  const utils = render(
    <>
      <button type="button" data-help="tempo">
        Tempo control
      </button>
      <StudioLearn whatsThis onWhatsThis={onWhatsThis} {...overrides} />
    </>
  );
  return { onWhatsThis, ...utils };
}

describe("StudioLearn menu", () => {
  it("opens the popover with the four captured rows in order", async () => {
    const user = userEvent.setup();
    renderLearn();

    await user.click(screen.getByRole("button", { name: /Learn/ }));
    const items = screen.getAllByRole("menuitem");
    expect(items.map((node) => node.textContent?.replace(/\s+/g, " ").trim())).toEqual([
      "Keyboard Shortcuts shift ?",
      "YouTube Tutorials ↗",
      "Learning Center",
    ]);

    const toggle = screen.getByRole("menuitemcheckbox");
    expect(toggle.textContent?.replace(/\s+/g, " ").trim()).toBe("What's This? On");
    expect(toggle.getAttribute("aria-checked")).toBe("true");

    // Destinations this build does not have stay visible but disabled.
    expect((items[1] as HTMLButtonElement).disabled).toBe(true);
    expect((items[2] as HTMLButtonElement).disabled).toBe(true);
  });

  it("toggles What's This? through the callback", async () => {
    const user = userEvent.setup();
    const { onWhatsThis } = renderLearn();

    await user.click(screen.getByRole("button", { name: /Learn/ }));
    await user.click(screen.getByRole("menuitemcheckbox"));
    expect(onWhatsThis).toHaveBeenCalledWith(false);
  });

  it("opens the shortcut list from the first row and from ?", async () => {
    const user = userEvent.setup();
    renderLearn();

    await user.click(screen.getByRole("button", { name: /Learn/ }));
    await user.click(screen.getByRole("menuitem", { name: /Keyboard Shortcuts/ }));
    const dialog = await screen.findByRole("dialog", { name: "Keyboard shortcuts" });
    expect(dialog.textContent).toContain("Undo");
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();

    await user.keyboard("?");
    expect(await screen.findByRole("dialog", { name: "Keyboard shortcuts" })).toBeTruthy();
  });
});

describe("What's This? hover help", () => {
  it("explains an annotated control on hover", async () => {
    const user = userEvent.setup();
    renderLearn();

    await user.hover(screen.getByRole("button", { name: "Tempo control" }));
    const card = await screen.findByRole("tooltip");
    expect(card.textContent).toContain("Tempo");
    expect(card.textContent).toContain("BPM");

    await user.unhover(screen.getByRole("button", { name: "Tempo control" }));
    await waitFor(() => expect(screen.queryByRole("tooltip")).toBeNull());
  });

  it("stays quiet when the feature is off", async () => {
    const user = userEvent.setup();
    renderLearn({ whatsThis: false });

    await user.hover(screen.getByRole("button", { name: "Tempo control" }));
    expect(screen.queryByRole("tooltip")).toBeNull();
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("introduces itself once and remembers the dismissal", async () => {
    const user = userEvent.setup();
    const { unmount } = renderLearn();

    const intro = await screen.findByRole("note");
    expect(intro.textContent).toContain("Hover over any control");
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("note")).toBeNull();
    expect(window.localStorage.getItem("studio:help:seen")).toBe("1");

    unmount();
    renderLearn();
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("turns the feature off from the intro card", async () => {
    const user = userEvent.setup();
    const { onWhatsThis } = renderLearn();

    await user.click(await screen.findByRole("button", { name: "Turn off" }));
    expect(onWhatsThis).toHaveBeenCalledWith(false);
    expect(window.localStorage.getItem("studio:help:seen")).toBe("1");
  });
});
