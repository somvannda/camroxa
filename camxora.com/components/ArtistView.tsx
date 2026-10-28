"use client";

import { Icon } from "@/components/Icon";
import { TrackCard } from "@/components/TrackCard";
import { usePlayer } from "@/components/PlayerProvider";
import type { ArtistProfile } from "@/lib/artist-data";

function parseTime(value: string): number {
  const match = value.match(/(\d+):(\d{2})/);
  return match ? Number(match[1]) * 60 + Number(match[2]) : 240;
}

export function ArtistView({ artist }: { artist: ArtistProfile }) {
  const { playTrack } = usePlayer();

  const playAll = () => {
    const first = artist.tracks[0];
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
      <section className="artist-hero">
        <img className="artist-hero-bg" src={artist.tracks[0]?.image || "/hero.png"} alt="" />
        <img className="artist-avatar" src={artist.avatar} alt={artist.name} />
        <div className="artist-hero-copy">
          <div className="eyebrow">Artist</div>
          <h1>{artist.name}</h1>
          <p>{artist.bio}</p>
          <div className="artist-meta">
            <span>{artist.genre}</span>
            <span>{artist.followers} followers</span>
            <span>{artist.monthlyPlays} monthly plays</span>
          </div>
          <button className="btn btn-primary" type="button" onClick={playAll}>
            <Icon name="fa-play" /> Play top tracks
          </button>
        </div>
      </section>

      <div className="sec-head" style={{ marginTop: 28 }}>
        <h2>Popular tracks</h2>
      </div>
      <div className="cards">
        {artist.tracks.map((track) => (
          <TrackCard
            key={`${track.title}-${track.artist}`}
            image={track.image}
            title={track.title}
            artist={track.artist}
            plays={track.plays}
            time={track.time}
          />
        ))}
      </div>
    </div>
  );
}
