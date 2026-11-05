import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { StudioHeader } from "@/components/studio/StudioHeader";
import { StudioFooter } from "@/components/studio/StudioFooter";
import { StudioLibrary, formatSongCount, formatUploadLength } from "@/components/studio/StudioLibrary";
import { ClipSourceStrip } from "@/components/studio/ClipSourceStrip";
import { StudioTrackPanel } from "@/components/studio/StudioTrackPanel";
import type { StudioTrack } from "@/lib/studio-tracks";
import type { StudioUpload } from "@/lib/studio-api";
import type { WebMusicGeneration } from "@/lib/library-api";
import type { WebMusicWorkspace } from "@/lib/web-music-api";

const noop = () => {};

// Without this each render stacks onto the previous one and queries match duplicates.
afterEach(cleanup);

function headerProps() {
  return {
    title: "Demo",
    projectId: "p1" as string | null,
    settings: { ghostDrag: true, whatsThis: true },
    onSettingsChange: noop,
    onRenamed: noop,
    onShowQuickStart: noop,
    timeSignature: "4/4",
    clock: "00:01.000",
    barBeat: "001.1.1",
    bpm: 120,
    onBpmChange: noop,
    onBpmCommit: noop,
    playing: false,
    loop: false,
    metronome: false,
    canUndo: false,
    canRedo: false,
    saveStatus: "saved" as const,
    onRetrySave: noop,
    meter: null,
    playbackRate: 1,
    onCycleSpeed: noop,
    exportOpen: false,
    exporting: false,
    rangeReady: false,
    onToggleExport: noop,
    onExport: noop,
    normalise: false,
    onToggleNormalise: noop,
    libraryOpen: false,
    onToggleLibrary: noop,
    onBackToStart: noop,
    onTogglePlay: noop,
    onToggleLoop: noop,
    onToggleMetronome: noop,
    onUndo: noop,
    onRedo: noop,
  };
}

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
    groupId: null,
    chain: [],
    clipIds: [],
    ...overrides,
  };
}

describe("StudioHeader", () => {
  it("shows the project, readouts and save state", () => {
    render(<StudioHeader {...headerProps()} />);
    expect(screen.getByText("Demo")).toBeTruthy();
    expect(screen.getByText("00:01.000")).toBeTruthy();
    expect(screen.getByText("001.1.1")).toBeTruthy();
    expect(screen.getByText("Saved")).toBeTruthy();
    expect(screen.getByLabelText("Tempo in BPM")).toBeTruthy();
  });

  it("disables undo and redo until history exists", () => {
    render(<StudioHeader {...headerProps()} />);
    expect((screen.getByLabelText("Undo") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByLabelText("Redo") as HTMLButtonElement).disabled).toBe(true);
  });

  it("labels the transport by state", () => {
    const { rerender } = render(<StudioHeader {...headerProps()} />);
    expect(screen.getByLabelText("Play")).toBeTruthy();
    rerender(<StudioHeader {...headerProps()} playing />);
    expect(screen.getByLabelText("Pause")).toBeTruthy();
  });

  it("marks the loop button as pressed when armed", () => {
    render(<StudioHeader {...headerProps()} loop />);
    expect(screen.getByLabelText("Loop").getAttribute("aria-pressed")).toBe("true");
  });

  it("disables the range export until a range exists", async () => {
    const user = userEvent.setup();
    render(<StudioHeader {...headerProps()} exportOpen />);
    const range = screen.getByText("Selected time range (WAV)") as HTMLButtonElement;
    expect(range.disabled).toBe(true);
    expect(screen.getByText("Full mix (WAV)")).toBeTruthy();
    await user.click(screen.getByLabelText("Export menu"));
  });

  it("exposes export normalisation as a checkbox that does not close the menu", async () => {
    const user = userEvent.setup();
    const onToggleNormalise = vi.fn();
    const { rerender } = render(
      <StudioHeader {...headerProps()} exportOpen onToggleNormalise={onToggleNormalise} />
    );
    const item = screen.getByRole("menuitemcheckbox", { name: /Normalise mix/ });
    expect(item.getAttribute("aria-checked")).toBe("false");

    await user.click(item);
    expect(onToggleNormalise).toHaveBeenCalledOnce();
    expect(screen.getByRole("menu")).toBeTruthy();

    rerender(<StudioHeader {...headerProps()} exportOpen normalise onToggleNormalise={onToggleNormalise} />);
    expect(
      screen.getByRole("menuitemcheckbox", { name: /Normalise mix/ }).getAttribute("aria-checked")
    ).toBe("true");
  });
});

function upload(overrides: Partial<StudioUpload> = {}): StudioUpload {
  return {
    id: "u1",
    filename: "take-1.wav",
    content_type: "audio/wav",
    size_bytes: 1024,
    duration_seconds: 127,
    url: "https://example.test/u1.wav",
    ...overrides,
  };
}

