"use client";

import { Icon } from "./Icon";
import { usePlayer } from "./PlayerProvider";

const parseTime = (value: string) => {
  const match = value.match(/(\d+):(\d{2})/);
  return match ? Number(match[1]) * 60 + Number(match[2]) : 0;
};

type ContinueCardProps = {
  image: string;
  title: string;
  artist: string;
  elapsed: string;
  duration: string;
  progress: number;
  position?: string;
};

export function ContinueCard({
  image,
  title,
  artist,
  elapsed,
  duration,
  progress,
  position,
}: ContinueCardProps) {
  const { current, playing, playTrack, togglePlay } = usePlayer();
  const active = current.title === title && current.artist === artist;
  const isPlaying = active && playing;

  const handlePlay = () => {
    if (active) {
      togglePlay();
      return;
    }
    playTrack({
      title,
      artist,
      cover: image,
      duration: parseTime(duration),
      elapsed: parseTime(elapsed),
    });
  };

  return (
    <article className={`continue-card${active ? " is-playing" : ""}`}>
      <img src={image} alt="" style={{ objectPosition: position }} />
      <div className="cc-copy">
        <strong>{title}</strong>
        <span>{artist}</span>
        <div className="cc-bar">
          <i style={{ width: `${progress}%` }} />
        </div>
        <div className="cc-meta">
          <span>
            {elapsed} / {duration}
          </span>
          <span>Take 2</span>
        </div>
      </div>
      <button
        className="cc-play"
        type="button"
        aria-label={isPlaying ? `Pause ${title}` : `Resume ${title}`}
        onClick={handlePlay}
      >
        <Icon name={isPlaying ? "fa-pause" : "fa-play"} />
      </button>
    </article>
  );
}
