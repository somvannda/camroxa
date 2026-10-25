import type { PlaylistTrack } from "@/lib/playlist-data";

export type ArtistProfile = {
  id: string;
  name: string;
  genre: string;
  bio: string;
  avatar: string;
  followers: string;
  monthlyPlays: string;
  tracks: PlaylistTrack[];
};

const kanyaTracks: PlaylistTrack[] = [
  { image: "/hero.png", title: "Bassac Moon", artist: "Kanya", plays: "2.4M", time: "3:24" },
  { image: "/hero.png", title: "Slow Motion", artist: "Kanya", plays: "220K", time: "3:18" },
  { image: "/hero.png", title: "Golden Hour", artist: "Kanya", plays: "1.2M", time: "3:02" },
];

const artists: Record<string, ArtistProfile> = {
  kanya: {
    id: "kanya",
    name: "Kanya",
    genre: "Khmer pop",
    bio: "Late-night Khmer pop with soft vocals, warm synths, and hooks built for the ride home.",
    avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=200&q=80",
    followers: "48.2K",
    monthlyPlays: "2.4M",
    tracks: kanyaTracks,
  },
  dara: {
    id: "dara",
    name: "Dara",
    genre: "R&B",
    bio: "Slow-burning R&B and river-light melodies from Phnom Penh.",
    avatar: "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=200&q=80",
    followers: "21.8K",
    monthlyPlays: "640K",
    tracks: [
      { image: "https://images.unsplash.com/photo-1495616811223-4d98c6e9c869?auto=format&fit=crop&w=600&q=80", title: "Sunset Vibes", artist: "Dara", plays: "64K", time: "4:01" },
      { image: "https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=600&q=80", title: "River Lights", artist: "Dara", plays: "410K", time: "2:41" },
    ],
  },
  malis: {
    id: "malis",
    name: "Malis",
    genre: "Ballad",
    bio: "Ballads about home, distance, and the people who stay.",
    avatar: "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=200&q=80",
    followers: "16.4K",
    monthlyPlays: "310K",
    tracks: [
      { image: "https://images.unsplash.com/photo-1461360228754-6e81c478b882?auto=format&fit=crop&w=600&q=80", title: "Golden Hour", artist: "Malis", plays: "1.2M", time: "3:02" },
    ],
  },
  rithy: {
    id: "rithy",
    name: "Rithy",
    genre: "EDM",
    bio: "Festival synths and bass lines with a Khmer pop centre.",
    avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=200&q=80",
    followers: "33.1K",
    monthlyPlays: "980K",
    tracks: [
      { image: "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=600&q=80", title: "Neon Lotus", artist: "Rithy", plays: "980K", time: "2:58" },
      { image: "https://images.unsplash.com/photo-1528181304800-259b08848526?auto=format&fit=crop&w=600&q=80", title: "Angkor Dreams", artist: "Rithy AI", plays: "79K", time: "3:12" },
    ],
  },
};

export function getArtist(id: string): ArtistProfile | null {
  return artists[id] ?? null;
}

export function allArtistSlugs(): string[] {
  return Object.keys(artists);
}
