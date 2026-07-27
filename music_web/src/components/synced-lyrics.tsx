'use client';

import { useEffect, useMemo, useRef } from 'react';

import { usePlayer } from '@/components/player-provider';
import { activeLyricIndex, buildLyricTimeline } from '@/lib/lyrics';

export default function SyncedLyrics({
  lyrics,
  className = '',
}: {
  lyrics?: string | null;
  className?: string;
}) {
  const { currentTime, seek } = usePlayer();
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const lineRefs = useRef<Map<number, HTMLButtonElement | HTMLParagraphElement>>(new Map());

  const { lines, synced } = useMemo(() => buildLyricTimeline(lyrics), [lyrics]);
  const activeIndex = synced ? activeLyricIndex(lines, currentTime) : -1;

  useEffect(() => {
    if (!synced || activeIndex < 0) return;
    const node = lineRefs.current.get(activeIndex);
    const scroller = scrollerRef.current;
    if (!node || !scroller) return;
    const nodeTop = node.offsetTop;
    const nodeHeight = node.offsetHeight;
    const target = nodeTop - scroller.clientHeight / 2 + nodeHeight / 2;
    scroller.scrollTo({ top: Math.max(0, target), behavior: 'smooth' });
  }, [activeIndex, synced]);

  if (!lines.length) {
    return (
      <div className={`rounded-xl bg-white/[0.04] p-4 text-sm text-slate-500 ${className}`}>
        No lyrics for this track.
      </div>
    );
  }

  return (
    <div className={className}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Lyrics</p>
        <p className="text-[10px] uppercase tracking-wide text-slate-600">
          {synced ? 'Synced' : 'Text'}
        </p>
      </div>
      <div
        ref={scrollerRef}
        className="lyrics-scroller relative max-h-[min(52vh,420px)] overflow-y-auto rounded-xl bg-gradient-to-b from-white/[0.05] to-white/[0.02] px-3 py-6"
      >
        <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-10 bg-gradient-to-b from-[rgba(8,10,20,0.95)] to-transparent" />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-10 bg-gradient-to-t from-[rgba(8,10,20,0.95)] to-transparent" />
        <div className="space-y-1">
          {lines.map((line) => {
            if (!synced) {
              return (
                <p
                  key={`${line.index}-${line.text.slice(0, 24)}`}
                  className={`rounded-lg px-2 py-1.5 ${
                    line.isSection
                      ? 'font-display text-[11px] uppercase tracking-[0.16em] text-slate-500'
                      : 'text-sm leading-relaxed text-slate-300'
                  }`}
                >
                  {line.text}
                </p>
              );
            }

            const isActive = line.index === activeIndex;
            const isPast = activeIndex >= 0 && line.index < activeIndex;
            return (
              <button
                key={`${line.index}-${line.start}`}
                type="button"
                ref={(el) => {
                  if (el) lineRefs.current.set(line.index, el);
                  else lineRefs.current.delete(line.index);
                }}
                onClick={() => seek(line.start + 0.01)}
                className={`lyric-line block w-full rounded-lg px-2 py-1.5 text-left transition-all duration-300 ${
                  line.isSection
                    ? 'font-display text-[11px] uppercase tracking-[0.16em]'
                    : 'text-sm leading-relaxed'
                } ${
                  isActive
                    ? 'lyric-line-active scale-[1.02] font-semibold text-fuchsia-100'
                    : isPast
                      ? 'text-slate-500'
                      : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {line.text}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
