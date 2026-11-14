import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
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
import { StudioMasterDock } from "@/components/studio/StudioMasterDock";
import { LIMITER_DEFAULTS } from "@/lib/studio-master-bus";
import { DEFAULT_STUDIO_SETTINGS } from "@/lib/studio-settings";
import type { StudioTrack } from "@/lib/studio-tracks";
import type { StudioProject, StudioStem, StudioUpload } from "@/lib/studio-api";
import { addStudioProjectComment, listStudioProjectComments } from "@/lib/studio-api";
import type { WebMusicGeneration } from "@/lib/library-api";
import type { WebMusicWorkspace } from "@/lib/web-music-api";


vi.mock("@/lib/studio-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/studio-api")>("@/lib/studio-api");
  return {
    ...actual,
    listStudioProjectComments: vi.fn(),
    addStudioProjectComment: vi.fn(),
  };
});

const noop = () => {};

// Without this each render stacks onto the previous one and queries match duplicates.
afterEach(cleanup);

function headerProps() {
  return {
    title: "Demo",
    projectId: "p1" as string | null,
    settings: { ...DEFAULT_STUDIO_SETTINGS },
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
    const range = screen.getByText("Selected Time Range") as HTMLButtonElement;
    expect(range.disabled).toBe(true);
    expect(screen.getByText("Full Song")).toBeTruthy();
    expect(screen.getByText("Multitrack")).toBeTruthy();
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
    stems: [] as StudioStem[] | null,
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
    onOpenStems: noop,
    onOpenUploads: noop,
    onOpenWorkspace: noop,
    onFilter: noop,
    onNewSong: noop,
    onNewWorkspace: async () => {},
    onUploadAudio: async () => {},
    onAddSong: noop,
    onTogglePlay: noop,
    onAudition: noop,
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
    const onOpenStems = vi.fn();
    const onOpenUploads = vi.fn();
    render(<StudioLibrary {...libraryProps({ onOpenSongs, onOpenStems, onOpenUploads })} />);

    const tiles = screen.getByRole("group", { name: "Library filters" }).querySelectorAll("button");
    expect([...tiles].map((node) => node.textContent)).toEqual([
      "All Songs",
      "Liked",
      "Stems",
      "Uploads",
    ]);
    // Completed stem sets exist now, so the tile opens the list (G12).
    expect((screen.getByRole("button", { name: "Stems" }) as HTMLButtonElement).disabled).toBe(false);

    await user.click(screen.getByRole("button", { name: "Stems" }));
    expect(onOpenStems).toHaveBeenCalledOnce();

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
    expect(screen.getByText("No songs found.")).toBeTruthy();
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
    expect(screen.getByText("No songs found.")).toBeTruthy();
  });

  it("changes the corpus from the level-2 filter toolbar", async () => {
    const user = userEvent.setup();
    const onFilter = vi.fn();
    const onOpenStems = vi.fn();
    const onOpenUploads = vi.fn();
    render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "All Songs", filter: "all" },
          onFilter,
          onOpenStems,
          onOpenUploads,
        })}
      />
    );
    await user.click(screen.getByRole("button", { name: "In Project" }));
    expect(onFilter).toHaveBeenCalledWith("project");
    await user.click(screen.getByLabelText("Liked only"));
    expect(onFilter).toHaveBeenCalledWith("liked");
    await user.click(screen.getByRole("button", { name: "Stems" }));
    expect(onOpenStems).toHaveBeenCalledOnce();
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
    expect(screen.getByText("No songs found.")).toBeTruthy();
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
    expect(screen.getAllByText(/3:04/).length).toBeGreaterThan(0);
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
    await user.click(screen.getAllByRole("button", { name: "Play Sunlit One" })[0]);
    expect(onTogglePlay).toHaveBeenCalledWith(detailSong);
  });

  it("remixes from the header when the song has a style", async () => {
    const user = userEvent.setup();
    const onRemix = vi.fn();
    render(<StudioSongDetail {...detailProps({ onRemix })} />);
    await user.click(screen.getByRole("button", { name: "Remix" }));
    expect(onRemix).toHaveBeenCalledWith(detailSong);
  });

  it("disables Remix while a remix is running", () => {
    render(<StudioSongDetail {...detailProps({ onRemix: noop, remixing: true })} />);
    expect((screen.getByRole("button", { name: /Remix/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("loads and posts project comments", async () => {
    const user = userEvent.setup();
    vi.mocked(listStudioProjectComments).mockResolvedValue({
      items: [
        {
          id: "c1",
          parent_id: null,
          author_name: "Sam",
          body: "Old note",
          created_at: "2026-11-10T00:00:00.000Z",
        },
      ],
    });
    vi.mocked(addStudioProjectComment).mockResolvedValue({
      id: "c2",
      parent_id: null,
      author_name: "me",
      body: "New note",
      created_at: "2026-11-10T00:01:00.000Z",
    });
    render(
      <StudioSongDetail {...detailProps({ projectId: "p1", commentAuthor: "me" })} />
    );
    expect(await screen.findByText("Old note")).toBeTruthy();
    await user.type(screen.getByLabelText("Comment"), "New note");
    await user.click(screen.getByLabelText("Send comment"));
    expect(await screen.findByText("New note")).toBeTruthy();
    expect(addStudioProjectComment).toHaveBeenCalledWith("p1", {
      authorName: "me",
      body: "New note",
      parentId: null,
    });
  });

  it("nests replies and posts with the parent id", async () => {
    const user = userEvent.setup();
    vi.mocked(listStudioProjectComments).mockResolvedValue({
      items: [
        {
          id: "c1",
          parent_id: null,
          author_name: "Sam",
          body: "Root note",
          created_at: "2026-11-10T00:00:00.000Z",
        },
        {
          id: "c2",
          parent_id: "c1",
          author_name: "Ana",
          body: "Nested reply",
          created_at: "2026-11-10T00:01:00.000Z",
        },
      ],
    });
    vi.mocked(addStudioProjectComment).mockResolvedValue({
      id: "c3",
      parent_id: "c1",
      author_name: "me",
      body: "Threaded note",
      created_at: "2026-11-10T00:02:00.000Z",
    });
    render(<StudioSongDetail {...detailProps({ projectId: "p1", commentAuthor: "me" })} />);

    expect(await screen.findByText("Root note")).toBeTruthy();
    expect(screen.getByText("Nested reply")).toBeTruthy();
    expect(document.querySelector(".se-song-comment-replies")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Reply to Sam" }));
    expect(screen.getByText("Replying to Sam")).toBeTruthy();
    await user.type(screen.getByLabelText("Comment"), "Threaded note");
    await user.click(screen.getByLabelText("Send comment"));
    expect(addStudioProjectComment).toHaveBeenCalledWith("p1", {
      authorName: "me",
      body: "Threaded note",
      parentId: "c1",
    });
  });

  it("opens the More menu and fires the real actions", async () => {
    const user = userEvent.setup();
    const onAddToProject = vi.fn();
    const onDownloadWav = vi.fn();
    const onTrash = vi.fn();
    render(
      <StudioSongDetail
        {...detailProps({ onAddToProject, onDownloadWav, onTrash })}
      />
    );
    await user.click(screen.getByRole("button", { name: "More song options" }));
    const menu = screen.getByRole("menu", { name: "Song options" });
    expect(within(menu).getAllByRole("menuitem")).toHaveLength(3);

    await user.click(within(menu).getByRole("menuitem", { name: /Download WAV/ }));
    expect(onDownloadWav).toHaveBeenCalledWith(detailSong);

    await user.click(screen.getByRole("button", { name: "More song options" }));
    await user.click(screen.getByRole("menuitem", { name: /Move to trash/ }));
    expect(onTrash).toHaveBeenCalledWith(detailSong);
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
      collapsed: false,
      onToggleCollapsed: noop,
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
      onAddMidiTrack: noop,
      onAddUploadTrack: noop,
      onToggleHidden: noop,
      onShowAllHidden: noop,
      onUnmuteAllHidden: noop,
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
      "Color",
      "Collapse controls",
      "Bounce track",
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
    // MIDI tracks are real now: the row creates one and opens the editor.
    expect((items[1] as HTMLButtonElement).disabled).toBe(false);

    await user.click(items[0]);
    expect(onAddTrack).toHaveBeenCalledOnce();
    expect(onAddUploadTrack).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /Add new track/ }));
    await user.click(screen.getAllByRole("menuitem")[2]);
    expect(onAddUploadTrack).toHaveBeenCalledOnce();
  });
});

describe("StudioMasterDock", () => {
  it("applies a master preset to the limiter and its links", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <StudioMasterDock
        chain={[
          {
            id: "limiter",
            type: "limiter",
            enabled: true,
            params: { ...LIMITER_DEFAULTS },
          },
        ]}
        onChange={onChange}
      />
    );

    await user.click(screen.getByRole("button", { name: "Default" }));
    await user.click(screen.getByRole("menuitem", { name: "Warm" }));

    const next = onChange.mock.calls[0][0] as Array<{
      type?: string;
      params?: Record<string, number>;
      amount?: number;
    }>;
    expect(next.find((entry) => entry.type === "limiter")?.params).toMatchObject({
      preGain: 1.5,
      attack: 15,
      release: 140,
    });
    expect(next.find((entry) => entry.type === "eq")?.amount).toBe(0.6);
    expect(next.find((entry) => entry.type === "compressor")?.amount).toBe(0.25);
  });
});

