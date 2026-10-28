import Link from "next/link";
import type { Metadata } from "next";
import { Icon } from "@/components/Icon";
import { TrackCard } from "@/components/TrackCard";

export const metadata: Metadata = {
  title: "Discover",
};

const vinyl =
  "https://images.unsplash.com/photo-1461360228754-6e81c478b882?auto=format&fit=crop&w=600&q=80";
const concert =
  "https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?auto=format&fit=crop&w=600&q=80";
const temple =
  "https://images.unsplash.com/photo-1528181304800-259b08848526?auto=format&fit=crop&w=600&q=80";
const mic =
  "https://images.unsplash.com/photo-1516280440614-37939bbacd81?auto=format&fit=crop&w=600&q=80";
const sunset =
  "https://images.unsplash.com/photo-1495616811223-4d98c6e9c869?auto=format&fit=crop&w=600&q=80";
const city =
  "https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=600&q=80";

const artists = [
  {
    name: "Kanya",
    meta: "Khmer pop · 1.2M plays",
    image:
      "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=100&q=80",
  },
  {
    name: "Dara",
    meta: "R&B · 640K plays",
    image:
      "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=100&q=80",
  },
  {
    name: "Malis",
    meta: "Ballad · 310K plays",
    image:
      "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=100&q=80",
  },
  {
    name: "Rithy",
    meta: "EDM · 980K plays",
    image:
      "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=100&q=80",
  },
];

export default function DiscoverPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Browse</div>
          <h1>Discover</h1>
          <p>Genres, moods, playlists and new voices from Cambodia and beyond.</p>
        </div>
        <Link className="btn btn-primary" href="/create">
          Create a song <Icon name="fa-arrow-right" />
        </Link>
      </div>

      <div className="chip-row discover-filters" aria-label="Filter by genre">
        <Link className="chip2 on" href="/discover">All</Link>
        <Link className="chip2" href="/discover">Khmer pop</Link>
        <Link className="chip2" href="/discover">Hip-hop</Link>
        <Link className="chip2" href="/discover">EDM</Link>
        <Link className="chip2" href="/discover">R&amp;B</Link>
        <Link className="chip2" href="/discover">Ballad</Link>
        <Link className="chip2" href="/discover">Lo-fi</Link>
        <Link className="chip2" href="/discover">Traditional</Link>
        <Link className="chip2" href="/discover">Chinese</Link>
      </div>

      <section className="banner">
        <img src="/hero.png" alt="Featured playlist" />
        <div className="banner-copy">
          <div className="eyebrow">Featured playlist</div>
          <h2>After hours</h2>
          <p>
            Neon-lit Khmer pop, late-night R&amp;B and slow-burning electronic
            tracks for the ride home.
          </p>
          <div className="banner-meta">
            <span className="live-dot" />
            18 tracks · 1h 12m · Updated today
          </div>
          <div className="page-actions">
            <Link className="btn btn-primary" href="/playlists/after-hours">
              Play playlist <Icon name="fa-play" />
            </Link>
            <Link className="btn btn-ghost" href="/charts">
              View chart
            </Link>
          </div>
        </div>
      </section>

      <div className="sec-head">
        <h2>New releases</h2>
        <Link href="/charts">See all</Link>
      </div>
      <div className="cards">
        <TrackCard image={vinyl} title="Golden Hour" artist="Malis" plays="1.2M" time="3:02" />
        <TrackCard image={concert} title="Bass Camp 2026" artist="Chmnaba Beats" plays="87K" time="4:30" />
        <TrackCard image={temple} title="Angkor Dreams" artist="Rithy AI" plays="79K" time="3:12" />
        <TrackCard image={mic} title="ស្រីមាស" artist="Vannak" plays="760K" time="4:11" />
        <TrackCard image={sunset} title="Sunset Vibes" artist="Dara AI" plays="64K" time="4:01" />
      </div>

      <div className="sec-head" style={{ marginTop: 30 }}>
        <h2>Because you listened to Kanya</h2>
        <Link href="/discover">See all</Link>
      </div>
      <div className="cards">
        <TrackCard image="/hero.png" title="Bassac Moon" artist="Kanya" plays="2.4M" time="3:24" position="50% 18%" />
        <TrackCard image={concert} title="Neon Lotus" artist="Rithy" plays="980K" time="2:58" />
        <TrackCard image={mic} title="ស្រីមាស" artist="Vannak" plays="760K" time="4:11" />
        <TrackCard image={vinyl} title="River Lights" artist="Dara" plays="410K" time="2:41" />
        <TrackCard image={city} title="Phnom Penh Nights" artist="Dara" plays="764K" time="3:24" />
      </div>

      <div className="sec-head" style={{ marginTop: 30 }}>
        <h2>Moods</h2>
        <Link href="/discover">All moods</Link>
      </div>
      <div className="mood-grid">
        <Link className="mood" href="/discover"><span /><b>Late night</b></Link>
        <Link className="mood" href="/discover"><span /><b>Focus</b></Link>
        <Link className="mood" href="/discover"><span /><b>Workout</b></Link>
        <Link className="mood" href="/discover"><span /><b>Rainy day</b></Link>
      </div>

      <div className="sec-head" style={{ marginTop: 30 }}>
        <h2>Khmer picks</h2>
        <Link href="/discover">See all</Link>
      </div>
      <div className="cards">
        <TrackCard image={mic} title="ស្រីមាស" artist="Vannak" plays="760K" time="4:11" />
        <TrackCard image={city} title="Khmer Love Story" artist="Mai AI" plays="98K" time="3:45" />
        <TrackCard image={temple} title="Angkor Dreams" artist="Rithy AI" plays="79K" time="3:12" />
        <TrackCard image="/hero.png" title="Bassac Moon" artist="Kanya" plays="2.4M" time="3:24" position="50% 18%" />
        <TrackCard image={city} title="Phnom Penh Nights" artist="Dara" plays="764K" time="3:24" />
      </div>

      <div className="sec-head" style={{ marginTop: 30 }}>
        <h2>Artists to follow</h2>
        <Link href="/community">All artists</Link>
      </div>
      <div className="creator-grid">
        {artists.map((artist) => (
          <div className="creator-card" key={artist.name}>
            <img src={artist.image} alt="" />
            <div>
              <strong>{artist.name}</strong>
              <span>{artist.meta}</span>
            </div>
            <button className="follow" type="button">Follow</button>
          </div>
        ))}
      </div>
    </div>
  );
}
