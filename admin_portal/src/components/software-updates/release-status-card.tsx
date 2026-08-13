import { Badge } from '@/components/ui/badge';

type ReleaseStatusCardProps = {
  version: string;
  downloadUrl: string;
  isPublished: boolean;
  publishedAt: string | null;
  liveVersion?: string;
  liveDownloadUrl?: string;
  liveMandatory?: boolean;
  livePublishedAt?: string | null;
};

function UrlRow({ label, url }: { label: string; url: string }) {
  if (!url.trim()) {
    return <p className="text-xs text-amber-400/90">No {label.toLowerCase()} yet.</p>;
  }
  return (
    <p className="text-xs text-slate-500 break-all">
      {label}: <span className="text-slate-300">{url}</span>
    </p>
  );
}

export function ReleaseStatusCard({
  version,
  downloadUrl,
  isPublished,
  publishedAt,
  liveVersion = '',
  liveDownloadUrl = '',
  liveMandatory = false,
  livePublishedAt = null,
}: ReleaseStatusCardProps) {
  const hasLive = Boolean(liveVersion.trim());
  const draftDiffersFromLive = hasLive && !isPublished;

  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/40 p-4 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium text-slate-200">Release status</p>
        <Badge variant={hasLive ? 'default' : 'secondary'}>
          {hasLive ? 'Live on /download' : 'Draft only'}
        </Badge>
        {liveMandatory ? <Badge variant="destructive">Force update</Badge> : null}
      </div>

      {hasLive ? (
        <div className="space-y-2">
          <p className="text-[11px] uppercase tracking-wide text-slate-500">Live (public)</p>
          <div className="grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
            <p>
              <span className="text-slate-500">Version:</span>{' '}
              <span className="text-slate-200">{liveVersion}</span>
            </p>
            <p>
              <span className="text-slate-500">Published:</span>{' '}
              <span className="text-slate-200">
                {livePublishedAt ? new Date(livePublishedAt).toLocaleString() : 'Live'}
              </span>
            </p>
          </div>
          <UrlRow
            label="Live download URL"
            url={liveDownloadUrl || (isPublished ? downloadUrl : '')}
          />
        </div>
      ) : (
        <p className="text-xs text-slate-500">
          Public website and in-app update prompts stay hidden until you publish a release.
        </p>
      )}

      {draftDiffersFromLive ? (
        <div className="rounded-md border border-amber-900/40 bg-amber-950/20 px-3 py-2 text-xs text-amber-100/80">
          Draft {version || '—'} is not public. Website, changelog, and force update stay on live{' '}
          {liveVersion}.
        </div>
      ) : null}

      <div className="space-y-2">
        <p className="text-[11px] uppercase tracking-wide text-slate-500">Draft (not public until Publish)</p>
        <div className="grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
          <p>
            <span className="text-slate-500">Version:</span>{' '}
            <span className="text-slate-200">{version || '—'}</span>
          </p>
          <p>
            <span className="text-slate-500">Status:</span>{' '}
            <span className="text-slate-200">
              {isPublished
                ? publishedAt
                  ? `Same as live · ${new Date(publishedAt).toLocaleString()}`
                  : 'Same as live'
                : 'Not published'}
            </span>
          </p>
        </div>
        <UrlRow
          label="Draft download URL"
          url={draftDiffersFromLive || !hasLive ? downloadUrl : downloadUrl || liveDownloadUrl}
        />
      </div>
    </div>
  );
}
