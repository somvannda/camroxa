import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { StudioSaveStatus } from "@/components/studio/StudioSaveStatus";

afterEach(cleanup);

describe("StudioSaveStatus mirror dot", () => {
  it("marks the save chip with the mirror state", () => {
    const { rerender } = render(
      <StudioSaveStatus
        status="saved"
        sync={{ status: "synced", last_error: null, state_sync: true }}
      />
    );
    expect(
      screen.getByRole("img", { name: /Suno Studio: mirrored/ }).getAttribute("data-state")
    ).toBe("synced");

    rerender(
      <StudioSaveStatus
        status="saved"
        sync={{ status: "conflict", last_error: null, state_sync: true }}
      />
    );
    expect(
      screen
        .getByRole("img", { name: /Suno Studio has newer changes/ })
        .getAttribute("data-state")
    ).toBe("conflict");
  });

  it("explains skipped clips and errors in the tooltip", () => {
    render(
      <StudioSaveStatus
        status="saved"
        sync={{ status: "synced", last_error: null, skipped_clips: ["a", "b"], state_sync: true }}
      />
    );
    expect(screen.getByRole("img", { name: /mirrored/i }).getAttribute("title")).toContain(
      "2 clip(s) have no Suno copy yet"
    );
  });

  it("renders no dot when the mirror state is unknown", () => {
    render(<StudioSaveStatus status="saved" />);
    expect(screen.queryByRole("img")).toBeNull();
  });
});
