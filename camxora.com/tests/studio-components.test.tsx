import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { StudioHeader } from "@/components/studio/StudioHeader";
import { StudioFooter } from "@/components/studio/StudioFooter";
import {
  SONG_DRAG_TYPE,
  StudioLibrary,
  formatSongCount,
  formatUploadLength,
  type LibraryView,
} from "@/components/studio/StudioLibrary";
import { StudioSongDetail } from "@/components/studio/StudioSongDetail";
import { ClipSourceStrip } from "@/components/studio/ClipSourceStrip";
import { StudioTrackPanel } from "@/components/studio/StudioTrackPanel";
import type { StudioTrack } from "@/lib/studio-tracks";
import type { StudioProject, StudioUpload } from "@/lib/studio-api";
import type { WebMusicGeneration } from "@/lib/library-api";
import type { WebMusicWorkspace } from "@/lib/web-music-api";

const noop = () => {};

// Without this each render stacks onto the previous one and queries match duplicates.
afterEach(cleanup);

function headerProps() {
  return {
    title: "Demo",
    projectId: "p1" as string | null,
    settings: { ghostDrag: true, whatsThis: true, inputDeviceId: null, countIn: false },
    onSettingsChange: noop,
    onRenamed: noop,
    onShowQuickStart: noop,
    timeSignature: "4/4",
    onTimeSignature: noop,
    clock: "00:01.000",
    barBeat: "001.1.1",
    bpm: 120,
    onBpmChange: noop,
    onBpmCommit: noop,
    playing: false,
    loop: false,
    metronome: false,
    beat: 0,
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
    onStop: noop,
    onTogglePlay: noop,
    onToggleRecord: noop,
    recording: false,
    inputDeviceId: null as string | null,
    inputDevices: [] as { id: string; label: string }[],
    inputOpen: false,
    onToggleInput: noop,
    onPickInput: noop,
    countIn: false,
    onToggleCountIn: noop,
    countInBeat: 0,
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
      collapsed: false,
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

  it("reports the metronome beat while the click track is on", () => {
    render(<StudioHeader {...headerProps()} metronome beat={3} />);
    const button = screen.getByLabelText(/Metronome \(click track\)/);
    expect(button.getAttribute("aria-pressed")).toBe("true");
    expect(button.getAttribute("data-beat")).toBe("3");
    expect(button.getAttribute("aria-label")).toContain("beat 3");
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
  it("lists recording inputs and picks one", async () => {
    const user = userEvent.setup();
    const onPickInput = vi.fn();
    render(
      <StudioHeader
        {...headerProps()}
        inputOpen
        onPickInput={onPickInput}
        inputDeviceId="mic2"
        inputDevices={[
          { id: "mic1", label: "Built-in Microphone" },
          { id: "mic2", label: "USB Microphone" },
        ]}
      />
    );
    const menu = screen.getByRole("menu", { name: "Recording input" });
    expect(menu).toBeTruthy();
    expect(
      screen.getByRole("menuitemradio", { name: "USB Microphone" }).getAttribute("aria-checked")
    ).toBe("true");
    await user.click(screen.getByRole("menuitemradio", { name: "Built-in Microphone" }));
    expect(onPickInput).toHaveBeenCalledWith("mic1");
    await user.click(screen.getByRole("menuitemradio", { name: "System default" }));
    expect(onPickInput).toHaveBeenLastCalledWith(null);
  });

  it("toggles the one-bar count-in from the input menu", async () => {
    const user = userEvent.setup();
    const onToggleCountIn = vi.fn();
    render(
      <StudioHeader
        {...headerProps()}
        inputOpen
        onToggleCountIn={onToggleCountIn}
        countIn={false}
      />
    );
    const item = screen.getByRole("menuitemcheckbox", { name: "Count-in (1 bar)" });
    expect(item.getAttribute("aria-checked")).toBe("false");
    await user.click(item);
    expect(onToggleCountIn).toHaveBeenCalledOnce();
  });

  it("labels Record and toggles it, disabled until a track is armed", async () => {
    const user = userEvent.setup();
    const onToggleRecord = vi.fn();
    const { rerender } = render(
      <StudioHeader {...headerProps()} onToggleRecord={onToggleRecord} recordDisabled />
    );
    expect((screen.getByRole("button", { name: "Record" }) as HTMLButtonElement).disabled).toBe(
      true
    );

    rerender(<StudioHeader {...headerProps()} onToggleRecord={onToggleRecord} />);
    await user.click(screen.getByRole("button", { name: "Record" }));
    expect(onToggleRecord).toHaveBeenCalledOnce();

    rerender(<StudioHeader {...headerProps()} onToggleRecord={onToggleRecord} recording />);
    expect(
      screen.getByRole("button", { name: "Stop recording" }).getAttribute("aria-pressed")
    ).toBe("true");
  });
});

function upload(overrides: Partial<StudioUpload> = {}): StudioUpload {  return {
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

function song(overrides: Partial<WebMusicGeneration> = {}): WebMusicGeneration {
  return {
    id: "s1",
    title: "Song one",
    style: "downtempo",
    status: "success",
    created_at: new Date().toISOString(),
    clips: [],
    ...overrides,
  } as WebMusicGeneration;
}

function libraryProps(overrides: Partial<Parameters<typeof StudioLibrary>[0]> = {}) {
  return {
    width: 368,
    view: { kind: "root" } as LibraryView,
    query: "",
    onQuery: noop,
    songs: [] as WebMusicGeneration[] | null,
    workspaces: [] as WebMusicWorkspace[] | null,
    activeWorkspaceId: null,
    projects: [] as StudioProject[] | null,
    uploads: [] as StudioUpload[] | null,
    currentProjectId: null,
    likedKeys: [] as string[] | null,
    playingSongId: null as string | null,
    playingUploadId: null as string | null,
    error: null as string | null,
    onRetry: noop,
    projectSongIds: [] as string[],
    onOpenSong: noop,
    onClose: noop,
    onBack: noop,
    onOpenSongs: noop,
    onOpenUploads: noop,
    onOpenWorkspace: noop,
    onFilter: noop,
    onNewSong: noop,
    onNewWorkspace: async () => {},
    onUploadAudio: async () => {},
    onAddSong: noop,
    onTogglePlay: noop,
    onToggleLike: noop,
    onToggleUploadPlay: noop,
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
  it("opens on the level-1 tile chooser", async () => {
    const user = userEvent.setup();
    const onOpenSongs = vi.fn();
    const onOpenUploads = vi.fn();
    render(<StudioLibrary {...libraryProps({ onOpenSongs, onOpenUploads })} />);

    const tiles = screen.getByRole("group", { name: "Library filters" }).querySelectorAll("button");
    expect([...tiles].map((node) => node.textContent)).toEqual([
      "All Songs",
      "Liked",
      "Stems",
      "Uploads",
    ]);
    // The stems tile is visible but explained rather than silently dead (B-005).
    expect((screen.getByRole("button", { name: "Stems" }) as HTMLButtonElement).disabled).toBe(true);

    await user.click(screen.getByRole("button", { name: "All Songs" }));
    expect(onOpenSongs).toHaveBeenCalledWith("all");
    await user.click(screen.getByRole("button", { name: "Liked" }));
    expect(onOpenSongs).toHaveBeenLastCalledWith("liked");
    await user.click(screen.getByRole("button", { name: "Uploads" }));
    expect(onOpenUploads).toHaveBeenCalled();
  });

  it("groups songs under date headers on the All Songs level", () => {
    render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "All Songs", filter: "all" },
          songs: [song()],
        })}
      />
    );
    expect(screen.getByText("Today")).toBeTruthy();
    expect(screen.getByText("Song one")).toBeTruthy();
  });

  it("auditions and likes a song from its row actions", async () => {
    const user = userEvent.setup();
    const onTogglePlay = vi.fn();
    const onToggleLike = vi.fn();
    const target = song({
      id: "s1",
      title: "Row actions",
      clips: [{ variant: "ok", audio_url: "https://example.test/s1.mp3" }],
    });
    const { rerender } = render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "All Songs", filter: "all" },
          songs: [target],
          onTogglePlay,
          onToggleLike,
        })}
      />
    );
    await user.click(screen.getByRole("button", { name: "Play Row actions" }));
    expect(onTogglePlay).toHaveBeenCalledWith(target);
    await user.click(screen.getByRole("button", { name: "Like Row actions" }));
    expect(onToggleLike).toHaveBeenCalledWith(target, true);

    rerender(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "All Songs", filter: "all" },
          songs: [target],
          playingSongId: "s1",
          likedKeys: ["s1:ok"],
          onTogglePlay,
          onToggleLike,
        })}
      />
    );
    expect(screen.getByRole("button", { name: "Pause Row actions" })).toBeTruthy();
    const unlike = screen.getByRole("button", { name: "Unlike Row actions" });
    expect(unlike.getAttribute("aria-pressed")).toBe("true");
  });

  it("opens the detail rail from the keyboard", () => {
    const onOpenSong = vi.fn();
    render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "All Songs", filter: "all" },
          songs: [song()],
          onOpenSong,
        })}
      />
    );
    const row = screen.getByText("Song one").closest("li") as HTMLLIElement;
    expect(row.getAttribute("tabindex")).toBe("0");
    fireEvent.keyDown(row, { key: "Enter" });
    expect(onOpenSong).toHaveBeenCalledOnce();
    // Enter on a control inside the row must act on that control, not open the rail.
    fireEvent.keyDown(screen.getByRole("button", { name: "Add Song one to the project" }), { key: "Enter" });
    expect(onOpenSong).toHaveBeenCalledOnce();
  });

  it("makes song rows draggable with the song id on the data transfer", () => {
    render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "All Songs", filter: "all" },
          songs: [song()],
        })}
      />
    );
    const row = screen.getByText("Song one").closest("li") as HTMLLIElement;
    expect(row.getAttribute("draggable")).toBe("true");
    const data = new Map<string, string>();
    fireEvent.dragStart(row, {
      dataTransfer: {
        setData: (type: string, value: string) => data.set(type, value),
        effectAllowed: "none",
      },
    });
    expect(data.get(SONG_DRAG_TYPE)).toBe("s1");
  });

  it("collapses a date group from its heading", async () => {
    const user = userEvent.setup();
    render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "All Songs", filter: "all" },
          songs: [song()],
        })}
      />
    );
    expect(screen.getByText("Song one")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Today" }));
    expect(screen.queryByText("Song one")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Today" }));
    expect(screen.getByText("Song one")).toBeTruthy();
  });

  it("offers a back control from level 2 to the tile chooser", async () => {    const user = userEvent.setup();
    const onBack = vi.fn();
    render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "All Songs", filter: "all" },
          onBack,
        })}
      />
    );
    await user.click(screen.getByLabelText("Back to library"));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("filters the song list to liked clips and explains an empty result", () => {
    const likedSong = song({
      id: "s1",
      title: "Liked one",
      clips: [{ variant: "ok", audio_url: "https://example.test/s1.mp3" }],
    });
    const otherSong = song({
      id: "s2",
      title: "Unliked one",
      clips: [{ variant: "ok", audio_url: "https://example.test/s2.mp3" }],
    });
    const { rerender } = render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "Liked", filter: "liked" },
          songs: [likedSong, otherSong],
          likedKeys: ["s1:ok"],
        })}
      />
    );
    expect(screen.getByText("Liked one")).toBeTruthy();
    expect(screen.queryByText("Unliked one")).toBeNull();

    rerender(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "Liked", filter: "liked" },
          songs: [otherSong],
          likedKeys: [],
        })}
      />
    );
    expect(screen.getByText("No liked songs yet.")).toBeTruthy();
  });

  it("shows the captured song tag strip", () => {
    const tagged = song({
      id: "s1",
      title: "Tagged",
      model_label: "V6",
      clips: [
        {
          variant: "alt",
          label: "Cover",
          audio_url: "https://example.test/s1.mp3",
          duration_seconds: 127,
        },
      ],
    });
    render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "All Songs", filter: "all" },
          songs: [tagged],
        })}
      />
    );
    for (const tag of ["V6", "Cover", "2:07"]) {
      expect(screen.getByText(tag)).toBeTruthy();
    }
  });

  it("narrows to songs the open project already uses", () => {
    const used = song({
      id: "s1",
      title: "In the project",
      clips: [{ variant: "ok", audio_url: "https://example.test/s1.mp3" }],
    });
    const unused = song({
      id: "s2",
      title: "Not used",
      clips: [{ variant: "ok", audio_url: "https://example.test/s2.mp3" }],
    });
    const { rerender } = render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "In Project", filter: "project" },
          songs: [used, unused],
          projectSongIds: ["s1"],
        })}
      />
    );
    expect(screen.getByText("In the project")).toBeTruthy();
    expect(screen.queryByText("Not used")).toBeNull();

    rerender(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "In Project", filter: "project" },
          songs: [unused],
          projectSongIds: [],
        })}
      />
    );
    expect(screen.getByText("No songs from this project in the library yet.")).toBeTruthy();
  });

  it("changes the corpus from the level-2 filter toolbar", async () => {
    const user = userEvent.setup();
    const onFilter = vi.fn();
    const onOpenUploads = vi.fn();
    render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "All Songs", filter: "all" },
          onFilter,
          onOpenUploads,
        })}
      />
    );
    await user.click(screen.getByRole("button", { name: "In Project" }));
    expect(onFilter).toHaveBeenCalledWith("project");
    await user.click(screen.getByLabelText("Liked only"));
    expect(onFilter).toHaveBeenCalledWith("liked");
    expect((screen.getByRole("button", { name: "Stems" }) as HTMLButtonElement).disabled).toBe(true);
    await user.click(screen.getByRole("button", { name: "Uploads" }));
    expect(onOpenUploads).toHaveBeenCalledOnce();
  });

  it("offers + New and imports audio from the toolbar", async () => {
    const user = userEvent.setup();
    const onNewSong = vi.fn();
    const onUploadAudio = vi.fn(async () => {});
    const { rerender } = render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "All Songs", filter: "all" },
          onNewSong,
        })}
      />
    );
    await user.click(screen.getByRole("button", { name: /New/ }));
    expect(onNewSong).toHaveBeenCalledOnce();

    // Import lives on the Uploads list, like the reference's toolbar.
    rerender(
      <StudioLibrary {...libraryProps({ view: { kind: "uploads" }, onUploadAudio })} />
    );
    const file = new File(["hello"], "take.wav", { type: "audio/wav" });
    await user.upload(screen.getByLabelText("Choose audio file"), file);
    expect(onUploadAudio).toHaveBeenCalledWith(file);
  });

  it("surfaces a failed load with a retry", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <StudioLibrary
        {...libraryProps({
          error: "Some library data could not load.",
          onRetry,
        })}
      />
    );
    expect(screen.getByRole("alert").textContent).toContain("could not load");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("creates a workspace from the captured New workspace row", async () => {
    const user = userEvent.setup();
    const onNewWorkspace = vi.fn(async () => {});
    render(<StudioLibrary {...libraryProps({ onNewWorkspace })} />);
    await user.click(screen.getByRole("button", { name: /New workspace/ }));
    expect(onNewWorkspace).toHaveBeenCalledOnce();
  });

  it("shows each workspace with its song count and opens it", async () => {
    const user = userEvent.setup();
    const onOpenWorkspace = vi.fn();
    render(
      <StudioLibrary
        {...libraryProps({
          workspaces: [workspace(), workspace({ id: "w2", name: "Empty", song_count: 1 })],
          onOpenWorkspace,
        })}
      />
    );

    expect(screen.getByText("946 songs")).toBeTruthy();
    expect(screen.getByText("1 song")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: /^Open My Workspace/ }));
    expect(onOpenWorkspace).toHaveBeenCalledWith("w1");
  });

  it("marks the active workspace's Open button as current", () => {
    render(
      <StudioLibrary
        {...libraryProps({ workspaces: [workspace()], activeWorkspaceId: "w1" })}
      />
    );
    expect(
      screen
        .getByRole("button", { name: /^Open My Workspace/ })
        .closest(".se-lib-row")
        ?.getAttribute("aria-current")
    ).toBe("true");
  });

  it("shows and clears the workspace filter on the song level", async () => {
    const user = userEvent.setup();
    const onOpenWorkspace = vi.fn();
    render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "My Workspace", filter: "all" },
          workspaces: [workspace()],
          activeWorkspaceId: "w1",
          songs: [],
          onOpenWorkspace,
        })}
      />
    );
    expect(screen.getByText("Workspace filter")).toBeTruthy();
    expect(screen.getByText("No songs in this workspace yet.")).toBeTruthy();
    await user.click(screen.getByLabelText("Clear workspace filter"));
    expect(onOpenWorkspace).toHaveBeenCalledWith(null);
  });

  it("lists other Studio projects and excludes the one that is open", () => {
    const recent = new Date(Date.now() - 4 * 60_000).toISOString();
    const project = (id: string, title: string) =>
      ({ id, title, bpm: 120, time_signature: "4/4", updated_at: recent }) as StudioProject;
    render(
      <StudioLibrary
        {...libraryProps({
          projects: [project("p1", "Current"), project("p2", "Other")],
          currentProjectId: "p1",
        })}
      />
    );
    expect(screen.queryByText("Current")).toBeNull();
    expect(screen.getByText("Other")).toBeTruthy();
    expect(screen.getByText("4m ago")).toBeTruthy();
  });

  it("shows uploads with their length and adds one to the timeline", async () => {
    const user = userEvent.setup();
    const onAddUpload = vi.fn();
    render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "uploads" },
          uploads: [upload()],
          onAddUpload,
        })}
      />
    );
    expect(screen.getByText("take-1.wav")).toBeTruthy();
    expect(screen.getByText("2:07")).toBeTruthy();
    await user.click(screen.getByLabelText("Add take-1.wav"));
    expect(onAddUpload).toHaveBeenCalledWith(upload());
  });

  it("auditions an upload from its row", async () => {
    const user = userEvent.setup();
    const onToggleUploadPlay = vi.fn();
    render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "uploads" },
          uploads: [upload()],
          onToggleUploadPlay,
        })}
      />
    );
    await user.click(screen.getByRole("button", { name: "Play take-1.wav" }));
    expect(onToggleUploadPlay).toHaveBeenCalledWith(upload());
  });

  it("disables adding an upload that has no signed url", () => {
    render(
      <StudioLibrary
        {...libraryProps({ view: { kind: "uploads" }, uploads: [upload({ url: "" })] })}
      />
    );
    expect((screen.getByLabelText("Add take-1.wav") as HTMLButtonElement).disabled).toBe(true);
  });

  it("explains the empty uploads state", () => {
    render(<StudioLibrary {...libraryProps({ view: { kind: "uploads" }, uploads: [] })} />);
    expect(screen.getByText("No uploads yet. Audio you import appears here.")).toBeTruthy();
  });

  it("filters uploads by the shared search box", async () => {
    const user = userEvent.setup();
    const onQuery = vi.fn();
    render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "uploads" },
          uploads: [upload()],
          query: "zzz",
          onQuery,
        })}
      />
    );
    expect(screen.queryByText("take-1.wav")).toBeNull();
    await user.type(screen.getByLabelText("Search library"), "a");
    expect(onQuery).toHaveBeenCalled();
  });
});

