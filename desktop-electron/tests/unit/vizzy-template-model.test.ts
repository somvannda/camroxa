import { describe, expect, it } from "vitest";
import {
  bindingsFromSelection,
  emptySelection,
  inferKind,
  kindAspectError,
  selectionFromDetected,
  validateBindingSelection,
  type BindingOptions,
} from "../../electron/shared/pipeline";
import {
  collectBindingOptions,
  detectBindings,
  summarizeTemplateContents,
  type ProjectSnapshot,
} from "../../electron/services/pipeline-templates";
import { renderFileNameForTemplate } from "../../electron/vizzy-host/renders";
import {
  draftFromInfo,
  templateDraftErrors,
  type TemplateDraftState,
} from "../../src/features/vizzy/vizzy-template-model";

function snapshot(overrides: Partial<ProjectSnapshot> = {}): ProjectSnapshot {
  return {
    project: { name: "Night Drive", width: 1920, height: 1080, fps: 30 },
    nodes: [
      {
        id: "media-bg",
        kind: "media",
        name: "Backdrop",
        visible: true,
        props: { imageUrl: "/creations/bg.webp" },
      },
      {
        id: "logo-1",
        kind: "logo",
        name: "Cover art",
        visible: true,
        props: { imageUrl: "/creations/logo.webp" },
      },
      { id: "text-title", kind: "skia-text", name: "Song Title", props: { text: "Track" } },
      { id: "text-artist", kind: "animated-text", name: "Artist", props: { text: "Artist" } },
      { id: "text-album", kind: "skia-text", name: "Album", props: { text: "Album" } },
      { id: "spec-1", kind: "effects", name: "Spectrum", props: { color: "#a855f7" } },
      { id: "noise-1", kind: "noise", name: "Solid", props: { fillStyle: "#111111" } },
      { id: "hidden-text", kind: "skia-text", name: "Hidden", visible: false, props: {} },
    ],
    layers: [
      { id: "l1", name: "Background Layer", enabled: true, nodeIds: ["media-bg"] },
      { id: "l2", name: "Text", enabled: true, nodeIds: ["text-title", "text-artist", "text-album"] },
    ],
    ...overrides,
  };
}

function optionsFor(value: ProjectSnapshot = snapshot()): BindingOptions {
  return collectBindingOptions(value);
}

describe("binding options", () => {
  it("offers only compatible nodes for each binding", () => {
    const options = optionsFor();
    expect(options.background.map((entry) => entry.nodeId)).toEqual(["media-bg"]);
    expect(options.logo.map((entry) => entry.nodeId)).toEqual(["media-bg", "logo-1"]);
    expect(options.title.map((entry) => entry.nodeId)).toEqual([
      "text-title",
      "text-artist",
      "text-album",
    ]);
    // Hidden nodes are never offered.
    expect(options.artist.some((entry) => entry.nodeId === "hidden-text")).toBe(false);
    // Palette accepts both `color` and `fillStyle` nodes.
    expect(options.palette.map((entry) => entry.nodeId)).toEqual(["spec-1", "noise-1"]);
    expect(options.palette[0]?.detail).toContain("effects");
  });

  it("pre-fills the dialog from detection without inventing nodes", () => {
    const options = optionsFor();
    const detected = selectionFromDetected(detectBindings(snapshot()), options);
    expect(detected).toEqual({
      background: "media-bg",
      logo: "logo-1",
      title: "text-title",
      artist: "text-artist",
      album: "text-album",
      palette: "spec-1",
    });

    // A stale detector result that is not an option is dropped.
    const stale = selectionFromDetected(
      { background: { nodeId: "gone" }, title: { nodeId: "media-bg" } },
      options,
    );
    expect(stale.background).toBe("");
    expect(stale.title).toBe("");
  });
});