function workspace(overrides: Partial<WebMusicWorkspace> = {}): WebMusicWorkspace {
  return { id: "w1", name: "My Workspace", is_default: true, song_count: 946, ...overrides };
}

function libraryProps(overrides: Partial<Parameters<typeof StudioLibrary>[0]> = {}) {
  return {
    width: 368,
    tab: "songs" as const,
    onTab: noop,
    query: "",
    onQuery: noop,
    songs: [],
    workspaces: [],
    activeWorkspaceId: null,
    projects: [],
    uploads: [],
    currentProjectId: null,
    onClose: noop,
    onAddSong: noop,
    onSelectWorkspace: noop,
    onAddUpload: noop,
    onOpenProject: noop,
    ...overrides,
  };
}

describe("formatUploadLength", () => {
  it("formats known lengths and admits when one is missing", () => {
    expect(formatUploadLength(127)).toBe("2:07");
    expect(formatUploadLength(59.6)).toBe("1:00");
    expect(formatUploadLength(null)).toBe("—");
    expect(formatUploadLength(0)).toBe("—");
  });
});

describe("formatSongCount", () => {
  it("pluralises and never shows a negative or fractional count", () => {
    expect(formatSongCount(946)).toBe("946 songs");
    expect(formatSongCount(1)).toBe("1 song");
    expect(formatSongCount(0)).toBe("0 songs");
    expect(formatSongCount(undefined)).toBe("0 songs");
    expect(formatSongCount(-3)).toBe("0 songs");
    expect(formatSongCount(2.4)).toBe("2 songs");
  });
});

describe("StudioLibrary", () => {
  it("lists the drawer's four sections in order", () => {
    render(<StudioLibrary {...libraryProps()} />);
    const tabs = screen.getAllByRole("tab").map((node) => node.textContent);
    expect(tabs).toEqual(["Songs", "Workspaces", "Projects", "Uploads"]);
  });

  it("shows each workspace with its song count and opens it", async () => {
    const user = userEvent.setup();
    const onSelectWorkspace = vi.fn();
    render(
      <StudioLibrary
        {...libraryProps({
          tab: "workspaces",
          workspaces: [workspace(), workspace({ id: "w2", name: "Empty", song_count: 1 })],
          onSelectWorkspace,
        })}
      />
    );

    expect(screen.getByText("946 songs")).toBeTruthy();
    expect(screen.getByText("1 song")).toBeTruthy();
    await user.click(screen.getByLabelText("Show songs in My Workspace"));
    expect(onSelectWorkspace).toHaveBeenCalledWith("w1");

    await user.click(screen.getByLabelText("Show songs from every workspace"));
    expect(onSelectWorkspace).toHaveBeenLastCalledWith(null);
  });

  it("marks the active workspace's Open button as current", () => {
    render(
      <StudioLibrary
        {...libraryProps({ tab: "workspaces", workspaces: [workspace()], activeWorkspaceId: "w1" })}
      />
    );
    expect(screen.getByLabelText("Show songs in My Workspace").getAttribute("aria-current")).toBe(
      "true"
    );
  });

  it("shows and clears the workspace filter on the songs tab", async () => {
    const user = userEvent.setup();
    const onSelectWorkspace = vi.fn();
    render(
      <StudioLibrary
        {...libraryProps({
          tab: "songs",
          workspaces: [workspace()],
          activeWorkspaceId: "w1",
          songs: [],
          onSelectWorkspace,
        })}
      />
    );
    expect(screen.getByText("My Workspace")).toBeTruthy();
    expect(screen.getByText("No songs in this workspace yet.")).toBeTruthy();
    await user.click(screen.getByLabelText("Clear workspace filter"));
    expect(onSelectWorkspace).toHaveBeenCalledWith(null);
  });

  it("shows uploads with their length and adds one to the timeline", async () => {
    const user = userEvent.setup();
    const onAddUpload = vi.fn();
    render(
      <StudioLibrary {...libraryProps({ tab: "uploads", uploads: [upload()], onAddUpload })} />
    );
    expect(screen.getByText("take-1.wav")).toBeTruthy();
    expect(screen.getByText("2:07")).toBeTruthy();
    await user.click(screen.getByLabelText("Add take-1.wav"));
    expect(onAddUpload).toHaveBeenCalledWith(upload());
  });

  it("disables adding an upload that has no signed url", () => {
    render(<StudioLibrary {...libraryProps({ tab: "uploads", uploads: [upload({ url: "" })] })} />);
    expect((screen.getByLabelText("Add take-1.wav") as HTMLButtonElement).disabled).toBe(true);
  });

  it("explains the empty uploads state", () => {
    render(<StudioLibrary {...libraryProps({ tab: "uploads", uploads: [] })} />);
    expect(screen.getByText("No uploads yet. Audio you import appears here.")).toBeTruthy();
  });

  it("filters uploads by the shared search box", async () => {
    const user = userEvent.setup();
    const onQuery = vi.fn();
    render(
      <StudioLibrary
        {...libraryProps({ tab: "uploads", uploads: [upload()], query: "zzz", onQuery })}
      />
    );
    expect(screen.queryByText("take-1.wav")).toBeNull();
    await user.type(screen.getByLabelText("Search library"), "a");
    expect(onQuery).toHaveBeenCalled();
  });
});

