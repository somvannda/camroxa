import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PlaylistView } from "@/components/PlaylistView";
import { allPlaylistSlugs, getPlaylist } from "@/lib/playlist-data";

type PlaylistPageProps = {
  params: Promise<{ slug: string }>;
};

export function generateStaticParams() {
  return allPlaylistSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PlaylistPageProps): Promise<Metadata> {
  const { slug } = await params;
  const playlist = getPlaylist(slug);
  return { title: playlist ? playlist.title : "Playlist" };
}

export default async function PlaylistPage({ params }: PlaylistPageProps) {
  const { slug } = await params;
  const playlist = getPlaylist(slug);
  if (!playlist) notFound();
  return <PlaylistView playlist={playlist} />;
}
