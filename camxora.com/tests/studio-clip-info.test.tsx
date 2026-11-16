import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import type { WebMusicGeneration } from "@/lib/library-api";
import { StudioClipInfo } from "@/components/studio/StudioClipInfo";

const clip = {
  id: "clip-1",
  title: "Loop",
  start: 0,
  duration: 4,
  audioUrl: "/seed/demo-loop.wav",
};

function source(overrides: Partial<WebMusicGeneration> = {}): WebMusicGeneration {
  return {
    id: "song-1",
    title: "Source song",
    style: "downtempo",
    status: "success",
    clips: [],
    created_at: "2026-11-16T00:00:00Z",
    ...overrides,
  } as WebMusicGeneration;
}

function renderInfo(music: WebMusicGeneration | null) {
  return render(
    <StudioClipInfo
      width={360}
      clip={clip}
      source={music}
      stems={null}
      onRequestStems={vi.fn()}
      onClose={vi.fn()}
    />
  );
}

/** QA B6: the rail showed a colour swatch where the capture shows the song's artwork. */
describe("StudioClipInfo artwork", () => {
  it("renders the source cover image when the song has one", () => {
    const { container } = renderInfo(
      source({ clips: [{ variant: "ok", image_url: "/art/cover.png", audio_url: clip.audioUrl }] })
    );
    const img = container.querySelector("img.se-clip-art");
    expect(img?.getAttribute("src")).toBe("/art/cover.png");
    expect(img?.getAttribute("alt")).toBe("");
  });

  it("falls back to the clip colour when the song has no artwork", () => {
    const { container } = renderInfo(source());
    expect(container.querySelector("img.se-clip-art")).toBeNull();
    expect(container.querySelector("span.se-clip-art")).toBeTruthy();
  });
});
