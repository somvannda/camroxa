import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";

import { StudioTimeline, type StudioTimelineProps } from "@/components/studio/StudioTimeline";
import type { StudioTrack } from "@/lib/studio-tracks";

afterEach(cleanup);

function track(overrides: Partial<StudioTrack> = {}): StudioTrack {
  return {
    id: "t1",
    name: "Track 1",
    color: "#38bdf8",
    index: 0,
    volume: 80,
    pan: 0,
    muted: false,
    solo: false,
    hidden: false,
      collapsed: false,
    groupId: null,
    chain: [],
    clipIds: ["c1"],
    ...overrides,
  };
}

function props(overrides: Partial<StudioTimelineProps> = {}): StudioTimelineProps {
  return {
    tracks: [track()],
    clips: [{ id: "c1", title: "Clip one", start: 0, duration: 4 }],
    barWidth: 96,
    barCount: 4,
    secondsPerBar: 2,
    beatsPerBar: 4,
    duration: 8,
    playhead: 0,
    clock: (seconds) => `00:${String(Math.floor(seconds)).padStart(2, "0")}`,
    rowStep: 86,
    selectedClip: null,
    selectedIds: [],
    drag: null,
    marquee: null,
    loop: false,
    loopStart: 0,
    loopEnd: 0,
    viewWidth: 0,
    viewLeft: 0,
    onScroll: () => {},
    onLanePointerDown: () => {},
    onClipPointerDown: () => {},
    onLoopHandleDown: () => {},
    ...overrides,
  };
}

describe("StudioTimeline", () => {
  it("labels every bar and the time ruler", () => {
    const { container } = render(<StudioTimeline {...props()} />);
    const bars = [...container.querySelectorAll(".se-bar-tick")].map((node) => node.textContent);
    expect(bars).toEqual(["1", "2", "3", "4"]);
    // duration 8s at 30s per time tick means exactly one label.
    expect(container.querySelectorAll(".se-time-tick")).toHaveLength(1);
  });

  it("renders a clip at its start position and width", () => {
    const { container } = render(
      <StudioTimeline {...props({ clips: [{ id: "c1", title: "Clip one", start: 2, duration: 2 }] })} />
    );
    const clip = container.querySelector(".se-clip") as HTMLElement;
    expect(clip).toBeTruthy();
    expect(clip.textContent).toContain("Clip one");
    // start 2s of a 2s bar = one bar = 96px; duration 2s = 96px.
    expect(clip.style.left).toBe("96px");
    expect(clip.style.width).toBe("96px");
  });

  it("marks the selected clip", () => {
    const { container } = render(<StudioTimeline {...props({ selectedClip: "c1" })} />);
    expect(container.querySelector(".se-clip")?.classList.contains("selected")).toBe(true);
  });

  it("draws the playhead where the transport is", () => {
    const { container } = render(<StudioTimeline {...props({ playhead: 4 })} />);
    const playhead = container.querySelector(".se-playhead") as HTMLElement;
    expect(playhead.style.left).toBe("192px");
  });

  it("only draws the loop band with a real range", () => {
    const { container, rerender } = render(
      <StudioTimeline {...props({ loop: true, loopStart: 2, loopEnd: 6 })} />
    );
    expect(container.querySelector(".se-loop-band")).toBeTruthy();
    expect(container.querySelector(".se-loop-handle")).toBeTruthy();

    rerender(<StudioTimeline {...props({ loop: true, loopStart: 4, loopEnd: 4 })} />);
    expect(container.querySelector(".se-loop-band")).toBeNull();
  });

  it("renders the marquee and snap line from the sessions it is given", () => {
    const { container } = render(
      <StudioTimeline
        {...props({
          marquee: { x1: 20, y1: 10, x2: 120, y2: 90 },
          drag: { ids: ["c1"], origins: { c1: 0 }, deltaPx: 96 },
        })}
      />
    );
    const band = container.querySelector(".se-marquee") as HTMLElement;
    expect(band.style.width).toBe("100px");
    expect(band.style.height).toBe("80px");
    const snap = container.querySelector(".se-snap-line") as HTMLElement;
    // one bar of drag snaps the guideline to 96px
    expect(snap.style.left).toBe("96px");
  });

  it("shifts a dragged clip by the snapped delta", () => {
    const { container } = render(
      <StudioTimeline
        {...props({ drag: { ids: ["c1"], origins: { c1: 0 }, deltaPx: 192 } })}
      />
    );
    const clip = container.querySelector(".se-clip") as HTMLElement;
    expect(clip.style.left).toBe("192px");
    expect(clip.classList.contains("dragging")).toBe(true);
  });

  it("culls clips outside the visible window plus its slack", () => {
    const far = [
      { id: "near", title: "Near", start: 0, duration: 2 },
      { id: "far", title: "Far", start: 2000, duration: 2 },
    ];
    const { container } = render(
      <StudioTimeline
        {...props({
          clips: far,
          tracks: [track({ clipIds: ["near", "far"] })],
          viewLeft: 0,
          viewWidth: 400,
          barCount: 1200,
        })}
      />
    );
    const titles = [...container.querySelectorAll(".se-clip-head")].map((node) => node.textContent);
    expect(titles).toContain("Near");
    expect(titles).not.toContain("Far");
  });

  it("shows the empty state without tracks", () => {
    const { container } = render(<StudioTimeline {...props({ tracks: [], clips: [] })} />);
    expect(container.querySelector(".se-empty")?.textContent).toContain("Your session is empty");
  });
});
