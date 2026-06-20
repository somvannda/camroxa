import React, { useEffect, useRef } from "react";
import { useSpectrumTemplateStore, SpectrumLayer, ColorConfig } from "@/store/spectrumTemplateStore";
import { AudioMetrics } from "./useSpectrumAudio";

interface Props {
  metricsRef: React.MutableRefObject<AudioMetrics>;
}

// Color Engine Helper
function applyColorConfig(
  ctx: CanvasRenderingContext2D,
  config: ColorConfig,
  bounds: { x: number; y: number; w: number; h: number }
) {
  if (config.mode === "solid" || !config.gradientColors || config.gradientColors.length === 0) {
    ctx.fillStyle = config.solidColor;
    ctx.strokeStyle = config.solidColor;
    return;
  }

  const { x, y, w, h } = bounds;
  let gradient: CanvasGradient;

  switch (config.gradientDirection) {
    case "left-to-right":
      gradient = ctx.createLinearGradient(x, y, x + w, y);
      break;
    case "top-to-bottom":
      gradient = ctx.createLinearGradient(x, y, x, y + h);
      break;
    case "diagonal":
      gradient = ctx.createLinearGradient(x, y, x + w, y + h);
      break;
    case "radial":
    case "circular":
      const cx = x + w / 2;
      const cy = y + h / 2;
      const r = Math.max(w, h) / 2;
      gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
      break;
    default:
      gradient = ctx.createLinearGradient(x, y, x + w, y);
  }

  const stops = config.gradientColors.length;
  config.gradientColors.forEach((color, i) => {
    gradient.addColorStop(i / Math.max(1, stops - 1), color);
  });

  ctx.fillStyle = gradient;
  ctx.strokeStyle = gradient;
}

