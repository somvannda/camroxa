import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type ColorMode = "solid" | "gradient";
export type GradientDirection = "left-to-right" | "top-to-bottom" | "radial" | "circular" | "diagonal";
export type AnchorPreset = "top-left" | "top-center" | "top-right" | "center" | "bottom-center" | "bottom-left" | "bottom-right";

export interface PositionConfig {
  anchor: AnchorPreset;
  x: number; // offset X
  y: number; // offset Y
}

export interface ColorConfig {
  mode: ColorMode;
  solidColor: string; // hex
  gradientColors: string[]; // hex array
  gradientDirection: GradientDirection;
}

export interface AudioSettings {
  sensitivity: number;
  smoothing: number;
  bounce: number;
  minHeight: number;
  peakHold: number;
}

export interface BackgroundConfig {
  brightness: number;
  reactivity: number;
}

export interface LogoConfig {
  size: number;
  scale: number;
  opacity: number;
  circleMask: boolean;
  reactivity: number;
  position: PositionConfig;
}

export interface ParticlesConfig {
  enabled: boolean;
  maxCount: number;
  spawnRate: number;
  lifetimeSec: number;
  speed: number;
  reactivity: number;
  size: number;
  opacity: number;
  color: string;
}

export interface SpectrumLayer {
  id: string;
  name: string;
  curved: boolean; // True = 180 degree half circle, False = straight line
  mirrored: boolean; // True = mirrors to 360 circle (if curved) or symmetrical line (if straight)
  fillCircle: boolean;
  fillColor: string;
  thickness: number; // The height/length of the spectrum spikes
  barWidth: number; // The width/stroke size of the bars/lines
  gravity: "bottom" | "top" | "left" | "right"; // Where the bass frequencies anchor
  color: ColorConfig;
  glow: number;
  blur: number;
  rotation: number;
  opacity: number;
}

export interface SpectrumTemplate {
  templateName: string;
  style: string; // The selected 1 of 10 styles for bars
  layers: SpectrumLayer[];
  globalColor: ColorConfig; // Global fallback if layers don't override
  position: PositionConfig; // Spectrum Position
  renderBaseHeight: number;
  audioSettings: AudioSettings;
  backgroundSettings: BackgroundConfig;
  logoSettings: LogoConfig;
  particlesSettings: ParticlesConfig;
  effects: any; // reserved for phase 3
  // Transient state (not saved in DB, just for preview)
  previewBackground?: string;
  previewLogo?: string;
}

const defaultTemplate: SpectrumTemplate = {
  templateName: "New Template",
  style: "classic-vertical",
  layers: [
    {
      id: "base-layer",
      name: "Base Ring",
      curved: true,
      mirrored: true,
      fillCircle: false,
      fillColor: "#000000",
      thickness: 150,
      barWidth: 4,
      gravity: "bottom",
      color: { mode: "solid", solidColor: "#ffffff", gradientColors: ["#ff00ff", "#00ffff"], gradientDirection: "left-to-right" },
      glow: 0,
      blur: 0,
      rotation: 0,
      opacity: 1,
    },
  ],
  globalColor: {
    mode: "solid",
    solidColor: "#ffffff",
    gradientColors: ["#ff00ff", "#00ffff"],
    gradientDirection: "left-to-right",
  },
  position: {
    anchor: "center",
    x: 0,
    y: 0,
  },
  renderBaseHeight: 450,
  audioSettings: {
    sensitivity: 1.0,
    smoothing: 0.8,
    bounce: 0,
    minHeight: 0.1,
    peakHold: 0,
  },
  backgroundSettings: {
    brightness: 1.0,
    reactivity: 0.0,
  },
  logoSettings: {
    size: 192,
    scale: 1.0,
    opacity: 1.0,
    circleMask: true,
    reactivity: 0.5,
    position: {
      anchor: "center",
      x: 0,
      y: 0,
    },
  },
  particlesSettings: {
    enabled: true,
    maxCount: 3000,
    spawnRate: 40,
    lifetimeSec: 1.6,
    speed: 120,
    reactivity: 1.5,
    size: 2,
    opacity: 0.35,
    color: "#ffffff",
  },
  effects: {},
};

