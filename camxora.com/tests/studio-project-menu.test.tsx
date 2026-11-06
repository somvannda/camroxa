import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/**
 * Project menu (reference §18.1). Network calls are mocked; the point is that the
 * captured item order exists, the wired items call the endpoints with the right
 * arguments, and the three we cannot honour are disabled with a reason.
 */

const api = vi.hoisted(() => ({
  listStudioProjects: vi.fn(),
  listStudioProjectVersions: vi.fn(),
  listStudioProjectShares: vi.fn(),
  createStudioProjectShare: vi.fn(),
  updateStudioProject: vi.fn(),
  restoreStudioProjectVersion: vi.fn(),
  createStudioProject: vi.fn(),
  forkStudioProject: vi.fn(),
}));

vi.mock("@/lib/studio-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/studio-api")>();
  return { ...actual, ...api };
});

import { StudioProjectMenu } from "@/components/studio/StudioProjectMenu";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderMenu(overrides: Partial<Parameters<typeof StudioProjectMenu>[0]> = {}) {
  const onRenamed = vi.fn();
  const onShowQuickStart = vi.fn();
  const onSettingsChange = vi.fn();
  render(
    <StudioProjectMenu
      projectId="p1"
      title="Demo"
      settings={{ ghostDrag: true, whatsThis: true }}
      onSettingsChange={onSettingsChange}
      onRenamed={onRenamed}
      onShowQuickStart={onShowQuickStart}
      {...overrides}
    />
  );
  return { onRenamed, onShowQuickStart, onSettingsChange };
}

