import { useMemo, useState } from 'react';

import { PageHeader } from '@/components/shared/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  useDeleteAlbum,
  useDeleteTrack,
  useRepublishAlbum,
  useRepublishTrack,
  useStreamingAlbums,
  useStreamingCatalog,
  useUnpublishAlbum,
  useUnpublishTrack,
} from '@/hooks/use-streaming';
import { toast } from '@/hooks/use-toast';

type StatusFilter = 'all' | 'published' | 'unpublished';

function confirmAction(message: string): boolean {
  return window.confirm(message);
}

export default function StreamingCatalogPage() {
  const { data: tracksData, isLoading: tracksLoading, isError: tracksError, refetch: refetchTracks } =
    useStreamingCatalog();
  const { data: albumsData, isLoading: albumsLoading, isError: albumsError, refetch: refetchAlbums } =
    useStreamingAlbums();
  const unpublishTrack = useUnpublishTrack();
  const republishTrack = useRepublishTrack();
  const deleteTrack = useDeleteTrack();
  const unpublishAlbum = useUnpublishAlbum();
  const republishAlbum = useRepublishAlbum();
  const deleteAlbum = useDeleteAlbum();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [query, setQuery] = useState('');

  const tracks = useMemo(() => {
    const items = tracksData ?? [];
    const q = query.trim().toLowerCase();
    return items.filter((track) => {
      if (statusFilter !== 'all' && track.publish_status !== statusFilter) return false;
      if (!q) return true;
      return (
        track.title.toLowerCase().includes(q) ||
        track.album_name.toLowerCase().includes(q) ||
        (track.artist_name ?? '').toLowerCase().includes(q)
      );
    });
  }, [tracksData, query, statusFilter]);

  const albums = useMemo(() => {
    const items = albumsData ?? [];
    const q = query.trim().toLowerCase();
    return items.filter((album) => {
      if (statusFilter !== 'all' && album.publish_status !== statusFilter) return false;
      if (!q) return true;
      return (
        album.album_name.toLowerCase().includes(q) ||
        (album.artist_name ?? '').toLowerCase().includes(q)
      );
    });
  }, [albumsData, query, statusFilter]);

  const refreshAll = () => {
    void refetchTracks();
    void refetchAlbums();
  };

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Music Streaming Catalog"
        description="Manage tracks and albums on music.camxora.com. Hide (unpublish) removes items from the public portal; delete removes them permanently from the catalog."
        actions={
          <Button variant="outline" onClick={refreshAll}>
            Refresh
          </Button>
        }
      />

      <Card className="border-slate-800 bg-slate-900/50">
        <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center">
          <Input
            className="md:max-w-sm"
            placeholder="Filter by title, album, or artist…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Select
            value={statusFilter}
            onValueChange={(value) => setStatusFilter(value as StatusFilter)}
          >
            <SelectTrigger className="md:w-48">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="published">Published</SelectItem>
              <SelectItem value="unpublished">Hidden</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Tabs defaultValue="tracks">
        <TabsList>
          <TabsTrigger value="tracks">Tracks</TabsTrigger>
          <TabsTrigger value="albums">Albums</TabsTrigger>
        </TabsList>

        <TabsContent value="tracks" className="mt-4 space-y-4">
          {tracksLoading ? <Skeleton className="h-64 w-full" /> : null}
          {tracksError ? (
            <Card className="border-slate-800 bg-slate-900/50">
              <CardContent className="space-y-3 p-6">
                <p className="text-sm text-red-300">Unable to load tracks.</p>
                <Button variant="outline" onClick={() => refetchTracks()}>
                  Retry
                </Button>
              </CardContent>
            </Card>
          ) : null}

          {!tracksLoading && !tracksError ? (
            <Card className="border-slate-800 bg-slate-900/50">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Title</TableHead>
                    <TableHead>Album</TableHead>
                    <TableHead>Artist</TableHead>
                    <TableHead>Variant</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tracks.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="py-8 text-center text-slate-400">
                        No tracks match this filter.
                      </TableCell>
                    </TableRow>
                  ) : (
                    tracks.map((track) => (
                      <TableRow key={track.id}>
                        <TableCell className="font-medium text-slate-100">{track.title}</TableCell>
                        <TableCell>{track.album_name}</TableCell>
                        <TableCell>{track.artist_name ?? '—'}</TableCell>
                        <TableCell className="uppercase">{track.variant}</TableCell>
                        <TableCell>
                          <Badge
                            variant={track.publish_status === 'published' ? 'default' : 'secondary'}
                          >
                            {track.publish_status === 'published' ? 'Published' : 'Hidden'}
                          </Badge>
                        </TableCell>
                        <TableCell className="space-x-2 text-right">
                          {track.publish_status === 'published' ? (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={unpublishTrack.isPending}
                              onClick={() =>
                                unpublishTrack.mutate(track.id, {
                                  onSuccess: () => toast({ title: 'Track hidden from portal' }),
                                  onError: () =>
                                    toast({ title: 'Hide failed', variant: 'destructive' }),
                                })
                              }
                            >
                              Hide
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={republishTrack.isPending}
                              onClick={() =>
                                republishTrack.mutate(track.id, {
                                  onSuccess: () => toast({ title: 'Track published' }),
                                  onError: () =>
                                    toast({ title: 'Publish failed', variant: 'destructive' }),
                                })
                              }
                            >
                              Publish
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-red-400/30 text-red-300"
                            disabled={deleteTrack.isPending}
                            onClick={() => {
                              if (
                                !confirmAction(
                                  `Delete "${track.title}" permanently? This cannot be undone.`,
                                )
                              ) {
                                return;
                              }
                              deleteTrack.mutate(track.id, {
                                onSuccess: () => toast({ title: 'Track deleted' }),
                                onError: () =>
                                  toast({ title: 'Delete failed', variant: 'destructive' }),
                              });
                            }}
                          >
                            Delete
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </Card>
          ) : null}
        </TabsContent>

        <TabsContent value="albums" className="mt-4 space-y-4">
          {albumsLoading ? <Skeleton className="h-64 w-full" /> : null}
          {albumsError ? (
            <Card className="border-slate-800 bg-slate-900/50">
              <CardContent className="space-y-3 p-6">
                <p className="text-sm text-red-300">Unable to load albums.</p>
                <Button variant="outline" onClick={() => refetchAlbums()}>
                  Retry
                </Button>
              </CardContent>
            </Card>
          ) : null}

          {!albumsLoading && !albumsError ? (
            <Card className="border-slate-800 bg-slate-900/50">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Album</TableHead>
                    <TableHead>Artist</TableHead>
                    <TableHead>Tracks</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {albums.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="py-8 text-center text-slate-400">
                        No albums match this filter.
                      </TableCell>
                    </TableRow>
                  ) : (
                    albums.map((album) => (
                      <TableRow key={album.id}>
                        <TableCell className="font-medium text-slate-100">{album.album_name}</TableCell>
                        <TableCell>{album.artist_name ?? '—'}</TableCell>
                        <TableCell>
                          {album.published_track_count} published / {album.track_count} total
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={album.publish_status === 'published' ? 'default' : 'secondary'}
                          >
                            {album.publish_status === 'published' ? 'Published' : 'Hidden'}
                          </Badge>
                          {album.published_track_count === 0 ? (
                            <span className="ml-2 text-xs text-slate-500">(hidden on portal — 0 tracks)</span>
                          ) : null}
                        </TableCell>
                        <TableCell className="space-x-2 text-right">
                          {album.publish_status === 'published' ? (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={unpublishAlbum.isPending}
                              onClick={() =>
                                unpublishAlbum.mutate(album.id, {
                                  onSuccess: () => toast({ title: 'Album hidden from portal' }),
                                  onError: () =>
                                    toast({ title: 'Hide failed', variant: 'destructive' }),
                                })
                              }
                            >
                              Hide
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={
                                republishAlbum.isPending || album.published_track_count === 0
                              }
                              onClick={() =>
                                republishAlbum.mutate(album.id, {
                                  onSuccess: () => toast({ title: 'Album published' }),
                                  onError: () =>
                                    toast({
                                      title: 'Publish failed — album needs at least one published track',
                                      variant: 'destructive',
                                    }),
                                })
                              }
                            >
                              Publish
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-red-400/30 text-red-300"
                            disabled={deleteAlbum.isPending}
                            onClick={() => {
                              if (
                                !confirmAction(
                                  `Delete album "${album.album_name}" and all its tracks permanently?`,
                                )
                              ) {
                                return;
                              }
                              deleteAlbum.mutate(album.id, {
                                onSuccess: () => toast({ title: 'Album deleted' }),
                                onError: () =>
                                  toast({ title: 'Delete failed', variant: 'destructive' }),
                              });
                            }}
                          >
                            Delete
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </Card>
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}
