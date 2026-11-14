import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { StudioProjectThumbView } from "@/components/studio/StudioProjectThumb";

describe("StudioProjectThumbView", () => {
  it("draws one bar per clip, scaled to the arrangement end", () => {
    const { container } = render(
      <StudioProjectThumbView
        thumb={{
          end: 8,
          tracks: [
            { c: "#ff0000", clips: [{ s: 0, d: 4 }, { s: 4, d: 4 }] },
            { c: "#00ff00", clips: [] },
          ],
        }}
      />
    );
    const bars = container.querySelectorAll(".se-thumb-clip");
    expect(bars).toHaveLength(2);
    expect((bars[0] as HTMLElement).style.width).toBe("50%");
    expect((bars[1] as HTMLElement).style.left).toBe("50%");
    expect(container.querySelectorAll(".se-thumb-row")).toHaveLength(2);
  });

  it("falls back to the neutral placeholder for an empty project", () => {
    const { container } = render(<StudioProjectThumbView thumb={null} />);
    expect(container.querySelector(".se-project-preview.is-thumb")).toBeNull();
    expect(container.querySelector(".se-project-preview")).not.toBeNull();
  });
});
