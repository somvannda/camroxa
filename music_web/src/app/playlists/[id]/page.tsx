import PlaylistDetailPageClient from '@/components/playlist-detail-page-client';

export default async function PlaylistDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PlaylistDetailPageClient playlistId={id} />;
}