function normalizeSpectrumTemplate(input: any): SpectrumTemplate {
  const base: SpectrumTemplate = {
    ...defaultTemplate,
    ...(input && typeof input === "object" ? input : null),
    position: {
      ...defaultTemplate.position,
      ...(input && typeof input === "object" ? input.position : null),
    },
    audioSettings: {
      ...defaultTemplate.audioSettings,
      ...(input && typeof input === "object" ? input.audioSettings : null),
    },
    backgroundSettings: {
      ...defaultTemplate.backgroundSettings,
      ...(input && typeof input === "object" ? input.backgroundSettings : null),
    },
    logoSettings: {
      ...defaultTemplate.logoSettings,
      ...(input && typeof input === "object" ? input.logoSettings : null),
      position: {
        ...defaultTemplate.logoSettings.position,
        ...(input && typeof input === "object" ? input.logoSettings?.position : null),
      },
    },
    particlesSettings: {
      ...defaultTemplate.particlesSettings,
      ...(input && typeof input === "object" ? input.particlesSettings : null),
    },
    globalColor: {
      ...defaultTemplate.globalColor,
      ...(input && typeof input === "object" ? input.globalColor : null),
    },
  };

  if (typeof (base as any).renderBaseHeight !== "number") (base as any).renderBaseHeight = 450;

  const ps: any = base.particlesSettings as any;
  if (typeof ps.maxCount !== "number" && typeof ps.count === "number") ps.maxCount = ps.count;
  if (typeof ps.spawnRate !== "number" && typeof ps.spawn_rate === "number") ps.spawnRate = ps.spawn_rate;
  if (typeof ps.lifetimeSec !== "number" && typeof ps.lifetime_sec === "number") ps.lifetimeSec = ps.lifetime_sec;
  if (typeof ps.opacity !== "number" && typeof ps.alpha === "number") ps.opacity = ps.alpha;
  ps.speed = Math.max(1, Math.min(15, Number(ps.speed ?? 1)));
  ps.reactivity = Math.max(0.1, Math.min(0.5, Number(ps.reactivity ?? 0.1)));
  ps.opacity = Math.max(0, Math.min(1, Number(ps.opacity ?? 0.35)));
  ps.maxCount = Math.max(200, Math.min(2000, Number(ps.maxCount ?? 200)));
  ps.spawnRate = Math.max(100, Math.min(1000, Number(ps.spawnRate ?? 100)));

  const ls: any = base.logoSettings as any;
  if (typeof ls.size !== "number") ls.size = 130;
  ls.size = Math.max(1, Math.min(130, Number(ls.size)));

  if (base.style === "symmetrical") base.style = "symmetrical-bars";

  const rawLayers: any[] = Array.isArray((input && typeof input === "object" ? input.layers : null)) ? input.layers : [];
  const fallbackLayer = defaultTemplate.layers[0];

  base.layers = (rawLayers.length ? rawLayers : [fallbackLayer]).map((l, i) => {
    const layerIn: any = l && typeof l === "object" ? l : {};

    const oldType = input && typeof input === "object" ? input.type : undefined;
    const wantsCircle = oldType === "circle-spectrum";
    const wantsBars = oldType === "graphic-bar";

    const curved =
      typeof layerIn.curved === "boolean"
        ? layerIn.curved
        : wantsBars
          ? false
          : wantsCircle
            ? true
            : typeof layerIn.radius === "number"
              ? true
              : fallbackLayer.curved;

    const mirrored = typeof layerIn.mirrored === "boolean" ? layerIn.mirrored : fallbackLayer.mirrored;

    const barWidth =
      typeof layerIn.barWidth === "number"
        ? layerIn.barWidth
        : typeof layerIn.thickness === "number" && typeof layerIn.strength === "number"
          ? layerIn.thickness
          : fallbackLayer.barWidth;

    const fillCircle = typeof layerIn.fillCircle === "boolean" ? layerIn.fillCircle : fallbackLayer.fillCircle;
    const fillColor = typeof layerIn.fillColor === "string" ? layerIn.fillColor : fallbackLayer.fillColor;

    const oldStrength = typeof layerIn.strength === "number" ? layerIn.strength : undefined;
    const oldLayerReact = typeof layerIn.reactivity === "number" ? layerIn.reactivity : 1;
    const thickness =
      typeof layerIn.thickness === "number" && typeof layerIn.strength !== "number"
        ? layerIn.thickness
        : typeof oldStrength === "number"
          ? oldStrength * oldLayerReact
          : fallbackLayer.thickness;
    const thicknessClamped = Math.max(1, Math.min(30, Number(thickness)));

    const gravity: SpectrumLayer["gravity"] =
      layerIn.gravity === "top" || layerIn.gravity === "left" || layerIn.gravity === "right" || layerIn.gravity === "bottom"
        ? layerIn.gravity
        : fallbackLayer.gravity;

    const color: ColorConfig = {
      ...fallbackLayer.color,
      ...(layerIn.color && typeof layerIn.color === "object" ? layerIn.color : null),
    };

    return {
      ...fallbackLayer,
      id: typeof layerIn.id === "string" ? layerIn.id : `layer-${i + 1}`,
      name: typeof layerIn.name === "string" ? layerIn.name : `Layer ${i + 1}`,
      curved,
      mirrored,
      fillCircle,
      fillColor,
      thickness: thicknessClamped,
      barWidth,
      gravity,
      color,
      glow: typeof layerIn.glow === "number" ? layerIn.glow : fallbackLayer.glow,
      blur: typeof layerIn.blur === "number" ? layerIn.blur : fallbackLayer.blur,
      rotation: typeof layerIn.rotation === "number" ? layerIn.rotation : fallbackLayer.rotation,
      opacity: typeof layerIn.opacity === "number" ? layerIn.opacity : fallbackLayer.opacity,
    };
  });

  return base;
}