describe("StudioProjectMenu", () => {
  it("shows the captured items in order, with the unwired ones disabled", async () => {
    const user = userEvent.setup();
    renderMenu();
    await user.click(screen.getByRole("button", { name: /Demo/ }));

    const items = screen.getAllByRole("menuitem");
    expect(items.map((node) => node.textContent?.trim())).toEqual([
      "New Project",
      "Open Project",
      "Rename",
      "Duplicate Project",
      "Version History",
      "Share Project",
      "Open a copy in v1",
      "Studio Settings",
      "Show Quick Start again",
    ]);

    expect((items[0] as HTMLButtonElement).disabled).toBe(false);
    expect((items[5] as HTMLButtonElement).disabled).toBe(false);
    expect((items[6] as HTMLButtonElement).disabled).toBe(true);
    expect(items[6].getAttribute("title")).toMatch(/v1/);
    expect((items[7] as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows the captured settings sections and toggles ghost drag", async () => {
    const user = userEvent.setup();
    const { onSettingsChange } = renderMenu();

    await user.click(screen.getByRole("button", { name: /Demo/ }));
    await user.click(screen.getByRole("menuitem", { name: "Studio Settings" }));

    const dialog = await screen.findByRole("dialog", { name: "Studio settings" });
    expect(dialog).toBeTruthy();
    for (const section of ["Performance", "Window management", "Content"]) {
      expect(screen.getByText(section)).toBeTruthy();
    }

    const ghost = screen.getByRole("checkbox", { name: "Ghost drag for arrangement moves" }) as HTMLInputElement;
    expect(ghost.checked).toBe(true);
    await user.click(ghost);
    expect(onSettingsChange).toHaveBeenCalledWith({ ghostDrag: false, whatsThis: true });
  });

  it("opens settings with ctrl shift ,", async () => {
    const user = userEvent.setup();
    renderMenu();
    await user.keyboard("{Control>}{Shift>},<{/Shift}{/Control}");
    expect(await screen.findByRole("dialog", { name: "Studio settings" })).toBeTruthy();
  });

  it("does not stack settings on top of an open dialog", async () => {
    const user = userEvent.setup();
    renderMenu();

    await user.click(screen.getByRole("button", { name: /Demo/ }));
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));
    expect(await screen.findByRole("dialog", { name: "Rename project" })).toBeTruthy();

    await user.keyboard("{Control>}{Shift>},<{/Shift}{/Control}");
    expect(screen.getByRole("dialog", { name: "Rename project" })).toBeTruthy();
    expect(screen.queryByRole("dialog", { name: "Studio settings" })).toBeNull();
  });

  it("renames through the API and reports the new title", async () => {
    const user = userEvent.setup();
    api.updateStudioProject.mockResolvedValue({ id: "p1", title: "Renamed" });
    const { onRenamed } = renderMenu();

    await user.click(screen.getByRole("button", { name: /Demo/ }));
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));

    const input = screen.getByLabelText("Project title") as HTMLInputElement;
    expect(input.value).toBe("Demo");
    await user.clear(input);
    await user.type(input, "Renamed");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(api.updateStudioProject).toHaveBeenCalledWith("p1", { title: "Renamed" }));
    expect(onRenamed).toHaveBeenCalledWith("Renamed");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("refuses an empty title", async () => {
    const user = userEvent.setup();
    renderMenu();

    await user.click(screen.getByRole("button", { name: /Demo/ }));
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));
    await user.clear(screen.getByLabelText("Project title"));
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(api.updateStudioProject).not.toHaveBeenCalled();
    expect(screen.getByText("A project title is required.")).toBeTruthy();
  });

  it("lists saved versions with their labels", async () => {
    const user = userEvent.setup();
    api.listStudioProjectVersions.mockResolvedValue({
      items: [
        { id: "v1", label: "Before the drop", title: "Demo", project_id: "p1", bpm: 120, time_signature: "4/4" },
      ],
      total: 1,
    });
    renderMenu();

    await user.click(screen.getByRole("button", { name: /Demo/ }));
    await user.click(screen.getByRole("menuitem", { name: "Version History" }));

    expect(await screen.findByText("Before the drop")).toBeTruthy();
    expect(screen.getByLabelText("Restore Before the drop")).toBeTruthy();
    expect(api.listStudioProjectVersions).toHaveBeenCalledWith("p1");
  });

  it("explains when there are no versions", async () => {
    const user = userEvent.setup();
    api.listStudioProjectVersions.mockResolvedValue({ items: [], total: 0 });
    renderMenu();

    await user.click(screen.getByRole("button", { name: /Demo/ }));
    await user.click(screen.getByRole("menuitem", { name: "Version History" }));

    expect(await screen.findByText(/No versions yet/)).toBeTruthy();
  });

  it("lists other projects to open", async () => {
    const user = userEvent.setup();
    api.listStudioProjects.mockResolvedValue({
      items: [
        { id: "p1", title: "Demo", bpm: 120, time_signature: "4/4", major_version: 2 },
        { id: "p2", title: "Other", bpm: 120, time_signature: "4/4", major_version: 2 },
      ],
      total: 2,
    });
    renderMenu();

    await user.click(screen.getByRole("button", { name: /Demo/ }));
    await user.click(screen.getByRole("menuitem", { name: "Open Project" }));

    expect(await screen.findByLabelText("Open Other")).toBeTruthy();
    expect(screen.getByLabelText("Open Demo")).toBeTruthy();
  });

  it("re-opens the quick start overlay from the last item", async () => {
    const user = userEvent.setup();
    const { onShowQuickStart } = renderMenu();

    await user.click(screen.getByRole("button", { name: /Demo/ }));
    await user.click(screen.getByRole("menuitem", { name: "Show Quick Start again" }));

    expect(onShowQuickStart).toHaveBeenCalledOnce();
    expect(screen.queryByRole("menu")).toBeNull();
  });
});

