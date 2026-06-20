import React, { useEffect, useRef, useState } from "react";
import { useSpectrumTemplateStore } from "@/store/spectrumTemplateStore";
import { useSpectrumAudio } from "./useSpectrumAudio";
import { SpectrumCanvas } from "./SpectrumCanvas";
import { ParticlesCanvas } from "./ParticlesCanvas";

export function WebglExportRunner(props: { jobId: string }) {
  const { template, setTemplate, updateTemplate } = useSpectrumTemplateStore();
  const [job, setJob] = useState<{
    jobId: string;
    mp3Path: string;
    backgroundPath: string;
    logoPath?: string;
    template: unknown;
    width: number;
    height: number;
    fps: number;
  } | null>(null);

  const metricsRef = useRef({ bass: 0, mid: 0, treble: 0, kick: 0, fft: new Float32Array(64) });
  const containerRef = useRef<HTMLDivElement>(null);
  const logoRef = useRef<HTMLImageElement>(null);
  const bgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    let alive = true;
    const run = async () => {
      const api = (window as any).mgApi;
      if (!api?.webglExportGetJob) return;
      const r = await api.webglExportGetJob({ jobId: props.jobId });
      if (!alive) return;
      if (!r || r.ok !== true) return;
      setJob(r.job);
      setTemplate(r.job.template);
      updateTemplate({ previewBackground: r.job.backgroundPath, previewLogo: r.job.logoPath || "" });
    };
    run();
    return () => {
      alive = false;
    };
  }, [props.jobId, setTemplate, updateTemplate]);

  const audioUrl = job?.mp3Path ? `mgsamples://file?path=${encodeURIComponent(job.mp3Path)}` : null;
  const bgUrl = job?.backgroundPath ? `mgsamples://file?path=${encodeURIComponent(job.backgroundPath)}` : null;
  const logoUrl = job?.logoPath ? `mgsamples://file?path=${encodeURIComponent(job.logoPath)}` : null;

  const { isReady, isPlaying, currentTime, duration, togglePlay, seek, updateMetrics } = useSpectrumAudio(audioUrl);
  const startedRef = useRef(false);
  const readySentRef = useRef(false);

  useEffect(() => {
    if (!job) return;
    if (!isReady) return;
    if (startedRef.current) return;
    startedRef.current = true;
    seek(0);
    togglePlay();
  }, [isReady, job, seek, togglePlay]);

  useEffect(() => {
    if (!job) return;
    if (!startedRef.current) return;
    if (readySentRef.current) return;
    if (!Number.isFinite(duration) || duration <= 0) return;
    const api = (window as any).mgApi;
    if (!api?.webglExportReady) return;
    readySentRef.current = true;
    api.webglExportReady({ jobId: job.jobId, duration });
  }, [duration, job]);

  useEffect(() => {
    let req: number;
    const loop = () => {
      if (isPlaying) {
        metricsRef.current = updateMetrics(template.audioSettings.smoothing, template.audioSettings.sensitivity);
      }
      if (logoRef.current && logoUrl) {
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
      if (bgRef.current && bgUrl) {
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
  }, [bgUrl, isPlaying, logoUrl, template, updateMetrics]);

  const getAnchorX = (anchor: string) => {
    const el = containerRef.current;
    if (!el) return 0;
    const w = el.clientWidth;
    if (anchor.includes("left")) return 0;
    if (anchor.includes("right")) return w;
    return w * 0.5;
  };

  const getAnchorY = (anchor: string) => {
    const el = containerRef.current;
    if (!el) return 0;
    const h = el.clientHeight;
    if (anchor.includes("top")) return 0;
    if (anchor.includes("bottom")) return h;
    return h * 0.5;
  };

  if (!job) {
    return <div className="w-screen h-screen bg-black" />;
  }

  return (
    <div className="w-screen h-screen bg-black flex items-center justify-center overflow-hidden">
      <div ref={containerRef} className="relative bg-black overflow-hidden" style={{ width: job.width, height: job.height }}>
        {bgUrl && (
          <img
            ref={bgRef}
            src={bgUrl}
            className="absolute inset-0 w-full h-full object-cover pointer-events-none"
            alt="bg"
            style={{ filter: `brightness(${template.backgroundSettings.brightness})` }}
          />
        )}

        <div className="absolute inset-0 pointer-events-none z-10">
          <SpectrumCanvas metricsRef={metricsRef} />
        </div>

        <div className="absolute inset-0 pointer-events-none z-20">
          <ParticlesCanvas metricsRef={metricsRef} />
        </div>

        {logoUrl && (
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
              className={`object-cover border-4 border-slate-900/50 shadow-2xl ${template.logoSettings.circleMask ? "rounded-full" : "rounded-md"}`}
              alt="logo"
              style={{ width: template.logoSettings.size, height: template.logoSettings.size }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
