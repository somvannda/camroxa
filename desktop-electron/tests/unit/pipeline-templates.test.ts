import { describe, expect, it } from "vitest";
import {
  applyPipelineBindings,
  buildPipelineTemplate,
  detectBindings,
  inferKind,
  summarizeTemplateContents,
  validatePipelineTemplate,
  type ProjectSnapshot,
} from "../../electron/services/pipeline-templates";

function snapshot(overrides: Partial<ProjectSnapshot> = {}): ProjectSnapshot {
  return {
    project: { name: "Night Drive", width: 1920, height: 1080, fps: 30 },
    nodes: [
      {
        id: "media-bg",
        kind: "media",
        name: "Background",
        visible: true,
        props: { imageUrl: "/creations/bg.webp", assetId: "asset-bg" },
      },
      {
        id: "logo-1",
        kind: "logo",
        name: "Logo",
        visible: true,
        props: { imageUrl: "/creations/logo.webp" },
      },
      {
        id: "text-title",
        kind: "skia-text",
        name: "Song Title",
        visible: true,
        props: { text: "Track name" },
      },
      {
        id: "text-artist",
        kind: "animated-text",
        name: "Artist",
        visible: true,
        props: { text: "Artist name" },
      },
      {
        id: "text-album",
        kind: "skia-text",
        name: "Album",
        visible: true,
        props: { text: "Album" },
      },
      {
        id: "spec-1",
        kind: "effects",
        name: "Spectrum",
        visible: true,
        props: { color: "#a855f7", layers: [] },
      },
    ],
    layers: [
      { id: "l1", name: "Background Layer", enabled: true, nodeIds: ["media-bg"] },
      { id: "l2", name: "Text", enabled: true, nodeIds: ["logo-1", "text-title", "text-artist", "text-album"] },
      { id: "l3", name: "Visualizers", enabled: true, nodeIds: ["spec-1"] },
    ],
    assets: [],
    ...overrides,
  };
}

describe("pipeline template bindings", () => {
  it("detects audio, background, logo, text and palette conservatively", () => {
    const bindings = detectBindings(snapshot());
    expect(bindings.audio).toEqual({ mode: "replace" });
    expect(bindings.background).toMatchObject({ nodeId: "media-bg", fit: "cover" });
    expect(bindings.logo).toMatchObject({ nodeId: "logo-1", circleMask: true });
    expect(bindings.title?.nodeId).toBe("text-title");
    expect(bindings.artist?.nodeId).toBe("text-artist");
    expect(bindings.album?.nodeId).toBe("text-album");
    expect(bindings.palette).toEqual({ nodeIds: ["spec-1"], mode: "accent" });
  });

  it("prefers the background layer over document order", () => {
    const value = snapshot({
      nodes: [
        { id: "top", kind: "media", name: "Overlay", visible: true, props: { imageUrl: "/a.webp" } },
        { id: "bottom", kind: "media", name: "Backdrop", visible: true, props: { imageUrl: "/b.webp" } },
      ],
      layers: [
        { name: "Overlay", enabled: true, nodeIds: ["top"] },
        { name: "Background", enabled: true, nodeIds: ["bottom"] },
      ],
    });
    expect(detectBindings(value).background?.nodeId).toBe("bottom");
  });

  it("never binds the same node twice", () => {
    const value = snapshot({
      nodes: [{ id: "only-text", kind: "skia-text", name: "Title", props: { text: "Title" } }],
      layers: [],
    });
    const bindings = detectBindings(value);
    expect(bindings.title?.nodeId).toBe("only-text");
    expect(bindings.artist).toBeUndefined();
    expect(bindings.album).toBeUndefined();
  });

  it("returns no bindings for an empty project", () => {
    expect(detectBindings({ project: { width: 1080, height: 1920 } })).toEqual({
      audio: { mode: "replace" },
    });
  });
});

describe("template contents summary", () => {
  it("counts the parts the save dialog lists", () => {
    const value = snapshot({
      nodes: [
        ...(snapshot().nodes as unknown[]),
        {
          id: "spec-2",
          kind: "effects",
          name: "Spectrum",
          visible: true,
          props: { layers: [{ id: "a" }, { id: "b" }, { id: "c" }] },
        },
        { id: "particles-1", kind: "particles", name: "Particles" },
        { id: "video-1", kind: "video", name: "Video" },
      ],
      analyzers: [{ id: "analyzer_default" }],
      automations: [{ id: "automation-1" }, { id: "automation-2" }],
      automationGroups: [{ id: "group-1" }],
      effects: [{ id: "effect:global_fade" }],
      assets: [{ id: "asset-bg" }],
    });
    expect(summarizeTemplateContents(value)).toEqual({
      layers: 3,
      objects: 9,
      effects: 1,
      spectrum: 2,
      spectrumLayers: 3,
      particles: 1,
      analyzers: 1,
      automations: 2,
      automationGroups: 1,
      media: 2,
      assets: 1,
    });
  });

  it("tolerates a project without optional arrays", () => {
    expect(summarizeTemplateContents({ project: {} })).toEqual({
      layers: 0,
      objects: 0,
      effects: 0,
      spectrum: 0,
      spectrumLayers: 0,
      particles: 0,
      analyzers: 0,
      automations: 0,
      automationGroups: 0,
      media: 0,
      assets: 0,
    });
  });
});