describe("binding validation", () => {
  it("blocks a duplicate node across two bindings", () => {
    const options = optionsFor();
    const errors = validateBindingSelection(options, {
      ...emptySelection(),
      background: "media-bg",
      logo: "media-bg",
    });
    expect(errors.logo).toMatch(/already bound to Background/i);
    expect(errors.background).toBeUndefined();
  });

  it("blocks an incompatible node kind and an unknown id", () => {
    const options = optionsFor();
    const wrongKind = validateBindingSelection(options, {
      ...emptySelection(),
      title: "media-bg",
    });
    expect(wrongKind.title).toMatch(/not a compatible title/i);

    const unknown = validateBindingSelection(options, {
      ...emptySelection(),
      palette: "does-not-exist",
    });
    expect(unknown.palette).toMatch(/not a compatible palette/i);
  });

  it("accepts a fully optional empty selection (audio is implicit)", () => {
    expect(validateBindingSelection(optionsFor(), emptySelection())).toEqual({});
  });
});

describe("template draft", () => {
  const info = {
    name: "Night Drive",
    width: 1920,
    height: 1080,
    fps: 30,
    kind: "long" as const,
    detected: selectionFromDetected(detectBindings(snapshot()), optionsFor()),
    options: optionsFor(),
    contents: summarizeTemplateContents(snapshot()),
    existing: [],
  };

  it("infers long/reel from the output aspect", () => {
    expect(inferKind(1920, 1080)).toBe("long");
    expect(inferKind(1080, 1920)).toBe("reel");
    expect(inferKind(1080, 1080)).toBe("long");
    expect(kindAspectError("reel", 1920, 1080)).toMatch(/landscape/i);
    expect(kindAspectError("long", 1080, 1920)).toMatch(/portrait/i);
    expect(kindAspectError("reel", 1080, 1920)).toBeNull();
  });

  it("seeds the dialog from the host draft", () => {
    const draft = draftFromInfo(info);
    expect(draft.name).toBe("Night Drive");
    expect(draft.kind).toBe("long");
    expect(draft.selection).toEqual(info.detected);
    // Export settings are opt-in, never inherited from the previous preview.
    expect(draft.includeExportSettings).toBe(false);
    // Copying must not alias the IPC payload.
    draft.selection.title = "";
    expect(info.detected.title).toBe("text-title");
  });

  it("reports the first error and the field errors", () => {
    const duplicate: TemplateDraftState = {
      name: "Night Drive",
      kind: "long",
      selection: { ...info.detected, logo: "text-title" },
      includeExportSettings: false,
    };
    const errors = templateDraftErrors(info, duplicate, "Night Drive");
    expect(errors.fields.logo).toMatch(/not a compatible logo/i);
    expect(errors.summary).toMatch(/not a compatible logo/i);

    const mismatchedKind = templateDraftErrors(info, { ...draftFromInfo(info), kind: "reel" }, "X");
    expect(mismatchedKind.kind).toMatch(/landscape/i);
    expect(mismatchedKind.summary).toMatch(/landscape/i);

    expect(templateDraftErrors(info, draftFromInfo(info), "   ").summary).toMatch(/name/i);
  });

  it("converts a selection into the pipeline bindings written on disk", () => {
    const bindings = bindingsFromSelection(info.detected);
    expect(bindings).toEqual({
      audio: { mode: "replace" },
      background: { nodeId: "media-bg", fit: "cover" },
      logo: { nodeId: "logo-1", circleMask: true },
      title: { nodeId: "text-title", maxChars: 80, overflow: "shrink" },
      artist: { nodeId: "text-artist", maxChars: 60, overflow: "clip" },
      album: { nodeId: "text-album", maxChars: 60, overflow: "clip" },
      palette: { nodeIds: ["spec-1"], mode: "accent" },
    });
  });
});

describe("template render file names", () => {
  it("uses the template slug and a timestamp, never a path", () => {
    const date = new Date(2026, 10, 19, 14, 25, 30);
    expect(renderFileNameForTemplate("night-drive", "mp4", date)).toBe(
      "night-drive-20261119-142530.mp4",
    );
    expect(renderFileNameForTemplate("../escape", "mp4", date)).toBe(
      "escape-20261119-142530.mp4",
    );
    expect(renderFileNameForTemplate("", "mp4", date)).toBe("untitled-project-20261119-142530.mp4");
  });
});