interface SpectrumTemplateStore {
  template: SpectrumTemplate;
  updateTemplate: (updates: Partial<SpectrumTemplate>) => void;
  setTemplate: (template: SpectrumTemplate) => void;
  updateLayer: (id: string, updates: Partial<SpectrumLayer>) => void;
  addLayer: (layer: SpectrumLayer) => void;
  removeLayer: (id: string) => void;
}

export const useSpectrumTemplateStore = create<SpectrumTemplateStore>()(
  persist(
    (set) => ({
      template: normalizeSpectrumTemplate(defaultTemplate),

      updateTemplate: (updates) =>
        set((state) => ({
          template: normalizeSpectrumTemplate({ ...state.template, ...updates }),
        })),

      setTemplate: (template) => set({ template: normalizeSpectrumTemplate(template) }),

      updateLayer: (id, updates) =>
        set((state) => ({
          template: normalizeSpectrumTemplate({
            ...state.template,
            layers: state.template.layers.map((l) => (l.id === id ? { ...l, ...updates } : l)),
          }),
        })),

      addLayer: (layer) =>
        set((state) => ({
          template: normalizeSpectrumTemplate({
            ...state.template,
            layers: [...state.template.layers, layer],
          }),
        })),

      removeLayer: (id) =>
        set((state) => ({
          template: normalizeSpectrumTemplate({
            ...state.template,
            layers: state.template.layers.filter((l) => l.id !== id),
          }),
        })),
    }),
    {
      name: "mg_spectrum_template_store",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ template: state.template }),
      merge: (persisted, current) => {
        const saved = (persisted as Partial<SpectrumTemplateStore> | undefined)?.template;
        return {
          ...current,
          template: normalizeSpectrumTemplate(saved ?? current.template),
        };
      },
    },
  ),
);
