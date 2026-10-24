"use client";

import { Icon } from "./Icon";
import { usePlayer } from "./PlayerProvider";

const fmt = (value: number) => {
  const seconds = Math.max(0, Math.round(value));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
};

export function Player() {
  const {
    tracks,
    current,
    playing,
    elapsed,
    liked,
    muted,
    queueOpen,
    currentIndex,
    togglePlay,
    seek,
    next,
    previous,
    toggleLike,
    toggleMute,
    toggleQueue,
    loadIndex,
  } = usePlayer();

  const progress = Math.min(100, (elapsed / current.duration) * 100);

  return (
    <div className={`player${playing ? " is-playing" : ""}`}>
      <div className="p-now">
        <img className="cover" src={current.cover} alt="" />
        <div className="p-info">
          <div className="p-title-row">
            <span className="p-eq" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <strong>{current.title}</strong>
          </div>
          <span>{current.artist}</span>
        </div>
        <button
          className={`p-like${liked ? " liked" : ""}`}
          type="button"
          aria-label={liked ? "Unlike this track" : "Like this track"}
          aria-pressed={liked}
          onClick={toggleLike}
        >
          <Icon name="fa-heart" />
        </button>
      </div>

      <div className="p-center">
        <div className="p-controls">
          <button className="pbtn" type="button" aria-label="Shuffle">
            <Icon name="fa-shuffle" />
          </button>
          <button className="pbtn" type="button" aria-label="Previous track" onClick={previous}>
            <Icon name="fa-backward-step" />
          </button>
          <button
            className="pbtn play"
            type="button"
            aria-label={playing ? "Pause" : "Play"}
            aria-pressed={playing}
            onClick={togglePlay}
          >
            <Icon name={playing ? "fa-pause" : "fa-play"} />
          </button>
          <button className="pbtn" type="button" aria-label="Next track" onClick={next}>
            <Icon name="fa-forward-step" />
          </button>
          <button className="pbtn" type="button" aria-label="Repeat">
            <Icon name="fa-repeat" />
          </button>
        </div>
        <div className="p-progress">
          <span className="p-time">{fmt(elapsed)}</span>
          <input
            className="p-range"
            type="range"
            min={0}
            max={current.duration}
            value={elapsed}
            aria-label="Seek"
            style={{ "--p": `${progress}%` } as React.CSSProperties}
            onChange={(event) => seek(Number(event.target.value))}
          />
          <span className="p-time">{fmt(current.duration)}</span>
        </div>
      </div>

      <div className="p-right">
        <button
          className={`pbtn${muted ? " on" : ""}`}
          type="button"
          aria-label={muted ? "Unmute" : "Mute"}
          aria-pressed={muted}
          onClick={toggleMute}
        >
          <Icon name={muted ? "fa-volume-xmark" : "fa-volume-high"} />
        </button>
        <button
          className="pbtn"
          type="button"
          aria-label="Queue"
          aria-expanded={queueOpen}
          aria-controls="player-queue"
          onClick={toggleQueue}
        >
          <Icon name="fa-list-ul" />
        </button>
      </div>

      <div
        id="player-queue"
        className={`p-queue-panel${queueOpen ? " open" : ""}`}
        hidden={!queueOpen}
      >
        <div className="p-queue-head">
          <strong>Up next</strong>
          <span>{tracks.length} tracks</span>
        </div>
        {tracks.map((track, trackIndex) => (
          <button
            key={`${track.title}-${track.artist}`}
            className={`p-queue-item${trackIndex === currentIndex ? " on" : ""}`}
            type="button"
            onClick={() => loadIndex(trackIndex)}
          >
            <img src={track.cover} alt="" />
            <span>
              <b>{track.title}</b>
              <small>
                {track.artist} · {fmt(track.duration)}
              </small>
            </span>
            <span className="p-queue-dur">{fmt(track.duration)}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
