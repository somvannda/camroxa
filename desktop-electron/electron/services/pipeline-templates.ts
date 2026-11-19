import { z } from "zod";

/**
 * Pipeline template contract (see docs/electron-desktop/vizzy/PIPELINE-TEMPLATE-CONTRACT.md).
 *
 * A saved video template is a `template.json` (the exact editor snapshot the user
 * previewed) plus a `pipeline.json` that names the nodes the pipeline rebinds for
 * each run. Detection is conservative: it only picks nodes whose kind and name
 * clearly match, and the save dialog lets the user override every field.
 */

export type PipelineKind = "long" | "reel";

export interface PipelineBinding {
  nodeId: string;
  /** Extra binding options understood by the pipeline. */
  [option: string]: string | number | boolean | undefined;
}

export interface PipelineBindings {
  /** Audio is implicit: the pipeline loads the run track into the project. */
  audio: { mode: "replace" };
  background?: PipelineBinding & { fit?: "cover" | "contain" | "stretch" };
  logo?: PipelineBinding & { circleMask?: boolean };
  title?: PipelineBinding & { maxChars?: number; overflow?: "clip" | "shrink" | "wrap" };
  artist?: PipelineBinding & { maxChars?: number; overflow?: "clip" | "shrink" | "wrap" };
  album?: PipelineBinding & { maxChars?: number; overflow?: "clip" | "shrink" | "wrap" };
  palette?: { nodeIds: string[]; mode: "accent" };
}

export interface PipelineTemplate {
  schemaVersion: 1;
  name: string;
  kind: PipelineKind;
  project: "template.json";
  output: { width: number; height: number; fps: number };
  duration: { mode: "audio" } | { mode: "fixed"; seconds: number };
  bindings: PipelineBindings;
  requirements: { renderer: "vizzy"; minVersion: string; features: string[] };
  createdAt: string;
}

interface SnapshotNode {
  id?: unknown;
  kind?: unknown;
  name?: unknown;
  visible?: unknown;
  props?: Record<string, unknown>;
}

interface SnapshotLayer {
  id?: unknown;
  name?: unknown;
  enabled?: unknown;
  nodeIds?: unknown;
}

export interface ProjectSnapshot {
  project?: Record<string, unknown>;
  nodes?: unknown;
  layers?: unknown;
  assets?: unknown;
}

