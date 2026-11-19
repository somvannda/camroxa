/**
 * Local project snapshots.
 *
 * The editor's nodes own three.js objects and per-frame caches, so the live
 * project cannot be persisted directly. This module captures the durable part:
 * each node's public fields, its animatable mapping, the composition layers,
 * analyzers, effects, automations and assets. Restoring recreates nodes through
 * `createNode` and applies the snapshot back onto them.
 *
 * The format is intentionally close to the live model (not the reference export
 * schema) so the round trip stays lossless while the reference importer remains
 * the path for captured Vizzy projects.
 */
import {
  createNode,
  type AnyNode,
  type NodeContext,
} from "./nodes";
import type { Analyzer } from "./analyzers";
import type { EffectInstance } from "./effects";
import type { Project, CompositionLayer, MediaAsset } from "./project";
import type { Automation, AutomationGroup, NodeKind } from "./types";
import { newId } from "./types";

export const PROJECT_FORMAT = "studio-project";
export const PROJECT_VERSION = 1;

interface NodeSnapshot {
  id: string;
  kind: NodeKind;
  name: string;
  start: number;
  duration: number;
  visible: boolean;
  /** Animatable numeric state (`objectMapping`). */
  mapping: [string, number][];
  /** Durable own properties; three.js objects and caches are excluded. */
  props: Record<string, unknown>;
}

export interface ProjectSnapshot {
  format: typeof PROJECT_FORMAT;
  version: number;
  savedAt: string;
  project: Pick<
    Project,
    | "id"
    | "name"
    | "width"
    | "height"
    | "fps"
    | "bpm"
    | "markers"
    | "duration"
    | "background"
    | "creatorNote"
    | "volume"
    | "muted"
    | "spectrumLayerColorMode"
    | "spectrumLayerColorShift"
    | "audioImpactMax"
    | "globals"
    | "audioSettings"
  >;
  nodes: NodeSnapshot[];
  layers: CompositionLayer[];
  automations: Automation[];
  automationGroups: AutomationGroup[];
  analyzers: Analyzer[];
  effects: EffectInstance[];
  assets: MediaAsset[];
}

/**
 * Fields that must never travel through JSON: the scene graph, renderer context,
 * GPU caches and other per-instance machinery. Anything else is accepted only
 * when it is a primitive or a small plain object/array.
 */
const INTERNAL_KEYS = new Set([
  "group",
  "ctx",
  "objectMapping",
  "gizmoBase",
  "prevMotion",
  "pathRenderer",
  "pathMesh",
  "layerPasses",
  "shaderPaints",
  "shaderErrors",
  "urlTexture",
  "urlPending",
  "mesh",
  "material",
  "geometry",
  "line",
  "helper",
  "particles",
  "textMesh",
  "font",
  "layout",
  "lineGeometry",
  "lineMaterial",
  "scratch",
  "scratchCtx",
  "layerTargets",
  "renderer",
]);

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== "object") return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