describe("StudioProjectMenu sharing", () => {
  function shareFixture(overrides: Partial<Parameters<typeof StudioProjectMenu>[0]> = {}) {
    api.listStudioProjectShares.mockResolvedValue({ items: [] });
    api.createStudioProjectShare.mockResolvedValue({
      id: "s1",
      token: "tok-1",
      path: "/studio/shared/tok-1",
      permission: "view",
      expires_at: new Date(Date.now() + 7 * 86_400_000).toISOString(),
    });
    return renderMenu({ title: "Demo", ...overrides });
  }

  it("creates a view link and copies it", async () => {
    const user = userEvent.setup();
    shareFixture();

    await user.click(screen.getByRole("button", { name: /Demo/ }));
    await user.click(screen.getByRole("menuitem", { name: "Share Project" }));

    const dialog = await screen.findByRole("dialog", { name: "Share project" });
    expect(api.createStudioProjectShare).toHaveBeenCalledWith("p1", 7, "view");

    const link = (await screen.findByLabelText("Share link")) as HTMLInputElement;
    expect(link.value).toMatch(/\/studio\/shared\/tok-1$/);
    expect(link.readOnly).toBe(true);

    await user.click(screen.getByRole("button", { name: "Copy Link" }));
    expect(await screen.findByRole("button", { name: "Copied" })).toBeTruthy();
    // user-event owns the clipboard stub, so read back what the component wrote.
    expect(await navigator.clipboard.readText()).toBe(link.value);

    await user.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("reuses a live link instead of minting another", async () => {
    const user = userEvent.setup();
    api.listStudioProjectShares.mockResolvedValue({
      items: [
        { id: "old", token: "old", path: "/studio/shared/old", revoked_at: "2026-01-01T00:00:00Z" },
        { id: "live", token: "live-tok", path: "/studio/shared/live-tok" },
      ],
    });
    renderMenu();

    await user.click(screen.getByRole("button", { name: /Demo/ }));
    await user.click(screen.getByRole("menuitem", { name: "Share Project" }));

    const link = (await screen.findByLabelText("Share link")) as HTMLInputElement;
    expect(link.value).toMatch(/live-tok$/);
    expect(api.createStudioProjectShare).not.toHaveBeenCalled();
  });

  it("gates an unnamed project and lets Skip proceed without renaming", async () => {
    const user = userEvent.setup();
    api.listStudioProjectShares.mockResolvedValue({ items: [] });
    api.createStudioProjectShare.mockResolvedValue({
      id: "s1",
      token: "tok-2",
      path: "/studio/shared/tok-2",
      permission: "view",
    });
    renderMenu({ title: "Untitled project" });

    await user.click(screen.getByRole("button", { name: /Untitled project/ }));
    await user.click(screen.getByRole("menuitem", { name: "Share Project" }));

    const gate = await screen.findByRole("dialog", { name: "Name project before sharing" });
    expect((screen.getByLabelText("Project title") as HTMLInputElement).value).toBe("Untitled project");

    await user.click(screen.getByRole("button", { name: "Skip" }));
    expect(await screen.findByLabelText("Share link")).toBeTruthy();
    expect(api.updateStudioProject).not.toHaveBeenCalled();
  });

  it("renames before sharing when the name is saved", async () => {
    const user = userEvent.setup();
    api.updateStudioProject.mockResolvedValue({ id: "p1", title: "Night drive" });
    api.listStudioProjectShares.mockResolvedValue({ items: [] });
    api.createStudioProjectShare.mockResolvedValue({
      id: "s1",
      token: "tok-3",
      path: "/studio/shared/tok-3",
      permission: "view",
    });
    const { onRenamed } = renderMenu({ title: "Untitled project" });

    await user.click(screen.getByRole("button", { name: /Untitled project/ }));
    await user.click(screen.getByRole("menuitem", { name: "Share Project" }));

    const input = (await screen.findByLabelText("Project title")) as HTMLInputElement;
    await user.clear(input);
    await user.type(input, "Night drive");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(api.updateStudioProject).toHaveBeenCalledWith("p1", { title: "Night drive" })
    );
    expect(onRenamed).toHaveBeenCalledWith("Night drive");
    expect(await screen.findByRole("dialog", { name: "Share project" })).toBeTruthy();
    expect(screen.getByText(/Share “Night drive”/)).toBeTruthy();
  });
});
