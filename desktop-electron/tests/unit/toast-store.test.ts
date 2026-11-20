import { beforeEach, describe, expect, it } from "vitest";
import { useToastStore } from "../../src/components/toast-store";

function reset(): void {
  useToastStore.setState({ items: [], history: [], unread: 0, panelOpen: false });
}

describe("toast store", () => {
  beforeEach(reset);

  it("keeps a history entry and unread count for each toast", () => {
    const id = useToastStore.getState().push("Saved.", "success", 0);
    const state = useToastStore.getState();
    expect(state.items).toHaveLength(1);
    expect(state.history).toHaveLength(1);
    expect(state.history[0]).toMatchObject({ id, message: "Saved.", tone: "success" });
    expect(state.unread).toBe(1);
  });

  it("dismisses the transient toast without losing history", () => {
    const id = useToastStore.getState().push("Queued.", "info", 0);
    useToastStore.getState().dismiss(id);
    const state = useToastStore.getState();
    expect(state.items).toHaveLength(0);
    expect(state.history).toHaveLength(1);
    expect(state.unread).toBe(1);
  });

  it("marks everything read and clears history on request", () => {
    useToastStore.getState().push("One", "info", 0);
    useToastStore.getState().push("Two", "danger", 0);
    useToastStore.getState().markAllRead();
    expect(useToastStore.getState().unread).toBe(0);
    expect(useToastStore.getState().history).toHaveLength(2);
    useToastStore.getState().clearHistory();
    expect(useToastStore.getState().history).toHaveLength(0);
    expect(useToastStore.getState().unread).toBe(0);
  });

  it("caps the history so a long session stays bounded", () => {
    for (let index = 0; index < 45; index += 1) {
      useToastStore.getState().push(`Event ${index}`, "info", 0);
    }
    expect(useToastStore.getState().history).toHaveLength(40);
    expect(useToastStore.getState().history[0]?.message).toBe("Event 44");
  });

  it("tracks whether the notifications panel is open", () => {
    useToastStore.getState().setPanelOpen(true);
    expect(useToastStore.getState().panelOpen).toBe(true);
    useToastStore.getState().setPanelOpen(false);
    expect(useToastStore.getState().panelOpen).toBe(false);
  });
});
