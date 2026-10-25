"use client";

import { Icon } from "@/components/Icon";
import { TrackCard } from "@/components/TrackCard";
import { usePlayer } from "@/components/PlayerProvider";
import type { Playlist } from "@/lib/playlist-data";

function parseTime(value: string): number {
  const match = value.match(/(\d+):(\d{2})/);
  return match ? Number(match[1]) * 60 + Number(match[2]) : 240;
}

function totalTime(playlist: Playlist): string {
  const seconds = playlist.tracks.reduce((sum, track) => sum + parseTime(track.time), 0);
  const minutes = Math.round(seconds / 60);
  return `${minutes} min`;
}

export function PlaylistView({ playlist }: { playlist: Playlist }) {
  const { playTrack } = usePlayer();

  const playAll = () => {
    const first = playlist.tracks[0];
    if (!first) return;
    playTrack({
      title: first.title,
      artist: first.artist,
      cover: first.image,
      duration: parseTime(first.time),
      elapsed: 0,
    });
  };

  return (
    <div className="page">
      <section className="playlist-hero">
        <img src={playlist.cover} alt="" />
        <div className="playlist-hero-copy">
          <div className="eyebrow">Playlist</div>
          <h1>{playlist.title}</h1>
          <p>{playlist.description}</p>
          <div className="playlist-meta">
            <span>{playlist.tracks.length} tracks</span>
            <span>{totalTime(playlist)}</span>
            <span>Camxora editorial</span>
          </div>
          <button className="btn btn-primary" type="button" onClick={playAll}>
            <Icon name="fa-play" /> Play all
          </button>
        </div>
      </section>

      <div className="sec-head" style={{ marginTop: 28 }}>
        <h2>Tracks</h2>
      </div>
      <div className="cards">
        {playlist.tracks.map((track) => (
          <TrackCard
            key={`${track.title}-${track.artist}`}
            image={track.image}
            title={track.title}
            artist={track.artist}
            plays={track.plays}
            time={track.time}
            position={track.position}
          />
        ))}
      </div>
    </div>
  );
}
