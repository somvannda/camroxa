import * as React from "react";
import { TopToolbar } from "@/components/dashboard/TopToolbar";
import { AppSidebar, type AppSection } from "@/components/dashboard/AppSidebar";
import { LeftSidebar } from "@/components/dashboard/LeftSidebar";
import { HistoryPanel, type HistoryRow } from "@/components/dashboard/HistoryPanel";
import { ImagePanel, type ImagePanelItem } from "@/components/dashboard/ImagePanel";
import { VideoPanel } from "@/components/dashboard/VideoPanel";
import { VideoRenderPanel } from "@/components/dashboard/VideoRenderPanel";
import { SpectrumEditor } from "@/components/spectrum/SpectrumEditor";
import { VideoParticlesPanel } from "@/components/dashboard/VideoParticlesPanel";
import { VideoEffectsPanel } from "@/components/dashboard/VideoEffectsPanel";
import { MusicControlsBar } from "@/components/dashboard/MusicControlsBar";
import { SettingsPanel } from "@/components/dashboard/SettingsDialog";
import { AppFooter } from "@/components/dashboard/AppFooter";
import { useAppStore } from "@/store/useAppStore";
import { jobClient } from "@/services/jobClient";
import type { ImageGenMeta, JobEvent, VideoExportSettings, VideoMergeEvent, VideoMergeItemStatus, VideoRenderEvent, VideoTemplateListItem } from "../../shared/app-types";
import { Tabs, TabsContent } from "@/components/ui/Tabs";
import { SavedTextsTab } from "@/components/dashboard/manage/SavedTextsTab";
import { PromptTemplatesTab } from "@/components/dashboard/manage/PromptTemplatesTab";
import { TextStylesTab } from "@/components/dashboard/manage/TextStylesTab";
import { ImageSamplesTab } from "@/components/dashboard/manage/ImageSamplesTab";
import { CarModelsTab } from "@/components/dashboard/manage/CarModelsTab";
import { PhrasePoolsTab } from "@/components/dashboard/manage/PhrasePoolsTab";

function pickRandom<T>(items: T[]) {
  if (!items.length) return null;
  return items[Math.floor(Math.random() * items.length)] ?? null;
}

function pickActiveItem<T extends { id: string }>(items: T[], activeIds: string[]) {
  if (!activeIds.length) return null;
  const pool = items.filter((x) => activeIds.includes(x.id));
  return pickRandom(pool);
}

function pickFromPoolItem<T extends { id: string }>(items: T[], enabled: string[]) {
  const pool = enabled.length ? items.filter((x) => enabled.includes(x.id)) : items;
  return pickRandom(pool);
}

function normalizeMatchKey(key: string) {
  return String(key || "").trim();
}

function renderTemplate(content: string, ctx: Record<string, string>) {
  return String(content || "").replace(/\{([a-zA-Z0-9_]+)\}/g, (_m, key) => ctx[String(key)] ?? "");
}

function applyMasterCarToken(prompt: string, carLabel: string) {
  return String(prompt || "").replace(/\[car model\/type\]/gi, carLabel);
}

function formatImageMeta(meta?: ImageGenMeta) {
  if (!meta) return "";
  const parts = [`Model: ${meta.model}`, `Attempts: ${meta.attempts}`, `Size: ${meta.size}`];
  if (meta.cost) parts.push(`Est: $${meta.cost.minUsd.toFixed(3)}-$${meta.cost.maxUsd.toFixed(3)}`);
  return parts.join(" · ");
}

function clamp(n: number, min: number, max: number) {
  if (!Number.isFinite(n)) return min;
  return Math.max(min, Math.min(max, n));
}

function clampPrompt(prompt: string, maxLen: number) {
  const s = String(prompt || "");
  if (s.length <= maxLen) return s;
  return `${s.slice(0, Math.max(0, maxLen - 1)).trimEnd()}…`;
}

function buildCappedPrompt(input: { base: string; negative: string; maxLen: number }) {
  const neg = input.negative.trim();
  const base = input.base.trim();
  const suffix = neg ? `\n\n${neg}` : "";
  const maxBaseLen = Math.max(0, input.maxLen - suffix.length);
  const cappedBase = clampPrompt(base, maxBaseLen);
  const out = `${cappedBase}${suffix}`;
  return out.length <= input.maxLen ? out : clampPrompt(out, input.maxLen);
}

