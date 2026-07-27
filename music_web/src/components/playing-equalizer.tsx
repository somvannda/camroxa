'use client';

/** Mini equalizer — animated when playing, static when paused/current. */
export default function PlayingEqualizer({
  playing,
  className = '',
}: {
  playing: boolean;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex h-4 items-end gap-[3px] ${className}`}
      aria-hidden
    >
      {[0, 1, 2, 3].map((i) => (
        <span
          key={i}
          className={`eq-bar w-[3px] rounded-sm bg-fuchsia-400 ${playing ? '' : 'eq-bar-paused'}`}
          style={playing ? { animationDelay: `${i * 0.14}s` } : undefined}
        />
      ))}
    </span>
  );
}
