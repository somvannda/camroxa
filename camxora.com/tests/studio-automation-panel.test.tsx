import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/react";
import { useState } from "react";

import { StudioAutomationPanel } from "@/components/studio/StudioAutomationPanel";
import type { StudioTrack } from "@/lib/studio-tracks";

afterEach(cleanup);

function track(overrides: Partial<StudioTrack> = {}): StudioTrack {
  return {
    id: "track-1",
    name: "Lead",
    color: "#7c5cf0",
    index: 0,
    volume: 80,
    pan: 0,
    muted: false,
    solo: false,
    hidden: false,
    collapsed: false,
    chain: [],
    clipIds: [],
    ...overrides,
  };
}

/** A real parent owns the track, so the arrows act on the updated document. */
function Harness({
  initial,
  onChange,
}: {
  initial: StudioTrack;
  onChange: (lane: string, points: Array<{ id: string; time: number; value: number }>) => void;
}) {
  const [current, setCurrent] = useState(initial);
  return (
    <StudioAutomationPanel
      track={current}
      duration={8}
      playhead={0}
      onChange={(lane, points) => {
        setCurrent((state) => ({
          ...state,
          volumeAutomation: lane === "volume" ? points : state.volumeAutomation,
          panAutomation: lane === "pan" ? points : state.panAutomation,
        }));
        onChange(lane, points);
      }}
      onClose={() => {}}
    />
  );
}

function renderPanel(overrides: Partial<StudioTrack> = {}) {
  const onChange = vi.fn();
  const view = render(<Harness initial={track(overrides)} onChange={onChange} />);
  return { ...view, onChange };
}

describe("StudioAutomationPanel", () => {
  it("selects a point and nudges its time and value with the arrow keys", () => {
    const { container, onChange } = renderPanel({
      volumeAutomation: [{ id: "p1", time: 1, value: 50 }],
    });
    const point = container.querySelector(".se-automation-point") as HTMLElement;

    fireEvent.pointerDown(point, { button: 0 });
    expect(point.className).toContain("is-selected");
    expect(point.getAttribute("aria-pressed")).toBe("true");

    fireEvent.keyDown(point, { key: "ArrowUp" });
    expect(onChange).toHaveBeenLastCalledWith("volume", [{ id: "p1", time: 1, value: 51 }]);

    fireEvent.keyDown(point, { key: "ArrowUp", shiftKey: true });
    expect(onChange).toHaveBeenLastCalledWith("volume", [{ id: "p1", time: 1, value: 61 }]);

    fireEvent.keyDown(point, { key: "ArrowRight" });
    expect(onChange).toHaveBeenLastCalledWith("volume", [{ id: "p1", time: 1.1, value: 61 }]);

    fireEvent.keyDown(point, { key: "ArrowLeft", shiftKey: true });
    expect(onChange).toHaveBeenLastCalledWith("volume", [{ id: "p1", time: 0.1, value: 61 }]);
  });

  it("clamps to the lane range and stops responding after Escape", () => {
    const { container, onChange } = renderPanel({
      panAutomation: [{ id: "p1", time: 4, value: 95 }],
    });
    fireEvent.click(container.querySelectorAll<HTMLElement>(".se-automation-tabs .se-pill")[1]);
    const point = container.querySelector(".se-automation-point") as HTMLElement;
    fireEvent.pointerDown(point, { button: 0 });

    fireEvent.keyDown(point, { key: "ArrowUp", shiftKey: true });
    expect(onChange).toHaveBeenLastCalledWith("pan", [{ id: "p1", time: 4, value: 100 }]);

    fireEvent.keyDown(point, { key: "Escape" });
    expect(container.querySelector(".se-automation-point.is-selected")).toBeNull();

    const calls = onChange.mock.calls.length;
    fireEvent.keyDown(point, { key: "ArrowDown" });
    expect(onChange.mock.calls.length).toBe(calls);
  });

  it("selects a newly added point so the keys work immediately", () => {
    const { container, onChange } = renderPanel();
    const lane = container.querySelector(".se-automation-lane") as HTMLElement;
    lane.getBoundingClientRect = () =>
      ({
        left: 0,
        top: 0,
        width: 400,
        height: 100,
        right: 400,
        bottom: 100,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      }) as DOMRect;

    fireEvent.pointerDown(lane, { clientX: 200, clientY: 25, button: 0 });
    const added = container.querySelector(".se-automation-point") as HTMLElement;
    expect(added.className).toContain("is-selected");
    expect(added.getAttribute("aria-label")).toBe("Volume 75 at 4.00s");

    fireEvent.keyDown(lane, { key: "ArrowDown" });
    const points = onChange.mock.calls.at(-1)?.[1] as Array<{ time: number; value: number }>;
    expect(points[0]).toMatchObject({ time: 4, value: 74 });
  });
});
