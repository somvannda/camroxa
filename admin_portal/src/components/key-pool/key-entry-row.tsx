import { useState } from 'react';
import { Key, Pencil, Trash2, Power, PowerOff, ChevronDown, ChevronUp } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useEnableKey, useDisableKey, useDeleteKey } from '@/hooks/use-key-pool';
import type { ApiKeyEntry, KeyStatus } from '@/types/key-pool';

interface KeyEntryRowProps {
  entry: ApiKeyEntry;
  provider: string;
  onEdit: (entry: ApiKeyEntry) => void;
  onDeleteConfirm: (entry: ApiKeyEntry) => void;
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

function formatLastUsed(lastUsed: string | null): string {
  if (!lastUsed) return 'Never';
  const date = new Date(lastUsed);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);

  if (diffMinutes < 1) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function calculateSuccessRate(entry: ApiKeyEntry): string {
  if (entry.total_requests === 0) return '—';
  const rate = (entry.success_count / entry.total_requests) * 100;
  return `${rate.toFixed(1)}%`;
}

function formatCooldownRemaining(seconds: number | null): string {
  if (seconds === null || seconds <= 0) return '—';
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSecs = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainingSecs}s`;
  const hours = Math.floor(minutes / 60);
  const remainingMins = minutes % 60;
  return `${hours}h ${remainingMins}m`;
}

export function KeyEntryRow({ entry, provider, onEdit, onDeleteConfirm }: KeyEntryRowProps) {
  const [expanded, setExpanded] = useState(false);
  const enableKey = useEnableKey(provider);
  const disableKey = useDisableKey(provider);
  const deleteKey = useDeleteKey(provider);

  const isToggling = enableKey.isPending || disableKey.isPending;
  const isDeleting = deleteKey.isPending;

  function handleToggleStatus() {
    if (entry.status === 'disabled') {
      enableKey.mutate(entry.id);
    } else if (entry.status === 'active') {
      disableKey.mutate(entry.id);
    }
  }

  function handleDelete() {
    onDeleteConfirm(entry);
  }

  const canToggle = entry.status === 'active' || entry.status === 'disabled';

  return (
    <div className="rounded-md border border-navy-700 bg-navy-900 transition-colors hover:border-navy-600">
      {/* Main row */}
      <div className="flex items-center justify-between px-4 py-3">
        {/* Expand toggle */}
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0 mr-2"
          onClick={() => setExpanded(!expanded)}
          aria-label={expanded ? 'Collapse details' : 'Expand details'}
          aria-expanded={expanded}
        >
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-slate-400" />
          ) : (
            <ChevronDown className="h-4 w-4 text-slate-400" />
          )}
        </Button>

        {/* Key info */}
        <div className="flex items-center gap-4 min-w-0 flex-1">
          <Key className="h-4 w-4 shrink-0 text-slate-400" />
          <div className="min-w-0 space-y-0.5">
            <p className="truncate text-sm font-medium text-white">{entry.label}</p>
            <p className="truncate text-xs font-mono text-slate-400">{entry.masked_key}</p>
          </div>
        </div>

        {/* Status and metrics */}
        <div className="flex items-center gap-4 shrink-0">
          <Badge className={STATUS_STYLES[entry.status]}>
            {STATUS_LABELS[entry.status]}
          </Badge>

          <div className="hidden md:flex items-center gap-4 text-xs text-slate-400">
            <span title="Priority">P{entry.priority}</span>
            <span title="Daily requests">{entry.daily_requests} reqs</span>
            <span title="Last used">{formatLastUsed(entry.last_used_at)}</span>
          </div>

          {/* Action buttons */}
          <TooltipProvider delayDuration={300}>
            <div className="flex items-center gap-1">
              {/* Enable/Disable toggle */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={handleToggleStatus}
                    disabled={!canToggle || isToggling}
                    aria-label={entry.status === 'disabled' ? 'Enable key' : 'Disable key'}
                  >
                    {entry.status === 'disabled' ? (
                      <Power className="h-4 w-4 text-green-400" />
                    ) : (
                      <PowerOff className="h-4 w-4 text-slate-400 hover:text-yellow-400" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {!canToggle
                    ? `Cannot toggle (${STATUS_LABELS[entry.status]})`
                    : entry.status === 'disabled'
                      ? 'Enable key'
                      : 'Disable key'}
                </TooltipContent>
              </Tooltip>

              {/* Edit */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => onEdit(entry)}
                    aria-label="Edit key"
                  >
                    <Pencil className="h-4 w-4 text-slate-400 hover:text-blue-400" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Edit key</TooltipContent>
              </Tooltip>

              {/* Delete */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={handleDelete}
                    disabled={isDeleting}
                    aria-label="Delete key"
                  >
                    <Trash2 className="h-4 w-4 text-slate-400 hover:text-red-400" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Delete key</TooltipContent>
              </Tooltip>
            </div>
          </TooltipProvider>
        </div>
      </div>

      {/* Expanded detail section */}
      {expanded && (
        <div className="border-t border-navy-700 bg-navy-900/50 px-4 py-3">
          <div className="grid grid-cols-2 gap-x-8 gap-y-2 sm:grid-cols-3 lg:grid-cols-5">
            <div className="space-y-0.5">
              <p className="text-xs text-slate-500">Total Requests</p>
              <p className="text-sm font-medium text-white">{entry.total_requests.toLocaleString()}</p>
            </div>
            <div className="space-y-0.5">
              <p className="text-xs text-slate-500">Daily Requests</p>
              <p className="text-sm font-medium text-white">{entry.daily_requests.toLocaleString()}</p>
            </div>
            <div className="space-y-0.5">
              <p className="text-xs text-slate-500">Success Rate</p>
              <p className="text-sm font-medium text-white">{calculateSuccessRate(entry)}</p>
            </div>
            <div className="space-y-0.5">
              <p className="text-xs text-slate-500">Last Used</p>
              <p className="text-sm font-medium text-white">{formatLastUsed(entry.last_used_at)}</p>
            </div>
            {entry.status === 'rate_limited' && entry.cooldown_remaining_seconds !== null && (
              <div className="space-y-0.5">
                <p className="text-xs text-slate-500">Cooldown Remaining</p>
                <p className="text-sm font-medium text-yellow-400">{formatCooldownRemaining(entry.cooldown_remaining_seconds)}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
