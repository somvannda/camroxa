import { useState } from 'react';
import { Loader2, Plus, Search, ShieldAlert, Snowflake, Trash2 } from 'lucide-react';

import {
  useSignupDomainAccounts,
  useSignupDomainAction,
  useSignupDomainGuard,
  useUpdateSignupDomainGuard,
} from '@/hooks/use-signup-domain-guard';
import { toast } from '@/hooks/use-toast';
import type { SignupDomainAccount } from '@/types/signup-domain-guard';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';

const FREEZE_HOURS = [6, 24, 72];

function normalizeDomain(value: string): string {
  return value.trim().toLowerCase().replace(/^https?:\/\//, '').replace(/^@/, '');
}

function DomainListCard({
  title,
  domains,
  emptyLabel,
  placeholder,
  onAdd,
  onRemove,
  disabled,
}: {
  title: string;
  domains: string[];
  emptyLabel: string;
  placeholder: string;
  onAdd: (domain: string) => void;
  onRemove: (domain: string) => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState('');

  const handleAdd = () => {
    const domain = normalizeDomain(value);
    if (!domain || !domain.includes('.')) return;
    onAdd(domain);
    setValue('');
  };

  return (
    <Card className="border-slate-800 bg-slate-900/50">
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <div>
          <CardTitle className="text-lg">{title}</CardTitle>
          <CardDescription>{domains.length} domains</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {domains.length === 0 ? (
          <p className="text-sm text-slate-400">{emptyLabel}</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {domains.map((domain) => (
              <span
                key={domain}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-800/60 px-2 py-1 text-xs text-slate-200"
              >
                {domain}
                <button
                  type="button"
                  aria-label={`Remove ${domain}`}
                  className="text-slate-400 hover:text-red-400 disabled:opacity-40"
                  disabled={disabled}
                  onClick={() => onRemove(domain)}
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleAdd();
            }}
            placeholder={placeholder}
          />
          <Button
            variant="outline"
            onClick={handleAdd}
            disabled={!value.trim().includes('.') || disabled}
          >
            <Plus className="mr-1 h-4 w-4" />
            Add
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function AccountRow({ account }: { account: SignupDomainAccount }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-slate-700 px-3 py-2 text-sm">
      <div className="min-w-[220px] flex-1">
        <p className="text-slate-100">{account.email}</p>
        <p className="text-xs text-slate-500">{account.created_at ?? ''}</p>
      </div>
      <span
        className={`rounded-full px-2 py-0.5 text-xs ${
          account.status === 'active'
            ? 'bg-emerald-500/15 text-emerald-300'
            : 'bg-red-500/15 text-red-300'
        }`}
      >
        {account.status}
      </span>
      <span className="text-xs text-slate-500">
        {account.email_confirmed ? 'verified' : 'unverified'}
      </span>
    </div>
  );
}

export function SignupDomainGuardSection() {
  const { data, isLoading, isError, refetch } = useSignupDomainGuard();
  const updateConfig = useUpdateSignupDomainGuard();
  const action = useSignupDomainAction();

  const [lookupInput, setLookupInput] = useState('');
  const [lookupDomain, setLookupDomain] = useState<string | null>(null);
  const { data: accountsData, isLoading: accountsLoading } = useSignupDomainAccounts(lookupDomain);
  const [freezeHours, setFreezeHours] = useState(72);
  const [suspendDomain, setSuspendDomain] = useState<string | null>(null);
  const [capInput, setCapInput] = useState<string>('');

  if (isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (isError) {
    return <Button onClick={() => refetch()}>Retry loading signup domain guard</Button>;
  }

  const blocked = data?.blocked ?? [];
  const trusted = data?.trusted ?? [];
  const maxFree = data?.max_free ?? 3;
  const accounts = accountsData?.accounts ?? [];
  const hasAccounts = lookupDomain !== null && accounts.length > 0;

  const applyAction = (domain: string, act: 'block' | 'freeze' | 'unfreeze' | 'suspend' | 'reactivate') => {
    action.mutate(
      {
        domain,
        action: act,
        hours: act === 'freeze' ? freezeHours : undefined,
        reason: 'Admin action via portal',
      },
      {
        onSuccess: (result) => {
          if (act === 'block') {
            toast({ title: `Blocked ${result.domain}` });
          } else {
            toast({
              title: `${act} applied to ${result.affected_accounts} account${
                result.affected_accounts === 1 ? '' : 's'
              }`,
            });
          }
        },
        onError: (error: Error) => {
          toast({ title: 'Action failed', description: error.message, variant: 'destructive' });
        },
      },
    );
  };

  const handleCapSave = () => {
    const parsed = parseInt(capInput, 10);
    if (!Number.isFinite(parsed) || parsed < 1 || parsed > 100) return;
    updateConfig.mutate(
      { max_free: parsed },
      {
        onSuccess: () => {
          toast({ title: `Free accounts per domain: ${parsed}` });
          setCapInput('');
        },
      },
    );
  };

  const changeList = (kind: 'blocked' | 'trusted', next: string[]) => {
    updateConfig.mutate(
      kind === 'blocked' ? { blocked: next } : { trusted: next },
      {
        onError: (error: Error) =>
          toast({ title: 'Update failed', description: error.message, variant: 'destructive' }),
      },
    );
  };

  return (
    <div className="space-y-4">
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <ShieldAlert className="h-5 w-5 text-purple-400" />
              Email Signup Guard
            </CardTitle>
            <CardDescription>
              Blocks disposable-email signups and caps free music-web accounts per domain.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 text-sm text-slate-300">
            <span className="text-slate-500">Max free per domain</span>
            <Input
              type="number"
              min={1}
              max={100}
              value={capInput || String(maxFree)}
              onChange={(e) => setCapInput(e.target.value)}
              className="h-9 w-20"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleCapSave}
              disabled={updateConfig.isPending}
            >
              Save
            </Button>
          </div>
        </CardHeader>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <DomainListCard
          title="Blocked domains"
          domains={blocked}
          emptyLabel="No blocked domains."
          placeholder="bowlfuel.com"
          disabled={updateConfig.isPending}
          onAdd={(domain) => changeList('blocked', [...blocked, domain])}
          onRemove={(domain) => changeList('blocked', blocked.filter((d) => d !== domain))}
        />
        <DomainListCard
          title="Trusted domains"
          domains={trusted}
          emptyLabel="No trusted domains (defaults apply)."
          placeholder="gmail.com"
          disabled={updateConfig.isPending}
          onAdd={(domain) => changeList('trusted', [...trusted, domain])}
          onRemove={(domain) => changeList('trusted', trusted.filter((d) => d !== domain))}
        />
      </div>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-lg">Domain Accounts</CardTitle>
          <CardDescription>Look up accounts using an email domain.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              value={lookupInput}
              onChange={(e) => setLookupInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') setLookupDomain(normalizeDomain(lookupInput) || null);
              }}
              placeholder="bowlfuel.com"
            />
            <Button
              variant="outline"
              onClick={() => setLookupDomain(normalizeDomain(lookupInput) || null)}
              disabled={!lookupInput.trim().includes('.')}
            >
              <Search className="mr-1 h-4 w-4" />
              Look up
            </Button>
          </div>

          {lookupDomain === null ? null : accountsLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <div className="space-y-2">
              <div className="text-sm text-slate-300">
                {lookupDomain}: {accounts.length} account{accounts.length === 1 ? '' : 's'}
              </div>
              {accounts.length === 0 ? (
                <p className="text-sm text-slate-500">No accounts found on this domain.</p>
              ) : (
                <div className="grid gap-2 sm:grid-cols-2">
                  {accounts.map((account) => (
                    <AccountRow key={account.id} account={account} />
                  ))}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2 pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!hasAccounts || action.isPending}
                  onClick={() => applyAction(lookupDomain, 'block')}
                >
                  Block domain
                </Button>
                <div className="flex items-center gap-1">
                  <select
                    value={freezeHours}
                    onChange={(e) => setFreezeHours(Number(e.target.value))}
                    className="h-8 rounded-md border border-slate-700 bg-slate-900 px-2 text-xs text-slate-100"
                    aria-label="Freeze duration hours"
                  >
                    {FREEZE_HOURS.map((h) => (
                      <option key={h} value={h}>
                        {h}h
                      </option>
                    ))}
                  </select>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!hasAccounts || action.isPending}
                    onClick={() => applyAction(lookupDomain, 'freeze')}
                  >
                    <Snowflake className="mr-1 h-3.5 w-3.5" />
                    Freeze generation
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!hasAccounts || action.isPending}
                    onClick={() => applyAction(lookupDomain, 'unfreeze')}
                  >
                    Unfreeze
                  </Button>
                </div>
                <Button
                  variant="destructive"
                  size="sm"
                  disabled={!hasAccounts || action.isPending}
                  onClick={() => setSuspendDomain(lookupDomain)}
                >
                  Suspend accounts
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={!hasAccounts || action.isPending}
                  onClick={() => applyAction(lookupDomain, 'reactivate')}
                >
                  Reactivate
                </Button>
                {action.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={suspendDomain !== null}
        onOpenChange={(open) => {
          if (!open) setSuspendDomain(null);
        }}
        title="Suspend domain accounts"
        description={`Suspend all active accounts using ${suspendDomain ?? ''}? They will be blocked from logging in and generating until reactivated.`}
        onConfirm={() => {
          if (suspendDomain !== null) {
            applyAction(suspendDomain, 'suspend');
            setSuspendDomain(null);
          }
        }}
        variant="destructive"
        confirmText="Suspend"
        isLoading={action.isPending}
      />
    </div>
  );
}
