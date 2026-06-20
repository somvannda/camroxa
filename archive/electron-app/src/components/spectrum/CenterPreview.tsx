import React, { useEffect, useRef, useState } from "react";
import { useSpectrumTemplateStore } from "@/store/spectrumTemplateStore";
import { Play, Pause, Music, Image as ImageIcon, CircleUser, Folder, Upload, SkipBack, SkipForward, Square } from "lucide-react";
import { useSpectrumAudio } from "./useSpectrumAudio";
import { SpectrumCanvas } from "./SpectrumCanvas";
import { ParticlesCanvas } from "./ParticlesCanvas";

type EngineMode =
  | "webgl_preview_python_export"
  | "webgl_preview_webgl_export"
  | "python_preview_python_export"
  | "python_preview_webgl_export";

export const CenterPreview: React.FC = () => {
  const { template, updateTemplate } = useSpectrumTemplateStore();
  const [audioPath, setAudioPath] = useState<string>(() => localStorage.getItem("mg_preview_mp3") || "");
  const [audioDirPath, setAudioDirPath] = useState<string>(() => localStorage.getItem("mg_batch_mp3_dir") || "");
  const [batchFiles, setBatchFiles] = useState<{ path: string; name: string }[]>([]);
  const [engineMode, setEngineMode] = useState<EngineMode>(() => {
    const v = String(localStorage.getItem("mg_spectrum_engine_mode") || "").trim();
    if (
      v === "webgl_preview_python_export" ||
      v === "webgl_preview_webgl_export" ||
      v === "python_preview_python_export" ||
      v === "python_preview_webgl_export"
    ) {
      return v;
    }
    return "webgl_preview_python_export";
  });

  const previewEngine: "webgl" | "python" = engineMode.startsWith("python_preview") ? "python" : "webgl";
  const exportEngine: "python" | "webgl" = engineMode.endsWith("_webgl_export") ? "webgl" : "python";

  const audioUrl = audioPath ? `mgsamples://file?path=${encodeURIComponent(audioPath)}` : null;

  const bgUrl = template.previewBackground ? `mgsamples://file?path=${encodeURIComponent(template.previewBackground)}` : null;
  const logoUrl = template.previewLogo ? `mgsamples://file?path=${encodeURIComponent(template.previewLogo)}` : null;

  const { isReady, isPlaying, currentTime, duration, togglePlay, seek, updateMetrics } = useSpectrumAudio(audioUrl);
  
  // We need a stable ref to pass the metrics down to the canvas without re-rendering it constantly
  const metricsRef = useRef({ bass: 0, mid: 0, treble: 0, kick: 0, fft: new Float32Array(64) });
  const containerRef = useRef<HTMLDivElement>(null);

  // We'll also use a ref to track the logo's dynamic scale so we can apply the bass react every frame without triggering a React re-render loop
  const logoRef = useRef<HTMLImageElement>(null);
  const bgRef = useRef<HTMLImageElement>(null);

  // Logo drag state
  const isLogoDragging = useRef(false);
  const logoDragStartPos = useRef({ x: 0, y: 0 });
  const logoStartOffset = useRef({ x: 0, y: 0 });

  const handleLogoPointerDown = (e: React.PointerEvent) => {
    isLogoDragging.current = true;
    logoDragStartPos.current = { x: e.clientX, y: e.clientY };
    logoStartOffset.current = { x: template.logoSettings.position.x, y: template.logoSettings.position.y };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    e.stopPropagation(); // prevent canvas from catching the drag
  };

  const handleLogoPointerMove = (e: React.PointerEvent) => {
    if (!isLogoDragging.current) return;
    const dx = e.clientX - logoDragStartPos.current.x;
    const dy = e.clientY - logoDragStartPos.current.y;
    updateTemplate({
      logoSettings: {
        ...template.logoSettings,
        position: {
          ...template.logoSettings.position,
          x: logoStartOffset.current.x + dx,
          y: logoStartOffset.current.y + dy,
        },
      },
    });
    e.stopPropagation();
  };

  const handleLogoPointerUp = (e: React.PointerEvent) => {
    if (!isLogoDragging.current) return;
    isLogoDragging.current = false;
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
    e.stopPropagation();
  };

  const getAnchorX = (anchor: string) => {
    if (!containerRef.current) return 0;
    const w = containerRef.current.clientWidth;
    if (anchor.includes("left")) return 0;
    if (anchor.includes("right")) return w;
    return w * 0.5; // center
  };

  const getAnchorY = (anchor: string) => {
    if (!containerRef.current) return 0;
    const h = containerRef.current.clientHeight;
    if (anchor.includes("top")) return 0;
    if (anchor.includes("bottom")) return h;
    return h * 0.5; // center
  };

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const apply = () => {
      const h = Math.max(1, Math.round(el.clientHeight));
      if (template.renderBaseHeight !== h) updateTemplate({ renderBaseHeight: h });
    };
    apply();
    const ro = new ResizeObserver(() => apply());
    ro.observe(el);
    return () => ro.disconnect();
  }, [template.renderBaseHeight, updateTemplate]);

  useEffect(() => {
    let req: number;
    const loop = () => {
      if (isPlaying) {
        metricsRef.current = updateMetrics(template.audioSettings.smoothing, template.audioSettings.sensitivity);
      }
      
      // Update logo dynamic scaling
      if (logoRef.current && template.previewLogo) {
        // We use the smoothed bass for the logo as well to match the background/spectrum style
        const bass = metricsRef.current.bass;
        const reactivity = template.logoSettings.reactivity;
        const baseH = Math.max(1, template.renderBaseHeight || 450);
        const sf = (containerRef.current?.clientHeight || baseH) / baseH;
        const baseSizePx = template.logoSettings.size * sf;
        const dynamicScale = 1.0 + bass * reactivity;
        const finalSize = baseSizePx * Math.max(0.05, Math.min(4.0, dynamicScale));
        
        logoRef.current.style.width = `${finalSize}px`;
        logoRef.current.style.height = `${finalSize}px`;
      }

      // Update background dynamic brightness
      if (bgRef.current && template.previewBackground) {
        // We use the smoothed bass for background instead of raw kick
        const bass = metricsRef.current.bass;
        const baseBrightness = template.backgroundSettings.brightness;
        const reactivity = template.backgroundSettings.reactivity;
        const dynamicBrightness = baseBrightness * (1.0 + bass * reactivity);
        bgRef.current.style.filter = `brightness(${Math.max(0, Math.min(3.0, dynamicBrightness))})`;
      }

      req = requestAnimationFrame(loop);
    };
    req = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(req);
  }, [isPlaying, updateMetrics, template.audioSettings, template.logoSettings, template.previewLogo, template.backgroundSettings, template.previewBackground]);

  const [batchExportState, setBatchExportState] = useState<{ running: boolean; message: string; progress: number; runId: string | null }>({
    running: false,
    message: "",
    progress: 0,
    runId: null,
  });

  useEffect(() => {
    if (!audioDirPath) {
      setBatchFiles([]);
      return;
    }
    const loadFiles = async () => {
      if (!(window as any).mgApi?.listMp3s) return;
      const res = await (window as any).mgApi.listMp3s(audioDirPath);
      if (res && res.ok) {
        setBatchFiles(res.files);
      } else {
        setBatchFiles([]);
      }
    };
    loadFiles();
  }, [audioDirPath]);

  const handlePickAudioFile = async () => {
    if (!(window as any).mgApi?.pickPath) return;
    const r = await (window as any).mgApi.pickPath({
      kind: "file",
      title: "Select MP3 to preview",
      defaultPath: audioDirPath || undefined,
      filters: [{ name: "MP3", extensions: ["mp3"] }],
    });
    if (r && r.path) {
      setAudioPath(r.path);
      localStorage.setItem("mg_preview_mp3", r.path);
    }
  };

  const handlePickAudioDir = async () => {
    if (!(window as any).mgApi?.pickPath) return;
    const r = await (window as any).mgApi.pickPath({
      kind: "directory",
      title: "Select Directory with MP3s",
    });
    if (r && r.path) {
      setAudioDirPath(r.path);
      localStorage.setItem("mg_batch_mp3_dir", r.path);
    }
  };

  const handleBatchExport = async () => {
    if (!audioDirPath) return;
    if (!template.previewBackground) return alert("Please set a background image first.");
    
    // We should pick an output directory first
    if (!(window as any).mgApi?.pickPath) return;
    const r = await (window as any).mgApi.pickPath({
      kind: "directory",
      title: "Select Output Directory for MP4s",
    });
    if (!r || !r.path) return;
    const outputDir = r.path;

    if (!(window as any).mgApi?.videoRenderStartBatch) return;

    setBatchExportState({ running: true, message: "Queuing...", progress: 0, runId: null });

    const res = await (window as any).mgApi.videoRenderStartBatch({
      mp3DirPath: audioDirPath,
      backgroundPath: template.previewBackground,
      template: template,
      logoPath: template.previewLogo || undefined,
      outputDir: outputDir,
      engine: exportEngine,
    });

    if (res && res.message && !res.ok) {
      setBatchExportState({ running: false, message: `Error: ${res.message}`, progress: 0, runId: null });
    } else if (res && res.ok) {
      setBatchExportState((s) => ({ ...s, runId: res.runId }));
    }
  };

  const handleStopExport = async () => {
    if (!(window as any).mgApi?.videoRenderStop) return;
    await (window as any).mgApi.videoRenderStop();
    setBatchExportState({ running: false, message: "Export stopped by user.", progress: 0, runId: null });
  };

  useEffect(() => {
    if (!(window as any).mgApi?.onVideoRenderEvent) return;
    const cleanup = (window as any).mgApi.onVideoRenderEvent((evt: any) => {
      // In a real app we'd match the runId, but since there's only one batch at a time we just listen
      if (evt.status === "running") {
        setBatchExportState((s) => ({ ...s, running: true, message: evt.message, progress: evt.progress }));
      } else if (evt.status === "done") {
        setBatchExportState((s) => ({ ...s, running: false, message: evt.message, progress: 1 }));
      } else if (evt.status === "failed") {
        setBatchExportState((s) => ({ ...s, running: false, message: `Failed: ${evt.message}`, progress: 0 }));
      }
    });
    return cleanup;
  }, []);

  const [pythonPreviewUrl, setPythonPreviewUrl] = useState<string>("");
  const pythonPreviewBusyRef = useRef(false);
  const pythonPreviewLastFrameRef = useRef<number>(-1);
  const pythonPreviewRenderVersionRef = useRef(0);
  const pythonPreviewPendingFrameRef = useRef<number | null>(null);
  useEffect(() => {
    if (previewEngine !== "python") return;
    pythonPreviewLastFrameRef.current = -1;
    pythonPreviewPendingFrameRef.current = null;
    pythonPreviewRenderVersionRef.current += 1;
  }, [previewEngine, template, audioPath, template.previewBackground, template.previewLogo]);

  const requestPythonFrame = async (frame: number) => {
    const mp3Path = String(audioPath || "").trim();
    const backgroundPath = String(template.previewBackground || "").trim();
    if (!mp3Path || !backgroundPath) return;
    if (!(window as any).mgApi?.videoRenderPreviewPng) return;
    const f = Math.max(0, Math.floor(frame));
    const renderVersion = pythonPreviewRenderVersionRef.current;
    if (pythonPreviewBusyRef.current) {
      pythonPreviewPendingFrameRef.current = f;
      return;
    }
    if (pythonPreviewLastFrameRef.current === f) return;
    pythonPreviewBusyRef.current = true;
    pythonPreviewLastFrameRef.current = f;
    try {
      const r = await (window as any).mgApi.videoRenderPreviewPng({
        mp3Path,
        backgroundPath,
        template,
        logoPath: template.previewLogo || undefined,
        width: 960,
        height: 540,
        frame: f,
      });
      if (r && r.ok) setPythonPreviewUrl(`${r.fileUrl}&v=${Date.now()}`);
    } finally {
      pythonPreviewBusyRef.current = false;
      const pendingFrame = pythonPreviewPendingFrameRef.current;
      pythonPreviewPendingFrameRef.current = null;
      if (pythonPreviewRenderVersionRef.current !== renderVersion) {
        pythonPreviewLastFrameRef.current = -1;
      }
      if (pendingFrame !== null) {
        void requestPythonFrame(pendingFrame);
      }
    }
  };

  useEffect(() => {
    localStorage.setItem("mg_spectrum_engine_mode", engineMode);
  }, [engineMode]);

  useEffect(() => {
    if (previewEngine !== "python") return;
    if (!audioPath || !template.previewBackground) return;
    requestPythonFrame(0);
  }, [audioPath, previewEngine, template.previewBackground]);

  useEffect(() => {
    if (previewEngine !== "python") return;
    const fps = 30;
    let t: number | null = null;
    const tick = () => {
      const frame = Math.floor((currentTime || 0) * fps);
      requestPythonFrame(frame);
    };
    if (isPlaying) {
      t = window.setInterval(tick, 140);
    } else {
      tick();
    }
    return () => {
      if (t) window.clearInterval(t);
    };
  }, [currentTime, isPlaying, previewEngine, template]);

  const [isLivePreviewOpen, setIsLivePreviewOpen] = useState(false);

  const handleToggleLivePreview = async () => {
    if (!isLivePreviewOpen) {
      const res = await (window as any).mgApi?.videoRenderStartLivePreview({
        mp3Path: audioPath,
        backgroundPath: template.previewBackground || "",
        template: template,
        logoPath: template.previewLogo || undefined,
      });
      if (res && res.ok) {
        setIsLivePreviewOpen(true);
      }
    } else {
      await (window as any).mgApi?.videoRenderStopLivePreview();
      setIsLivePreviewOpen(false);
    }
  };

  useEffect(() => {
    if (!isLivePreviewOpen) return;
    (window as any).mgApi?.videoRenderUpdateLivePreview({
      template,
      backgroundPath: template.previewBackground,
      logoPath: template.previewLogo,
      audioPath: audioPath,
    });
  }, [template, template.previewBackground, template.previewLogo, audioPath, isLivePreviewOpen]);

  useEffect(() => {
    if (!isLivePreviewOpen) return;
    let t: number | null = null;
    const tick = () => {
      (window as any).mgApi?.videoRenderUpdateLivePreview({ time: currentTime });
      t = window.requestAnimationFrame(tick);
    };
    t = window.requestAnimationFrame(tick);
    return () => {
      if (t) window.cancelAnimationFrame(t);
    };
  }, [currentTime, isLivePreviewOpen]);

  const handlePickBg = async () => {
    if (!(window as any).mgApi?.pickPath) return;
    const r = await (window as any).mgApi.pickPath({
      kind: "file",
      filters: [{ name: "Images", extensions: ["png", "jpg", "jpeg"] }],
    });
    if (r && r.path) updateTemplate({ previewBackground: r.path });
  };

  const handlePickLogo = async () => {
    if (!(window as any).mgApi?.pickPath) return;
    const r = await (window as any).mgApi.pickPath({
      kind: "file",
      filters: [{ name: "Images", extensions: ["png", "jpg", "jpeg"] }],
    });
    if (r && r.path) updateTemplate({ previewLogo: r.path });
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-black relative">
      {/* Top Toolbar */}
      <div className="absolute top-0 left-0 right-0 h-12 flex items-center px-4 justify-between z-10 bg-gradient-to-b from-black/80 to-transparent">
        <div className="text-sm font-medium text-slate-300">
          Preview: {template.templateName}
        </div>
        <div className="flex items-center space-x-2">
          <button
            className={`px-3 py-1.5 flex items-center gap-2 text-xs font-medium rounded-md transition-colors ${
              isLivePreviewOpen ? "bg-purple-600 hover:bg-purple-500 text-white" : "bg-slate-800 hover:bg-slate-700 text-slate-200"
            }`}
            onClick={handleToggleLivePreview}
            title="Pop Out Native Python Live Preview"
          >
            🚀 {isLivePreviewOpen ? "Close Live Preview" : "Pop Out Live Preview"}
          </button>
          
          <button 
            className="px-3 py-1.5 flex items-center gap-2 text-xs font-medium rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors"
            onClick={handlePickBg}
            title="Set Background Image"
          >
            <ImageIcon size={14} />
            {template.previewBackground ? "Change BG" : "Set BG"}
          </button>
          
          <button 
            className="px-3 py-1.5 flex items-center gap-2 text-xs font-medium rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors"
            onClick={handlePickLogo}
            title="Set Center Logo"
          >
            <CircleUser size={14} />
            {template.previewLogo ? "Change Logo" : "Set Logo"}
          </button>
        </div>
      </div>

      {/* Progress Bar overlay for batch export */}
      {batchExportState.running && (
        <div className="absolute top-12 left-0 right-0 z-50 bg-slate-900/90 border-b border-slate-800 p-2 px-4 flex items-center gap-4 backdrop-blur-sm">
           <div className="text-xs text-slate-300 whitespace-nowrap min-w-[200px]">
             {batchExportState.message}
           </div>
           <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
             <div 
               className="h-full bg-green-500 transition-all duration-300 ease-out" 
               style={{ width: `${Math.max(2, batchExportState.progress * 100)}%` }} 
             />
           </div>
           <div className="text-xs text-slate-400 font-mono">
             {Math.round(batchExportState.progress * 100)}%
           </div>
        </div>
      )}
      
      {/* Success Message */}
      {batchExportState.message && !batchExportState.running && batchExportState.progress === 1 && (
        <div className="absolute top-12 left-0 right-0 z-50 bg-green-900/90 border-b border-green-800 p-2 px-4 flex items-center justify-between backdrop-blur-sm">
           <div className="text-xs text-green-100 font-medium">
             {batchExportState.message}
           </div>
           <button 
             className="text-xs bg-green-800 hover:bg-green-700 text-green-100 px-3 py-1 rounded transition-colors"
             onClick={() => setBatchExportState({ running: false, message: "", progress: 0, runId: null })}
           >
             Dismiss
           </button>
        </div>
      )}
      
      {/* Error Message */}
      {batchExportState.message && !batchExportState.running && batchExportState.progress === 0 && (
        <div className="absolute top-12 left-0 right-0 z-50 bg-red-900/90 border-b border-red-800 p-2 px-4 flex items-center justify-between backdrop-blur-sm">
           <div className="text-xs text-red-100 font-medium whitespace-pre-wrap max-h-40 overflow-y-auto w-full">
             {batchExportState.message}
           </div>
           <button 
             className="text-xs bg-red-800 hover:bg-red-700 text-red-100 px-3 py-1 rounded transition-colors ml-4 shrink-0"
             onClick={() => setBatchExportState({ running: false, message: "", progress: 0, runId: null })}
           >
             Dismiss
           </button>
        </div>
      )}

      {/* Render Canvas Container - Locked to 16:9 */}
      <div className="flex-1 flex items-center justify-center p-4 min-h-0">
        <div 
          ref={containerRef}
          className="relative w-full overflow-hidden bg-slate-950 border border-slate-800 shadow-2xl rounded-sm"
          style={{ aspectRatio: "16/9", maxHeight: "100%" }}
        >
          {/* Layer 1: Background (Full brightness) */}
          {bgUrl && (
            <img 
              ref={bgRef}
              src={bgUrl} 
              className="absolute inset-0 w-full h-full object-cover pointer-events-none z-0" 
              alt="bg" 
              style={{ filter: `brightness(${template.backgroundSettings.brightness})` }}
            />
          )}
          
          {/* Layer 1.5: Particles Engine */}
          {previewEngine === "webgl" && (
            <div className="absolute inset-0 z-20 pointer-events-none">
              <ParticlesCanvas metricsRef={metricsRef} />
            </div>
          )}
          
          {/* Layer 2: Spectrum Canvas */}
          {previewEngine === "webgl" && (
            <div className="absolute inset-0 z-10 pointer-events-auto">
              <SpectrumCanvas metricsRef={metricsRef} />
            </div>
          )}

          {previewEngine === "python" && pythonPreviewUrl && (
            <img src={pythonPreviewUrl} className="absolute inset-0 w-full h-full object-cover pointer-events-none z-10" alt="py" draggable={false} />
          )}

          {/* Layer 3: Logo (Anchored to the exact same position as the spectrum) */}
          {previewEngine === "webgl" && logoUrl && (
            <div 
              className="absolute pointer-events-none transform -translate-x-1/2 -translate-y-1/2 z-30"
              style={{
                left: getAnchorX(template.position.anchor) + template.position.x + "px",
                top: getAnchorY(template.position.anchor) + template.position.y + "px",
                opacity: template.logoSettings.opacity,
              }}
            >
              <img 
                ref={logoRef}
                src={logoUrl} 
                className={`object-cover shadow-2xl transition-transform duration-75 ${template.logoSettings.circleMask ? "rounded-full" : "rounded-md"}`} 
                alt="logo" 
                style={{ 
                  width: template.logoSettings.size,
                  height: template.logoSettings.size
                }}
              />
            </div>
          )}
        </div>
      </div>
      {/* Bottom Controls Area (Player & Batch) */}
      <div className="h-32 bg-slate-900 border-t border-slate-800 flex flex-col p-4 gap-4">
        {/* Real Audio Player */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 shrink-0">
            <button 
              className={`w-8 h-8 flex items-center justify-center rounded-full transition-colors ${!isReady ? "bg-slate-800 text-slate-600 cursor-not-allowed" : "bg-slate-800 hover:bg-slate-700 text-slate-200"}`}
              onClick={() => seek(Math.max(0, currentTime - 10))}
              disabled={!isReady}
              title="-10s"
            >
              <SkipBack size={14} />
            </button>
            <button 
              className={`w-10 h-10 flex items-center justify-center rounded-full transition-colors ${!isReady ? "bg-slate-800 text-slate-600 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-500 text-white"}`}
              onClick={togglePlay}
              disabled={!isReady}
            >
              {isPlaying ? <Pause size={18} /> : <Play size={18} className="ml-1" />}
            </button>
            <button 
              className={`w-8 h-8 flex items-center justify-center rounded-full transition-colors ${!isReady ? "bg-slate-800 text-slate-600 cursor-not-allowed" : "bg-slate-800 hover:bg-slate-700 text-slate-200"}`}
              onClick={() => seek(Math.min(duration, currentTime + 10))}
              disabled={!isReady}
              title="+10s"
            >
              <SkipForward size={14} />
            </button>
          </div>

          <div className="flex-1 flex items-center gap-3">
            <button
              className="px-2 py-1 text-xs font-medium rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors shrink-0"
              onClick={handlePickAudioFile}
              title="Pick a single MP3 file to preview"
            >
              <Music size={14} className="inline-block mr-1" />
              Pick MP3
            </button>
            <span className="text-xs font-mono text-slate-400 w-10 text-right">
              {Math.floor(currentTime / 60)}:{(Math.floor(currentTime % 60)).toString().padStart(2, '0')}
            </span>
            <input
              type="range"
              min={0}
              max={duration || 100}
              value={currentTime}
              onChange={(e) => seek(Number(e.target.value))}
              disabled={!isReady}
              className="flex-1 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <span className="text-xs font-mono text-slate-400 w-10">
              {Math.floor(duration / 60)}:{(Math.floor(duration % 60)).toString().padStart(2, '0')}
            </span>
          </div>
        </div>

        {/* Batch Export Area */}
        <div className="flex items-center gap-4 border-t border-slate-800/50 pt-3">
          <button 
            className="px-3 py-1.5 flex items-center gap-2 text-xs font-medium rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors shrink-0"
            onClick={handlePickAudioDir}
            title="Select directory with multiple MP3s"
          >
            <Folder size={14} />
            Select MP3 Folder
          </button>
          
          <div className="flex-1 flex items-center gap-2">
            <select
              className="flex-1 h-9 rounded-md border border-slate-200/10 bg-slate-950/40 px-3 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/60 truncate"
              value={audioPath}
              onChange={(e) => {
                const p = e.target.value;
                setAudioPath(p);
                localStorage.setItem("mg_preview_mp3", p);
              }}
              disabled={batchFiles.length === 0}
            >
              <option value="" disabled>
                {batchFiles.length === 0 ? "No MP3s loaded..." : "Select an MP3 to preview..."}
              </option>
              {batchFiles.map((f) => (
                <option key={f.path} value={f.path}>
                  {f.name}
                </option>
              ))}
            </select>
          </div>

          <select
            className="h-9 rounded-md border border-slate-200/10 bg-slate-950/40 px-2 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/60"
            value={engineMode}
            onChange={(e) => setEngineMode(e.target.value as EngineMode)}
            disabled={batchExportState.running}
            title="Choose preview/export engine combo"
          >
            <option value="webgl_preview_python_export">WebGL Preview + Python Export</option>
            <option value="webgl_preview_webgl_export">WebGL Preview + WebGL Export</option>
            <option value="python_preview_python_export">Python Preview + Python Export</option>
            <option value="python_preview_webgl_export">Python Preview + WebGL Export</option>
          </select>

          {batchExportState.running ? (
            <button 
              className="px-4 py-1.5 flex items-center gap-2 text-xs font-bold rounded-md bg-red-600 hover:bg-red-500 text-white shadow-[0_0_15px_rgba(220,38,38,0.4)] transition-colors shrink-0"
              onClick={handleStopExport}
            >
              <Square size={14} fill="currentColor" />
              Stop Export
            </button>
          ) : (
            <button 
              className={`px-4 py-1.5 flex items-center gap-2 text-xs font-bold rounded-md transition-colors shrink-0 ${
                !audioDirPath 
                  ? "bg-slate-800 text-slate-600 cursor-not-allowed" 
                  : "bg-green-600 hover:bg-green-500 text-white shadow-[0_0_15px_rgba(22,163,74,0.4)]"
              }`}
              onClick={handleBatchExport}
              disabled={!audioDirPath}
            >
              <Upload size={14} />
              Start Batch Export
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