const TEXT_KINDS = new Set(["skia-text", "animated-text", "lyrics"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function textOf(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function nodesOf(snapshot: ProjectSnapshot): SnapshotNode[] {
  return Array.isArray(snapshot.nodes)
    ? (snapshot.nodes.filter((node) => isRecord(node)) as SnapshotNode[])
    : [];
}

function layersOf(snapshot: ProjectSnapshot): SnapshotLayer[] {
  return Array.isArray(snapshot.layers)
    ? (snapshot.layers.filter((layer) => isRecord(layer)) as SnapshotLayer[])
    : [];
}

function nodeName(node: SnapshotNode): string {
  const propsName = isRecord(node.props) ? textOf(node.props.name) : "";
  return textOf(node.name) || propsName;
}

function nodeLabel(node: SnapshotNode): string {
  const props = isRecord(node.props) ? node.props : {};
  return [
    nodeName(node),
    textOf(props.textValue),
    textOf(props.text),
    textOf(props.imageUrl),
    textOf(props.assetId),
  ]
    .filter(Boolean)
    .join(" ");
}

function hasVisualAsset(node: SnapshotNode): boolean {
  const props = isRecord(node.props) ? node.props : {};
  return Boolean(textOf(props.imageUrl) || textOf(props.assetId) || textOf(props.textureUrlPending));
}

/** Bottom-most enabled layer, then its first media node. */
function backgroundCandidate(snapshot: ProjectSnapshot): SnapshotNode | null {
  const nodes = nodesOf(snapshot);
  const layers = layersOf(snapshot).filter((layer) => layer.enabled !== false);
  const ordered: SnapshotNode[] = [];
  for (const layer of layers) {
    if (!Array.isArray(layer.nodeIds)) continue;
    for (const id of layer.nodeIds) {
      const node = nodes.find((candidate) => candidate.id === id);
      if (node) ordered.push(node);
    }
  }
  const pool = ordered.length ? ordered : nodes;
  const media = pool.filter(
    (node) => textOf(node.kind) === "media" && node.visible !== false && hasVisualAsset(node),
  );
  if (!media.length) return null;
  const backgroundLayer = layers.find((layer) => /background|backdrop|bg/i.test(textOf(layer.name)));
  if (backgroundLayer && Array.isArray(backgroundLayer.nodeIds)) {
    const ids = backgroundLayer.nodeIds;
    const inBackground = media.find((node) => ids.includes(node.id));
    if (inBackground) return inBackground;
  }
  return media[0] ?? null;
}

function firstMatch<T>(items: T[], test: (item: T) => boolean): T | null {
  return items.find(test) ?? null;
}

function textCandidate(
  nodes: SnapshotNode[],
  used: Set<string>,
  pattern: RegExp,
): SnapshotNode | null {
  const texts = nodes.filter(
    (node) => TEXT_KINDS.has(textOf(node.kind)) && node.visible !== false && !used.has(String(node.id)),
  );
  return firstMatch(texts, (node) => pattern.test(nodeLabel(node)));
}

export function detectBindings(snapshot: ProjectSnapshot): PipelineBindings {
  const nodes = nodesOf(snapshot);
  const used = new Set<string>();
  const bindings: PipelineBindings = { audio: { mode: "replace" } };

  const background = backgroundCandidate(snapshot);
  if (background && background.id) {
    bindings.background = { nodeId: String(background.id), fit: "cover" };
    used.add(String(background.id));
  }

  const logo =
    firstMatch(
      nodes,
      (node) =>
        !used.has(String(node.id)) &&
        node.visible !== false &&
        (textOf(node.kind) === "logo" || /logo|cover art|coverart/i.test(nodeLabel(node))),
    ) ?? null;
  if (logo?.id) {
    bindings.logo = { nodeId: String(logo.id), circleMask: true };
    used.add(String(logo.id));
  }

  const title =
    textCandidate(nodes, used, /title|song|track|heading|artist name/i) ??
    textCandidate(nodes, used, /.*/) ??
    null;
  if (title?.id) {
    bindings.title = { nodeId: String(title.id), maxChars: 80, overflow: "shrink" };
    used.add(String(title.id));
  }

  const artist = textCandidate(nodes, used, /artist|author|performer|singer/i);
  if (artist?.id) {
    bindings.artist = { nodeId: String(artist.id), maxChars: 60, overflow: "clip" };
    used.add(String(artist.id));
  }

  const album = textCandidate(nodes, used, /album|release|record/i);
  if (album?.id) {
    bindings.album = { nodeId: String(album.id), maxChars: 60, overflow: "clip" };
    used.add(String(album.id));
  }

  const palette = nodes.filter((node) => {
    if (textOf(node.kind) !== "effects") return false;
    const props = isRecord(node.props) ? node.props : {};
    return Boolean(textOf(props.color) || textOf(props.fillStyle) || Array.isArray(props.layers));
  });
  if (palette.length) {
    bindings.palette = { nodeIds: palette.slice(0, 3).map((node) => String(node.id)), mode: "accent" };
  }

  return bindings;
}

const bindingSchema = z
  .object({ nodeId: z.string().min(1).max(200) })
  .catchall(z.union([z.string(), z.number(), z.boolean()]).optional());

const pipelineSchema = z.object({
  schemaVersion: z.literal(1),
  name: z.string().min(1).max(200),
  kind: z.enum(["long", "reel"]),
  project: z.literal("template.json"),
  output: z.object({
    width: z.number().int().min(16).max(7680),
    height: z.number().int().min(16).max(7680),
    fps: z.number().int().min(1).max(240),
  }),
  duration: z.union([
    z.object({ mode: z.literal("audio") }),
    z.object({ mode: z.literal("fixed"), seconds: z.number().positive().max(86_400) }),
  ]),
  bindings: z.object({
    audio: z.object({ mode: z.literal("replace") }),
    background: bindingSchema.optional(),
    logo: bindingSchema.optional(),
    title: bindingSchema.optional(),
    artist: bindingSchema.optional(),
    album: bindingSchema.optional(),
    palette: z
      .object({
        nodeIds: z.array(z.string().min(1).max(200)).min(1).max(16),
        mode: z.literal("accent"),
      })
      .optional(),
  }),
  requirements: z.object({
    renderer: z.literal("vizzy"),
    minVersion: z.string().min(1),
    features: z.array(z.string().min(1).max(80)).max(32),
  }),
  createdAt: z.string().min(1),
});

export function validatePipelineTemplate(value: unknown): PipelineTemplate {
  return pipelineSchema.parse(value) as PipelineTemplate;
}

export function inferKind(width: number, height: number): PipelineKind {
  return width >= height ? "long" : "reel";
}

export interface PipelineRunInputs {
  title?: string;
  artist?: string;
  album?: string;
  /** Displayable URL for the run background (usually a `camxora-media://` URL). */
  backgroundUrl?: string;
  /** Displayable URL for the run logo. */
  logoUrl?: string;
  /** Accent colours applied to palette-bound nodes. */
  palette?: string[];
}

function clipText(value: string, binding: PipelineBinding): string {
  const max = typeof binding.maxChars === "number" ? binding.maxChars : 0;
  if (!max || value.length <= max) return value;
  return binding.overflow === "clip" ? value.slice(0, max) : value;
}

/**
 * Apply a run's inputs to the saved project. The result is still the exact saved
 * project; only the bound properties change. Throws when a bound node is missing
 * so the pipeline reports the exact template problem instead of rendering a
 * silently unbound video.
 */
export function applyPipelineBindings(
  snapshotJson: string,
  pipeline: PipelineTemplate,
  inputs: PipelineRunInputs,
): string {
  const parsed = JSON.parse(snapshotJson) as Record<string, unknown>;
  const nodes = Array.isArray(parsed.nodes) ? parsed.nodes : [];
  const byId = new Map<string, Record<string, unknown>>();
  for (const node of nodes) {
    if (isRecord(node) && typeof node.id === "string") byId.set(node.id, node);
  }

  const propsFor = (nodeId: string, field: string): Record<string, unknown> => {
    const node = byId.get(nodeId);
    if (!node) throw new Error(`The template is missing its ${field} node (${nodeId}).`);
    if (!isRecord(node.props)) node.props = {};
    return node.props as Record<string, unknown>;
  };

  const setText = (
    binding: PipelineBinding | undefined,
    field: string,
    value: string | undefined,
  ) => {
    if (!binding || value === undefined) return;
    propsFor(binding.nodeId, field).textValue = clipText(value, binding);
  };

  const { bindings } = pipeline;
  setText(bindings.title, "title", inputs.title);
  setText(bindings.artist, "artist", inputs.artist);
  setText(bindings.album, "album", inputs.album);

  if (bindings.background && inputs.backgroundUrl) {
    propsFor(bindings.background.nodeId, "background").imageUrl = inputs.backgroundUrl;
  }
  if (bindings.logo && inputs.logoUrl) {
    propsFor(bindings.logo.nodeId, "logo").imageUrl = inputs.logoUrl;
  }

  if (bindings.palette && inputs.palette?.length) {
    for (const [index, nodeId] of bindings.palette.nodeIds.entries()) {
      const props = propsFor(nodeId, "palette");
      if ("color" in props) props.color = inputs.palette[index % inputs.palette.length];
    }
  }

  return JSON.stringify(parsed, null, 2) + "\n";
}

export function buildPipelineTemplate(input: {
  name: string;
  snapshot: ProjectSnapshot;
  bindings?: PipelineBindings;
  kind?: PipelineKind;
  createdAt?: string;
}): PipelineTemplate {
  const project = isRecord(input.snapshot.project) ? input.snapshot.project : {};
  const width = Number(project.width ?? 1920);
  const height = Number(project.height ?? 1080);
  const fps = Number(project.fps ?? 30);
  const name = input.name.trim() || textOf(project.name) || "Untitled template";
  const template: PipelineTemplate = {
    schemaVersion: 1,
    name,
    kind: input.kind ?? inferKind(width, height),
    project: "template.json",
    output: {
      width: Math.round(Number.isFinite(width) ? width : 1920),
      height: Math.round(Number.isFinite(height) ? height : 1080),
      fps: Math.round(Number.isFinite(fps) ? fps : 30),
    },
    duration: { mode: "audio" },
    bindings: input.bindings ?? detectBindings(input.snapshot),
    requirements: { renderer: "vizzy", minVersion: "2.0.0", features: ["audio-analysis"] },
    createdAt: input.createdAt ?? new Date().toISOString(),
  };

  const nodeIds = [
    template.bindings.background?.nodeId,
    template.bindings.logo?.nodeId,
    template.bindings.title?.nodeId,
    template.bindings.artist?.nodeId,
    template.bindings.album?.nodeId,
  ].filter((id): id is string => Boolean(id));
  if (new Set(nodeIds).size !== nodeIds.length) {
    throw new Error("A node can only hold one binding.");
  }

  return validatePipelineTemplate(template);
}