function serializable(value: unknown, depth = 0): boolean {
  if (value === null || value === undefined) return true;
  const type = typeof value;
  if (type === "string" || type === "number" || type === "boolean") return true;
  if (type !== "object") return false;
  if (depth > 3) return false;
  if (Array.isArray(value)) return value.every((entry) => serializable(entry, depth + 1));
  if (!isPlainObject(value)) return false;
  return Object.values(value).every((entry) => serializable(entry, depth + 1));
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function captureNode(node: AnyNode): NodeSnapshot {
  const props: Record<string, unknown> = {};
  for (const key of Object.keys(node)) {
    if (INTERNAL_KEYS.has(key)) continue;
    if (key === "id" || key === "kind" || key === "typeLabel") continue;
    const value = (node as unknown as Record<string, unknown>)[key];
    if (value === undefined) continue;
    if (typeof value === "number" && !Number.isFinite(value)) continue;
    if (!serializable(value)) continue;
    try {
      props[key] = cloneJson(value);
    } catch {
      /* a value JSON cannot represent; keep the node's default */
    }
  }
  return {
    id: node.id,
    kind: node.kind,
    name: node.name,
    start: node.start,
    duration: node.duration,
    visible: node.visible,
    mapping: [...node.objectMapping.entries()],
    props,
  };
}

/** Recreate one node and apply its durable state. */
export function restoreNode(snapshot: NodeSnapshot, ctx: NodeContext): AnyNode {
  const node = createNode(snapshot.kind, snapshot.name, ctx);
  // `id` is readonly to TypeScript but is a normal writable field at runtime;
  // keeping it preserves layer order and automation/analyzer bindings.
  (node as unknown as { id: string }).id = snapshot.id;
  node.name = snapshot.name;
  node.start = snapshot.start;
  node.duration = snapshot.duration;
  node.visible = snapshot.visible;

  for (const [key, value] of Object.entries(snapshot.props)) {
    if (["name", "start", "duration", "visible"].includes(key)) continue;
    try {
      (node as unknown as Record<string, unknown>)[key] = cloneJson(value);
    } catch {
      /* a readonly or accessor property; its default is already correct */
    }
  }

  node.objectMapping.clear();
  for (const [key, value] of snapshot.mapping) {
    node.objectMapping.set(key, Number(value));
  }

  // Some nodes build geometry from their fields in the constructor; rebuild it
  // for the restored values (Text/AnimatedText and similar).
  const rebuild = (node as unknown as { rebuildGeometry?: (force?: boolean) => void })
    .rebuildGeometry;
  if (typeof rebuild === "function") rebuild.call(node, true);
  try {
    node.sync(0);
  } catch {
    /* the first animation frame applies the rest */
  }
  return node;
}

export function serializeProject(project: Project): ProjectSnapshot {
  return {
    format: PROJECT_FORMAT,
    version: PROJECT_VERSION,
    savedAt: new Date().toISOString(),
    project: {
      id: project.id,
      name: project.name,
      width: project.width,
      height: project.height,
      fps: project.fps,
      bpm: project.bpm,
      markers: project.markers.map((marker) => ({ ...marker })),
      duration: project.duration,
      background: project.background,
      creatorNote: project.creatorNote,
      volume: project.volume,
      muted: project.muted,
      spectrumLayerColorMode: project.spectrumLayerColorMode,
      spectrumLayerColorShift: project.spectrumLayerColorShift,
      audioImpactMax: project.audioImpactMax,
      globals: [...project.globals],
      audioSettings: { ...project.audioSettings },
    },
    nodes: project.nodes.map(captureNode),
    layers: cloneJson(project.layers),
    automations: cloneJson(project.automations),
    automationGroups: cloneJson(project.automationGroups),
    analyzers: cloneJson(project.analyzers),
    effects: cloneJson(project.effects),
    assets: cloneJson(project.assets),
  };
}

export function isProjectSnapshot(value: unknown): value is ProjectSnapshot {
  if (!value || typeof value !== "object") return false;
  const snapshot = value as Partial<ProjectSnapshot>;
  return (
    snapshot.format === PROJECT_FORMAT &&
    Array.isArray(snapshot.nodes) &&
    Boolean(snapshot.project) &&
    Array.isArray(snapshot.layers)
  );
}

/**
 * Replace a live project with a snapshot. The caller owns renderer attach and
 * UI refresh; this function only rebuilds the data model.
 */
export function restoreProject(
  project: Project,
  snapshot: ProjectSnapshot,
  ctx: NodeContext,
): AnyNode[] {
  const nodes = snapshot.nodes.map((node) => restoreNode(node, ctx));
  Object.assign(project, snapshot.project);
  // Older saves have no `muted` flag.
  project.muted = snapshot.project.muted === true;
  if (!Number.isFinite(project.bpm) || project.bpm <= 0) project.bpm = 120;
  project.markers = Array.isArray(snapshot.project.markers)
    ? cloneJson(snapshot.project.markers)
    : [];
  // Normalise older saves that stored the pre-reference Off/Fixed/Cycle enum
  // and a 0..360 hue shift.
  if (project.spectrumLayerColorMode !== "lighten" && project.spectrumLayerColorMode !== "darken") {
    project.spectrumLayerColorMode = "lighten";
  }
  if (project.spectrumLayerColorShift > 1) {
    project.spectrumLayerColorShift = project.spectrumLayerColorShift / 360;
  }
  project.nodes = nodes;
  project.layers = cloneJson(snapshot.layers ?? []);
  project.automations = cloneJson(snapshot.automations ?? []);
  // Older saves have no ids or groups; give every automation a stable id.
  const automationIds = new Set<string>();
  for (const automation of project.automations) {
    if (!automation.id) automation.id = newId("automation");
    automationIds.add(automation.id);
  }
  const groups: AutomationGroup[] = cloneJson(snapshot.automationGroups ?? []).map((group) => ({
    id: group.id,
    name: group.name || "Untitled group",
    children: (Array.isArray(group.children) ? group.children : []).filter((id) =>
      automationIds.has(id),
    ),
  }));
  const groupById = new Map(groups.map((group) => [group.id, group]));
  for (const automation of project.automations) {
    // Drop memberships whose group did not survive.
    if (automation.groupId && !groupById.has(automation.groupId)) {
      automation.groupId = undefined;
    }
    // A row that points at a group must appear in its children (and vice versa).
    if (automation.groupId) {
      const group = groupById.get(automation.groupId);
      if (group && !group.children.includes(automation.id)) group.children.push(automation.id);
    }
  }
  for (const group of groups) {
    for (const id of group.children) {
      const automation = project.automations.find((entry) => entry.id === id);
      if (automation) automation.groupId = group.id;
    }
  }
  project.automationGroups = groups;
  project.analyzers = cloneJson(snapshot.analyzers ?? []);
  project.effects = cloneJson(snapshot.effects ?? []);
  project.assets = cloneJson(snapshot.assets ?? []);
  return nodes;
}