describe("StudioFooter", () => {
  it("explains an empty effect chain and fires zoom actions", async () => {
    const user = userEvent.setup();
    const onZoomIn = vi.fn();
    render(
      <StudioFooter
        chain={[]}
        hasTrack
        loop={false}
        onLoop={noop}
        onZoomOut={noop}
        onZoomFit={noop}
        onZoomIn={onZoomIn}
        onSearch={noop}
        onToggleLibrary={noop}
        whatsThis={false}
        onWhatsThis={noop}
      />
    );
    expect(screen.getByText("No effects on this track yet.")).toBeTruthy();
    await user.click(screen.getByLabelText("Zoom in"));
    expect(onZoomIn).toHaveBeenCalledOnce();
    expect(screen.getByLabelText("All projects").getAttribute("href")).toBe("/studio");
  });
});

describe("ClipSourceStrip", () => {
  it("renders nothing without a source", () => {
    const { container } = render(
      <ClipSourceStrip source={null} stems={null} onRequestStems={noop} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows provenance and requests stems", async () => {
    const user = userEvent.setup();
    const onRequestStems = vi.fn();
    const source = {
      id: "s1",
      title: "Seed Demo Loop",
      style: "downtempo",
      model_label: "V6 Pro",
      created_at: "2026-11-03T00:00:00Z",
    } as unknown as WebMusicGeneration;

    render(<ClipSourceStrip source={source} stems={null} onRequestStems={onRequestStems} />);
    expect(screen.getByText("Seed Demo Loop")).toBeTruthy();
    expect(screen.getByText(/V6 Pro/)).toBeTruthy();
    await user.click(screen.getByText("Get stems"));
    expect(onRequestStems).toHaveBeenCalledOnce();
  });

  it("surfaces a stem error verbatim", () => {
    const source = { id: "s1", title: "Song" } as unknown as WebMusicGeneration;
    render(
      <ClipSourceStrip
        source={source}
        stems={{ status: "error", message: "The clip is not ready for Studio edits yet." }}
        onRequestStems={noop}
      />
    );
    expect(screen.getByText("The clip is not ready for Studio edits yet.")).toBeTruthy();
  });
});

describe("StudioTrackPanel", () => {
  function panelProps(overrides: Partial<Parameters<typeof StudioTrackPanel>[0]> = {}) {
    return {
      tracks: [track()],
      selectedTrack: null,
      menuTrackId: null,
      renameTrackId: null,
      renameValue: "",
      hiddenOpen: false,
      onSelectTrack: noop,
      onToggleMenu: noop,
      onToggleFlag: noop,
      onUpdateTrack: noop,
      onRenameStart: noop,
      onRenameChange: noop,
      onRenameCommit: noop,
      onRenameCancel: noop,
      onDuplicate: noop,
      onHide: noop,
      onDelete: noop,
      onAddTrack: noop,
      onToggleHidden: noop,
      onShowAllHidden: noop,
      ...overrides,
    };
  }

  it("counts tracks and hides hidden ones", () => {
    render(<StudioTrackPanel {...panelProps({ tracks: [track(), track({ id: "t2", name: "Track 2", hidden: true })] })} />);
    expect(screen.getByText("2 tracks")).toBeTruthy();
    expect(screen.getByText("Track 1")).toBeTruthy();
    expect(screen.queryByText("Track 2")).toBeNull();
    expect(screen.getByLabelText("1 hidden track")).toBeTruthy();
  });

  it("exposes the captured track menu in order", () => {
    render(<StudioTrackPanel {...panelProps({ menuTrackId: "t1" })} />);
    const items = screen.getAllByRole("menuitem").map((node) => node.textContent?.trim());
    expect(items).toEqual([
      "Rename track",
      "Collapse controls",
      "Duplicate",
      "Hide & Mute Track",
      "Delete",
    ]);
  });

  it("reports mute and solo state through aria-pressed", () => {
    render(<StudioTrackPanel {...panelProps({ tracks: [track({ muted: true, solo: true })] })} />);
    expect(screen.getByLabelText("Mute Track 1").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByLabelText("Solo Track 1").getAttribute("aria-pressed")).toBe("true");
  });

  it("keeps arm disabled and says why", () => {
    render(<StudioTrackPanel {...panelProps()} />);
    const arm = screen.getByLabelText(/^Arm Track 1/);
    expect((arm as HTMLButtonElement).disabled).toBe(true);
    expect(arm.getAttribute("aria-label")).toContain("recording not implemented");
  });
});
