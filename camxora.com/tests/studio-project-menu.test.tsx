import { afterEach, describe, expect, it, vi } from "vitest";
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
  render(
    <StudioProjectMenu
      projectId="p1"
      title="Demo"
      onRenamed={onRenamed}
      onShowQuickStart={onShowQuickStart}
      {...overrides}
    />
  );
  return { onRenamed, onShowQuickStart };
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
    expect((items[5] as HTMLButtonElement).disabled).toBe(true);
    expect(items[5].getAttribute("title")).toMatch(/Sharing/);
    expect((items[6] as HTMLButtonElement).disabled).toBe(true);
    expect((items[7] as HTMLButtonElement).disabled).toBe(true);
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

    expect(await screen.findByText(/No saved versions yet/)).toBeTruthy();
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