describe("pipeline template", () => {
  it("builds a valid template with output from the project", () => {
    const template = buildPipelineTemplate({
      name: "Night Drive",
      snapshot: snapshot(),
      createdAt: "2026-11-19T00:00:00.000Z",
    });
    expect(template).toMatchObject({
      schemaVersion: 1,
      project: "template.json",
      kind: "long",
      output: { width: 1920, height: 1080, fps: 30 },
      duration: { mode: "audio" },
    });
    expect(validatePipelineTemplate(template)).toEqual(template);
  });

  it("infers reel from a portrait project", () => {
    const template = buildPipelineTemplate({
      name: "Reel",
      snapshot: { project: { width: 1080, height: 1920, fps: 30 } },
    });
    expect(template.kind).toBe("reel");
    expect(inferKind(1920, 1080)).toBe("long");
  });

  it("rejects a duplicate binding", () => {
    expect(() =>
      buildPipelineTemplate({
        name: "Dup",
        snapshot: snapshot(),
        bindings: {
          audio: { mode: "replace" },
          background: { nodeId: "same" },
          logo: { nodeId: "same" },
        },
      }),
    ).toThrow(/only hold one binding/i);
  });

  it("rejects an invalid schema", () => {
    expect(() => validatePipelineTemplate({ schemaVersion: 1 })).toThrow();
    expect(() =>
      validatePipelineTemplate({
        ...buildPipelineTemplate({ name: "A", snapshot: snapshot() }),
        output: { width: 0, height: 1080, fps: 30 },
      }),
    ).toThrow();
  });
});

describe("pipeline export settings", () => {
  it("captures the Export rail into output and export", () => {
    const pipeline = buildPipelineTemplate({
      name: "Reel",
      snapshot: snapshot(),
      kind: "reel",
      exportSettings: {
        width: 1080,
        height: 1920,
        fps: 60,
        format: "mp4",
        codec: "h264",
        engine: "wasm",
        bitrate: 50,
        crf: 18,
        preset: "slow",
        profile: "main",
        audioBitrate: 256,
        start: 0,
        end: 12,
      },
    });
    expect(pipeline.output).toEqual({ width: 1080, height: 1920, fps: 60 });
    expect(pipeline.export).toMatchObject({
      width: 1080,
      height: 1920,
      fps: 60,
      bitrate: 50,
      crf: 18,
      preset: "slow",
      profile: "main",
      audioBitrate: 256,
    });
  });
});

describe("pipeline bindings applied to a run", () => {
  function json(): string {
    return JSON.stringify({ format: "studio-project", version: 1, ...snapshot() });
  }

  it("rebinds text, background, logo and palette without touching other state", () => {
    const pipeline = buildPipelineTemplate({ name: "Night Drive", snapshot: snapshot() });
    const output = applyPipelineBindings(json(), pipeline, {
      title: "Run title",
      artist: "Run artist",
      album: "Run album",
      backgroundUrl: "camxora-media://local/bg",
      logoUrl: "camxora-media://local/logo",
      palette: ["#ff0000"],
    });
    const parsed = JSON.parse(output);
    const props = Object.fromEntries(parsed.nodes.map((node: { id: string; props: unknown }) => [node.id, node.props]));
    expect(props["text-title"].textValue).toBe("Run title");
    expect(props["text-artist"].textValue).toBe("Run artist");
    expect(props["text-album"].textValue).toBe("Run album");
    expect(props["media-bg"].imageUrl).toBe("camxora-media://local/bg");
    expect(props["media-bg"].assetId).toBeNull();
    expect(props["logo-1"].imageUrl).toBe("camxora-media://local/logo");
    expect(props["logo-1"].assetId).toBeNull();
    expect(props["spec-1"].color).toBe("#ff0000");
    expect(parsed.project.name).toBe("Night Drive");
  });

  it("clips text when the binding asks for it", () => {
    const pipeline = buildPipelineTemplate({
      name: "Clip",
      snapshot: snapshot(),
      bindings: {
        audio: { mode: "replace" },
        title: { nodeId: "text-title", maxChars: 5, overflow: "clip" },
      },
    });
    const parsed = JSON.parse(
      applyPipelineBindings(json(), pipeline, { title: "123456789" }),
    );
    const title = parsed.nodes.find((node: { id: string }) => node.id === "text-title");
    expect(title.props.textValue).toBe("12345");
  });

  it("fails loudly when a bound node is missing", () => {
    const pipeline = buildPipelineTemplate({ name: "Broken", snapshot: snapshot() });
    const value = JSON.parse(json());
    value.nodes = value.nodes.filter((node: { id: string }) => node.id !== "text-title");
    expect(() => applyPipelineBindings(JSON.stringify(value), pipeline, { title: "x" })).toThrow(
      /missing its title node/i,
    );
  });
});
