import { ArrowRight, Clock, History } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useProviderEvents } from '@/hooks/use-key-pool';
import type { KeyStatus } from '@/types/key-pool';

interface EventLogProps {
  provider: string;
}

const STATUS_STYLES: Record<KeyStatus, string> = {
  active: 'bg-green-500/10 text-green-400 border-green-500/30',
  rate_limited: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  exhausted: 'bg-red-500/10 text-red-400 border-red-500/30',
  disabled: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
};

const STATUS_LABELS: Record<KeyStatus, string> = {
  active: 'Active',
  rate_limited: 'Rate Limited',
  exhausted: 'Exhausted',
  disabled: 'Disabled',
};

const TRIGGER_LABELS: Record<string, string> = {
  rate_limit_429: 'Rate limit (429)',
  exhausted_402: 'Payment required (402)',
  exhausted_403: 'Billing error (403)',
  cooldown_recovery: 'Cooldown recovery',
  admin_disable: 'Admin disabled',
  admin_enable: 'Admin enabled',
};

function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);

  if (diffSeconds < 60) return 'Just now';
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function formatAbsoluteTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function EventLog({ provider }: EventLogProps) {
  const { data: events, isLoading, isError } = useProviderEvents(provider);

  if (isLoading) {
    return (
      <div className="rounded-lg border border-navy-700 bg-navy-800 p-6">
        <div className="flex items-center gap-2 mb-4">
          <History className="h-4 w-4 text-slate-400" />
          <h3 className="text-sm font-medium text-white">Event Log</h3>
        </div>
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-10 animate-pulse rounded bg-navy-700/50"
            />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-navy-700 bg-navy-800 p-6">
        <div className="flex items-center gap-2 mb-4">
          <History className="h-4 w-4 text-slate-400" />
          <h3 className="text-sm font-medium text-white">Event Log</h3>
        </div>
        <p className="text-sm text-red-400">Failed to load events.</p>
      </div>
    );
  }

  if (!events || events.length === 0) {
    return (
      <div className="rounded-lg border border-navy-700 bg-navy-800 p-6">
        <div className="flex items-center gap-2 mb-4">
          <History className="h-4 w-4 text-slate-400" />
          <h3 className="text-sm font-medium text-white">Event Log</h3>
        </div>
        <p className="text-sm text-slate-400">No status transitions recorded yet.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-navy-700 bg-navy-800 p-6">
      <div className="flex items-center gap-2 mb-4">
        <History className="h-4 w-4 text-slate-400" />
        <h3 className="text-sm font-medium text-white">Event Log</h3>
        <span className="text-xs text-slate-500">Last {events.length} transitions</span>
      </div>

      <TooltipProvider delayDuration={300}>
        <Table>
          <TableHeader>
            <TableRow className="border-navy-700 hover:bg-transparent">
              <TableHead className="text-slate-400">Time</TableHead>
              <TableHead className="text-slate-400">Key</TableHead>
              <TableHead className="text-slate-400">Status Change</TableHead>
              <TableHead className="text-slate-400">Trigger</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {events.map((event) => (
              <TableRow
                key={event.id}
                className="border-navy-700 hover:bg-navy-700/30"
              >
                {/* Timestamp with tooltip */}
                <TableCell className="py-2.5">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="inline-flex items-center gap-1.5 text-xs text-slate-400 cursor-default">
                        <Clock className="h-3 w-3" />
                        {formatRelativeTime(event.created_at)}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      {formatAbsoluteTime(event.created_at)}
                    </TooltipContent>
                  </Tooltip>
                </TableCell>

                {/* Key label */}
                <TableCell className="py-2.5">
                  <span className="text-xs font-medium text-white">
                    {event.key_label}
                  </span>
                </TableCell>

                {/* Status transition: previous → new */}
                <TableCell className="py-2.5">
                  <div className="flex items-center gap-1.5">
                    <Badge className={`text-[10px] px-1.5 py-0 ${STATUS_STYLES[event.previous_status]}`}>
                      {STATUS_LABELS[event.previous_status]}
                    </Badge>
                    <ArrowRight className="h-3 w-3 text-slate-500 shrink-0" />
                    <Badge className={`text-[10px] px-1.5 py-0 ${STATUS_STYLES[event.new_status]}`}>
                      {STATUS_LABELS[event.new_status]}
                    </Badge>
                  </div>
                </TableCell>

                {/* Trigger reason */}
                <TableCell className="py-2.5">
                  <span className="text-xs text-slate-400">
                    {TRIGGER_LABELS[event.trigger_reason] || event.trigger_reason}
                    {event.http_status_code && (
                      <span className="ml-1 text-slate-500">
                        ({event.http_status_code})
                      </span>
                    )}
                  </span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TooltipProvider>
    </div>
  );
}
