import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Mail, Send, Trash2 } from 'lucide-react';

import { ErrorState } from '@/components/shared/error-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { toast } from '@/hooks/use-toast';
import { apiClient } from '@/lib/http-client';

type Tab = 'deliveries' | 'campaigns' | 'templates' | 'automations' | 'suppressions';

interface Health {
  configured: boolean;
  enabled: boolean;
  from_transactional: string;
  from_campaign: string;
  base_url: string;
  queue_depth: number;
  suppressed: number;
  counts: Record<string, number>;
}

interface Delivery {
  id: string;
  email: string;
  kind: string;
  subject: string;
  status: string;
  open_count: number;
  click_count: number;
  error: string | null;
  created_at: string;
}

interface Campaign {
  id: string;
  name: string;
  status: string;
  template_name: string;
  queued: number;
  opened: number;
  clicked: number;
  created_at: string;
}

interface Template {
  id: string;
  name: string;
  subject: string;
  send_mode: string;
  is_active: boolean;
  var_count: number;
}

interface Automation {
  id: string;
  name: string;
  trigger: string;
  template_name: string;
  send_mode: string;
  cooldown_days: number;
  is_active: boolean;
  last_run_at: string | null;
}

interface Suppression {
  email: string;
  reason: string;
  source: string | null;
  created_at: string;
}

const TABS: Array<{ key: Tab; label: string }> = [
  { key: 'deliveries', label: 'Deliveries' },
  { key: 'campaigns', label: 'Campaigns' },
  { key: 'templates', label: 'Templates' },
  { key: 'automations', label: 'Automations' },
  { key: 'suppressions', label: 'Suppressions' },
];

