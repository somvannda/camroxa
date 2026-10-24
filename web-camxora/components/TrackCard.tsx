"use client";

import { Icon } from "./Icon";
import { usePlayer } from "./PlayerProvider";

type TrackCardProps = {
  image: string;
  title: string;
  artist: string;
  plays: string;
  time: string;
  position?: string;
  filter?: string;
};

const parseTime = (value: string) => {
  const match = value.match(/(\d+):(\d{2})/);
  return match ? Number(match[1]) * 60 + Number(match[2]) : 240;
};

export function TrackCard({
  image,
  title,
  artist,
  plays,
  time,
  position,
  filter,
}: TrackCardProps) {
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
      duration: parseTime(time),
      elapsed: 0,
    });
  };

  return (
    <article className={`card${active ? " is-playing" : ""}`}>
      <div className="art">
        <img src={image} alt="" style={{ objectPosition: position, filter }} />
        <button
          className="play"
          type="button"
          aria-label={isPlaying ? `Pause ${title}` : `Play ${title}`}
          onClick={handlePlay}
        >
          <Icon name={isPlaying ? "fa-pause" : "fa-play"} />
        </button>
      </div>
      <h3>{title}</h3>
      <p>{artist}</p>
      <div className="stats">
        <span>
          <Icon name="fa-play" /> {plays}
        </span>
        <span>{time}</span>
      </div>
    </article>
  );
}
