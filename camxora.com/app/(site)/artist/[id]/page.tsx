import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArtistView } from "@/components/ArtistView";
import { allArtistSlugs, getArtist } from "@/lib/artist-data";

type ArtistPageProps = {
  params: Promise<{ id: string }>;
};

export function generateStaticParams() {
  return allArtistSlugs().map((id) => ({ id }));
}

export async function generateMetadata({ params }: ArtistPageProps): Promise<Metadata> {
  const { id } = await params;
  const artist = getArtist(id);
  return { title: artist ? artist.name : "Artist" };
}

export default async function ArtistPage({ params }: ArtistPageProps) {
  const { id } = await params;
  const artist = getArtist(id);
  if (!artist) notFound();
  return <ArtistView artist={artist} />;
}