function fmt(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

export default function MailPage() {
  const [tab, setTab] = useState<Tab>('deliveries');
  const [newEmail, setNewEmail] = useState('');
  const queryClient = useQueryClient();

  const health = useQuery({
    queryKey: ['mail', 'health'],
    queryFn: async () => (await apiClient.get<Health>('/mail/health')).data,
  });

  const deliveries = useQuery({
    queryKey: ['mail', 'deliveries'],
    queryFn: async () =>
      (
        await apiClient.get<{ rows: Delivery[]; stats: Record<string, number> }>(
          '/mail/deliveries?limit=100',
        )
      ).data,
    enabled: tab === 'deliveries',
  });

  const campaigns = useQuery({
    queryKey: ['mail', 'campaigns'],
    queryFn: async () =>
      (await apiClient.get<{ rows: Campaign[] }>('/mail/campaigns')).data,
    enabled: tab === 'campaigns',
  });

  const templates = useQuery({
    queryKey: ['mail', 'templates'],
    queryFn: async () =>
      (await apiClient.get<{ rows: Template[] }>('/mail/templates')).data,
    enabled: tab === 'templates',
  });

  const automations = useQuery({
    queryKey: ['mail', 'automations'],
    queryFn: async () =>
      (await apiClient.get<{ rows: Automation[] }>('/mail/automations')).data,
    enabled: tab === 'automations',
  });

  const suppressions = useQuery({
    queryKey: ['mail', 'suppressions'],
    queryFn: async () =>
      (await apiClient.get<{ rows: Suppression[] }>('/mail/suppressions')).data,
    enabled: tab === 'suppressions',
  });

  const invalidate = (key: string) =>
    queryClient.invalidateQueries({ queryKey: ['mail', key] });

  const sendCampaign = useMutation({
    mutationFn: async (id: string) =>
      (await apiClient.post<{ queued: number; skipped: number; audience: number }>(
        `/mail/campaigns/${id}/send`,
      )).data,
    onSuccess: (result) => {
      toast({
        title: 'Campaign queued',
        description: `${result.queued} of ${result.audience} recipients queued, ${result.skipped} skipped.`,
      });
      void invalidate('campaigns');
    },
    onError: (error) =>
      toast({ title: 'Send failed', description: String(error), variant: 'destructive' }),
  });

  const testCampaign = useMutation({
    mutationFn: async (id: string) =>
      (await apiClient.post<{ to: string }>(`/mail/campaigns/${id}/test`, {})).data,
    onSuccess: (result) =>
      toast({ title: 'Test sent', description: `Delivered to ${result.to}.` }),
    onError: (error) =>
      toast({ title: 'Test failed', description: String(error), variant: 'destructive' }),
  });

  const toggleAutomation = useMutation({
    mutationFn: async (input: { id: string; isActive: boolean }) =>
      (await apiClient.put(`/mail/automations/${input.id}`, { isActive: input.isActive })).data,
    onSuccess: () => void invalidate('automations'),
    onError: (error) =>
      toast({ title: 'Update failed', description: String(error), variant: 'destructive' }),
  });

  const addSuppression = useMutation({
    mutationFn: async (email: string) =>
      (await apiClient.post('/mail/suppressions', { email })).data,
    onSuccess: () => {
      setNewEmail('');
      void invalidate('suppressions');
    },
    onError: (error) =>
      toast({ title: 'Could not add', description: String(error), variant: 'destructive' }),
  });

  const removeSuppression = useMutation({
    mutationFn: async (email: string) =>
      (await apiClient.delete(`/mail/suppressions/${encodeURIComponent(email)}`)).data,
    onSuccess: () => void invalidate('suppressions'),
  });

  const healthTone = useMemo(() => {
    if (!health.data) return 'bg-white/10';
    if (health.data.configured && health.data.enabled) return 'bg-emerald-500';
    if (health.data.configured) return 'bg-amber-500';
    return 'bg-red-500';
  }, [health.data]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <Mail className="h-6 w-6" /> Mail
          </h1>
          <p className="text-sm text-muted-foreground">
            Delivery ledger, campaigns and journeys for music.camxora.com
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className={`h-2.5 w-2.5 rounded-full ${healthTone}`} />
          {health.data?.configured
            ? health.data.enabled
              ? 'Resend connected'
              : 'Sending paused'
            : 'API key not configured'}
        </div>
      </div>

      {health.error && <ErrorState message={String(health.error)} />}

      {health.data && (
        <Card>
          <CardContent className="grid gap-3 pt-6 text-xs sm:grid-cols-2">
            <div>
              <div className="text-muted-foreground">Transactional from</div>
              <div className="break-all">{health.data.from_transactional}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Marketing from</div>
              <div className="break-all">{health.data.from_campaign}</div>
            </div>
            <div className="sm:col-span-2">
              <div className="text-muted-foreground">Tracking / unsubscribe base</div>
              <div className="break-all">{health.data.base_url}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Queued</div>
              <div className="font-semibold">{health.data.queue_depth}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Suppressed</div>
              <div className="font-semibold">{health.data.suppressed}</div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap gap-2">
        {TABS.map((item) => (
          <Button
            key={item.key}
            size="sm"
            variant={tab === item.key ? 'default' : 'outline'}
            onClick={() => setTab(item.key)}
          >
            {item.label}
          </Button>
        ))}
      </div>

      {tab === 'deliveries' && (
        <Card>
          <CardHeader>
            <CardTitle>Deliveries</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            {deliveries.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
            {deliveries.data && deliveries.data.rows.length === 0 && (
              <p className="text-sm text-muted-foreground">No mail sent yet.</p>
            )}
            {deliveries.data && deliveries.data.rows.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Recipient</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Opens</TableHead>
                    <TableHead className="text-right">Clicks</TableHead>
                    <TableHead>Sent</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {deliveries.data.rows.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell className="break-all">{row.email}</TableCell>
                      <TableCell className="max-w-[22rem] truncate" title={row.subject}>
                        {row.subject}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{row.status}</Badge>
                        {row.error && (
                          <span className="ml-2 text-[11px] text-destructive">{row.error}</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">{row.open_count}</TableCell>
                      <TableCell className="text-right">{row.click_count}</TableCell>
                      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                        {fmt(row.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {tab === 'campaigns' && (
        <Card>
          <CardHeader>
            <CardTitle>Campaigns</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            {campaigns.data && campaigns.data.rows.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No campaigns yet. Create one from the mail templates you want to send.
              </p>
            )}
            {campaigns.data && campaigns.data.rows.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Campaign</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Queued</TableHead>
                    <TableHead className="text-right">Opened</TableHead>
                    <TableHead className="text-right">Clicked</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {campaigns.data.rows.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell>
                        <div>{row.name}</div>
                        <div className="text-xs text-muted-foreground">{row.template_name}</div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{row.status}</Badge>
                      </TableCell>
                      <TableCell className="text-right">{row.queued}</TableCell>
                      <TableCell className="text-right">{row.opened}</TableCell>
                      <TableCell className="text-right">{row.clicked}</TableCell>
                      <TableCell className="whitespace-nowrap text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => testCampaign.mutate(row.id)}
                        >
                          Test
                        </Button>
                        <Button
                          size="sm"
                          disabled={row.status === 'sent' || row.status === 'sending'}
                          onClick={() => sendCampaign.mutate(row.id)}
                        >
                          <Send className="mr-1 h-3.5 w-3.5" /> Send
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {tab === 'templates' && (
        <Card>
          <CardHeader>
            <CardTitle>Templates</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            {templates.data && templates.data.rows.length === 0 && (
              <p className="text-sm text-muted-foreground">No templates yet.</p>
            )}
            {templates.data && templates.data.rows.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Mode</TableHead>
                    <TableHead className="text-right">Vars</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {templates.data.rows.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell>{row.name}</TableCell>
                      <TableCell className="max-w-[20rem] truncate" title={row.subject}>
                        {row.subject}
                      </TableCell>
                      <TableCell>
                        <Badge variant={row.send_mode === 'manual' ? 'secondary' : 'outline'}>
                          {row.send_mode}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">{row.var_count}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {tab === 'automations' && (
        <Card>
          <CardHeader>
            <CardTitle>Automations</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            {automations.data && automations.data.rows.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No journeys yet. Manual-only templates never run here — use a campaign.
              </p>
            )}
            {automations.data && automations.data.rows.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Journey</TableHead>
                    <TableHead>Trigger</TableHead>
                    <TableHead>Cooldown</TableHead>
                    <TableHead>Last run</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {automations.data.rows.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell>
                        <div>{row.name}</div>
                        <div className="text-xs text-muted-foreground">{row.template_name}</div>
                      </TableCell>
                      <TableCell className="text-xs">
                        <Badge variant="outline">{row.trigger}</Badge>
                      </TableCell>
                      <TableCell>{row.cooldown_days}d</TableCell>
                      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                        {fmt(row.last_run_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant={row.is_active ? 'secondary' : 'default'}
                          onClick={() =>
                            toggleAutomation.mutate({ id: row.id, isActive: !row.is_active })
                          }
                        >
                          {row.is_active ? 'Disable' : 'Enable'}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {tab === 'suppressions' && (
        <Card>
          <CardHeader>
            <CardTitle>Suppressions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="add address to the hard stop list"
                value={newEmail}
                onChange={(event) => setNewEmail(event.target.value)}
              />
              <Button
                disabled={!newEmail.includes('@')}
                onClick={() => addSuppression.mutate(newEmail)}
              >
                Add
              </Button>
            </div>
            {suppressions.data && suppressions.data.rows.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Nothing suppressed. Bounces and complaints are added automatically by Resend.
              </p>
            )}
            {suppressions.data && suppressions.data.rows.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Email</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Added</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {suppressions.data.rows.map((row) => (
                    <TableRow key={row.email}>
                      <TableCell className="break-all">{row.email}</TableCell>
                      <TableCell>{row.reason}</TableCell>
                      <TableCell className="text-muted-foreground">{row.source ?? '—'}</TableCell>
                      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                        {fmt(row.created_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => removeSuppression.mutate(row.email)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
