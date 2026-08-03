"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type { GuideSlide } from "./deck";
import { SlideMockPanel } from "./slide-mocks";

function SlideVisual(props: { slide: GuideSlide }) {
  const [imageFailed, setImageFailed] = React.useState(false);
  React.useEffect(() => {
    setImageFailed(false);
  }, [props.slide.id, props.slide.imageSrc]);

  if (props.slide.imageSrc && !imageFailed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={props.slide.imageSrc}
        alt=""
        className="h-full w-full rounded-2xl border border-white/10 object-cover object-top"
        onError={() => setImageFailed(true)}
      />
    );
  }
  if (props.slide.mock) {
    return <SlideMockPanel mock={props.slide.mock} />;
  }
  return null;
}

export function SlideFrame(props: { slide: GuideSlide; className?: string }) {
  const { slide } = props;
  const showVisual = Boolean(slide.mock || slide.imageSrc);
  const isWin = slide.kind === "win";
  const isSection = slide.kind === "section";
  const isTitle = slide.kind === "title";
  const isCta = slide.kind === "cta";
  /** Section / title dividers: centered hero text, no left-rail emptiness. */
  const centeredHero = isSection || isTitle;
  const showFooter = Boolean(slide.footerNote) && !centeredHero;

  return (
    <article
      className={cn(
        "relative flex h-full w-full flex-col overflow-hidden rounded-[28px] border border-white/10 bg-[linear-gradient(165deg,rgba(10,16,40,0.98),rgba(3,7,18,0.99))] p-6 text-slate-100 shadow-[0_40px_120px_rgba(2,6,23,0.55)] sm:p-8 md:p-10",
        isWin && "border-emerald-400/25 ring-1 ring-emerald-400/20",
        isCta && "border-cyan-400/20",
        props.className,
      )}
    >
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(34,211,238,0.12),transparent_45%),radial-gradient(ellipse_at_bottom_left,rgba(16,185,129,0.10),transparent_40%)]"
        aria-hidden
      />

      {/* Content grows; footer stays a sibling pinned to the slide bottom. */}
      <div
        className={cn(
          "relative z-10 flex min-h-0 flex-1 flex-col",
          centeredHero && "items-center justify-center text-center",
        )}
      >
        {!centeredHero ? (
          <div className="flex shrink-0 items-start justify-between gap-4">
            <div className="min-w-0">
              {slide.eyebrow ? (
                <div
                  className={cn(
                    "text-[11px] font-medium uppercase tracking-[0.22em]",
                    isWin ? "text-emerald-200/80" : "text-cyan-200/70",
                  )}
                >
                  {slide.eyebrow}
                </div>
              ) : null}
              <h2 className="mt-3 font-display text-2xl font-semibold tracking-[-0.04em] text-white sm:text-3xl md:text-[2.1rem]">
                {slide.title}
              </h2>
              {slide.subtitle ? (
                <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300/80 sm:text-base sm:leading-8">
                  {slide.subtitle}
                </p>
              ) : null}
            </div>
            <div className="hidden shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-slate-500 sm:block">
              {slide.section}
            </div>
          </div>
        ) : (
          <div className="mx-auto flex max-w-4xl flex-col items-center px-2">
            {slide.eyebrow ? (
              <div className="text-[11px] font-medium uppercase tracking-[0.22em] text-cyan-200/70">
                {slide.eyebrow}
              </div>
            ) : null}
            <h2 className="mt-4 font-display text-3xl font-semibold leading-tight tracking-[-0.04em] text-white sm:text-4xl md:text-5xl">
              {slide.title}
            </h2>
            {slide.subtitle ? (
              <p className="mt-5 max-w-2xl text-sm leading-7 text-slate-300/80 sm:text-base sm:leading-8">
                {slide.subtitle}
              </p>
            ) : null}
            {slide.bullets?.length ? (
              <ul className="mt-8 space-y-3 text-left sm:mx-auto sm:max-w-xl">
                {slide.bullets.map((bullet) => (
                  <li key={bullet} className="flex gap-3 text-sm leading-6 text-slate-200/85 sm:text-[15px]">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" />
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="mt-10 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-slate-500">
              {slide.section}
            </div>
          </div>
        )}

        {!centeredHero ? (
          <div
            className={cn(
              "mt-6 grid min-h-0 flex-1 gap-6",
              showVisual ? "lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:items-center" : "",
            )}
          >
            <div className="min-w-0">
              {slide.bullets?.length ? (
                <ul className="space-y-3">
                  {slide.bullets.map((bullet) => (
                    <li key={bullet} className="flex gap-3 text-sm leading-6 text-slate-200/85 sm:text-[15px]">
                      <span
                        className={cn(
                          "mt-2 h-1.5 w-1.5 shrink-0 rounded-full",
                          isWin ? "bg-emerald-400" : "bg-cyan-400",
                        )}
                      />
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>

            {showVisual ? (
              <div className="min-h-0 self-stretch">
                <SlideVisual slide={slide} />
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {showFooter ? (
        <p
          className={cn(
            "relative z-10 mt-6 shrink-0 rounded-2xl border px-4 py-3 text-sm leading-6 shadow-[0_0_24px_rgba(34,211,238,0.12)]",
            isWin
              ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-50"
              : "border-cyan-400/40 bg-cyan-400/10 text-cyan-50",
          )}
        >
          {slide.footerNote}
        </p>
      ) : null}
    </article>
  );
}
