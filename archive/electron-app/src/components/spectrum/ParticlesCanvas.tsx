import React, { useEffect, useRef } from "react";
import { useSpectrumTemplateStore } from "@/store/spectrumTemplateStore";
import { AudioMetrics } from "./useSpectrumAudio";

interface Props {
  metricsRef: React.MutableRefObject<AudioMetrics>;
}

class Particle {
  x: number = 0;
  y: number = 0;
  vx: number = 0;
  vy: number = 0;
  life: number = 0;
  maxLife: number = 1;

  spawn(w: number, h: number, baseSpeed: number, lifetimeSec: number, spawnRadius: number) {
    const cx = w / 2;
    const cy = h / 2;
    const a0 = Math.random() * Math.PI * 2;
    const r0 = Math.max(0, spawnRadius) * (0.9 + Math.random() * 0.3);
    this.x = cx + Math.cos(a0) * r0;
    this.y = cy + Math.sin(a0) * r0;
    const angle = Math.random() * Math.PI * 2;
    const s = baseSpeed * (0.3 + Math.random() * 0.7);
    this.vx = Math.cos(angle) * s;
    this.vy = Math.sin(angle) * s;
    const lf = Math.max(0.05, lifetimeSec);
    this.maxLife = lf * (0.7 + Math.random() * 0.6);
    this.life = this.maxLife;
  }

  update(dt: number, speedMult: number) {
    this.life -= dt;
    this.x += this.vx * speedMult * dt;
    this.y += this.vy * speedMult * dt;
  }
}

export const ParticlesCanvas: React.FC<Props> = ({ metricsRef }) => {
  const { template } = useSpectrumTemplateStore();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const reqRef = useRef<number>(0);
  const particlesRef = useRef<Particle[]>([]);
  const lastTimeRef = useRef<number>(performance.now());
  const spawnCarryRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const render = (time: number) => {
      reqRef.current = requestAnimationFrame(render);
      
      const dt = Math.min((time - lastTimeRef.current) / 1000, 0.1);
      lastTimeRef.current = time;

      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      const w = rect.width * dpr;
      const h = rect.height * dpr;
      
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }

      ctx.clearRect(0, 0, w, h);

      const config = template.particlesSettings;
      if (!config || !config.enabled) {
        particlesRef.current = [];
        return;
      }

      const metrics = metricsRef.current;
      
      // Same curve as Python Export
      const fixedDt = 1.0 / 60.0;
      const bass = metrics.bass;
      const prb = Math.max(0, Math.min(6, Number(config.reactivity ?? 0)));
      
      // Spawn rate scales with kick and bass reactivity exactly like Python
      const kickPow = metrics.kick;
      let spawnRate = config.spawnRate * (0.12 + kickPow * (0.9 + prb * 2.8));
      spawnRate = Math.max(0, Math.min(20000, spawnRate));
      
      // Accumulate fractional particles to spawn over time
      spawnCarryRef.current += spawnRate * fixedDt;
      const spawnCount = Math.floor(spawnCarryRef.current);
      spawnCarryRef.current -= spawnCount;

      let particles = particlesRef.current;

      // Spawn new particles
      const baseH = Math.max(1, template.renderBaseHeight || 450);
      const sf = rect.height / baseH;
      const logoDynamicScale = 1.0 + bass * template.logoSettings.reactivity;
      const logoRadius = (template.logoSettings.size * 0.5) * sf * Math.max(0.05, Math.min(4.0, logoDynamicScale));
      const spawnRadius = (logoRadius + 2) * dpr;
      for (let i = 0; i < spawnCount; i++) {
        if (particles.length >= config.maxCount) break;
        const p = new Particle();
        p.spawn(w, h, 120 * dpr, config.lifetimeSec, spawnRadius);
        particles.push(p);
      }

      // Apply Python speed multiplier exactly
      let pySpeedMult = config.speed * (0.08 + kickPow * prb * 0.75);
      pySpeedMult = Math.max(0.0, Math.min(2500.0, pySpeedMult));
      
      // Convert to a generic multiplier since Python expects config.speed=120 as baseline
      const speedMult = pySpeedMult / 120.0;

      // Update and draw particles
      ctx.fillStyle = config.color;
      ctx.globalCompositeOperation = "lighter";
      
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.update(dt, speedMult * 60);

        // Remove dead particles or out of bounds
        if (p.life <= 0 || p.x < 0 || p.x > w || p.y < 0 || p.y > h) {
          particles.splice(i, 1);
          continue;
        }

        const lifePct = Math.max(0, p.life / p.maxLife);
        // Fade in quick, fade out slow
        const opacity = Math.min(1, lifePct * 4.0) * (lifePct);
        ctx.globalAlpha = opacity * Math.max(0, Math.min(1, config.opacity));

        const currentSize = config.size * dpr * (0.5 + 0.5 * lifePct);
        
        ctx.beginPath();
        ctx.arc(p.x, p.y, currentSize, 0, Math.PI * 2);
        ctx.fill();
      }

      particlesRef.current = particles;
      ctx.globalAlpha = 1.0;
      ctx.globalCompositeOperation = "source-over";
    };

    reqRef.current = requestAnimationFrame(render);
    return () => cancelAnimationFrame(reqRef.current);
  }, [template, metricsRef]);

  return (
    <canvas 
      ref={canvasRef} 
      className="w-full h-full block absolute inset-0 pointer-events-none"
    />
  );
};
