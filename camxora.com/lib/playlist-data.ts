export type PlaylistTrack = {
  image: string;
  title: string;
  artist: string;
  plays: string;
  time: string;
  position?: string;
};

export type Playlist = {
  slug: string;
  title: string;
  description: string;
  cover: string;
  tracks: PlaylistTrack[];
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
const cinema =
  "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=600&q=80";

const playlists: Record<string, Playlist> = {
  "chill-vibes": {
    slug: "chill-vibes",
    title: "Chill Vibes",
    description: "Slow burns, soft vocals, and late-night electronic textures for the ride home.",
    cover: sunset,
    tracks: [
      { image: sunset, title: "Sunset Vibes", artist: "Dara AI", plays: "64K", time: "4:01" },
      { image: vinyl, title: "Golden Hour", artist: "Malis", plays: "1.2M", time: "3:02" },
      { image: city, title: "River Lights", artist: "Dara", plays: "410K", time: "2:41" },
      { image: mic, title: "Slow Motion", artist: "Kanya", plays: "220K", time: "3:18" },
      { image: "/hero.png", title: "Bassac Moon", artist: "Kanya", plays: "2.4M", time: "3:24" },
    ],
  },
  "edm-party": {
    slug: "edm-party",
    title: "EDM Party",
    description: "High-energy drops, festival synths, and bass lines built for the main stage.",
    cover: concert,
    tracks: [
      { image: concert, title: "Bass Camp 2026", artist: "Chmnaba Beats", plays: "87K", time: "4:30" },
      { image: cinema, title: "Neon Lotus", artist: "Rithy", plays: "980K", time: "2:58" },
      { image: city, title: "After Hours", artist: "Malis", plays: "312K", time: "3:44" },
      { image: vinyl, title: "Pulse Check", artist: "Rithy AI", plays: "91K", time: "3:12" },
      { image: sunset, title: "Last Light", artist: "Chmnaba Beats", plays: "54K", time: "4:08" },
    ],
  },
  "khmer-hits": {
    slug: "khmer-hits",
    title: "Khmer Hits",
    description: "The Khmer pop, ballad, and hip-hop tracks getting the most plays right now.",
    cover: temple,
    tracks: [
      { image: "/hero.png", title: "Bassac Moon", artist: "Kanya", plays: "2.4M", time: "3:24" },
      { image: mic, title: "Golden Hour", artist: "Malis", plays: "1.2M", time: "3:02" },
      { image: temple, title: "Angkor Dreams", artist: "Rithy AI", plays: "79K", time: "3:12" },
      { image: city, title: "Phnom Penh Tonight", artist: "Sochcat AI", plays: "1.8M", time: "4:12" },
      { image: vinyl, title: "River Lights", artist: "Dara", plays: "410K", time: "2:41" },
    ],
  },
  "my-playlist": {
    slug: "my-playlist",
    title: "My Playlist",
    description: "A starter mix of Camxora tracks. Add your own from Discover or the Create studio.",
    cover: "/hero.png",
    tracks: [
      { image: "/hero.png", title: "Phnom Penh Tonight", artist: "Sochcat AI", plays: "1.8M", time: "4:12" },
      { image: vinyl, title: "Golden Hour", artist: "Malis", plays: "1.2M", time: "3:02" },
      { image: concert, title: "Bass Camp 2026", artist: "Chmnaba Beats", plays: "87K", time: "4:30" },
      { image: temple, title: "Angkor Dreams", artist: "Rithy AI", plays: "79K", time: "3:12" },
    ],
  },
};

export function getPlaylist(slug: string): Playlist | null {
  return playlists[slug] ?? null;
}

export function allPlaylistSlugs(): string[] {
  return Object.keys(playlists);
}