describe("StudioLibrary audition keys", () => {
  const first = song({
    id: "s1",
    title: "First",
    clips: [{ variant: "ok", audio_url: "https://example.test/s1.mp3" }],
  });
  const second = song({
    id: "s2",
    title: "Second",
    clips: [{ variant: "ok", audio_url: "https://example.test/s2.mp3" }],
  });

  it("auditions the next and previous row and replays the current one", () => {
    const onAudition = vi.fn();
    const { container } = render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "All Songs", filter: "all" },
          songs: [first, second],
          onAudition,
        })}
      />
    );
    const list = container.querySelector(".se-lib-list") as HTMLElement;

    fireEvent.keyDown(list, { key: "ArrowDown" });
    expect(onAudition).toHaveBeenLastCalledWith(first);
    fireEvent.keyDown(list, { key: "ArrowDown" });
    expect(onAudition).toHaveBeenLastCalledWith(second);
    // The cursor stops at the last row instead of wrapping past it.
    fireEvent.keyDown(list, { key: "ArrowDown" });
    expect(onAudition).toHaveBeenLastCalledWith(second);
    fireEvent.keyDown(list, { key: "ArrowUp" });
    expect(onAudition).toHaveBeenLastCalledWith(first);
    fireEvent.keyDown(list, { key: "ArrowRight" });
    expect(onAudition).toHaveBeenLastCalledWith(first);
    expect(onAudition).toHaveBeenCalledTimes(5);
  });

  it("ignores the keys outside the song list and inside inputs", () => {
    const onAudition = vi.fn();
    const { container } = render(
      <StudioLibrary
        {...libraryProps({
          view: { kind: "songs", title: "All Songs", filter: "all" },
          songs: [first],
          onAudition,
        })}
      />
    );
    const list = container.querySelector(".se-lib-list") as HTMLElement;
    const search = container.querySelector("input") as HTMLInputElement;
    fireEvent.keyDown(search, { key: "ArrowDown" });
    expect(onAudition).not.toHaveBeenCalled();
    fireEvent.keyDown(list, { key: "Enter" });
    expect(onAudition).not.toHaveBeenCalled();
  });
});


