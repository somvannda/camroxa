"use client";

import * as React from "react";
import {
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { GUIDE_DECK, GUIDE_SECTIONS, type GuideSlide } from "./deck";
import { SlideFrame } from "./slide-frame";

function parseHashIndex(): number {
  if (typeof window === "undefined") return 0;
  const match = window.location.hash.match(/slide-(\d+)/i);
  if (!match) return 0;
  const index = Number(match[1]) - 1;
  if (!Number.isFinite(index)) return 0;
  return Math.max(0, Math.min(GUIDE_DECK.length - 1, index));
}

export function GuidesDeck() {
  const stageRef = React.useRef<HTMLDivElement>(null);
  const [index, setIndex] = React.useState(0);
  const [fullscreen, setFullscreen] = React.useState(false);
  const [hydrated, setHydrated] = React.useState(false);

  const slide: GuideSlide = GUIDE_DECK[index] ?? GUIDE_DECK[0];
  const total = GUIDE_DECK.length;
  const progress = ((index + 1) / total) * 100;

  const goTo = React.useCallback((next: number) => {
    setIndex(Math.max(0, Math.min(total - 1, next)));
  }, [total]);

  const goNext = React.useCallback(() => goTo(index + 1), [goTo, index]);
  const goPrev = React.useCallback(() => goTo(index - 1), [goTo, index]);

  React.useEffect(() => {
    setIndex(parseHashIndex());
    setHydrated(true);
  }, []);

  React.useEffect(() => {
    if (!hydrated || typeof window === "undefined") return;
    const hash = `#slide-${index + 1}`;
    if (window.location.hash !== hash) {
      window.history.replaceState(null, "", `${window.location.pathname}${hash}`);
    }
  }, [hydrated, index]);

  React.useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      if (event.key === "ArrowRight" || event.key === " " || event.key === "PageDown") {
        event.preventDefault();
        goNext();
      } else if (event.key === "ArrowLeft" || event.key === "PageUp") {
        event.preventDefault();
        goPrev();
      } else if (event.key === "Home") {
        event.preventDefault();
        goTo(0);
      } else if (event.key === "End") {
        event.preventDefault();
        goTo(total - 1);
      } else if (event.key === "Escape" && document.fullscreenElement) {
        void document.exitFullscreen();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goNext, goPrev, goTo, total]);

  React.useEffect(() => {
    const onFs = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  const toggleFullscreen = async () => {
    const node = stageRef.current;
    if (!node) return;
    try {
      if (!document.fullscreenElement) {
        await node.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch {
      // Fullscreen may be blocked by the browser; controls still work.
    }
  };

  const jumpSection = (section: string) => {
    const next = GUIDE_DECK.findIndex((item) => item.section === section);
    if (next >= 0) goTo(next);
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.22em] text-cyan-200/70">Guides</div>
          <h1 className="font-display text-2xl font-semibold tracking-[-0.04em] text-white">
            Product walkthrough
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="border-white/10 bg-white/[0.03]"
            onClick={() => void toggleFullscreen()}
          >
            {fullscreen ? <Minimize2 className="mr-2 h-4 w-4" /> : <Maximize2 className="mr-2 h-4 w-4" />}
            {fullscreen ? "Exit" : "Fullscreen"}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="border-white/10 bg-white/[0.03]"
            onClick={goPrev}
            disabled={index <= 0}
          >
            <ChevronLeft className="mr-1 h-4 w-4" />
            Prev
          </Button>
          <Button
            type="button"
            size="sm"
            className="bg-cyan-400 text-slate-950 hover:bg-cyan-300"
            onClick={goNext}
            disabled={index >= total - 1}
          >
            Next
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {GUIDE_SECTIONS.map((section) => (
          <button
            key={section}
            type="button"
            onClick={() => jumpSection(section)}
            className={cn(
              "rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.14em] transition",
              slide.section === section
                ? "border-cyan-400/40 bg-cyan-400/15 text-cyan-100"
                : "border-white/10 bg-white/[0.02] text-slate-500 hover:text-slate-300",
            )}
          >
            {section}
          </button>
        ))}
      </div>

      <div
        ref={stageRef}
        className={cn(
          "relative flex min-h-0 flex-1 items-center justify-center",
          fullscreen && "bg-slate-950 p-4 sm:p-8",
        )}
      >
        <div className="relative w-full max-w-6xl">
          <div className="relative aspect-video w-full">
            <button
              type="button"
              aria-label="Previous slide"
              className="absolute inset-y-0 left-0 z-20 w-[12%] cursor-w-resize bg-transparent"
              onClick={goPrev}
            />
            <button
              type="button"
              aria-label="Next slide"
              className="absolute inset-y-0 right-0 z-20 w-[12%] cursor-e-resize bg-transparent"
              onClick={goNext}
            />
            <SlideFrame slide={slide} className="absolute inset-0" />
          </div>
        </div>

        {fullscreen ? (
          <div className="pointer-events-none absolute inset-x-0 bottom-4 flex justify-center">
            <div className="pointer-events-auto flex items-center gap-3 rounded-full border border-white/10 bg-slate-950/80 px-4 py-2 backdrop-blur">
              <button type="button" className="text-slate-300 hover:text-white" onClick={goPrev}>
                <ChevronLeft className="h-4 w-4" />
              </button>
              <div className="min-w-[7rem] text-center text-xs text-slate-400">
                {index + 1} / {total}
              </div>
              <button type="button" className="text-slate-300 hover:text-white" onClick={goNext}>
                <ChevronRight className="h-4 w-4" />
              </button>
              <button type="button" className="text-slate-300 hover:text-white" onClick={() => void toggleFullscreen()}>
                <Minimize2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ) : null}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>
            Slide {index + 1} of {total}
          </span>
          <span className="hidden sm:inline">← → or Space to navigate · F fullscreen via button</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
          <div
            className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-cyan-400 to-sky-300 transition-[width] duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {GUIDE_DECK.map((item, dotIndex) => (
            <button
              key={item.id}
              type="button"
              aria-label={`Go to slide ${dotIndex + 1}`}
              onClick={() => goTo(dotIndex)}
              className={cn(
                "h-2 w-2 rounded-full transition",
                dotIndex === index ? "bg-cyan-300" : "bg-white/15 hover:bg-white/30",
              )}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