export default function Home() {
  const {
    hydrated,
    data,
    currentDescription,
    currentStructure,
    currentSongId,
    hydrate,
    setCurrentDescription,
    setCurrentStructure,
    setCurrentSongId,
    setRunning,
    footerText,
    footerProgress,
    setFooterStatus,
    updateSettings,
    deleteText,
    addSong,
    updateSongDraft,
    updateSong,
    addHistory,
  } = useAppStore();

  const activeGenerateJobs = React.useRef(new Set<string>());
  const [generating, setGenerating] = React.useState(false);
  const cancelRequested = React.useRef(false);
  const generateJobIds = React.useRef(new Set<string>());
  const autoImageQueue = React.useRef(Promise.resolve());
  const autoImageRequestedBatches = React.useRef(new Set<string>());
  const bgTemplateCycleIndexRef = React.useRef(0);
  const aiCallsRef = React.useRef(0);

  type BatchRun = {
    batchId: string;
    expected: number;
    attempted: number;
    completed: number;
    failed: number;
    cancelled: number;
    failures: Array<{ jobId: string; message: string }>;
    blockedReason?: string;
    maxAttempts: number;
  };

  const batchRunRef = React.useRef<BatchRun | null>(null);

  function describeStatus(event: JobEvent) {
    if (event.action !== "generate") return { text: event.message, progress: typeof event.progress === "number" ? event.progress : null };

    const p = typeof event.progress === "number" ? event.progress : null;
    if (event.status === "queued") return { text: "Queued song generation", progress: p ?? 5 };
    if (event.status === "cancelled") return { text: "Stopping…", progress: p };
    if (event.status === "failed") return { text: "This song failed to generate", progress: p };
    if (event.status === "completed") return { text: "Song saved", progress: 100 };

    const msg = String(event.message || "").toLowerCase();
    if (msg.includes("draft")) return { text: "Writing lyrics and melody idea…", progress: p ?? 30 };
    if (msg.includes("saving")) return { text: "Saving song…", progress: p ?? 90 };
    return { text: "Generating…", progress: p ?? 35 };
  }

  const lastSettings = React.useRef(data.settings);
  React.useEffect(() => {
    if (lastSettings.current === data.settings) return;
    lastSettings.current = data.settings;
    setFooterStatus("Saved settings", 100);
    const t = setTimeout(() => setFooterStatus("Ready", null), 1200);
    return () => clearTimeout(t);
  }, [data.settings, setFooterStatus]);

  React.useEffect(() => {
    bgTemplateCycleIndexRef.current = Math.max(0, Math.floor(data.settings.backgroundTemplateCycleIndex ?? 0));
  }, [data.settings.backgroundTemplateCycleIndex]);

  const [mainTab, setMainTab] = React.useState<AppSection>("music");
  const [musicTab, setMusicTab] = React.useState<"composer" | "descriptions" | "structures" | "suno" | "pools" | "generation">(
    "composer",
  );
  const [imageTab, setImageTab] = React.useState<"preview" | "templates" | "text" | "refs" | "cars" | "settings">("preview");
  const [videoTab, setVideoTab] = React.useState<"render" | "spectrum" | "particles" | "effects">("render");
  const [mergerTab, setMergerTab] = React.useState<"merge">("merge");
  const [settingsTab, setSettingsTab] = React.useState<"api" | "profiles" | "paths" | "database">("api");
  const [lastBatchOnly, setLastBatchOnly] = React.useState(false);
  const todayLocal = React.useMemo(() => {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  }, []);

  const [runFromDate, setRunFromDate] = React.useState(todayLocal);
  const [runToDate, setRunToDate] = React.useState(todayLocal);

  const [fromDate, setFromDate] = React.useState(todayLocal);
  const [toDate, setToDate] = React.useState(todayLocal);

  type ImageSide = "ok" | "alt";

  const [bgGenerating, setBgGenerating] = React.useState(false);
  const [thumbnailing, setThumbnailing] = React.useState(false);
  const [manualGenerateBoth, setManualGenerateBoth] = React.useState(false);
  const [manualIncludeThumbnail, setManualIncludeThumbnail] = React.useState(false);
  const [backgroundItems, setBackgroundItems] = React.useState<ImagePanelItem[]>([]);
  const [thumbnailItems, setThumbnailItems] = React.useState<ImagePanelItem[]>([]);
  const [selectedBackgroundPath, setSelectedBackgroundPath] = React.useState<string | null>(null);
  const [selectedThumbnailPath, setSelectedThumbnailPath] = React.useState<string | null>(null);
  const [backgroundLogs, setBackgroundLogs] = React.useState<string[]>([]);
  const [thumbnailLogs, setThumbnailLogs] = React.useState<string[]>([]);
  const [thumbnailSourcePath, setThumbnailSourcePath] = React.useState<string | null>(null);
  const [sunoRunDirs, setSunoRunDirs] = React.useState<{ okDir: string | null; altDir: string | null; message?: string }>(() => ({
    okDir: null,
    altDir: null,
  }));
  const [sunoStatus, setSunoStatus] = React.useState("");
  const [videoMergeState, setVideoMergeState] = React.useState<{
    runId: string | null;
    running: boolean;
    total: number;
    rows: Record<string, { directory: string; status: VideoMergeItemStatus; message: string; outputPath?: string }>;
  }>(() => ({ runId: null, running: false, total: 0, rows: {} }));

  const [videoRenderMp3Path, setVideoRenderMp3Path] = React.useState("");
  const [videoRenderMode, setVideoRenderMode] = React.useState<"manual" | "auto">("manual");
  const [videoRenderState, setVideoRenderState] = React.useState<{
    runId: string | null;
    running: boolean;
    message: string;
    progress: number | null;
    outputPath: string | null;
  }>(() => ({ runId: null, running: false, message: "Ready", progress: null, outputPath: null }));

  const [videoTemplates, setVideoTemplates] = React.useState<VideoTemplateListItem[]>([]);
  const [videoTemplatesBlocked, setVideoTemplatesBlocked] = React.useState<string | null>(null);
  const [videoTemplateDeletingPath, setVideoTemplateDeletingPath] = React.useState("");
  const [videoSpectrumPreviewUrl, setVideoSpectrumPreviewUrl] = React.useState<string | null>(null);
  const [videoSpectrumPreviewBusy, setVideoSpectrumPreviewBusy] = React.useState(false);
  const [videoSpectrumAutoPreview, setVideoSpectrumAutoPreview] = React.useState(true);
  const [videoSpectrumPreviewAutoLogoSource, setVideoSpectrumPreviewAutoLogoSource] = React.useState<"ok" | "alt">("ok");
  const [videoSpectrumPreviewMp3Path, setVideoSpectrumPreviewMp3Path] = React.useState("");
  const [videoSpectrumPreviewMp3Url, setVideoSpectrumPreviewMp3Url] = React.useState("");
  const [videoSpectrumPreviewBackgroundPath, setVideoSpectrumPreviewBackgroundPath] = React.useState("");
  const [videoSpectrumPreviewLogoPath, setVideoSpectrumPreviewLogoPath] = React.useState("");
  const [videoSpectrumBgBrightness, setVideoSpectrumBgBrightness] = React.useState(1);
  const [videoSpectrumBgReactBass, setVideoSpectrumBgReactBass] = React.useState(0);
  const [videoSpectrumLogoCircleMask, setVideoSpectrumLogoCircleMask] = React.useState(true);
  const [videoSpectrumLogoOpacity, setVideoSpectrumLogoOpacity] = React.useState(1);
  const [videoSpectrumLogoScale, setVideoSpectrumLogoScale] = React.useState(1);
  const [videoSpectrumLogoReactBass, setVideoSpectrumLogoReactBass] = React.useState(0.5);
  const [videoSpectrumExtraLayers, setVideoSpectrumExtraLayers] = React.useState<
    Array<{
      id: string;
      color: string;
      opacity: number;
      thickness: number;
      radiusOffset: number;
      strengthMul: number;
      gradientEnabled: boolean;
      gradientColor: string;
      blendMode: "normal" | "additive";
    }>
  >(() => []);
  const [spectrumDraft, setSpectrumDraft] = React.useState<{
    spectrumType: "circle" | "bars" | "custom";
    renderMode: "stroke" | "fill";
    drawType: "line" | "curve";
    mirror: boolean;
    clipCircle: boolean;
    fillCircle: boolean;
    connect: boolean;
    dotSize: number;
    reactGain: number;
    reactBass: number;
    feather: number;
    downsample: number;
    antiAlias: boolean;
    shadowEnabled: boolean;
    shadowScale: number;
    shadowAlpha: number;
    shadowOffsetX: number;
    shadowOffsetY: number;
    textureX: number;
    textureY: number;
    textureScale: number;
    textureScaleMul: number;
    textureDisableAspect: boolean;
    radius: number;
    strength: number;
    thickness: number;
    pointCount: number;
    smoothing: number;
    color: string;
    gradientEnabled: boolean;
    gradientColor: string;
    glowColor: string;
    glowLayers: number;
    glowSpread: number;
    glowOpacity: number;
    rotationDeg: number;
  }>(() => ({
    spectrumType: "circle",
    renderMode: "stroke",
    drawType: "curve",
    mirror: false,
    clipCircle: false,
    fillCircle: false,
    connect: true,
    dotSize: 0,
    reactGain: 1,
    reactBass: 2.5,
    feather: 0,
    downsample: 1,
    antiAlias: true,
    shadowEnabled: false,
    shadowScale: 8,
    shadowAlpha: 0.5,
    shadowOffsetX: 0,
    shadowOffsetY: 0,
    textureX: 0,
    textureY: 0,
    textureScale: 1,
    textureScaleMul: 1,
    textureDisableAspect: false,
    radius: 240,
    strength: 120,
    thickness: 4,
    pointCount: 256,
    smoothing: 0.8,
    color: "#ffffff",
    gradientEnabled: false,
    gradientColor: "#00ffff",
    glowColor: "#ffffff",
    glowLayers: 3,
    glowSpread: 6,
    glowOpacity: 0.35,
    rotationDeg: 0,
  }));
  const [particlesDraft, setParticlesDraft] = React.useState<{
    enabled: boolean;
    maxCount: number;
    spawnRate: number;
    reactBass: number;
    lifetimeSec: number;
    size: number;
    opacity: number;
    color: string;
    speed: number;
  }>(() => ({ enabled: false, maxCount: 800, spawnRate: 80, reactBass: 3, lifetimeSec: 2, size: 2, opacity: 0.35, color: "#ffffff", speed: 120 }));
  const [effectsDraft, setEffectsDraft] = React.useState<{
    bloomEnabled: boolean;
    bloomStrength: number;
    bloomBlurRadius: number;
    bloomThreshold: number;
    bloomOpacity: number;
    rgbEnabled: boolean;
    rgbOpacity: number;
    shakeEnabled: boolean;
    shakeIntensity: number;
    shakeSmoothing: number;
  }>(() => ({
    bloomEnabled: false,
    bloomStrength: 1,
    bloomBlurRadius: 11,
    bloomThreshold: 0.75,
    bloomOpacity: 0.9,
    rgbEnabled: false,
    rgbOpacity: 0.6,
    shakeEnabled: false,
    shakeIntensity: 8,
    shakeSmoothing: 0.85,
  }));
  const [spectrumSaveLabel, setSpectrumSaveLabel] = React.useState("My Template");
  const videoSpectrumPreviewBusyRef = React.useRef(false);

  React.useEffect(() => {
    videoSpectrumPreviewBusyRef.current = videoSpectrumPreviewBusy;
  }, [videoSpectrumPreviewBusy]);

  React.useEffect(() => {
    const p = String(videoSpectrumPreviewMp3Path || "").trim();
    setVideoSpectrumPreviewMp3Url(p ? `mgsamples://file?path=${encodeURIComponent(p)}` : "");
  }, [videoSpectrumPreviewMp3Path]);

  const hexToRgb = React.useCallback((hex: string) => {
    const h = String(hex || "").trim();
    if (!/^#[0-9a-fA-F]{6}$/.test(h)) return [255, 255, 255];
    return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  }, []);

  const buildVideoTemplateDraft = React.useCallback(() => {
    const spectrumColor = hexToRgb(spectrumDraft.color);
    const glowColor = hexToRgb(spectrumDraft.glowColor || spectrumDraft.color);
    const gradientColor = hexToRgb(spectrumDraft.gradientColor);
    const gradientEnabled = Boolean(spectrumDraft.gradientEnabled);

    const mainLayer: any = {
      type: "main",
      color: spectrumColor,
      opacity: 1,
      thickness: spectrumDraft.thickness,
      blur: 0,
      radius_offset: 0,
      blend_mode: "normal",
      radius: spectrumDraft.radius,
      strength: spectrumDraft.strength,
      point_count: spectrumDraft.pointCount,
      smoothing: spectrumDraft.smoothing,
    };
    if (gradientEnabled) mainLayer.gradient_color = gradientColor;

    const glowLayers = Array.from({ length: Math.max(0, Math.min(8, Math.floor(spectrumDraft.glowLayers))) }).map((_, i) => {
      const k = i + 1;
      const op = Math.max(0, Math.min(1, spectrumDraft.glowOpacity)) / k;
      const gl: any = {
        type: "glow",
        color: glowColor,
        opacity: op,
        thickness: spectrumDraft.thickness + k,
        blur: 0,
        radius_offset: spectrumDraft.glowSpread * k,
        blend_mode: "additive",
        radius: spectrumDraft.radius,
        strength: spectrumDraft.strength * 0.75,
        point_count: spectrumDraft.pointCount,
        smoothing: spectrumDraft.smoothing,
      };
      if (gradientEnabled) gl.gradient_color = gradientColor;
      return gl;
    });

    const extraLayers = videoSpectrumExtraLayers.map((l) => {
      const col = hexToRgb(l.color);
      const grad = hexToRgb(l.gradientColor);
      const layer: any = {
        type: "custom",
        color: col,
        opacity: Math.max(0, Math.min(1, Number(l.opacity) || 0)),
        thickness: Math.max(1, Number(l.thickness) || 1),
        blur: 0,
        radius_offset: Number(l.radiusOffset) || 0,
        blend_mode: l.blendMode === "additive" ? "additive" : "normal",
        radius: spectrumDraft.radius,
        strength: spectrumDraft.strength * Math.max(0, Number(l.strengthMul) || 0),
        point_count: spectrumDraft.pointCount,
        smoothing: spectrumDraft.smoothing,
      };
      if (l.gradientEnabled) layer.gradient_color = grad;
      return layer;
    });

    return {
      version: 2,
      background: "",
      background_settings: {
        brightness: Math.max(0, Math.min(1.4, Number(videoSpectrumBgBrightness) || 1)),
        react_bass: Math.max(0, Math.min(2, Number(videoSpectrumBgReactBass) || 0)),
      },
      logo: {
        circle_mask: Boolean(videoSpectrumLogoCircleMask),
        opacity: Math.max(0, Math.min(1, Number(videoSpectrumLogoOpacity) || 1)),
        scale: Math.max(0.1, Math.min(2.5, Number(videoSpectrumLogoScale) || 1)),
        react_bass: Math.max(0, Math.min(2, Number(videoSpectrumLogoReactBass) || 0)),
      },
      layers: [
        { type: "background", enabled: true, z_index: 0, opacity: 1, blend_mode: "normal" },
        {
          type: "spectrum",
          enabled: true,
          z_index: 10,
          opacity: 1,
          blend_mode: "normal",
          analyzer: "default",
          rotation_deg: spectrumDraft.rotationDeg,
          glow_layers: spectrumDraft.glowLayers,
          glow_spread: spectrumDraft.glowSpread,
          glow_opacity: spectrumDraft.glowOpacity,
          style: {
            spectrum_type: spectrumDraft.spectrumType,
            render_mode: spectrumDraft.renderMode,
            draw_type: spectrumDraft.drawType,
            mirror: Boolean(spectrumDraft.mirror),
            clip_circle: Boolean(spectrumDraft.clipCircle),
            fill_circle: Boolean(spectrumDraft.fillCircle),
            connect: Boolean(spectrumDraft.connect),
            dot_size: Math.max(0, Math.min(80, Number(spectrumDraft.dotSize) || 0)),
            react_gain: Math.max(0.1, Math.min(8, Number(spectrumDraft.reactGain) || 1)),
            react_bass: Math.max(0, Math.min(6, Number(spectrumDraft.reactBass) || 0)),
            feather: Math.max(0, Math.min(1, Number(spectrumDraft.feather) || 0)),
            downsample: Math.max(1, Math.min(32, Math.floor(Number(spectrumDraft.downsample) || 1))),
            anti_alias: Boolean(spectrumDraft.antiAlias),
            shadow: {
              enabled: Boolean(spectrumDraft.shadowEnabled),
              scale: Math.max(0, Math.min(80, Number(spectrumDraft.shadowScale) || 0)),
              alpha: Math.max(0, Math.min(1, Number(spectrumDraft.shadowAlpha) || 0)),
              offset_x: Math.max(-200, Math.min(200, Number(spectrumDraft.shadowOffsetX) || 0)),
              offset_y: Math.max(-200, Math.min(200, Number(spectrumDraft.shadowOffsetY) || 0)),
            },
            texture_transform: {
              x: Math.max(-1, Math.min(1, Number(spectrumDraft.textureX) || 0)),
              y: Math.max(-1, Math.min(1, Number(spectrumDraft.textureY) || 0)),
              scale: Math.max(0.1, Math.min(8, Number(spectrumDraft.textureScale) || 1)),
              scale_mul: Math.max(0.25, Math.min(8, Number(spectrumDraft.textureScaleMul) || 1)),
              disable_aspect: Boolean(spectrumDraft.textureDisableAspect),
            },
          },
          spectrum_layers: [mainLayer, ...glowLayers, ...extraLayers],
        },
        { type: "particles", enabled: true, z_index: 20, opacity: 1, blend_mode: "additive" },
      ],
      particles: {
        enabled: particlesDraft.enabled,
        max_count: particlesDraft.maxCount,
        spawn_rate: particlesDraft.spawnRate,
        react_bass: Math.max(0, Math.min(6, Number(particlesDraft.reactBass) || 0)),
        lifetime_sec: particlesDraft.lifetimeSec,
        size: particlesDraft.size,
        opacity: particlesDraft.opacity,
        color: hexToRgb(particlesDraft.color),
        speed: particlesDraft.speed,
      },
      effects: {
        bloom: {
          enabled: effectsDraft.bloomEnabled,
          strength: effectsDraft.bloomStrength,
          blur_radius: effectsDraft.bloomBlurRadius,
          threshold: effectsDraft.bloomThreshold,
          opacity: effectsDraft.bloomOpacity,
        },
        rgb_split: {
          enabled: effectsDraft.rgbEnabled,
          red_offset: [2, 0],
          green_offset: [0, 0],
          blue_offset: [-2, 0],
          opacity: effectsDraft.rgbOpacity,
        },
        camera_shake: {
          enabled: effectsDraft.shakeEnabled,
          intensity: effectsDraft.shakeIntensity,
          smoothing: effectsDraft.shakeSmoothing,
        },
      },
      analyzers: { default: { smoothing: spectrumDraft.smoothing, sensitivity: 1 } },
      automations: [],
    };
  }, [
    effectsDraft,
    hexToRgb,
    particlesDraft,
    spectrumDraft,
    videoSpectrumBgBrightness,
    videoSpectrumBgReactBass,
    videoSpectrumExtraLayers,
    videoSpectrumLogoCircleMask,
    videoSpectrumLogoOpacity,
    videoSpectrumLogoReactBass,
    videoSpectrumLogoScale,
  ]);

  const spectrumAutoTimerRef = React.useRef<number | null>(null);
  const spectrumAutoPendingRef = React.useRef(false);

  const runSpectrumPreview = React.useCallback(
    async (reason: "manual" | "auto", frameOverride?: number) => {
      if (videoSpectrumPreviewBusyRef.current) {
        spectrumAutoPendingRef.current = true;
        return;
      }
      if (videoTab !== "spectrum") return;
      if (!window.mgApi?.videoRenderPreviewPng) return;

      const backgroundPath = String(videoSpectrumPreviewBackgroundPath || data.settings.videoRenderBackgroundPath || "").trim();

      const autoProfileId =
        videoSpectrumPreviewAutoLogoSource === "alt"
          ? data.settings.activeProfileAltId ?? null
          : data.settings.activeProfileOkId ?? data.settings.activeProfileId ?? null;
      const autoLogoPath = autoProfileId ? data.profiles.find((p) => p.id === autoProfileId)?.logoPath ?? "" : "";
      const logoPath = String(videoSpectrumPreviewLogoPath || autoLogoPath || "").trim();

      setVideoSpectrumPreviewBusy(true);
      try {
        const isAuto = reason === "auto";
        const frame2 = Number.isFinite(Number(frameOverride)) ? Math.max(0, Math.floor(Number(frameOverride))) : isAuto ? 0 : 8;
        const r = await window.mgApi.videoRenderPreviewPng({
          mp3Path: String(videoSpectrumPreviewMp3Path || videoRenderMp3Path || "").trim() || undefined,
          backgroundPath,
          template: buildVideoTemplateDraft(),
          logoPath: logoPath || undefined,
          width: 960,
          height: 540,
          frame: frame2,
        });
        if ("message" in r) {
          if (reason === "manual") setFooterStatus(r.message, null);
          return;
        }
        setVideoSpectrumPreviewUrl(r.fileUrl);
      } catch (e) {
        if (reason === "manual") setFooterStatus(e instanceof Error ? e.message : "Preview failed", null);
      } finally {
        setVideoSpectrumPreviewBusy(false);
        if (reason === "auto" && spectrumAutoPendingRef.current) {
          spectrumAutoPendingRef.current = false;
          window.setTimeout(() => {
            runSpectrumPreview("auto").catch(() => undefined);
          }, 0);
        }
      }
    },
    [
      buildVideoTemplateDraft,
      data.profiles,
      data.settings.activeProfileId,
      data.settings.activeProfileAltId,
      data.settings.activeProfileOkId,
      data.settings.videoRenderBackgroundPath,
      videoSpectrumPreviewBackgroundPath,
      setFooterStatus,
      videoSpectrumPreviewMp3Path,
      videoRenderMp3Path,
      videoSpectrumPreviewAutoLogoSource,
      videoSpectrumPreviewLogoPath,
      videoTab,
    ],
  );
  React.useEffect(() => {
    if (!videoSpectrumAutoPreview) return;
    if (videoTab !== "spectrum") return;
    if (spectrumAutoTimerRef.current) window.clearTimeout(spectrumAutoTimerRef.current);
    spectrumAutoTimerRef.current = window.setTimeout(async () => {
      spectrumAutoTimerRef.current = null;
      if (videoSpectrumPreviewBusyRef.current) {
        spectrumAutoPendingRef.current = true;
        return;
      }
      await runSpectrumPreview("auto");
    }, 120);
    return () => {
      if (spectrumAutoTimerRef.current) window.clearTimeout(spectrumAutoTimerRef.current);
      spectrumAutoTimerRef.current = null;
    };
  }, [
    data.settings.videoRenderBackgroundPath,
    effectsDraft,
    particlesDraft,
    runSpectrumPreview,
    spectrumDraft,
    videoSpectrumBgBrightness,
    videoSpectrumExtraLayers,
    videoSpectrumAutoPreview,
    videoSpectrumLogoCircleMask,
    videoSpectrumLogoOpacity,
    videoSpectrumLogoReactBass,
    videoSpectrumLogoScale,
    videoSpectrumPreviewAutoLogoSource,
    videoSpectrumPreviewBackgroundPath,
    videoSpectrumPreviewLogoPath,
    videoSpectrumPreviewMp3Path,
    videoTab,
  ]);

  React.useEffect(() => {
    if (!spectrumAutoPendingRef.current) return;
    if (videoSpectrumPreviewBusy) return;
    spectrumAutoPendingRef.current = false;
    runSpectrumPreview("auto");
  }, [runSpectrumPreview, videoSpectrumPreviewBusy]);

  const enabledDescriptionIds = data.settings.enabledDescriptionIds;
  const enabledStructureIds = data.settings.enabledStructureIds;

  React.useEffect(() => {
    if (!window.mgApi?.onVideoMergeEvent) return;
    return window.mgApi.onVideoMergeEvent((evt: VideoMergeEvent) => {
      setVideoMergeState((s) => {
        if (s.runId && evt.runId !== s.runId) return s;
        const nextRows = {
          ...s.rows,
          [evt.directory]: { directory: evt.directory, status: evt.status, message: evt.message, outputPath: evt.outputPath },
        };
        const done = Object.values(nextRows).filter((r) => r.status === "done" || r.status === "failed").length;
        const total = Math.max(s.total || 0, evt.total || 0);
        const running = total > 0 ? done < total : s.running;
        return { runId: evt.runId, running, total, rows: nextRows };
      });
    });
  }, []);

  React.useEffect(() => {
    if (!window.mgApi?.onVideoRenderEvent) return;
    return window.mgApi.onVideoRenderEvent((evt: VideoRenderEvent) => {
      setVideoRenderState((s) => {
        if (s.runId && evt.runId !== s.runId) return s;
        const running = evt.status === "running" || evt.status === "pending";
        const progress = typeof evt.progress === "number" ? Math.max(0, Math.min(1, evt.progress)) : s.progress;
        const outputPath = evt.outputPath ? evt.outputPath : s.outputPath;
        return { runId: evt.runId, running, message: evt.message || "", progress, outputPath };
      });
    });
  }, []);

  const reloadVideoTemplates = React.useCallback(async () => {
    if (!window.mgApi?.videoTemplatesList) {
      setFooterStatus("Template list is only available in the Electron app", null);
      return;
    }
    if (videoTemplatesBlocked) return;
    try {
      const r = await window.mgApi.videoTemplatesList();
      if ("message" in r) {
        if (String(r.message || "").toLowerCase().includes("database is not configured")) {
          setVideoTemplatesBlocked(String(r.message || "Database is not configured"));
          setVideoTemplates([]);
        }
        setFooterStatus(r.message, null);
        return;
      }
      setVideoTemplates(r.items);
      const current = String(data.settings.videoRenderTemplatePath || "").trim();
      if (!current && r.items.length) {
        const preferred = r.items.find((x) => x.label.toLowerCase() === "default") ?? r.items[0]!;
        updateSettings({ videoRenderTemplatePath: preferred.path });
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Template IPC failed";
      if (String(msg || "").toLowerCase().includes("database is not configured")) {
        setVideoTemplatesBlocked(String(msg || "Database is not configured"));
        setVideoTemplates([]);
      }
      setFooterStatus(`${msg} (restart Electron)`, null);
    }
  }, [data.settings.videoRenderTemplatePath, setFooterStatus, updateSettings, videoTemplatesBlocked]);

  const saveVideoTemplate = React.useCallback(async () => {
    if (!window.mgApi?.videoTemplatesSave) {
      setFooterStatus("Template save is only available in the Electron app", null);
      return;
    }
    const label = String(spectrumSaveLabel || "").trim();
    if (!label) return;
    const template = buildVideoTemplateDraft();

    try {
      const r = await window.mgApi.videoTemplatesSave({ label, template });
      if ("message" in r) {
        setFooterStatus(r.message, null);
        return;
      }
      await reloadVideoTemplates();
      await updateSettings({ videoRenderTemplatePath: r.path });
      setFooterStatus("Template saved", 100);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Template save IPC failed";
      setFooterStatus(`${msg} (restart Electron)`, null);
    }
  }, [buildVideoTemplateDraft, reloadVideoTemplates, setFooterStatus, spectrumSaveLabel, updateSettings]);

  const deleteVideoTemplateByPath = React.useCallback(
    async (input: { path: string; label: string; source: "builtin" | "user" }) => {
      const id = String(input.path || "").trim();
      const label = String(input.label || "").trim();
      if (!id) return;
      if (input.source !== "user") return;
      if (!window.mgApi?.videoTemplatesDelete) {
        setFooterStatus("Template delete is only available in the Electron app", null);
        return;
      }
      const ok = window.confirm(`Delete template "${label}"?\n\nThis permanently removes it from the database.`);
      if (!ok) return;
      setVideoTemplateDeletingPath(id);
      try {
        const r = await window.mgApi.videoTemplatesDelete({ path: id });
        if ("message" in r) {
          setFooterStatus(r.message, null);
          return;
        }
        if (String(data.settings.videoRenderTemplatePath || "") === id) {
          await updateSettings({ videoRenderTemplatePath: "" });
          setSpectrumSaveLabel("");
        }
        await reloadVideoTemplates();
        setFooterStatus("Template deleted", 100);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Template delete IPC failed";
        setFooterStatus(`${msg} (restart Electron)`, null);
      } finally {
        setVideoTemplateDeletingPath("");
      }
    },
    [data.settings.videoRenderTemplatePath, reloadVideoTemplates, setFooterStatus, updateSettings],
  );

  React.useEffect(() => {
    reloadVideoTemplates();
  }, [reloadVideoTemplates]);

  const parseTemplateToDraft = React.useCallback((template: unknown) => {
    const t = template as any;
    const v2Layers = Array.isArray(t?.layers) ? t.layers : null;
    const v2SpectrumContainer =
      v2Layers?.find((x: any) => x && typeof x === "object" && String(x.type || "").toLowerCase() === "spectrum") ?? null;
    const spectrumLayersRaw = Array.isArray(v2SpectrumContainer?.spectrum_layers) ? v2SpectrumContainer.spectrum_layers : [];
    const v2SpectrumLayer = spectrumLayersRaw?.[0] ?? null;
    const v2Style = v2SpectrumContainer?.style && typeof v2SpectrumContainer.style === "object" ? v2SpectrumContainer.style : {};
    const v2Shadow = v2Style.shadow && typeof v2Style.shadow === "object" ? v2Style.shadow : {};
    const v2Tex = v2Style.texture_transform && typeof v2Style.texture_transform === "object" ? v2Style.texture_transform : {};

    const s = (t && typeof t === "object" ? (v2SpectrumLayer ?? t.spectrum) : null) as any;
    const radius = Number(s?.radius);
    const strength = Number(s?.strength);
    const thickness = Number(s?.thickness);
    const pointCount = Number(s?.point_count);
    const smoothing = Number(s?.smoothing);
    const colorRaw = s?.color;
    const gradientRaw = s?.gradient_color;
    const rotationDeg = Number(v2SpectrumContainer?.rotation_deg);
    const glowLayersRaw = Number(v2SpectrumContainer?.glow_layers);
    const glowSpread = Number(v2SpectrumContainer?.glow_spread);
    const glowOpacity = Number(v2SpectrumContainer?.glow_opacity);

    const color =
      typeof colorRaw === "string" && /^#[0-9a-fA-F]{6}$/.test(colorRaw)
        ? colorRaw
        : Array.isArray(colorRaw) && colorRaw.length === 3
          ? `#${[0, 1, 2]
              .map((i) => Math.max(0, Math.min(255, Number(colorRaw[i] ?? 255))))
              .map((n) => n.toString(16).padStart(2, "0"))
              .join("")}`
          : "#ffffff";

    const rgbArrToHex = (arr: unknown, fallback: string) => {
      if (!Array.isArray(arr) || arr.length !== 3) return fallback;
      return `#${[0, 1, 2]
        .map((i) => Math.max(0, Math.min(255, Number((arr as any)[i] ?? 255))))
        .map((n) => n.toString(16).padStart(2, "0"))
        .join("")}`;
    };
    const gradientEnabled = Array.isArray(gradientRaw) && gradientRaw.length === 3;
    const gradientColor = rgbArrToHex(gradientRaw, "#00ffff");
    const glowLayersList = spectrumLayersRaw.slice(1).filter((x: any) => x && typeof x === "object" && String(x.type || "").toLowerCase() === "glow");
    const extraLayersList = spectrumLayersRaw.slice(1).filter((x: any) => !(x && typeof x === "object" && String(x.type || "").toLowerCase() === "glow"));
    const glowColorRaw = glowLayersList?.[0]?.color;
    const glowColor = typeof glowColorRaw === "string" ? glowColorRaw : rgbArrToHex(glowColorRaw, color);
    const derivedGlowLayers = glowLayersList.length;

    setSpectrumDraft((d) => ({
      spectrumType:
        String((v2Style as any).spectrum_type || d.spectrumType).toLowerCase() === "bars"
          ? "bars"
          : String((v2Style as any).spectrum_type || d.spectrumType).toLowerCase() === "custom"
            ? "custom"
            : "circle",
      renderMode: String((v2Style as any).render_mode || d.renderMode).toLowerCase() === "fill" ? "fill" : "stroke",
      drawType: String((v2Style as any).draw_type || d.drawType).toLowerCase() === "line" ? "line" : "curve",
      mirror: typeof (v2Style as any).mirror === "boolean" ? (v2Style as any).mirror : d.mirror,
      clipCircle: typeof (v2Style as any).clip_circle === "boolean" ? (v2Style as any).clip_circle : d.clipCircle,
      fillCircle: typeof (v2Style as any).fill_circle === "boolean" ? (v2Style as any).fill_circle : d.fillCircle,
      connect: typeof (v2Style as any).connect === "boolean" ? (v2Style as any).connect : d.connect,
      dotSize: Number.isFinite(Number((v2Style as any).dot_size)) ? Math.max(0, Math.min(80, Number((v2Style as any).dot_size))) : d.dotSize,
      reactGain: Number.isFinite(Number((v2Style as any).react_gain)) ? Math.max(0.1, Math.min(8, Number((v2Style as any).react_gain))) : d.reactGain,
      reactBass: Number.isFinite(Number((v2Style as any).react_bass)) ? Math.max(0, Math.min(6, Number((v2Style as any).react_bass))) : d.reactBass,
      feather: Number.isFinite(Number((v2Style as any).feather)) ? Math.max(0, Math.min(1, Number((v2Style as any).feather))) : d.feather,
      downsample: Number.isFinite(Number((v2Style as any).downsample))
        ? Math.max(1, Math.min(32, Math.floor(Number((v2Style as any).downsample))))
        : d.downsample,
      antiAlias: typeof (v2Style as any).anti_alias === "boolean" ? (v2Style as any).anti_alias : d.antiAlias,
      shadowEnabled: typeof (v2Shadow as any).enabled === "boolean" ? (v2Shadow as any).enabled : d.shadowEnabled,
      shadowScale: Number.isFinite(Number((v2Shadow as any).scale)) ? Math.max(0, Math.min(80, Number((v2Shadow as any).scale))) : d.shadowScale,
      shadowAlpha: Number.isFinite(Number((v2Shadow as any).alpha)) ? Math.max(0, Math.min(1, Number((v2Shadow as any).alpha))) : d.shadowAlpha,
      shadowOffsetX: Number.isFinite(Number((v2Shadow as any).offset_x))
        ? Math.max(-200, Math.min(200, Number((v2Shadow as any).offset_x)))
        : d.shadowOffsetX,
      shadowOffsetY: Number.isFinite(Number((v2Shadow as any).offset_y))
        ? Math.max(-200, Math.min(200, Number((v2Shadow as any).offset_y)))
        : d.shadowOffsetY,
      textureX: Number.isFinite(Number((v2Tex as any).x)) ? Math.max(-1, Math.min(1, Number((v2Tex as any).x))) : d.textureX,
      textureY: Number.isFinite(Number((v2Tex as any).y)) ? Math.max(-1, Math.min(1, Number((v2Tex as any).y))) : d.textureY,
      textureScale: Number.isFinite(Number((v2Tex as any).scale)) ? Math.max(0.1, Math.min(8, Number((v2Tex as any).scale))) : d.textureScale,
      textureScaleMul: Number.isFinite(Number((v2Tex as any).scale_mul))
        ? Math.max(0.25, Math.min(8, Number((v2Tex as any).scale_mul)))
        : d.textureScaleMul,
      textureDisableAspect: typeof (v2Tex as any).disable_aspect === "boolean" ? (v2Tex as any).disable_aspect : d.textureDisableAspect,
      radius: Number.isFinite(radius) ? radius : d.radius,
      strength: Number.isFinite(strength) ? strength : d.strength,
      thickness: Number.isFinite(thickness) ? thickness : d.thickness,
      pointCount: Number.isFinite(pointCount) ? pointCount : d.pointCount,
      smoothing: Number.isFinite(smoothing) ? smoothing : d.smoothing,
      color,
      gradientEnabled,
      gradientColor,
      glowColor,
      glowLayers: Number.isFinite(glowLayersRaw)
        ? Math.max(0, Math.min(8, Math.floor(glowLayersRaw)))
        : Number.isFinite(derivedGlowLayers)
          ? Math.max(0, Math.min(8, derivedGlowLayers))
          : d.glowLayers,
      glowSpread: Number.isFinite(glowSpread) ? glowSpread : d.glowSpread,
      glowOpacity: Number.isFinite(glowOpacity) ? glowOpacity : d.glowOpacity,
      rotationDeg: Number.isFinite(rotationDeg) ? rotationDeg : d.rotationDeg,
    }));

    setVideoSpectrumExtraLayers(() => {
      const baseStrength = Number.isFinite(strength) && strength > 0 ? strength : 1;
      return extraLayersList
        .filter((x: any) => x && typeof x === "object")
        .slice(0, 6)
        .map((x: any, idx: number) => {
          const cRaw = x.color;
          const col =
            typeof cRaw === "string" && /^#[0-9a-fA-F]{6}$/.test(cRaw) ? cRaw : Array.isArray(cRaw) ? rgbArrToHex(cRaw, "#ffffff") : "#ffffff";
          const gradRaw = x.gradient_color;
          const gradientEnabled2 = Array.isArray(gradRaw) && gradRaw.length === 3;
          const gradientColor2 = rgbArrToHex(gradRaw, "#00ffff");
          const strengthMul = Number(x.strength) / baseStrength;
          return {
            id: `${Date.now()}_${idx}_${Math.random().toString(16).slice(2)}`,
            color: col,
            opacity: Math.max(0, Math.min(1, Number(x.opacity) || 0)),
            thickness: Math.max(1, Math.min(80, Number(x.thickness) || 1)),
            radiusOffset: Number(x.radius_offset) || 0,
            strengthMul: Number.isFinite(strengthMul) ? Math.max(0, Math.min(2, strengthMul)) : 0.85,
            gradientEnabled: gradientEnabled2,
            gradientColor: gradientColor2,
            blendMode: String(x.blend_mode || "").toLowerCase() === "additive" ? "additive" : "normal",
          };
        });
    });

    if (t && typeof t === "object" && Array.isArray(t.layers)) {
      const p = t.particles && typeof t.particles === "object" ? t.particles : {};
      const pColorRaw = (p as any).color;
      const pColor =
        typeof pColorRaw === "string" && /^#[0-9a-fA-F]{6}$/.test(pColorRaw)
          ? pColorRaw
          : Array.isArray(pColorRaw) && pColorRaw.length === 3
            ? `#${[0, 1, 2]
                .map((i) => Math.max(0, Math.min(255, Number(pColorRaw[i] ?? 255))))
                .map((n) => n.toString(16).padStart(2, "0"))
                .join("")}`
            : "#ffffff";

      setParticlesDraft((d) => ({
        enabled: typeof (p as any).enabled === "boolean" ? (p as any).enabled : d.enabled,
        maxCount: Number.isFinite(Number((p as any).max_count)) ? Number((p as any).max_count) : d.maxCount,
        spawnRate: Number.isFinite(Number((p as any).spawn_rate)) ? Number((p as any).spawn_rate) : d.spawnRate,
        reactBass: Number.isFinite(Number((p as any).react_bass)) ? Math.max(0, Math.min(6, Number((p as any).react_bass))) : d.reactBass,
        lifetimeSec: Number.isFinite(Number((p as any).lifetime_sec)) ? Number((p as any).lifetime_sec) : d.lifetimeSec,
        size: Number.isFinite(Number((p as any).size)) ? Number((p as any).size) : d.size,
        opacity: Number.isFinite(Number((p as any).opacity)) ? Number((p as any).opacity) : d.opacity,
        color: pColor,
        speed: Number.isFinite(Number((p as any).speed)) ? Number((p as any).speed) : d.speed,
      }));

      const eff = t.effects && typeof t.effects === "object" ? t.effects : {};
      const bloom = (eff as any).bloom && typeof (eff as any).bloom === "object" ? (eff as any).bloom : {};
      const rgb = (eff as any).rgb_split && typeof (eff as any).rgb_split === "object" ? (eff as any).rgb_split : {};
      const shake = (eff as any).camera_shake && typeof (eff as any).camera_shake === "object" ? (eff as any).camera_shake : {};

      setEffectsDraft((d) => ({
        bloomEnabled: typeof bloom.enabled === "boolean" ? bloom.enabled : d.bloomEnabled,
        bloomStrength: Number.isFinite(Number(bloom.strength)) ? Number(bloom.strength) : d.bloomStrength,
        bloomBlurRadius: Number.isFinite(Number(bloom.blur_radius)) ? Number(bloom.blur_radius) : d.bloomBlurRadius,
        bloomThreshold: Number.isFinite(Number(bloom.threshold)) ? Number(bloom.threshold) : d.bloomThreshold,
        bloomOpacity: Number.isFinite(Number(bloom.opacity)) ? Number(bloom.opacity) : d.bloomOpacity,
        rgbEnabled: typeof rgb.enabled === "boolean" ? rgb.enabled : d.rgbEnabled,
        rgbOpacity: Number.isFinite(Number(rgb.opacity)) ? Number(rgb.opacity) : d.rgbOpacity,
        shakeEnabled: typeof shake.enabled === "boolean" ? shake.enabled : d.shakeEnabled,
        shakeIntensity: Number.isFinite(Number(shake.intensity)) ? Number(shake.intensity) : d.shakeIntensity,
        shakeSmoothing: Number.isFinite(Number(shake.smoothing)) ? Number(shake.smoothing) : d.shakeSmoothing,
      }));

      const bg = (t as any).background_settings && typeof (t as any).background_settings === "object" ? (t as any).background_settings : {};
      const logo = (t as any).logo && typeof (t as any).logo === "object" ? (t as any).logo : {};
      const bgBrightness = Number(bg.brightness);
      if (Number.isFinite(bgBrightness)) setVideoSpectrumBgBrightness(Math.max(0, Math.min(1.4, bgBrightness)));
      const bgReact = Number(bg.react_bass);
      if (Number.isFinite(bgReact)) setVideoSpectrumBgReactBass(Math.max(0, Math.min(2, bgReact)));
      if (typeof logo.circle_mask === "boolean") setVideoSpectrumLogoCircleMask(logo.circle_mask);
      const logoOpacity = Number(logo.opacity);
      if (Number.isFinite(logoOpacity)) setVideoSpectrumLogoOpacity(Math.max(0, Math.min(1, logoOpacity)));
      const logoScale = Number(logo.scale);
      if (Number.isFinite(logoScale)) setVideoSpectrumLogoScale(Math.max(0.1, Math.min(2.5, logoScale)));
      const logoReact = Number(logo.react_bass);
      if (Number.isFinite(logoReact)) setVideoSpectrumLogoReactBass(Math.max(0, Math.min(2, logoReact)));
    }
  }, []);

  React.useEffect(() => {
    const p = String(data.settings.videoRenderTemplatePath || "").trim();
    const currentLabel = videoTemplates.find((x) => x.path === p)?.label ?? "";
    setSpectrumSaveLabel(currentLabel);
    if (!p) return;
    if (videoTemplatesBlocked) return;
    if (!window.mgApi?.videoTemplatesRead) return;
    window.mgApi
      .videoTemplatesRead({ path: p })
      .then((r) => {
        if ("message" in r) {
          if (String(r.message || "").toLowerCase().includes("database is not configured")) {
            setVideoTemplatesBlocked(String(r.message || "Database is not configured"));
            setVideoTemplates([]);
          }
          return;
        }
        parseTemplateToDraft(r.template);
        const currentLabel2 = videoTemplates.find((x) => x.path === p)?.label ?? "";
        if (currentLabel2) setSpectrumSaveLabel(currentLabel2);
      })
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "Template read IPC failed";
        if (String(msg || "").toLowerCase().includes("database is not configured")) {
          setVideoTemplatesBlocked(String(msg || "Database is not configured"));
          setVideoTemplates([]);
          setFooterStatus(msg, null);
          return;
        }
        setFooterStatus(`${msg} (restart Electron)`, null);
      });
  }, [data.settings.videoRenderTemplatePath, parseTemplateToDraft, setFooterStatus, videoTab, videoTemplates, videoTemplatesBlocked]);

  function pickFromPool(items: { id: string; content: string }[], enabled: string[]) {
    const picked = pickFromPoolItem(items, enabled);
    return picked ? picked.content : "";
  }

  React.useEffect(() => {
    if (!hydrated) hydrate();
  }, [hydrated, hydrate]);

  React.useEffect(() => {
    return jobClient.onEvent(async (event) => {
      const activeBatch = batchRunRef.current;
      const isTrackedGenerate = event.action === "generate" && generateJobIds.current.has(event.jobId);

      if (event.action === "generate" && isTrackedGenerate && activeBatch && (event.status === "running" || event.status === "queued")) {
        const s = describeStatus(event);
        const perSong = typeof s.progress === "number" ? Math.max(0, Math.min(100, s.progress)) / 100 : 0.25;
        const p = Math.min(
          99,
          Math.max(0, Math.round(((activeBatch.completed + perSong) / Math.max(1, activeBatch.expected)) * 100)),
        );
        setFooterStatus(`Generating ${activeBatch.completed}/${activeBatch.expected} · ${s.text}`, p);
      }

      if (!(event.action === "generate" && isTrackedGenerate)) {
        const s = describeStatus(event);
        setFooterStatus(s.text, s.progress);
      }

      if (event.jobType === "suno") {
        const p = typeof event.progress === "number" ? Math.max(0, Math.min(100, event.progress)) : null;
        const rawMsg = String(event.message || "").trim();
        const statusText = String(event.status || "").trim();
        const msgLower = rawMsg.toLowerCase();
        const statusLower = statusText.toLowerCase();
        const redundantMsg =
          !rawMsg ||
          msgLower === statusLower ||
          msgLower === `suno ${statusLower}` ||
          msgLower === `suno: ${statusLower}` ||
          msgLower === `suno ${statusLower}...`;
        setSunoStatus(`Suno: ${statusText}${p !== null ? ` (${p}%)` : ""}${redundantMsg ? "" : ` · ${rawMsg}`}`);
      }
      if (event.action === "generate") {
        if (event.status === "running" || event.status === "queued") {
          activeGenerateJobs.current.add(event.jobId);
          setGenerating(true);
        }
        if (event.status === "completed" || event.status === "failed" || event.status === "cancelled") {
          activeGenerateJobs.current.delete(event.jobId);
          setGenerating(activeGenerateJobs.current.size > 0);
        }

        if (activeBatch && isTrackedGenerate && (event.status === "completed" || event.status === "failed" || event.status === "cancelled")) {
          if (event.status === "completed") activeBatch.completed += 1;
          if (event.status === "failed") {
            activeBatch.failed += 1;
            activeBatch.failures.push({ jobId: event.jobId, message: event.message || "job failed" });
          }
          if (event.status === "cancelled") activeBatch.cancelled += 1;

          const seedError =
            event.status === "failed" &&
            /pool is empty|Seed Postgres table|Postgres database is not configured/i.test(String(event.message || ""));

          if (seedError && !activeBatch.blockedReason) {
            activeBatch.blockedReason = String(event.message || "Pool is empty");
            cancelRequested.current = true;
            const ids = Array.from(generateJobIds.current);
            await Promise.all(ids.map((id) => jobClient.cancel(id).catch(() => undefined)));
          } else if (
            event.status === "failed" &&
            !cancelRequested.current &&
            activeBatch.batchId !== "multi" &&
            activeBatch.completed < activeBatch.expected &&
            activeBatch.attempted < activeBatch.maxAttempts
          ) {
            const activeDescriptionItem = pickActiveItem(data.descriptions, data.settings.activeDescriptionIds);
            const activeStructureItem = pickActiveItem(data.structures, data.settings.activeStructureIds);
            const shuffleDescriptionItem = data.settings.shuffleDescription
              ? pickFromPoolItem(data.descriptions, enabledDescriptionIds)
              : null;
            const shuffleStructureItem = data.settings.shuffleStructure ? pickFromPoolItem(data.structures, enabledStructureIds) : null;

            const effectiveDescription = shuffleDescriptionItem ? shuffleDescriptionItem.content : currentDescription;
            const effectiveStructure = shuffleStructureItem ? shuffleStructureItem.content : currentStructure;

            const finalDescription = activeDescriptionItem ? activeDescriptionItem.content : effectiveDescription;
            const finalStructure = activeStructureItem ? activeStructureItem.content : effectiveStructure;

            const descriptionTitle = activeDescriptionItem
              ? activeDescriptionItem.name
              : shuffleDescriptionItem
                ? shuffleDescriptionItem.name
                : finalDescription.trim()
                  ? "Custom"
                  : "";
            const structureTitle = activeStructureItem
              ? activeStructureItem.name
              : shuffleStructureItem
                ? shuffleStructureItem.name
                : finalStructure.trim()
                  ? "Custom"
                  : "";

            const enq = await jobClient.enqueue({
              jobType: "workflow",
              action: "generate",
              description: finalDescription,
              structure: finalStructure,
              descriptionTitle,
              structureTitle,
              language: data.settings.language,
              creativity: data.settings.creativity,
              songDraftProvider: data.settings.songDraftProvider,
              deepseekApiKey: data.settings.deepseekApiKey,
              openaiApiKey: data.settings.openaiApiKey,
              slaiSongApiKey: data.settings.slaiSongApiKey,
              slaiSongModel: data.settings.slaiSongModel,
              batchId: activeBatch.batchId,
              uniqueOpening: data.settings.uniqueOpening,
              strictLevel: data.settings.strictLevel,
              uniquenessHistoryWindow: data.settings.uniquenessHistoryWindow,
              sunoAutoSubmit: data.settings.autoGSuno,
            });
            generateJobIds.current.add(enq.jobId);
            activeBatch.attempted += 1;
          }

          const progressPct = Math.round((activeBatch.completed / Math.max(1, activeBatch.expected)) * 100);
          if (activeBatch.blockedReason) {
            setFooterStatus(`Stopped: ${activeBatch.blockedReason}`, null);
          } else if (activeBatch.completed >= activeBatch.expected) {
            setFooterStatus(`Done: ${activeBatch.completed}/${activeBatch.expected} songs saved`, 100);
          } else {
            const suffix =
              activeBatch.failed > 0
                ? ` · ${activeBatch.failed} failed${activeBatch.attempted > activeBatch.expected ? " (retrying)" : ""}`
                : "";
            const lastFail = activeBatch.failures[activeBatch.failures.length - 1]?.message;
            const short = lastFail ? String(lastFail).replace(/\s+/g, " ").trim().slice(0, 140) : "";
            const hint = short ? ` · last: ${short}` : "";
            setFooterStatus(`Generating ${activeBatch.completed}/${activeBatch.expected} songs saved${suffix}${hint}`, progressPct);
          }
        }

        if (event.song && event.status === "completed") {
          const okName = event.song.profileOkId ? data.profiles.find((p) => p.id === event.song.profileOkId)?.name ?? "" : "";
          const altName = event.song.profileAltId ? data.profiles.find((p) => p.id === event.song.profileAltId)?.name ?? "" : "";
          const created = await addSong({
            id: event.song.id,
            createdAt: event.song.createdAt,
            title: event.song.title,
            album: event.song.album,
            lyricsRaw: event.song.lyricsRaw,
            lyricsPolished: event.song.lyricsPolished,
            batchIndex: event.song.batchIndex,
            songDescriptionTitle: event.song.songDescriptionTitle ?? "",
            songStructureTitle: event.song.songStructureTitle ?? "",
            songDescription: event.song.songDescription,
            songStructure: event.song.songStructure,
            profileOkId: event.song.profileOkId ?? "",
            profileAltId: event.song.profileAltId ?? "",
            profileOkName: okName,
            profileAltName: altName,
            language: event.song.language,
            creativity: event.song.creativity,
            batchId: event.song.batchId,
          });
          setCurrentSongId(created.id);
          setFooterStatus(`Saved: ${created.title}`, 100);
        }
      } else {
        const label = event.jobType === "workflow" ? event.action ?? "workflow" : event.jobType;
        await addHistory({
          path: `job:${event.jobId}`,
          task: `${label} ${event.status}${typeof event.progress === "number" ? ` (${event.progress}%)` : ""}: ${event.message}`,
          status: event.status === "failed" ? "error" : event.status === "running" ? "running" : "ok",
          kind: event.jobType === "merge" ? "merge" : "job",
        });
      }

      const terminal = event.status === "completed" || event.status === "failed" || event.status === "cancelled";
      if (terminal && !(event.action === "generate" && generateJobIds.current.has(event.jobId))) {
        setTimeout(() => setFooterStatus("Ready", null), 2500);
      }
    });
  }, [addHistory, addSong, currentDescription, currentStructure, data.descriptions, data.profiles, data.settings, data.structures, enabledDescriptionIds, enabledStructureIds, setCurrentSongId, setFooterStatus]);

  async function stopAllGeneration() {
    cancelRequested.current = true;
    setFooterStatus("Stopping…", 5);
    const ids = Array.from(generateJobIds.current);
    await Promise.all(ids.map((id) => jobClient.cancel(id).catch(() => undefined)));
    generateJobIds.current.clear();
    activeGenerateJobs.current.clear();
    setGenerating(false);
    setRunning(false);
    setFooterStatus("Stopped", 100);
    setTimeout(() => setFooterStatus("Ready", null), 1200);
  }

  const historyRows = React.useMemo(() => {
    const lastBatchId = data.songs[0]?.batchId ?? null;
    let rows = !lastBatchOnly || !lastBatchId ? data.songs : data.songs.filter((s) => (s.batchId ?? "legacy") === lastBatchId);

    if (fromDate) rows = rows.filter((s) => s.createdAt.slice(0, 10) >= fromDate);
    if (toDate) rows = rows.filter((s) => s.createdAt.slice(0, 10) <= toDate);

    const out: HistoryRow[] = [];
    let lastBatch: string | null = null;
    for (const s of rows) {
      const bid = s.batchId ?? "legacy";
      if (bid !== lastBatch) {
        out.push({ kind: "separator", batchId: bid, album: s.album, createdAt: s.createdAt });
        lastBatch = bid;
      }
      out.push({ kind: "song", song: s });
    }
    return out;
  }, [data.songs, fromDate, lastBatchOnly, toDate]);

  const currentSong = React.useMemo(() => {
    if (currentSongId) {
      const found = data.songs.find((s) => s.id === currentSongId);
      if (found) return found;
    }
    return data.songs[0] ?? null;
  }, [currentSongId, data.songs]);

  React.useEffect(() => {
    const songUid = currentSong?.id ?? null;
    if (!songUid || !window.mgApi?.sunoGetSongOutputDirs) {
      setSunoRunDirs({ okDir: null, altDir: null });
      return;
    }
    let alive = true;
    window.mgApi
      .sunoGetSongOutputDirs(songUid)
      .then((r) => {
        if (!alive) return;
        if ("message" in r) setSunoRunDirs({ okDir: null, altDir: null, message: r.message });
        else setSunoRunDirs({ okDir: r.okDir, altDir: r.altDir });
      })
      .catch((e) => {
        if (!alive) return;
        const msg = e instanceof Error ? e.message : "Failed to resolve batch folders";
        setSunoRunDirs({ okDir: null, altDir: null, message: msg });
      });
    return () => {
      alive = false;
    };
  }, [currentSong?.id]);

  React.useEffect(() => {
    if (mainTab !== "image") return;
    refreshImageGalleries().catch(() => undefined);
  }, [mainTab, sunoRunDirs.okDir, sunoRunDirs.altDir, data.settings.imageOutputDir, currentSong?.profileOkName, currentSong?.profileAltName]);

  const effects = React.useMemo(() => {
    const c = data.settings.creativity;
    return {
      valence: Math.min(95, Math.max(5, 20 + c * 0.7)),
      dance: Math.min(95, Math.max(5, 15 + c * 0.75)),
      instr: Math.min(95, Math.max(5, 10 + c * 0.55)),
    };
  }, [data.settings.creativity]);

  function resolveRunDirForSide(side: ImageSide) {
    return side === "alt" ? sunoRunDirs.altDir : sunoRunDirs.okDir;
  }

  function appendBackgroundLog(line: string) {
    const msg = String(line || "").trim();
    if (!msg) return;
    setBackgroundLogs((s) => [...s.slice(-80), msg]);
  }

  function appendThumbnailLog(line: string) {
    const msg = String(line || "").trim();
    if (!msg) return;
    setThumbnailLogs((s) => [...s.slice(-80), msg]);
  }

  function getImageContext() {
    const okDir = sunoRunDirs.okDir;
    const altDir = sunoRunDirs.altDir;
    const sandbox = String(data.settings.imageOutputDir || "").trim();
    if (okDir && altDir) {
      return { mode: "batch" as const, okDir, altDir, label: `Batch: ${currentSong?.album || currentSong?.title || "Selected song"}` };
    }
    if (sandbox) {
      return { mode: "sandbox" as const, okDir: sandbox, altDir: null, label: `Sandbox: ${sandbox}` };
    }
    return { mode: "none" as const, okDir: null, altDir: null, label: "Configure Image output folder in Settings" };
  }

  function getBaseName(p: string) {
    return p.split(/[\\/]/).filter(Boolean).slice(-1)[0] ?? p;
  }

  function getDirName(p: string) {
    const parts = p.split(/[\\/]/);
    if (parts.length <= 1) return "";
    parts.pop();
    return parts.join("\\");
  }

  function joinPath(dir: string, name: string) {
    const d = String(dir || "").trim();
    if (!d) return name;
    if (d.endsWith("\\") || d.endsWith("/")) return `${d}${name}`;
    return `${d}\\${name}`;
  }

  function getRunRootFromChildDir(dir: string) {
    return String(dir || "").replace(/[\\/](backgrounds|thumbnails)$/i, "");
  }

  async function pickThumbnailSource() {
    if (!window.mgApi?.pickPath) return;
    const ctx = getImageContext();
    const defaultPath = ctx.okDir ?? undefined;
    const r = await window.mgApi.pickPath({
      kind: "file",
      defaultPath,
      title: "Select an image to generate thumbnail",
      filters: [
        { name: "Images", extensions: ["png", "jpg", "jpeg", "webp"] },
      ],
    });
    if (!("path" in r)) return;
    setThumbnailSourcePath(r.path);
  }

  async function generateThumbnailFromSelectedSource() {
    if (thumbnailing || bgGenerating) return;
    const src = String(thumbnailSourcePath || "").trim();
    if (!src) {
      setFooterStatus("Select an image first", null);
      return;
    }
    const ctx = getImageContext();
    if (ctx.mode === "none" || !ctx.okDir) {
      setFooterStatus(ctx.label, null);
      return;
    }

    setThumbnailing(true);
    setThumbnailLogs([]);
    try {
      await generateThumbnailForSide("ok", { bgPath: src, outDir: ctx.okDir, outFileName: "", setAsCurrent: true });
      setFooterStatus("Thumbnail generated", 100);
      setTimeout(() => setFooterStatus("Ready", null), 1600);
    } finally {
      setThumbnailing(false);
    }
  }

  async function refreshImageGalleries() {
    if (!window.mgApi?.listGeneratedImages) return;
    const ctx = getImageContext();
    const limit = 80;

    const dirs: Array<{ dir: string; label: string }> = [];
    if (ctx.okDir) dirs.push({ dir: ctx.okDir, label: ctx.mode === "batch" ? (currentSong?.profileOkName ?? "OK") : "Sandbox" });
    if (manualGenerateBoth && ctx.altDir) dirs.push({ dir: ctx.altDir, label: ctx.mode === "batch" ? (currentSong?.profileAltName ?? "ALT") : "ALT" });

    const nextBg: ImagePanelItem[] = [];
    const nextTh: ImagePanelItem[] = [];

    for (const d of dirs) {
      const bg = await window.mgApi.listGeneratedImages({ outputDir: d.dir, kind: "background", limit });
      if ("items" in bg) nextBg.push(...bg.items.map((x) => ({ ...x, label: d.label })));
      const th = await window.mgApi.listGeneratedImages({ outputDir: d.dir, kind: "thumbnail", limit });
      if ("items" in th) nextTh.push(...th.items.map((x) => ({ ...x, label: d.label })));
    }

    nextBg.sort((a, b) => b.mtimeMs - a.mtimeMs);
    nextTh.sort((a, b) => b.mtimeMs - a.mtimeMs);

    setBackgroundItems(nextBg);
    setThumbnailItems(nextTh);

    setSelectedBackgroundPath((cur) => (cur && nextBg.some((x) => x.filePath === cur) ? cur : nextBg[0]?.filePath ?? null));
    setSelectedThumbnailPath((cur) => (cur && nextTh.some((x) => x.filePath === cur) ? cur : nextTh[0]?.filePath ?? null));
    setThumbnailSourcePath((cur) => (cur ? cur : nextBg[0]?.filePath ?? null));
  }

  async function buildBackgroundPrompt(sourceMode: "samples" | "prompt") {
    if (!data.carModels.length) return { ok: false as const, message: "Car list is empty. Add car models in Manage → Car Models" };

    let sample: null | { fileName: string; filePath: string } = null;
    if (sourceMode === "samples") {
      if (!window.mgApi?.imageSamplesList) return { ok: false as const, message: "Electron runtime required" };
      const folder = String(data.settings.imageSamplesDir || "").trim();
      if (!folder) return { ok: false as const, message: "Select an Image Samples folder first" };
      const listed = await window.mgApi.imageSamplesList({ folderPath: folder });
      if ("message" in listed) return { ok: false as const, message: listed.message };
      const picked = pickRandom(listed.items);
      if (!picked) return { ok: false as const, message: "No images found in the selected folder" };
      sample = { fileName: picked.fileName, filePath: picked.filePath };
    }

    const car = pickRandom(data.carModels);
    if (!car) return { ok: false as const, message: "Car list is empty" };

    const sceneTemplates = data.promptTemplates.filter((t) => String(t.scene || "").trim().length > 0);
    if (!sceneTemplates.length) {
      return { ok: false as const, message: "No scene templates found. Add at least 1 template with a Scene." };
    }

    const ordered = [...sceneTemplates].sort((a, b) => String(a.id).localeCompare(String(b.id)));
    const currentIndex = Math.max(0, Math.floor(bgTemplateCycleIndexRef.current ?? 0));
    const pickIndex = ordered.length ? currentIndex % ordered.length : 0;
    const tpl = ordered[pickIndex] ?? ordered[0];
    const nextIndex = ordered.length ? (pickIndex + 1) % ordered.length : 0;
    bgTemplateCycleIndexRef.current = nextIndex;
    void updateSettings({ backgroundTemplateCycleIndex: nextIndex });

    const sceneText = tpl?.scene?.trim() ? tpl.scene : "";
    const negativeText = String(tpl?.negativePrompt || "").trim() || "No text, no typography, no watermark, no logos, no letters, no numbers.";

    const resolution = data.settings.imageResolution;
    const carInfo = `${car.year} ${car.make} ${car.model} ${car.trim} (${car.category})`.replace(/\s+/g, " ").trim();
    const ctx = {
      car: `${car.make} ${car.model} ${car.trim}`.replace(/\s+/g, " ").trim(),
      make: car.make,
      model: car.model,
      trim: car.trim,
      year: String(car.year),
      category: car.category,
      sampleName: sample?.fileName ?? "",
      sampleFile: sample?.filePath ?? "",
      resolution,
      styleStrength: String(data.settings.styleStrength ?? 60),
    };

    const carLabel = ctx.car;
    const scenePrompt = applyMasterCarToken(renderTemplate(sceneText, ctx), carLabel).replace(/\s+\n/g, "\n").trim();
    const carEnhancement =
      "Car styling: keep the exact make/model identifiable, but present it as a premium modern futuristic concept version with subtle aerodynamic body kit, sharp LED lighting, clean high-end materials, and cinematic reflections. Do not change the car type.";
    const basePrompt = (
      `Photorealistic cinematic car background. The car must be clearly visible and be the main subject.\n` +
      `Car: ${carInfo}.\n` +
      `${carEnhancement}\n` +
      `Scene: ${scenePrompt}\n` +
      `Output resolution: ${resolution}.`
    )
      .replace(/\s+\n/g, "\n")
      .trim();
    const prompt = buildCappedPrompt({
      base: basePrompt,
      negative: negativeText,
      maxLen: 1000,
    });

    const pickInfo = {
      sample: sample?.fileName ?? "",
      car: carInfo,
      template: `${tpl?.name?.trim() ? tpl.name : "Template"} (${pickIndex + 1}/${ordered.length})`,
    };

    return { ok: true as const, prompt, sampleFilePath: sample?.filePath ?? null, pickInfo };
  }

  function buildThumbnailPromptFromStyle(textStyle: (typeof data.textStyles)[number]) {
    const line2 = String(textStyle.subtitle || "").trim();
    const line3 = String(textStyle.subtitle2 || "").trim();
    return (
      `Only add typography overlay on top of the existing background image. Do not change the car or background composition.\n` +
      `Add centered typography overlay (exact spelling):\n` +
      `Line 1 (large): "${textStyle.title}"\n` +
      `Line 2 (medium): "${line2}"\n` +
      `Line 3 (small): "${line3}"\n` +
      `Style name: ${textStyle.name}. Opacity: ${textStyle.opacity.toFixed(2)}. Position: center.\n` +
      `Typography style prompt: ${String(textStyle.prompt || "").trim()}\n` +
      `Keep text sharp, readable, and aligned.`
    );
  }

  async function generateThumbnailForSide(side: ImageSide, input: { bgPath: string; outDir: string; outFileName: string; setAsCurrent: boolean }) {
    const textStyle = pickRandom(data.textStyles);
    if (!textStyle) {
      setFooterStatus("Text styles are empty. Generate them in Manage → Text Styles", null);
      appendThumbnailLog("Generate text styles first");
      return null;
    }

    appendThumbnailLog(`Generating (${side.toUpperCase()})…`);
    let out: { ok: true; filePath: string; fileUrl: string; meta?: ImageGenMeta } | { ok: false; message: string };
    try {
      if (!window.mgApi?.generateThumbnailImage) {
        setFooterStatus("Thumbnail generation requires the Electron app runtime", null);
        appendThumbnailLog("Electron runtime required");
        return null;
      }
      aiCallsRef.current += 1;
      out = await window.mgApi.generateThumbnailImage({
        prompt: buildThumbnailPromptFromStyle(textStyle),
        backgroundFilePath: input.bgPath,
        resolution: data.settings.imageResolution,
        outputDir: input.outDir,
        outputFileName: input.outFileName,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Thumbnail generation failed";
      const hint = msg.includes("No handler registered") ? " Restart the Electron app (stop and run dev again)." : "";
      setFooterStatus(`Thumbnail failed: ${msg}${hint}`, null);
      appendThumbnailLog(`Failed: ${msg}${hint}`);
      return null;
    }

    if (out.ok !== true) {
      setFooterStatus(out.message, null);
      appendThumbnailLog(out.message);
      return null;
    }
    if (out.meta) appendThumbnailLog(formatImageMeta(out.meta));

    if (input.setAsCurrent) setSelectedThumbnailPath(out.filePath);
    appendThumbnailLog(`Saved: ${out.filePath}`);
    await addHistory({ path: out.filePath, task: `thumbnail generated (${side.toUpperCase()})`, status: "ok", kind: "thumbnail" });
    await refreshImageGalleries();
    return out;
  }

  async function generateBackgroundForSide(side: ImageSide, input: { outDir: string; outFileName: string; setAsCurrent: boolean }) {
    if (!window.mgApi?.generateBackgroundImage) {
      setFooterStatus("Background generation requires the Electron app runtime", null);
      appendBackgroundLog("Electron runtime required");
      return null;
    }

    const prep = await buildBackgroundPrompt("samples");
    if (!prep.ok) {
      setFooterStatus(prep.message, null);
      appendBackgroundLog(prep.message);
      return null;
    }

    appendBackgroundLog(`Generating (${side.toUpperCase()})…`);
    if (prep.pickInfo.sample) appendBackgroundLog(`Sample: ${prep.pickInfo.sample}`);
    appendBackgroundLog(`Car: ${prep.pickInfo.car}`);
    appendBackgroundLog(`Template: ${prep.pickInfo.template}`);

    let out: { ok: true; filePath: string; fileUrl: string; meta?: ImageGenMeta } | { ok: false; message: string };
    try {
      if (!prep.sampleFilePath) {
        setFooterStatus("No sample image selected", null);
        appendBackgroundLog("No sample image selected");
        return null;
      }
      aiCallsRef.current += 1;
      out = await window.mgApi.generateBackgroundImage({
        prompt: prep.prompt,
        sampleFilePath: prep.sampleFilePath,
        resolution: data.settings.imageResolution,
        outputDir: input.outDir,
        outputFileName: input.outFileName,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Image generation failed";
      const hint = msg.includes("No handler registered") ? " Restart the Electron app (stop and run dev again)." : "";
      setFooterStatus(`Image failed: ${msg}${hint}`, null);
      appendBackgroundLog(`Failed: ${msg}${hint}`);
      return null;
    }

    if (out.ok !== true) {
      setFooterStatus(out.message, null);
      appendBackgroundLog(out.message);
      return null;
    }
    if (out.meta) appendBackgroundLog(formatImageMeta(out.meta));

    if (input.setAsCurrent) setSelectedBackgroundPath(out.filePath);
    appendBackgroundLog(`Saved: ${out.filePath}`);
    await addHistory({ path: out.filePath, task: `background generated (${side.toUpperCase()})`, status: "ok", kind: "thumbnail" });
    await refreshImageGalleries();
    return out;
  }

  async function preflightManualImages() {
    if (!window.mgApi?.generateBackgroundImage) {
      return { ok: false as const, message: "Background generation requires the Electron app runtime" };
    }

    if (!data.carModels.length) {
      return { ok: false as const, message: "Car list is empty. Add car models in Manage → Car Models" };
    }

    const sceneTemplates = data.promptTemplates.filter((t) => String(t.scene || "").trim().length > 0);
    if (!sceneTemplates.length) {
      return { ok: false as const, message: "No scene templates found. Add at least 1 template with a Scene." };
    }

    if (!window.mgApi?.imageSamplesList) {
      return { ok: false as const, message: "Electron runtime required" };
    }
    const folder = String(data.settings.imageSamplesDir || "").trim();
    if (!folder) {
      return { ok: false as const, message: "Select an Image Samples folder first (Settings → Image)" };
    }
    const listed = await window.mgApi.imageSamplesList({ folderPath: folder });
    if ("message" in listed) return { ok: false as const, message: listed.message };
    if (!listed.items.length) return { ok: false as const, message: "No images found in the selected Image Samples folder" };

    if (manualIncludeThumbnail) {
      if (!window.mgApi?.generateThumbnailImage) {
        return { ok: false as const, message: "Thumbnail generation requires the Electron app runtime" };
      }
      if (!data.textStyles.length) {
        return { ok: false as const, message: "Text styles are empty. Generate them in Manage → Text Styles" };
      }
    }

    return { ok: true as const };
  }

  async function runManualImages() {
    if (bgGenerating || thumbnailing) return;

    const ctx = getImageContext();
    if (ctx.mode === "none" || !ctx.okDir) {
      setFooterStatus(ctx.label, null);
      return;
    }

    setBgGenerating(true);
    setBackgroundLogs([]);
    setThumbnailLogs([]);
    aiCallsRef.current = 0;
    try {
      const preflight = await preflightManualImages();
      if (!preflight.ok) {
        appendBackgroundLog(`Blocked: ${preflight.message}`);
        appendThumbnailLog(`Blocked: ${preflight.message}`);
        setFooterStatus(preflight.message, null);
        return;
      }

      const pairs: Array<{ side: ImageSide; outDir: string }> =
        manualGenerateBoth && ctx.mode === "batch" && ctx.altDir
          ? [{ side: "ok", outDir: ctx.okDir }, { side: "alt", outDir: ctx.altDir }]
          : [{ side: "ok", outDir: ctx.okDir }];

      const plannedBackgrounds = pairs.length;
      const plannedThumbnails = manualIncludeThumbnail ? pairs.length : 0;
      const plannedAiCalls = plannedBackgrounds + plannedThumbnails;
      appendBackgroundLog(`Plan: backgrounds=${plannedBackgrounds}, thumbnails=${plannedThumbnails}, AI calls≈${plannedAiCalls}`);
      appendThumbnailLog(`Plan: thumbnails=${plannedThumbnails}`);

      for (const p of pairs) {
        const bg = await generateBackgroundForSide(p.side, { outDir: p.outDir, outFileName: "background.png", setAsCurrent: true });
        if (!bg) continue;
        if (manualIncludeThumbnail) {
          setThumbnailing(true);
          try {
            await generateThumbnailForSide(p.side, { bgPath: bg.filePath, outDir: p.outDir, outFileName: "thumbnail.png", setAsCurrent: true });
          } finally {
            setThumbnailing(false);
          }
        }
      }
      appendBackgroundLog(`AI calls used: ${aiCallsRef.current}`);
      appendThumbnailLog(`AI calls used: ${aiCallsRef.current}`);
      setFooterStatus(manualIncludeThumbnail ? "Image + Thumbnail saved" : "Image saved", 100);
      setTimeout(() => setFooterStatus("Ready", null), 1600);
    } finally {
      setBgGenerating(false);
    }
  }

  async function regenerateBackgroundSelected() {
    if (bgGenerating || thumbnailing) return;
    if (!selectedBackgroundPath) return;
    if (!window.mgApi?.generateBackgroundImage) return;

    const ctx = getImageContext();
    if (ctx.mode === "none") return;

    const outDir = getDirName(selectedBackgroundPath);
    const outFileName = getBaseName(selectedBackgroundPath);
    const side: ImageSide = ctx.mode === "batch" && ctx.altDir && selectedBackgroundPath.toLowerCase().startsWith(ctx.altDir.toLowerCase()) ? "alt" : "ok";

    setBgGenerating(true);
    setBackgroundLogs([]);
    try {
      await generateBackgroundForSide(side, { outDir, outFileName, setAsCurrent: true });
      setFooterStatus("Background regenerated", 100);
      setTimeout(() => setFooterStatus("Ready", null), 1600);
    } finally {
      setBgGenerating(false);
    }
  }

  async function regenerateThumbnailSelected() {
    if (bgGenerating || thumbnailing) return;
    if (!selectedThumbnailPath) return;

    const ctx = getImageContext();
    if (ctx.mode === "none") return;

    const outDir = getDirName(selectedThumbnailPath);
    const outFileName = getBaseName(selectedThumbnailPath);
    const rootDir = getRunRootFromChildDir(outDir);
    const bgPath = joinPath(rootDir, "background.png");
    const side: ImageSide = ctx.mode === "batch" && ctx.altDir && selectedThumbnailPath.toLowerCase().startsWith(ctx.altDir.toLowerCase()) ? "alt" : "ok";

    setThumbnailing(true);
    setThumbnailLogs([]);
    try {
      await generateThumbnailForSide(side, { bgPath, outDir, outFileName, setAsCurrent: true });
      setFooterStatus("Thumbnail regenerated", 100);
      setTimeout(() => setFooterStatus("Ready", null), 1600);
    } finally {
      setThumbnailing(false);
    }
  }

  async function autoGenerateImagesForBatch(batchId: string) {
    if (!window.mgApi?.sunoGetBatchRunDirs) return;
    if (!data.settings.autoGSuno) return;

    const dirs = await window.mgApi.sunoGetBatchRunDirs(batchId);
    if ("message" in dirs) return;
    const okDir = dirs.okDir;
    const altDir = dirs.altDir;
    if (!okDir || !altDir) return;
    if (!window.mgApi?.generateBackgroundImage) return;

    for (const side of ["ok", "alt"] as const) {
      const outDir = side === "ok" ? okDir : altDir;
      const prep = await buildBackgroundPrompt("samples");
      if (!prep.ok) return;

      const bg = await window.mgApi.generateBackgroundImage({
        prompt: prep.prompt,
        sampleFilePath: prep.sampleFilePath ?? "",
        resolution: data.settings.imageResolution,
        outputDir: outDir,
        outputFileName: "background.png",
      });
      if (!("filePath" in bg)) return;

      const bgPath = bg.filePath;
      const thumb = await generateThumbnailForSide(side, { bgPath, outDir, outFileName: "thumbnail.png", setAsCurrent: false });
      if (!thumb) return;

      await addHistory({ path: bgPath, task: `auto background generated (${side.toUpperCase()} · ${batchId})`, status: "ok", kind: "thumbnail" });
      await addHistory({
        path: thumb.filePath,
        task: `auto thumbnail generated (${side.toUpperCase()} · ${batchId})`,
        status: "ok",
        kind: "thumbnail",
      });
    }
  }

  function enqueueAutoImageForBatch(batchId: string) {
    const key = String(batchId || "").trim();
    if (!key) return;
    if (autoImageRequestedBatches.current.has(key)) return;
    autoImageRequestedBatches.current.add(key);
    autoImageQueue.current = autoImageQueue.current.then(() => autoGenerateImagesForBatch(key)).catch(() => autoGenerateImagesForBatch(key));
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopToolbar title="Music Generator" variant="titleOnly" />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <AppSidebar section={mainTab} onSectionChange={setMainTab} />
        <div className="min-w-0 flex-1 overflow-hidden">
        {mainTab === "music" ? (
          <Tabs value={musicTab} onValueChange={(v) => setMusicTab(v as typeof musicTab)}>
            <div className="flex h-full min-h-0 flex-col overflow-hidden">
              <TopToolbar
                variant="tabsOnly"
                tabs={[
                  { value: "composer", label: "Music" },
                  { value: "descriptions", label: "Descriptions" },
                  { value: "structures", label: "Structures" },
                  { value: "suno", label: "Suno" },
                  { value: "pools", label: "Pools" },
                  { value: "generation", label: "Generation" },
                ]}
              />
              <div className="min-h-0 flex-1 overflow-hidden p-3">
                  <TabsContent value="composer" className="mt-0 h-full min-h-0">
                    <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden">
                      <MusicControlsBar
                        runFromDate={runFromDate}
                        runToDate={runToDate}
                        onRunFromDateChange={setRunFromDate}
                        onRunToDateChange={setRunToDate}
                        description={currentDescription}
                        onDescriptionChange={setCurrentDescription}
                        onLoadDescription={() => setMusicTab("descriptions")}
                        onSelectAllDescription={() => {
                          if (data.settings.activeDescriptionIds.length) return;
                          updateSettings({
                            enabledDescriptionIds:
                              enabledDescriptionIds.length === data.descriptions.length ? [] : data.descriptions.map((x) => x.id),
                          });
                        }}
                        shuffleDescription={data.settings.activeDescriptionIds.length ? false : data.settings.shuffleDescription}
                        onShuffleDescriptionChange={(v) => {
                          if (data.settings.activeDescriptionIds.length) return;
                          updateSettings({ shuffleDescription: v });
                        }}
                        allDescriptionsSelected={
                          !data.settings.activeDescriptionIds.length &&
                          enabledDescriptionIds.length === data.descriptions.length &&
                          data.descriptions.length > 0
                        }
                        matchDescriptionStructure={data.settings.matchDescriptionStructure}
                        onMatchDescriptionStructureChange={(v) =>
                          updateSettings({ matchDescriptionStructure: v, cycleStructures: v ? false : data.settings.cycleStructures })
                        }
                        structure={currentStructure}
                        onStructureChange={setCurrentStructure}
                        onLoadStructure={() => setMusicTab("structures")}
                        onSelectAllStructure={() => {
                          if (data.settings.activeStructureIds.length) return;
                          updateSettings({
                            enabledStructureIds:
                              enabledStructureIds.length === data.structures.length ? [] : data.structures.map((x) => x.id),
                          });
                        }}
                        shuffleStructure={
                          data.settings.activeStructureIds.length || data.settings.cycleStructures || data.settings.matchDescriptionStructure
                            ? false
                            : data.settings.shuffleStructure
                        }
                        onShuffleStructureChange={(v) => {
                          if (data.settings.activeStructureIds.length) return;
                          if (data.settings.cycleStructures) return;
                          if (data.settings.matchDescriptionStructure) return;
                          updateSettings({ shuffleStructure: v });
                        }}
                        cycleStructures={data.settings.cycleStructures}
                        onCycleStructuresChange={(v) => {
                          if (data.settings.matchDescriptionStructure) return;
                          updateSettings({ cycleStructures: v, shuffleStructure: v ? false : data.settings.shuffleStructure });
                        }}
                        allStructuresSelected={
                          !data.settings.activeStructureIds.length &&
                          enabledStructureIds.length === data.structures.length &&
                          data.structures.length > 0
                        }
                        language={data.settings.language}
                        onLanguageChange={(v) => updateSettings({ language: v as typeof data.settings.language })}
                        creativity={data.settings.creativity}
                        onCreativityChange={(v) => updateSettings({ creativity: v })}
                        uniqueOpening={data.settings.uniqueOpening}
                        onUniqueOpeningChange={(v) => updateSettings({ uniqueOpening: v })}
                        strictLevel={data.settings.strictLevel}
                        onStrictLevelChange={(v) => updateSettings({ strictLevel: v })}
                        uniquenessHistoryWindow={data.settings.uniquenessHistoryWindow}
                        onUniquenessHistoryWindowChange={(v) => updateSettings({ uniquenessHistoryWindow: v })}
                        sort={data.settings.sort}
                        onSortChange={(v) => updateSettings({ sort: v })}
                        defaultSongCount={data.settings.defaultSongCount}
                        onDefaultSongCountChange={(v) => {
                          updateSettings({ defaultSongCount: v });
                          setFooterStatus(`Saved: Default song count = ${v}`, 100);
                          setTimeout(() => setFooterStatus("Ready", null), 1600);
                        }}
                        shuffle={data.settings.shuffle}
                        onToggleShuffle={() => updateSettings({ shuffle: !data.settings.shuffle })}
                        profiles={data.profiles}
                        channelOkProfileIds={data.settings.channelOkProfileIds}
                        channelAltProfileIds={data.settings.channelAltProfileIds}
                        onChannelOkProfileIdsChange={(ids) =>
                          updateSettings({
                            channelOkProfileIds: ids,
                            activeProfileId: ids[0] ?? null,
                            activeProfileOkId: ids[0] ?? null,
                            activeProfileAltId:
                              ids[0] && data.settings.activeProfileAltId === ids[0] ? null : data.settings.activeProfileAltId,
                          })
                        }
                        onChannelAltProfileIdsChange={(ids) =>
                          updateSettings({
                            channelAltProfileIds: ids,
                            activeProfileAltId: ids[0] ?? null,
                          })
                        }
                        generating={generating}
                        onStop={stopAllGeneration}
                        onGenerate={async () => {
                          if (generating) return;
                          const draftProvider = data.settings.songDraftProvider ?? "deepseek";
                          if (draftProvider === "slai" && !String(data.settings.slaiSongApiKey || "").trim()) {
                            console.error("[ui] Missing SLAI Song API key");
                            setFooterStatus("SLAI Song API key is missing. Set it in Settings → API.", null);
                            return;
                          }
                          const okIds = (data.settings.channelOkProfileIds?.length ? data.settings.channelOkProfileIds : []).filter((id) =>
                            data.profiles.some((p) => p.id === id),
                          );
                          const altIds = (data.settings.channelAltProfileIds?.length ? data.settings.channelAltProfileIds : []).filter((id) =>
                            data.profiles.some((p) => p.id === id),
                          );
                          if (!okIds.length || !altIds.length || okIds.length !== altIds.length) {
                            setFooterStatus("Select the same number of OK and ALT channels before generating", null);
                            return;
                          }
                          if (!runFromDate || !runToDate) {
                            setFooterStatus("Select a From and To date", null);
                            return;
                          }

                          const parseYmd = (s: string) => {
                            const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s || "").trim());
                            if (!m) return null;
                            const y = Number(m[1]);
                            const mm = Number(m[2]);
                            const dd = Number(m[3]);
                            if (!Number.isFinite(y) || !Number.isFinite(mm) || !Number.isFinite(dd)) return null;
                            const d = new Date(y, mm - 1, dd);
                            if (Number.isNaN(d.getTime())) return null;
                            return d;
                          };
                          const start = parseYmd(runFromDate);
                          const end = parseYmd(runToDate);
                          if (!start || !end) {
                            setFooterStatus("Invalid date range", null);
                            return;
                          }
                          if (start.getTime() > end.getTime()) {
                            setFooterStatus("From date must be before To date", null);
                            return;
                          }

                          const dateList: string[] = [];
                          for (
                            let d = new Date(start.getTime());
                            d.getTime() <= end.getTime();
                            d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1)
                          ) {
                            const yyyy = d.getFullYear();
                            const mm = String(d.getMonth() + 1).padStart(2, "0");
                            const dd = String(d.getDate()).padStart(2, "0");
                            dateList.push(`${yyyy}-${mm}-${dd}`);
                          }
                          if (!dateList.length) {
                            setFooterStatus("No days selected", null);
                            return;
                          }

                          cancelRequested.current = false;
                          generateJobIds.current.clear();
                          setRunning(true);
                          const songsPerBatch = Math.max(1, data.settings.defaultSongCount || 1);
                          const totalBatches = dateList.length * okIds.length;
                          const totalSongs = totalBatches * songsPerBatch;

                          const maxAttempts = totalSongs + Math.min(10, Math.ceil(totalSongs * 0.5));
                          batchRunRef.current = {
                            batchId: "multi",
                            expected: totalSongs,
                            attempted: 0,
                            completed: 0,
                            failed: 0,
                            cancelled: 0,
                            failures: [],
                            maxAttempts,
                          };
                          setFooterStatus(`Generating 0/${totalSongs} songs saved`, 0);

                          const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] as const;
                          const toRunLabel = (ymd: string) => {
                            const d = parseYmd(ymd);
                            if (!d) return ymd;
                            const mon = months[d.getMonth()] ?? "May";
                            const day = String(d.getDate()).padStart(2, "0");
                            const yy = String(d.getFullYear()).slice(-2);
                            return `${mon}-${day}-${yy}`;
                          };

                          for (const ymd of dateList) {
                            const sunoRunLabel = toRunLabel(ymd);
                            for (let pairIndex = 0; pairIndex < okIds.length; pairIndex += 1) {
                              const batchId = `batch-${new Date().toISOString()}`;
                              const profileOkId = okIds[pairIndex];
                              const profileAltId = altIds[pairIndex];
                              for (let i = 0; i < songsPerBatch; i += 1) {
                                if (cancelRequested.current) break;
                                let finalDescription = currentDescription;
                                let finalStructure = currentStructure;
                                let descriptionTitle = finalDescription.trim() ? "Custom" : "";
                                let structureTitle = finalStructure.trim() ? "Custom" : "";

                                if (data.settings.matchDescriptionStructure) {
                                  const pickDescBase = data.settings.activeDescriptionIds.length
                                    ? data.descriptions.filter((d) => data.settings.activeDescriptionIds.includes(d.id))
                                    : enabledDescriptionIds.length
                                      ? data.descriptions.filter((d) => enabledDescriptionIds.includes(d.id))
                                      : data.descriptions;
                                  const pickStructBase = data.settings.activeStructureIds.length
                                    ? data.structures.filter((s) => data.settings.activeStructureIds.includes(s.id))
                                    : enabledStructureIds.length
                                      ? data.structures.filter((s) => enabledStructureIds.includes(s.id))
                                      : data.structures;

                                  const structuresById = new Map(pickStructBase.map((s) => [s.id, s] as const));
                                  const matchedDescriptions = pickDescBase.filter((d) => {
                                    const key = normalizeMatchKey(d.matchKey ?? "");
                                    if (!key) return false;
                                    return structuresById.has(key);
                                  });
                                  const pickedDescription = pickRandom(matchedDescriptions);
                                  if (!pickedDescription) {
                                    setFooterStatus("Match is ON but no matched pairs found. In Descriptions, pick a Match structure.", null);
                                    cancelRequested.current = true;
                                    break;
                                  }

                                  const structId = normalizeMatchKey(pickedDescription.matchKey ?? "");
                                  const pickedStructure = structuresById.get(structId) ?? null;
                                  if (!pickedStructure) {
                                    setFooterStatus("Match is ON but the selected description has no matching structure. Check Match structure.", null);
                                    cancelRequested.current = true;
                                    break;
                                  }

                                  finalDescription = pickedDescription.content;
                                  finalStructure = pickedStructure.content;
                                  descriptionTitle = pickedDescription.name;
                                  structureTitle = pickedStructure.name;
                                  setCurrentDescription(finalDescription);
                                  setCurrentStructure(finalStructure);
                                } else {
                                  const activeDescriptionItem = pickActiveItem(data.descriptions, data.settings.activeDescriptionIds);
                                  const shuffleDescriptionItem = data.settings.shuffleDescription
                                    ? pickFromPoolItem(data.descriptions, enabledDescriptionIds)
                                    : null;

                                  const effectiveDescription = shuffleDescriptionItem ? shuffleDescriptionItem.content : currentDescription;
                                  finalDescription = activeDescriptionItem ? activeDescriptionItem.content : effectiveDescription;

                                  descriptionTitle = activeDescriptionItem
                                    ? activeDescriptionItem.name
                                    : shuffleDescriptionItem
                                      ? shuffleDescriptionItem.name
                                      : finalDescription.trim()
                                        ? "Custom"
                                        : "";

                                  if (!activeDescriptionItem && data.settings.shuffleDescription && shuffleDescriptionItem?.content) {
                                    setCurrentDescription(shuffleDescriptionItem.content);
                                  }

                                  if (data.settings.cycleStructures) {
                                    const structurePool = data.settings.activeStructureIds.length
                                      ? data.structures.filter((s) => data.settings.activeStructureIds.includes(s.id))
                                      : enabledStructureIds.length
                                        ? data.structures.filter((s) => enabledStructureIds.includes(s.id))
                                        : data.structures;
                                    const cycleItem = structurePool.length ? structurePool[i % structurePool.length] : null;
                                    finalStructure = cycleItem ? cycleItem.content : currentStructure;
                                    structureTitle = cycleItem ? cycleItem.name : finalStructure.trim() ? "Custom" : "";
                                    if (cycleItem?.content) setCurrentStructure(cycleItem.content);
                                  } else {
                                    const activeStructureItem = pickActiveItem(data.structures, data.settings.activeStructureIds);
                                    const shuffleStructureItem = data.settings.shuffleStructure ? pickFromPoolItem(data.structures, enabledStructureIds) : null;
                                    const effectiveStructure = shuffleStructureItem ? shuffleStructureItem.content : currentStructure;
                                    finalStructure = activeStructureItem ? activeStructureItem.content : effectiveStructure;
                                    structureTitle = activeStructureItem
                                      ? activeStructureItem.name
                                      : shuffleStructureItem
                                        ? shuffleStructureItem.name
                                        : finalStructure.trim()
                                          ? "Custom"
                                          : "";
                                    if (!activeStructureItem && data.settings.shuffleStructure && shuffleStructureItem?.content) {
                                      setCurrentStructure(shuffleStructureItem.content);
                                    }
                                  }
                                }

                                try {
                                  const enq = await jobClient.enqueue({
                                    jobType: "workflow",
                                    action: "generate",
                                    description: finalDescription,
                                    structure: finalStructure,
                                    descriptionTitle,
                                    structureTitle,
                                    language: data.settings.language,
                                    creativity: data.settings.creativity,
                                    songDraftProvider: data.settings.songDraftProvider,
                                    deepseekApiKey: data.settings.deepseekApiKey,
                                    openaiApiKey: data.settings.openaiApiKey,
                                    slaiSongApiKey: data.settings.slaiSongApiKey,
                                    slaiSongModel: data.settings.slaiSongModel,
                                    batchId,
                                    batchIndex: i + 1,
                                    uniqueOpening: data.settings.uniqueOpening,
                                    strictLevel: data.settings.strictLevel,
                                    uniquenessHistoryWindow: data.settings.uniquenessHistoryWindow,
                                    sunoAutoSubmit: data.settings.autoGSuno,
                                    profileOkId,
                                    profileAltId,
                                    sunoRunLabel,
                                  });
                                  console.log("[ui] enqueued generate job", { jobId: enq.jobId, batchId });
                                  generateJobIds.current.add(enq.jobId);
                                  if (batchRunRef.current) batchRunRef.current.attempted += 1;
                                } catch (e) {
                                  const msg = e instanceof Error ? e.message : "failed to enqueue generate job";
                                  console.error("[ui] enqueue generate failed", e);
                                  setFooterStatus(`Failed to enqueue: ${msg}`, null);
                                  cancelRequested.current = true;
                                  break;
                                }
                              }
                              if (data.settings.autoGenImage) {
                                enqueueAutoImageForBatch(batchId);
                              }
                              if (cancelRequested.current) break;
                            }
                            if (cancelRequested.current) break;
                          }
                          setRunning(false);

                          if (data.settings.autoGSuno) {
                            setSunoStatus(`Suno: auto-submit enabled · submitting as songs are generated`);
                          }

                          if (data.settings.autoGenImage) {
                            appendBackgroundLog("Auto Image: queued per batch");
                            appendThumbnailLog("Auto Image: queued per batch");
                          }
                        }}
                      />

                      <div className="grid min-h-0 flex-1 grid-cols-[470px_1fr] gap-3 overflow-hidden">
                        <div className="min-h-0 overflow-hidden">
                          <LeftSidebar
                            effects={effects}
                            song={currentSong}
                            drafts={data.songDrafts}
                            onDraftChange={(id, patch) => updateSongDraft(id, patch)}
                            onPolishLyrics={async (strength) => {
                              if (!currentSong) return;
                              setFooterStatus("Polishing lyrics...", 20);
                              const base = currentSong.lyricsPolished || currentSong.lyricsRaw;
                              if (window.mgApi?.polishLyrics) {
                                const res = await window.mgApi.polishLyrics({
                                  lyrics: base,
                                  strength,
                                  apiKey: data.settings.openaiApiKey || undefined,
                                });
                                if (res.ok) {
                                  await updateSong(currentSong.id, { lyricsPolished: res.lyrics });
                                  setFooterStatus("Polished", 100);
                                } else if ("message" in res) {
                                  setFooterStatus(res.message, null);
                                }
                              } else {
                                const cleaned = base.replace(/\s+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
                                await updateSong(currentSong.id, { lyricsPolished: cleaned });
                                setFooterStatus("Polished (local)", 100);
                              }
                              setTimeout(() => setFooterStatus("Ready", null), 1800);
                            }}
                            autoGenImage={data.settings.autoGenImage}
                            autoGSuno={data.settings.autoGSuno}
                            onAutoGenImageChange={(v) => updateSettings({ autoGenImage: v })}
                            onAutoGSunoChange={(v) => updateSettings({ autoGSuno: v })}
                          />
                        </div>

                        <div className="flex min-h-0 min-w-0 flex-col overflow-hidden">
                          <HistoryPanel
                            lastBatchOnly={lastBatchOnly}
                            onLastBatchOnlyChange={setLastBatchOnly}
                            fromDate={fromDate}
                            toDate={toDate}
                            onFromDateChange={setFromDate}
                            onToDateChange={setToDate}
                            onShowAll={() => {
                              setFromDate("");
                              setToDate("");
                            }}
                            onRetrySuno={async (song) => {
                              if (!String(data.settings.sunoApiKey || "").trim()) {
                                setFooterStatus("Suno API key is missing. Set it in Music → Suno.", null);
                                return;
                              }
                              const profileOkId = song.profileOkId || data.settings.channelOkProfileIds[0] || data.settings.activeProfileOkId || null;
                              const profileAltId =
                                song.profileAltId || data.settings.channelAltProfileIds[0] || data.settings.activeProfileAltId || null;
                              if (!profileOkId) {
                                setFooterStatus("Select an OK channel first (Music tab)", null);
                                return;
                              }
                              setSunoStatus(`Suno: queued · retry ${song.title}`);
                              await jobClient.enqueue({
                                jobType: "suno",
                                batchId: song.batchId ?? `song-${song.id}`,
                                expectedCount: 1,
                                songs: [song],
                                version: data.settings.sunoDefaultVersion,
                                profileOkId,
                                profileAltId: profileAltId ?? undefined,
                              });
                            }}
                            onOpenSongFolder={async (song) => {
                              try {
                                const r = await window.mgApi?.sunoGetSongOutputDirs(song.id);
                                if (!r) {
                                  setFooterStatus("Electron bridge not available", null);
                                  return;
                                }
                                if (r.ok === false) {
                                  setFooterStatus(r.message || "Failed to locate Suno output directory", null);
                                  return;
                                }
                                const dir = r.okDir || r.altDir;
                                if (!dir) {
                                  setFooterStatus("No output directory recorded for this song yet", null);
                                  return;
                                }
                                await window.mgApi?.openPath(dir);
                              } catch {
                                const base = String(data.settings.sunoOutputDir || "").trim();
                                if (base) await window.mgApi?.openPath(base);
                                else setFooterStatus("Restart the Electron app to enable the folder button", null);
                              }
                            }}
                            onSelectRow={(songId) => {
                              setCurrentSongId(songId);
                              const found = data.songs.find((s) => s.id === songId);
                              if (found) {
                                updateSongDraft("draft-01", { title: found.title, album: found.album });
                                setCurrentDescription(found.songDescription || "");
                                setCurrentStructure(found.songStructure || "");
                              }
                            }}
                            selectedSongId={currentSongId}
                            rows={historyRows}
                          />
                        </div>
                      </div>
                    </div>
                  </TabsContent>

                  <TabsContent value="descriptions" className="mt-0 h-full min-h-0">
                    <div className="h-full min-h-0 overflow-auto rounded-xl border border-slate-200/10 bg-slate-950/20 p-3">
                      <SavedTextsTab
                        kind="descriptions"
                        title="Song Descriptions"
                        onLoad={(text) => {
                          setCurrentDescription(text);
                          setMusicTab("composer");
                        }}
                      />
                    </div>
                  </TabsContent>

                  <TabsContent value="structures" className="mt-0 h-full min-h-0">
                    <div className="h-full min-h-0 overflow-auto rounded-xl border border-slate-200/10 bg-slate-950/20 p-3">
                      <SavedTextsTab
                        kind="structures"
                        title="Song Structures"
                        onLoad={(text) => {
                          setCurrentStructure(text);
                          setMusicTab("composer");
                        }}
                      />
                    </div>
                  </TabsContent>

                  <TabsContent value="suno" className="mt-0 h-full min-h-0">
                    <div className="h-full min-h-0 overflow-hidden">
                      <SettingsPanel mode="page" tab="automation" allowedTabs={["automation"]} hideTabsList />
                    </div>
                  </TabsContent>

                  <TabsContent value="pools" className="mt-0 h-full min-h-0">
                    <div className="h-full min-h-0 overflow-hidden rounded-xl border border-slate-200/10 bg-slate-950/20 p-3">
                      <PhrasePoolsTab />
                    </div>
                  </TabsContent>

                  <TabsContent value="generation" className="mt-0 h-full min-h-0">
                    <div className="h-full min-h-0 overflow-hidden">
                      <SettingsPanel mode="page" tab="generation" allowedTabs={["generation"]} hideTabsList />
                    </div>
                  </TabsContent>
              </div>
            </div>
          </Tabs>
        ) : mainTab === "image" ? (
          <Tabs value={imageTab} onValueChange={(v) => setImageTab(v as typeof imageTab)}>
            <div className="flex h-full min-h-0 flex-col overflow-hidden">
              <TopToolbar
                variant="tabsOnly"
                tabs={[
                  { value: "preview", label: "Preview" },
                  { value: "templates", label: "Templates" },
                  { value: "text", label: "Text Styles" },
                  { value: "refs", label: "Reference Images" },
                  { value: "cars", label: "Car Catalog" },
                  { value: "settings", label: "Image Settings" },
                ]}
              />
              <div className="min-h-0 flex-1 overflow-hidden p-3">
                  <TabsContent value="preview" className="mt-0 h-full min-h-0">
                    <div className="flex h-full min-h-0 flex-col">
                      <ImagePanel
                        contextLabel={getImageContext().label}
                        backgroundPreviewUrl={backgroundItems.find((x) => x.filePath === selectedBackgroundPath)?.fileUrl ?? null}
                        backgroundItems={backgroundItems}
                        selectedBackgroundPath={selectedBackgroundPath}
                        onSelectBackground={setSelectedBackgroundPath}
                        backgroundLogs={backgroundLogs}
                        thumbnailPreviewUrl={thumbnailItems.find((x) => x.filePath === selectedThumbnailPath)?.fileUrl ?? null}
                        thumbnailItems={thumbnailItems}
                        selectedThumbnailPath={selectedThumbnailPath}
                        onSelectThumbnail={setSelectedThumbnailPath}
                        thumbnailLogs={thumbnailLogs}
                        manualGenerateBoth={manualGenerateBoth}
                        onManualGenerateBothChange={setManualGenerateBoth}
                        canManualGenerateBoth={getImageContext().mode === "batch" && Boolean(getImageContext().altDir)}
                        manualIncludeThumbnail={manualIncludeThumbnail}
                        onManualIncludeThumbnailChange={setManualIncludeThumbnail}
                        onRunManual={runManualImages}
                        onRegenerateBackground={regenerateBackgroundSelected}
                        thumbnailActionLabel={thumbnailItems.length ? "Regenerate" : "Generate"}
                        onThumbnailAction={generateThumbnailFromSelectedSource}
                        onPickThumbnailSource={pickThumbnailSource}
                        thumbnailSourceLabel={thumbnailSourcePath ? getBaseName(thumbnailSourcePath) : ""}
                        running={bgGenerating || thumbnailing}
                        canRun={getImageContext().mode !== "none"}
                        canRegenerateBackground={getImageContext().mode !== "none" && Boolean(selectedBackgroundPath)}
                        canThumbnailAction={getImageContext().mode !== "none" && Boolean(thumbnailSourcePath)}
                      />
                    </div>
                  </TabsContent>

                  <TabsContent value="templates" className="mt-0 h-full min-h-0">
                    <div className="h-full min-h-0 overflow-hidden rounded-xl border border-slate-200/10 bg-slate-950/20 p-3">
                      <PromptTemplatesTab />
                    </div>
                  </TabsContent>

                  <TabsContent value="text" className="mt-0 h-full min-h-0">
                    <div className="h-full min-h-0 overflow-hidden rounded-xl border border-slate-200/10 bg-slate-950/20 p-3">
                      <TextStylesTab />
                    </div>
                  </TabsContent>

                  <TabsContent value="refs" className="mt-0 h-full min-h-0">
                    <div className="h-full min-h-0 overflow-hidden rounded-xl border border-slate-200/10 bg-slate-950/20 p-3">
                      <ImageSamplesTab />
                    </div>
                  </TabsContent>

                  <TabsContent value="cars" className="mt-0 h-full min-h-0">
                    <div className="h-full min-h-0 overflow-hidden rounded-xl border border-slate-200/10 bg-slate-950/20 p-3">
                      <CarModelsTab />
                    </div>
                  </TabsContent>

                  <TabsContent value="settings" className="mt-0 h-full min-h-0">
                    <div className="h-full min-h-0 overflow-hidden">
                      <SettingsPanel mode="page" tab="image" allowedTabs={["image"]} hideTabsList />
                    </div>
                  </TabsContent>
              </div>
            </div>
          </Tabs>
        ) : mainTab === "merger" ? (
          <Tabs value={mergerTab} onValueChange={(v) => setMergerTab(v as typeof mergerTab)}>
            <div className="flex h-full min-h-0 flex-col overflow-hidden">
              <TopToolbar variant="tabsOnly" tabs={[{ value: "merge", label: "Merge" }]} />
              <div className="min-h-0 flex-1 overflow-hidden p-3">
                  <TabsContent value="merge" className="mt-0 h-full min-h-0">
                    <div className="flex h-full min-h-0 flex-col">
                      <VideoPanel
                        videoMergeDirs={data.settings.videoMergeDirectories}
                        videoExport={data.settings.videoExport}
                        onVideoExportChange={(patch) => {
                          const next: VideoExportSettings = {
                            ...data.settings.videoExport,
                            ...patch,
                            crf: clamp(Number((patch as { crf?: unknown }).crf ?? data.settings.videoExport.crf), 10, 40),
                          };
                          updateSettings({ videoExport: next });
                        }}
                        onSelectVideoMergeDirs={async () => {
                          if (!window.mgApi?.pickDirectories) return;
                          const r = await window.mgApi.pickDirectories({ title: "Select directories to merge" });
                          if (!("paths" in r)) return;
                          const next = Array.from(new Set([...(data.settings.videoMergeDirectories ?? []), ...(r.paths ?? [])]));
                          updateSettings({ videoMergeDirectories: next });
                        }}
                        onRemoveVideoMergeDir={(dir) =>
                          updateSettings({ videoMergeDirectories: (data.settings.videoMergeDirectories ?? []).filter((d) => d !== dir) })
                        }
                        onClearVideoMergeDirs={() => updateSettings({ videoMergeDirectories: [] })}
                        onMergeVideos={async () => {
                          if (!window.mgApi?.videoMergeStart) return;
                          const dirs = data.settings.videoMergeDirectories ?? [];
                          setVideoMergeState({ runId: null, running: true, total: dirs.length, rows: {} });
                          const r = await window.mgApi.videoMergeStart({ directories: dirs, exportSettings: data.settings.videoExport });
                          if ("message" in r) {
                            setVideoMergeState((s) => ({ ...s, running: false }));
                            setFooterStatus(r.message, null);
                          }
                        }}
                        mergeRunning={videoMergeState.running}
                        mergeProgress={{
                          done: Object.values(videoMergeState.rows).filter((x) => x.status === "done" || x.status === "failed").length,
                          total: videoMergeState.total || (data.settings.videoMergeDirectories ?? []).length,
                        }}
                        mergeRows={(data.settings.videoMergeDirectories ?? []).map((dir) =>
                          videoMergeState.rows[dir] ?? { directory: dir, status: "pending", message: "Pending" },
                        )}
                      />
                    </div>
                  </TabsContent>
              </div>
            </div>
          </Tabs>
        ) : mainTab === "settings" ? (
          <Tabs value={settingsTab} onValueChange={(v) => setSettingsTab(v as typeof settingsTab)}>
            <div className="flex h-full min-h-0 flex-col overflow-hidden">
              <TopToolbar
                variant="tabsOnly"
                tabs={[
                  { value: "api", label: "API" },
                  { value: "profiles", label: "Profiles" },
                  { value: "paths", label: "Paths" },
                  { value: "database", label: "Database" },
                ]}
              />
              <div className="min-h-0 flex-1 overflow-hidden p-3">
                  <TabsContent value="api" className="mt-0 h-full min-h-0">
                    <SettingsPanel mode="page" tab="api" allowedTabs={["api"]} hideTabsList />
                  </TabsContent>
                  <TabsContent value="profiles" className="mt-0 h-full min-h-0">
                    <SettingsPanel mode="page" tab="profiles" allowedTabs={["profiles"]} hideTabsList />
                  </TabsContent>
                  <TabsContent value="paths" className="mt-0 h-full min-h-0">
                    <SettingsPanel mode="page" tab="paths" allowedTabs={["paths"]} hideTabsList />
                  </TabsContent>
                  <TabsContent value="database" className="mt-0 h-full min-h-0">
                    <SettingsPanel mode="page" tab="db" allowedTabs={["db"]} hideTabsList />
                  </TabsContent>
              </div>
            </div>
          </Tabs>
        ) : (
          <Tabs value={videoTab} onValueChange={(v) => setVideoTab(v as typeof videoTab)}>
            <div className="flex h-full min-h-0 flex-col overflow-hidden">
              <TopToolbar
                variant="tabsOnly"
                tabs={[
                  { value: "render", label: "Render" },
                  { value: "spectrum", label: "Spectrum" },
                ]}
              />
              <div className="min-h-0 flex-1 overflow-hidden p-3">
                <TabsContent value="render" className="mt-0 h-full min-h-0">
                  <VideoRenderPanel
                    mode={videoRenderMode}
                    mp3Path={videoRenderMp3Path}
                    templatePath={data.settings.videoRenderTemplatePath ?? ""}
                    templates={videoTemplates}
                    backgroundPath={data.settings.videoRenderBackgroundPath ?? ""}
                    outputDir={data.settings.videoRenderOutputDir ?? ""}
                    running={videoRenderState.running}
                    message={videoRenderState.message}
                    progress={videoRenderState.progress}
                    outputPath={videoRenderState.outputPath}
                    onChangeMode={setVideoRenderMode}
                    onChangeMp3Path={(v) => setVideoRenderMp3Path(v)}
                    onPickMp3Path={async () => {
                      if (!window.mgApi?.pickPath) {
                        setFooterStatus("File picker is only available in the Electron app", null);
                        return;
                      }
                      const r = await window.mgApi.pickPath({
                        kind: "file",
                        title: "Select MP3",
                        filters: [{ name: "MP3", extensions: ["mp3"] }],
                      });
                      if ("path" in r) setVideoRenderMp3Path(r.path);
                    }}
                    onChangeTemplatePath={(v) => updateSettings({ videoRenderTemplatePath: v })}
                    onReloadTemplates={reloadVideoTemplates}
                    onChangeBackgroundPath={(v) => updateSettings({ videoRenderBackgroundPath: v })}
                    onPickBackgroundPath={async () => {
                      if (!window.mgApi?.pickPath) {
                        setFooterStatus("File picker is only available in the Electron app", null);
                        return;
                      }
                      const r = await window.mgApi.pickPath({
                        kind: "file",
                        title: "Select background image",
                        filters: [{ name: "Images", extensions: ["png", "jpg", "jpeg"] }],
                      });
                      if ("path" in r) await updateSettings({ videoRenderBackgroundPath: r.path });
                    }}
                    onChangeOutputDir={(v) => updateSettings({ videoRenderOutputDir: v })}
                    onPickOutputDir={async () => {
                      if (!window.mgApi?.pickPath) {
                        setFooterStatus("File picker is only available in the Electron app", null);
                        return;
                      }
                      const r = await window.mgApi.pickPath({ kind: "directory", title: "Select output directory" });
                      if ("path" in r) await updateSettings({ videoRenderOutputDir: r.path });
                    }}
                    onStart={async () => {
                      if (!window.mgApi?.videoRenderStart) return;
                      setVideoRenderState({ runId: null, running: true, message: "Starting...", progress: 0, outputPath: null });
                      const templatePath = data.settings.videoRenderTemplatePath ? data.settings.videoRenderTemplatePath : undefined;
                      const isAlt = videoRenderMp3Path.toLowerCase().includes("_alt.mp3");
                      const activeProfileId = isAlt
                        ? data.settings.activeProfileAltId ?? null
                        : data.settings.activeProfileOkId ?? data.settings.activeProfileId ?? null;
                      const logoPath = activeProfileId ? data.profiles.find((p) => p.id === activeProfileId)?.logoPath ?? "" : "";

                      const r =
                        videoRenderMode === "auto" && window.mgApi.videoRenderAutoLatestBatch
                          ? await window.mgApi.videoRenderAutoLatestBatch({ templatePath })
                          : await window.mgApi.videoRenderStart({
                              mp3Path: videoRenderMp3Path,
                              backgroundPath: data.settings.videoRenderBackgroundPath ?? "",
                              outputDir: data.settings.videoRenderOutputDir ?? "",
                              templatePath,
                              logoPath: logoPath ? logoPath : undefined,
                            });
                      if ("message" in r) {
                        setVideoRenderState((s) => ({ ...s, running: false, message: r.message }));
                        setFooterStatus(r.message, null);
                      } else {
                        setVideoRenderState((s) => ({ ...s, runId: r.runId }));
                      }
                    }}
                    onShowOutput={async () => {
                      if (!videoRenderState.outputPath) return;
                      if (!window.mgApi?.showItemInFolder) return;
                      await window.mgApi.showItemInFolder(videoRenderState.outputPath);
                    }}
                  />
                </TabsContent>

                <TabsContent value="spectrum" className="mt-0 h-full min-h-0">
                  <SpectrumEditor />
                </TabsContent>
                
              </div>
            </div>
          </Tabs>
        )}
        </div>
      </div>

      <div className="shrink-0">
        <AppFooter text={footerText} progress={footerProgress} sunoText={sunoStatus} />
      </div>
    </div>
  );
}
