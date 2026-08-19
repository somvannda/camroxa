'use client';

/** Mini equalizer — animated when playing, static when paused/current. */
export default function PlayingEqualizer({
  playing,
  className = '',
  compact = false,
  size = 'sm',
}: {
  playing: boolean;
  className?: string;
  compact?: boolean;
  size?: 'xs' | 'sm' | 'lg';
}) {
  const box = compact
    ? 'h-[1em] gap-px'
    : size === 'lg'
      ? 'h-7 gap-[3px]'
      : size === 'xs'
        ? 'h-3 gap-[2px]'
        : 'h-4 gap-[3px]';
  const barWidth =
    compact ? 'eq-bar-inline w-px' : size === 'xs' ? 'w-[2px]' : size === 'lg' ? 'w-[3.5px]' : 'w-[3px]';

  return (
    <span className={`inline-flex items-end ${box} ${className}`} aria-hidden>
      {[0, 1, 2, 3].map((i) => (
        <span
          key={i}
          className={`eq-bar eq-bar-brand rounded-[0.5px] ${barWidth} ${playing ? '' : 'eq-bar-paused'}`}
          style={playing ? { animationDelay: `${i * 0.14}s` } : undefined}
        />
      ))}
    </span>
  );
}