export const SpectrumCanvas: React.FC<Props> = ({ metricsRef }) => {
  const { template, updateTemplate } = useSpectrumTemplateStore();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const reqRef = useRef<number>(0);

  // Drag state
  const isDragging = useRef(false);
  const dragStartPos = useRef({ x: 0, y: 0 });
  const startOffset = useRef({ x: 0, y: 0 });

  const handlePointerDown = (e: React.PointerEvent) => {
    isDragging.current = true;
    dragStartPos.current = { x: e.clientX, y: e.clientY };
    startOffset.current = { x: template.position.x, y: template.position.y };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isDragging.current) return;
    const dx = e.clientX - dragStartPos.current.x;
    const dy = e.clientY - dragStartPos.current.y;
    updateTemplate({
      position: {
        ...template.position,
        x: startOffset.current.x + dx,
        y: startOffset.current.y + dy,
      },
    });
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    isDragging.current = false;
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const render = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      const w = rect.width * dpr;
      const h = rect.height * dpr;

      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }

      ctx.clearRect(0, 0, w, h);
      ctx.save();

      let cx = w / 2;
      let cy = h / 2;
      const { anchor, x: offsetX, y: offsetY } = template.position;

      if (anchor.includes("top")) cy = 0;
      if (anchor.includes("bottom")) cy = h;
      if (anchor.includes("left")) cx = 0;
      if (anchor.includes("right")) cx = w;

      cx += offsetX * dpr;
      cy += offsetY * dpr;

      const metrics = metricsRef.current;

      template.layers.forEach((layer) => {
        ctx.save();
        ctx.translate(cx, cy);

        // Logo base size is defined by logoSettings.size, scaled by current preview height
        const baseH = Math.max(1, template.renderBaseHeight || 450);
        const sf = rect.height / baseH;
        const logoDynamicScale = 1.0 + metrics.bass * template.logoSettings.reactivity;
        const logoVisualRadius = (template.logoSettings.size * 0.5) * sf * Math.max(0.05, Math.min(4.0, logoDynamicScale));
        const baseRadius = logoVisualRadius + layer.barWidth * 0.5;
        const currentRadius = baseRadius * dpr;

        ctx.globalAlpha = layer.opacity;
        if (layer.blur > 0) {
          ctx.filter = `blur(${layer.blur}px)`;
        } else {
          ctx.filter = "none";
        }

        const size = currentRadius * 2;
        applyColorConfig(ctx, layer.color, { x: -size / 2, y: -size / 2, w: size, h: size });

        if (layer.fillCircle && layer.curved && layer.mirrored) {
          const fillR = Math.max(0, currentRadius - (layer.barWidth * dpr) * 0.5 - (1 * dpr));
          ctx.beginPath();
          ctx.arc(0, 0, fillR, 0, Math.PI * 2);
          ctx.fill();
        }

        drawUnifiedSpectrum(ctx, layer, currentRadius, metrics, template.style, template.audioSettings.sensitivity);

        ctx.restore();
      });

      ctx.restore();
      reqRef.current = requestAnimationFrame(render);
    };

    reqRef.current = requestAnimationFrame(render);
    return () => cancelAnimationFrame(reqRef.current);
  }, [template, metricsRef]);

  const drawUnifiedSpectrum = (
    ctx: CanvasRenderingContext2D, 
    layer: SpectrumLayer, 
    radius: number, 
    metrics: AudioMetrics, 
    style: string, 
    sensitivity: number
  ) => {
    let bins = metrics.fft.length; // 64
    const dpr = window.devicePixelRatio || 1;

    if (style === "liquid" || style === "soft-plasma" || style === "neon-pulse") {
      ctx.shadowBlur = style === "liquid" ? 30 : 15;
      ctx.shadowColor = typeof ctx.fillStyle === "string" ? ctx.fillStyle : typeof ctx.strokeStyle === "string" ? ctx.strokeStyle : "#ffffff";
    } else {
      ctx.shadowBlur = 0;
    }

    // 1. Prepare FFT Data
    const renderFft = new Float32Array(bins);
    if (layer.mirrored) {
      // Symmetrical FFT (bass in middle, treble on edges)
      const half = Math.floor(bins / 2);
      for (let i = 0; i < half; i++) {
        let smoothed = metrics.fft[i];
        if (i > 1 && i < half - 2) {
          smoothed = (metrics.fft[i-2]*0.1 + metrics.fft[i-1]*0.2 + metrics.fft[i]*0.4 + metrics.fft[i+1]*0.2 + metrics.fft[i+2]*0.1);
        }
        renderFft[half - 1 - i] = smoothed;
        renderFft[half + i] = smoothed;
      }
    } else {
      // Standard FFT (bass left, treble right)
      for (let i = 0; i < bins; i++) {
        let smoothed = metrics.fft[i];
        if (i > 1 && i < bins - 2) {
          smoothed = (metrics.fft[i-2]*0.1 + metrics.fft[i-1]*0.2 + metrics.fft[i]*0.4 + metrics.fft[i+1]*0.2 + metrics.fft[i+2]*0.1);
        }
        renderFft[i] = smoothed;
      }
    }

    // 2. Generate Path Points
    const points: { px: number, py: number, dx: number, dy: number, val: number }[] = [];
    const canvasW = ctx.canvas.width;
    const canvasH = ctx.canvas.height;
    
    // Total physical length of the spectrum
    let totalLength = 0;
    if (layer.curved) {
      const totalAngle = layer.mirrored ? Math.PI * 2 : Math.PI;
      totalLength = radius * totalAngle;
    } else {
      // If gravity is top/bottom, it spans width. If left/right, it spans height.
      totalLength = (layer.gravity === "left" || layer.gravity === "right") ? (canvasH * 0.8) : (canvasW * 0.8);
    }

    const reactMult = sensitivity * layer.thickness * dpr;

    // Determine Anchor Angles & Offsets
    let startAngle = Math.PI / 2; // Bottom
    if (layer.gravity === "top") startAngle = -Math.PI / 2;
    if (layer.gravity === "left") startAngle = Math.PI;
    if (layer.gravity === "right") startAngle = 0;

    const startX = -totalLength / 2;

    for (let i = 0; i < bins; i++) {
      const t = bins > 1 ? i / (bins - 1) : 0;
      let px = 0, py = 0, dx = 0, dy = -1;
      
      if (layer.curved) {
        const totalAngle = layer.mirrored ? Math.PI * 2 : Math.PI;
        // Center the arc symmetrically around the startAngle
        const angle = startAngle - (totalAngle / 2) + (t * totalAngle);
        px = Math.cos(angle) * radius;
        py = Math.sin(angle) * radius;
        dx = Math.cos(angle);
        dy = Math.sin(angle);
      } else {
        const offset = startX + (t * totalLength);
        if (layer.gravity === "bottom") {
          px = offset; py = 0; dx = 0; dy = -1;
        } else if (layer.gravity === "top") {
          px = offset; py = 0; dx = 0; dy = 1;
        } else if (layer.gravity === "left") {
          px = 0; py = offset; dx = 1; dy = 0;
        } else if (layer.gravity === "right") {
          px = 0; py = offset; dx = -1; dy = 0;
        }
      }
      
      points.push({ px, py, dx, dy, val: renderFft[i] * reactMult });
    }

    // 3. Render
    ctx.lineWidth = layer.barWidth * dpr;
    const bw = Math.max(1 * dpr, (totalLength / bins) * (layer.barWidth / 10));

    if (style === "soft-waveform" || style === "mountain" || style === "liquid" || style === "continuous-waveform") {
      ctx.beginPath();
      for (let i = 0; i < points.length; i++) {
        const p = points[i];
        const h = Math.max(2 * dpr, p.val);
        const x = p.px + p.dx * h;
        const y = p.py + p.dy * h;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      
      if (style === "mountain" || style === "liquid") {
        // Connect to baseline
        for (let i = points.length - 1; i >= 0; i--) {
          const p = points[i];
          ctx.lineTo(p.px, p.py);
        }
        ctx.closePath();
        ctx.fill();
      } else {
        if (layer.curved && layer.mirrored) ctx.closePath();
        ctx.stroke();
      }
    } else {
      // Bar styles
      for (let i = 0; i < points.length; i++) {
        const p = points[i];
        let h = Math.max(2 * dpr, p.val);
        
        ctx.save();
        ctx.translate(p.px, p.py);
        const angle = Math.atan2(p.dy, p.dx);
        // Rotate so the X axis points outward (direction of the spike)
        ctx.rotate(angle);
        
        if (style === "symmetrical-bars") {
          ctx.fillRect(-h/2, -bw/2, h, bw);
        } else if (style === "floating-blocks") {
          ctx.fillRect(h + 20*dpr, -bw/2, 10*dpr, bw);
        } else if (style === "pixel-bars") {
          const step = 20 * dpr;
          h = Math.ceil(h / step) * step;
          ctx.fillRect(0, -bw/2, h, bw);
        } else if (style === "thin-lines") {
          ctx.fillRect(0, -1*dpr, h, 2*dpr);
        } else if (style === "dot-matrix") {
          const dotSize = bw * 0.8;
          const numDots = Math.floor(h / (dotSize * 1.5));
          for(let d = 0; d < numDots; d++) {
            ctx.beginPath();
            ctx.arc((d * dotSize * 1.5) + dotSize/2, 0, dotSize/2, 0, Math.PI * 2);
            ctx.fill();
          }
        } else {
          // classic-vertical, neon-pulse
          ctx.fillRect(0, -bw/2, h, bw);
        }
        
        ctx.restore();
      }
    }
    
    ctx.shadowBlur = 0;
  };

  return (
    <canvas 
      ref={canvasRef} 
      className="w-full h-full block cursor-move absolute inset-0 bg-transparent"
      style={{ touchAction: "none" }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
    />
  );
};