describe("StudioSongDetail", () => {
  const detailSong = {
    id: "s1",
    title: "Sunlit One",
    style: "EDM, electronic dance music",
    lyrics: "[Intro]\nTonight",
    status: "success",
    created_at: "2026-11-03T10:00:00.000Z",
    clips: [{ variant: "ok", audio_url: "https://example.test/s1.mp3", duration_seconds: 184 }],
  } as unknown as WebMusicGeneration;

  function detailProps(overrides: Partial<Parameters<typeof StudioSongDetail>[0]> = {}) {
    return {
      width: 368,
      song: detailSong,
      liked: false,
      disliked: false,
      playing: false,
      onBack: noop,
      onClose: noop,
      onTogglePlay: noop,
      onToggleLike: noop,
      onToggleDislike: noop,
      ...overrides,
    };
  }

  it("shows the song's info, styles and lyrics", () => {
    render(<StudioSongDetail {...detailProps()} />);
    expect(screen.getAllByText("Sunlit One").length).toBeGreaterThan(0);
    expect(screen.getByText(/3:04/)).toBeTruthy();
    expect(screen.getByText("EDM, electronic dance music")).toBeTruthy();
    expect(screen.getByText(/Tonight/)).toBeTruthy();
    expect(screen.getByRole("img", { name: "Song waveform" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Info" }).getAttribute("aria-selected")).toBe("true");
  });

  it("likes, dislikes and plays from the header", async () => {
    const user = userEvent.setup();
    const onToggleLike = vi.fn();
    const onToggleDislike = vi.fn();
    const onTogglePlay = vi.fn();
    render(
      <StudioSongDetail
        {...detailProps({ onToggleLike, onToggleDislike, onTogglePlay })}
      />
    );
    await user.click(screen.getByRole("button", { name: "Like Sunlit One" }));
    expect(onToggleLike).toHaveBeenCalledWith(detailSong, true);
    await user.click(screen.getByRole("button", { name: "Dislike Sunlit One" }));
    expect(onToggleDislike).toHaveBeenCalledWith(detailSong, true);
    await user.click(screen.getByRole("button", { name: "Play Sunlit One" }));
    expect(onTogglePlay).toHaveBeenCalledWith(detailSong);
  });

  it("explains the blocked Stems tab instead of pretending", async () => {
    const user = userEvent.setup();
    render(<StudioSongDetail {...detailProps()} />);
    await user.click(screen.getByRole("tab", { name: "Stems" }));
    expect(screen.getByText(/B-005/)).toBeTruthy();
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
    expect(screen.getByRole("button", { name: /Add Track Effects/ })).toBeTruthy();
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
      onToggleArm: noop,
      onUpdateTrack: noop,
      onPreviewTrack: noop,
      onRenameStart: noop,
      onRenameChange: noop,
      onRenameCommit: noop,
      onRenameCancel: noop,
      onDuplicate: noop,
      onHide: noop,
      onDelete: noop,
      onAddTrack: noop,
      onAddUploadTrack: noop,
      onToggleHidden: noop,
      onShowAllHidden: noop,
      onToggleAllCollapsed: noop,
      masterVolume: 85,
      masterMuted: false,
      onMasterVolume: noop,
      onMasterCommit: noop,
      onToggleMasterMute: noop,
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

  it("arms one track at a time and exposes the state", async () => {
    const user = userEvent.setup();
    const onToggleArm = vi.fn();
    const { rerender } = render(<StudioTrackPanel {...panelProps({ onToggleArm })} />);
    const arm = screen.getByRole("button", { name: "Arm Track 1" });
    expect(arm.getAttribute("aria-pressed")).toBe("false");
    await user.click(arm);
    expect(onToggleArm).toHaveBeenCalledWith("t1");

    rerender(<StudioTrackPanel {...panelProps({ tracks: [track({ armed: true })] })} />);
    expect(
      screen.getByRole("button", { name: "Disarm Track 1" }).getAttribute("aria-pressed")
    ).toBe("true");
  });

  it("offers the captured add-track menu with its letters", async () => {
    const user = userEvent.setup();
    const onAddTrack = vi.fn();
    const onAddUploadTrack = vi.fn();
    render(<StudioTrackPanel {...panelProps({ onAddTrack, onAddUploadTrack })} />);

    await user.click(screen.getByRole("button", { name: /Add new track/ }));
    const items = screen.getAllByRole("menuitem");
    expect(items.map((node) => node.textContent?.replace(/\s+/g, " ").trim())).toEqual([
      "Audio A",
      "MIDI M",
      "Upload U",
    ]);
    // No MIDI tracks exist in this editor, so that row says so instead of pretending.
    expect((items[1] as HTMLButtonElement).disabled).toBe(true);
    expect(items[1].getAttribute("title")).toMatch(/MIDI/);

    await user.click(items[0]);
    expect(onAddTrack).toHaveBeenCalledOnce();
    expect(onAddUploadTrack).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /Add new track/ }));
    await user.click(screen.getAllByRole("menuitem")[2]);
    expect(onAddUploadTrack).toHaveBeenCalledOnce();
  });
});


