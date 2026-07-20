import { Badge } from '@/components/ui/badge';

type ReleaseStatusCardProps = {
  version: string;
  downloadUrl: string;
  isPublished: boolean;
  publishedAt: string | null;
};

export function ReleaseStatusCard({
  version,
  downloadUrl,
  isPublished,
  publishedAt,
}: ReleaseStatusCardProps) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium text-slate-200">Release status</p>
        <Badge variant={isPublished ? 'default' : 'secondary'}>
          {isPublished ? 'Live on /download' : 'Draft only'}
        </Badge>
      </div>
      <div className="grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
        <p>
          <span className="text-slate-500">Version:</span>{' '}
          <span className="text-slate-200">{version || '—'}</span>
        </p>
        <p>
          <span className="text-slate-500">Published:</span>{' '}
          <span className="text-slate-200">
            {publishedAt ? new Date(publishedAt).toLocaleString() : 'Not published'}
          </span>
        </p>
      </div>
      {downloadUrl ? (
        <p className="text-xs text-slate-500 break-all">
          Download URL: <span className="text-slate-300">{downloadUrl}</span>
        </p>
      ) : (
        <p className="text-xs text-amber-400/90">No download URL configured yet.</p>
      )}
      {!isPublished ? (
        <p className="text-xs text-slate-500">
          Public website and in-app update prompts stay hidden until you publish a release.
        </p>
      ) : null}
    </div>
  );
}
