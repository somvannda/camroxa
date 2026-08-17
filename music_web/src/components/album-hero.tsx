'use client';

import { useEffect, useMemo, useState, type ReactNode } from 'react';

import AlbumPlaybackControls from '@/components/album-playback-controls';
import { formatDuration, formatPlayCount, type StreamAlbum, type StreamTrack } from '@/lib/streaming-api';

type AlbumHeroProps = {
  album: StreamAlbum;
  tracks: StreamTrack[];
  totalDuration: number;
  playCount: number;
};

type Palette = {
  r: number;
  g: number;
  b: number;
};

const FALLBACK: Palette = { r: 88, g: 40, b: 160 };

function clampChannel(n: number): number {
  return Math.max(0, Math.min(255, Math.round(n)));
}

function extractDominantColor(img: HTMLImageElement): Palette {
  const size = 48;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) return FALLBACK;
  ctx.drawImage(img, 0, 0, size, size);
  const { data } = ctx.getImageData(0, 0, size, size);

  let r = 0;
  let g = 0;
  let b = 0;
  let weight = 0;
  for (let i = 0; i < data.length; i += 4) {
    const pr = data[i];
    const pg = data[i + 1];
    const pb = data[i + 2];
    const a = data[i + 3];
    if (a < 200) continue;
    const max = Math.max(pr, pg, pb);
    const min = Math.min(pr, pg, pb);
    if (max < 28 || min > 230) continue;
    const sat = max === 0 ? 0 : (max - min) / max;
    const w = 0.35 + sat;
    r += pr * w;
    g += pg * w;
    b += pb * w;
    weight += w;
  }
  if (weight < 1) return FALLBACK;
  return {
    r: clampChannel(r / weight),
    g: clampChannel(g / weight),
    b: clampChannel(b / weight),
  };
}

function useCoverPalette(coverUrl?: string | null): Palette {
  const [palette, setPalette] = useState<Palette>(FALLBACK);

  useEffect(() => {
    if (!coverUrl) {
      setPalette(FALLBACK);
      return;
    }
    let cancelled = false;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      if (cancelled) return;
      try {
        setPalette(extractDominantColor(img));
      } catch {
        setPalette(FALLBACK);
      }
    };
    img.onerror = () => {
      if (!cancelled) setPalette(FALLBACK);
    };
    img.src = coverUrl;
    return () => {
      cancelled = true;
    };
  }, [coverUrl]);

  return palette;
}

export function CollectionHero({
  kind,
  title,
  subtitle,
  coverUrl,
  tracks,
  totalDuration = 0,
  playCount = 0,
  tags = [],
  description,
  extraActions,
}: {
  kind: string;
  title: string;
  subtitle?: string;
  coverUrl?: string | null;
  tracks: StreamTrack[];
  totalDuration?: number;
  playCount?: number;
  tags?: string[];
  description?: string | null;
  extraActions?: ReactNode;
}) {
  const palette = useCoverPalette(coverUrl);
  const overlayStyle = useMemo(() => {
    const { r, g, b } = palette;
    return {
      background: `linear-gradient(135deg, rgba(${r},${g},${b},0.55) 0%, rgba(${r},${g},${b},0.18) 45%, rgba(5,8,18,0.75) 100%)`,
    } as const;
  }, [palette]);

  return (
    <div className="relative overflow-hidden rounded-3xl border border-white/8 shadow-[0_24px_60px_rgba(0,0,0,0.35)]">
      {coverUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={coverUrl}
          alt=""
          aria-hidden
          className="pointer-events-none absolute inset-0 h-full w-full scale-125 object-cover opacity-55 blur-3xl"
        />
      ) : null}
      <div className="absolute inset-0" style={overlayStyle} />
      <div className="relative flex flex-col gap-6 p-6 md:flex-row md:items-end md:p-10">
        {coverUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={coverUrl}
            alt=""
            className="h-48 w-48 rounded-2xl object-cover shadow-2xl md:h-56 md:w-56"
          />
        ) : (
          <div className="h-48 w-48 rounded-2xl bg-white/[0.06] md:h-56 md:w-56" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-xs uppercase tracking-[0.2em] text-white/70">{kind}</p>
          <h1 className="mt-2 font-display text-4xl font-semibold text-white drop-shadow md:text-6xl">
            {title}
          </h1>
          {subtitle ? <p className="mt-3 text-white/85">{subtitle}</p> : null}
          {description ? <p className="mt-2 max-w-2xl text-sm text-white/70">{description}</p> : null}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {tags.map((item) => (
              <span
                key={item}
                className="rounded-full bg-black/30 px-3 py-1 text-xs font-medium text-white/90 backdrop-blur"
              >
                {item}
              </span>
            ))}
            <span className="text-sm text-white/75">
              {tracks.length} song{tracks.length === 1 ? '' : 's'}
              {playCount > 0 ? ` · ${formatPlayCount(playCount)} plays` : ''}
              {totalDuration > 0 ? ` · ${formatDuration(totalDuration)}` : ''}
            </span>
          </div>
          <AlbumPlaybackControls tracks={tracks} extraActions={extraActions} />
        </div>
      </div>
    </div>
  );
}

export default function AlbumHero({ album, tracks, totalDuration, playCount }: AlbumHeroProps) {
  return (
    <CollectionHero
      kind="Album"
      title={album.album_name}
      subtitle={album.artist_name}
      coverUrl={album.cover_url}
      tracks={tracks}
      totalDuration={totalDuration}
      playCount={playCount}
      tags={album.genres?.length ? album.genres : album.genre ? [album.genre] : []}
    />
  );
}
