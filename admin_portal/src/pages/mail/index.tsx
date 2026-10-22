import { useEffect, useMemo, useState } from 'react';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from '@/hooks/use-toast';
import { apiClient } from '@/lib/http-client';

type Tab = 'deliveries' | 'campaigns' | 'templates' | 'automations' | 'suppressions' | 'settings';

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

interface TemplateDetail {
  id: string;
  name: string;
  subject: string;
  html: string;
  text: string | null;
  send_mode: string;
  locale: string;
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
  { key: 'settings', label: 'Settings' },
];

function fmt(value: string | null): string {
  if (!value) return 'â€”';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'â€”' : date.toLocaleString();
}

interface MailSettings {
  configured: boolean;
  webhook_configured: boolean;
  from_transactional: string;
  from_campaign: string;
  public_base_url: string;
  app_url: string;
  enabled: boolean;
}

const EMPTY_SETTINGS = {
  apiKey: '',
  webhookSecret: '',
  fromTransactional: '',
  fromCampaign: '',
  publicBaseUrl: '',
  appUrl: '',
};

export default function MailPage() {
  const [tab, setTab] = useState<Tab>('deliveries');
  const [newEmail, setNewEmail] = useState('');
  const queryClient = useQueryClient();

  const health = useQuery({
    queryKey: ['mail', 'health'],
    queryFn: async () => (await apiClient.get<Health>('/api/v3/mail/health')).data,
  });

  const mailSettings = useQuery({
    queryKey: ['mail', 'settings'],
    queryFn: async () => (await apiClient.get<MailSettings>('/api/v3/mail/settings')).data,
    enabled: tab === 'settings',
  });

  const [form, setForm] = useState(EMPTY_SETTINGS);

  // Seed the non-secret fields once the server view arrives; secrets stay blank
  // so an empty field means "leave the stored value alone".
  useEffect(() => {
    if (!mailSettings.data) return;
    setForm((prev) => ({
      ...prev,
      fromTransactional: mailSettings.data?.from_transactional ?? '',
      fromCampaign: mailSettings.data?.from_campaign ?? '',
      publicBaseUrl: mailSettings.data?.public_base_url ?? '',
      appUrl: mailSettings.data?.app_url ?? '',
    }));
  }, [mailSettings.data]);

  const saveSettings = useMutation({
    mutationFn: async (payload: Record<string, string>) =>
      (await apiClient.put<MailSettings>('/api/v3/mail/settings', payload)).data,
    onSuccess: () => {
      toast({ title: 'Mail settings saved' });
      setForm((prev) => ({ ...prev, apiKey: '', webhookSecret: '' }));
      void queryClient.invalidateQueries({ queryKey: ['mail', 'settings'] });
      void queryClient.invalidateQueries({ queryKey: ['mail', 'health'] });
    },
    onError: (error) =>
      toast({ title: 'Save failed', description: String(error), variant: 'destructive' }),
  });

  const deliveries = useQuery({
    queryKey: ['mail', 'deliveries'],
    queryFn: async () =>
      (
        await apiClient.get<{ rows: Delivery[]; stats: Record<string, number> }>(
          '/api/v3/mail/deliveries?limit=100',
        )
      ).data,
    enabled: tab === 'deliveries',
  });

  const campaigns = useQuery({
    queryKey: ['mail', 'campaigns'],
    queryFn: async () =>
      (await apiClient.get<{ rows: Campaign[] }>('/api/v3/mail/campaigns')).data,
    enabled: tab === 'campaigns',
  });

  const segmentsQuery = useQuery({
    queryKey: ['mail', 'segments'],
    queryFn: async () =>
      (
        await apiClient.get<{
          presets: Array<{ key: string; label: string; count: number }>;
          cooldownDays: number;
        }>('/api/v3/mail/segments')
      ).data,
    enabled: tab === 'campaigns',
  });

  const triggersQuery = useQuery({
    queryKey: ['mail', 'triggers'],
    queryFn: async () =>
      (
        await apiClient.get<{
          triggers: Array<{
            key: string;
            label: string;
            description: string;
            paramLabel?: string;
            defaultParam?: number;
            defaultCooldownDays: number;
          }>;
        }>('/api/v3/mail/triggers')
      ).data,
    enabled: tab === 'automations',
  });

  const [journeyName, setJourneyName] = useState('');
  const [journeyTemplate, setJourneyTemplate] = useState('');
  const [journeyTrigger, setJourneyTrigger] = useState('welcome');
  const [journeyParam, setJourneyParam] = useState('');
  const [journeyCooldown, setJourneyCooldown] = useState('');

  const createJourney = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post('/api/v3/mail/automations', {
          name: journeyName.trim(),
          templateId: journeyTemplate,
          trigger: journeyTrigger,
          cooldownDays: journeyCooldown ? Number(journeyCooldown) : undefined,
          audience: { triggerValue: journeyParam ? Number(journeyParam) : undefined },
        })
      ).data,
    onSuccess: () => {
      toast({ title: 'Journey created', description: 'Enable it when you are ready.' });
      setJourneyName('');
      setJourneyTemplate('');
      void queryClient.invalidateQueries({ queryKey: ['mail', 'automations'] });
    },
    onError: (error) =>
      toast({ title: 'Create failed', description: String(error), variant: 'destructive' }),
  });

  const [editingTemplate, setEditingTemplate] = useState<string | null>(null);
  const [tplForm, setTplForm] = useState({
    name: '',
    subject: '',
    html: '',
    sendMode: 'auto',
  });

  const templateDetail = useQuery({
    queryKey: ['mail', 'template', editingTemplate],
    queryFn: async () =>
      (await apiClient.get<TemplateDetail>(`/api/v3/mail/templates/${editingTemplate}`)).data,
    enabled: Boolean(editingTemplate),
  });

  // Seed the editor once the detail arrives; the form is local state so typing
  // does not fight a refetch.
  useEffect(() => {
    const detail = templateDetail.data;
    if (!detail) return;
    setTplForm({
      name: detail.name,
      subject: detail.subject,
      html: detail.html,
      sendMode: detail.send_mode,
    });
  }, [templateDetail.data]);

  const saveTemplate = useMutation({
    mutationFn: async () =>
      (
        await apiClient.put(`/api/v3/mail/templates/${editingTemplate}`, {
          name: tplForm.name,
          subject: tplForm.subject,
          html: tplForm.html,
          sendMode: tplForm.sendMode,
          locale: 'en',
          text: null,
        })
      ).data,
    onSuccess: () => {
      toast({ title: 'Template saved' });
      setEditingTemplate(null);
      void queryClient.invalidateQueries({ queryKey: ['mail', 'templates'] });
    },
    onError: (error) =>
      toast({ title: 'Save failed', description: String(error), variant: 'destructive' }),
  });

  const [campaignName, setCampaignName] = useState('');  const [campaignTemplate, setCampaignTemplate] = useState('');
  const [audience, setAudience] = useState({
    lifecycle: '',
    spendTier: '',
    excludeRecentPayers: false,
  });

  const createCampaign = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post('/api/v3/mail/campaigns', {
          name: campaignName.trim(),
          templateId: campaignTemplate,
          audience: {
            lifecycle: audience.lifecycle || null,
            spendTier: audience.spendTier || null,
            excludeRecentPayers: audience.excludeRecentPayers,
          },
        })
      ).data,
    onSuccess: () => {
      toast({
        title: 'Draft created',
        description: 'Press Test to review it, then Send.',
      });
      setCampaignName('');
      setCampaignTemplate('');
      void queryClient.invalidateQueries({ queryKey: ['mail', 'campaigns'] });
    },
    onError: (error) =>
      toast({ title: 'Create failed', description: String(error), variant: 'destructive' }),
  });

  const templates = useQuery({
    queryKey: ['mail', 'templates'],
    queryFn: async () =>
      (await apiClient.get<{ rows: Template[] }>('/api/v3/mail/templates')).data,
    // Always fetched: the campaign and journey builders both need it, and tying
    // it to the active tab left those pickers empty.
  });

  const automations = useQuery({
    queryKey: ['mail', 'automations'],
    queryFn: async () =>
      (await apiClient.get<{ rows: Automation[] }>('/api/v3/mail/automations')).data,
    enabled: tab === 'automations',
  });

  const suppressions = useQuery({
    queryKey: ['mail', 'suppressions'],
    queryFn: async () =>
      (await apiClient.get<{ rows: Suppression[] }>('/api/v3/mail/suppressions')).data,
    enabled: tab === 'suppressions',
  });

  const invalidate = (key: string) =>
    queryClient.invalidateQueries({ queryKey: ['mail', key] });

  const sendCampaign = useMutation({
    mutationFn: async (id: string) =>
      (await apiClient.post<{ queued: number; skipped: number; audience: number }>(
        `/api/v3/mail/campaigns/${id}/send`,
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
      (await apiClient.post<{ to: string }>(`/api/v3/mail/campaigns/${id}/test`, {})).data,
    onSuccess: (result) =>
      toast({ title: 'Test sent', description: `Delivered to ${result.to}.` }),
    onError: (error) =>
      toast({ title: 'Test failed', description: String(error), variant: 'destructive' }),
  });

  const toggleAutomation = useMutation({
    mutationFn: async (input: { id: string; isActive: boolean }) =>
      (await apiClient.put(`/api/v3/mail/automations/${input.id}`, { isActive: input.isActive })).data,
    onSuccess: () => void invalidate('automations'),
    onError: (error) =>
      toast({ title: 'Update failed', description: String(error), variant: 'destructive' }),
  });

  const addSuppression = useMutation({
    mutationFn: async (email: string) =>
      (await apiClient.post('/api/v3/mail/suppressions', { email })).data,
    onSuccess: () => {
      setNewEmail('');
      void invalidate('suppressions');
    },
    onError: (error) =>
      toast({ title: 'Could not add', description: String(error), variant: 'destructive' }),
  });

  const removeSuppression = useMutation({
    mutationFn: async (email: string) =>
      (await apiClient.delete(`/api/v3/mail/suppressions/${encodeURIComponent(email)}`)).data,
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
            {deliveries.isLoading && <p className="text-sm text-muted-foreground">Loadingâ€¦</p>}
            {(deliveries.data?.rows ?? []).length === 0 && (
              <p className="text-sm text-muted-foreground">No mail sent yet.</p>
            )}
            {(deliveries.data?.rows ?? []).length > 0 && (
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
                  {(deliveries.data?.rows ?? []).map((row) => (
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
          <CardContent className="space-y-4 overflow-x-auto">
            <div className="space-y-3 rounded-lg border border-border p-4">
              <div className="text-sm font-semibold">New campaign</div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  placeholder="Campaign name"
                  value={campaignName}
                  onChange={(event) => setCampaignName(event.target.value)}
                />
                <Select value={campaignTemplate} onValueChange={setCampaignTemplate}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a template" />
                  </SelectTrigger>
                  <SelectContent>
                    {(templates.data?.rows ?? [])
                      .filter((row) => row.is_active)
                      .map((row) => (
                        <SelectItem key={row.id} value={row.id}>
                          {row.name}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-wrap gap-2">
                {(segmentsQuery.data?.presets ?? []).map((preset) => {
                  const [presetLifecycle = '', presetSpendTier = ''] = preset.key.split('-');
                  const active =
                    audience.lifecycle === presetLifecycle &&
                    audience.spendTier === presetSpendTier;
                  return (
                    <Button
                      key={preset.key}
                      size="sm"
                      variant={active ? 'default' : 'outline'}
                      onClick={() =>
                        setAudience((prev) => ({
                          ...prev,
                          lifecycle: presetLifecycle,
                          spendTier: presetSpendTier,
                        }))
                      }
                    >
                      {preset.label}
                      <span className="ml-2 font-semibold">{preset.count}</span>
                    </Button>
                  );
                })}
              </div>

              <label className="flex items-start gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={audience.excludeRecentPayers}
                  onChange={(event) =>
                    setAudience({ ...audience, excludeRecentPayers: event.target.checked })
                  }
                />
                <span>
                  Exclude anyone who paid in the last 14 days — keep this on for discount mail.
                </span>
              </label>

              <Button
                disabled={
                  createCampaign.isPending || !campaignName.trim() || !campaignTemplate
                }
                onClick={() => createCampaign.mutate()}
              >
                {createCampaign.isPending ? 'Creating…' : 'Create draft'}
              </Button>
            </div>

            {(campaigns.data?.rows ?? []).length === 0 && (
              <p className="text-sm text-muted-foreground">
                No campaigns yet. Create one from the mail templates you want to send.
              </p>
            )}
            {(campaigns.data?.rows ?? []).length > 0 && (
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
                  {(campaigns.data?.rows ?? []).map((row) => (
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
          <CardContent className="space-y-4 overflow-x-auto">
            {editingTemplate && (
              <div className="space-y-3 rounded-lg border border-border p-4">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold">Edit template</div>
                  <Button size="sm" variant="ghost" onClick={() => setEditingTemplate(null)}>
                    Close
                  </Button>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <Input
                    placeholder="Name"
                    value={tplForm.name}
                    onChange={(event) => setTplForm({ ...tplForm, name: event.target.value })}
                  />
                  <Input
                    placeholder="Subject"
                    value={tplForm.subject}
                    onChange={(event) => setTplForm({ ...tplForm, subject: event.target.value })}
                  />
                </div>

                <textarea
                  className="min-h-[240px] w-full rounded-md border border-input bg-transparent p-3 font-mono text-xs"
                  value={tplForm.html}
                  onChange={(event) => setTplForm({ ...tplForm, html: event.target.value })}
                />

                <div className="flex flex-wrap items-center gap-3">
                  <Select
                    value={tplForm.sendMode}
                    onValueChange={(value) => setTplForm({ ...tplForm, sendMode: value })}
                  >
                    <SelectTrigger className="w-40">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">auto</SelectItem>
                      <SelectItem value="manual">manual</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button
                    disabled={
                      saveTemplate.isPending || !tplForm.name.trim() || !tplForm.subject.trim()
                    }
                    onClick={() => saveTemplate.mutate()}
                  >
                    {saveTemplate.isPending ? 'Saving…' : 'Save template'}
                  </Button>
                  {templateDetail.isLoading && (
                    <span className="text-xs text-muted-foreground">Loading…</span>
                  )}
                </div>

                <p className="text-xs text-muted-foreground">
                  Variables are re-extracted on save. Switching to <strong>manual</strong> removes the
                  template from the automation picker; existing journeys keep sending.
                </p>
              </div>
            )}

            {(templates.data?.rows ?? []).length === 0 && (
              <p className="text-sm text-muted-foreground">No templates yet.</p>
            )}
            {(templates.data?.rows ?? []).length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Mode</TableHead>
                    <TableHead className="text-right">Vars</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(templates.data?.rows ?? []).map((row) => (
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
                      <TableCell className="text-right">
                        <Button size="sm" variant="ghost" onClick={() => setEditingTemplate(row.id)}>
                          Edit
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

      {tab === 'automations' && (
        <Card>
          <CardHeader>
            <CardTitle>Automations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 overflow-x-auto">
            <div className="space-y-3 rounded-lg border border-border p-4">
              <div className="text-sm font-semibold">New journey</div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  placeholder="Journey name"
                  value={journeyName}
                  onChange={(event) => setJourneyName(event.target.value)}
                />
                <Select value={journeyTemplate} onValueChange={setJourneyTemplate}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a template" />
                  </SelectTrigger>
                  <SelectContent>
                    {(templates.data?.rows ?? [])
                      .filter((row) => row.is_active && row.send_mode !== 'manual')
                      .map((row) => (
                        <SelectItem key={row.id} value={row.id}>
                          {row.name}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <Select
                  value={journeyTrigger}
                  onValueChange={(value) => {
                    setJourneyTrigger(value);
                    setJourneyParam('');
                    setJourneyCooldown('');
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Trigger" />
                  </SelectTrigger>
                  <SelectContent>
                    {(triggersQuery.data?.triggers ?? []).map((trigger) => (
                      <SelectItem key={trigger.key} value={trigger.key}>
                        {trigger.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  type="number"
                  placeholder={
                    triggersQuery.data?.triggers.find((t) => t.key === journeyTrigger)
                      ?.paramLabel ?? 'Threshold'
                  }
                  value={journeyParam}
                  onChange={(event) => setJourneyParam(event.target.value)}
                />
                <Input
                  type="number"
                  min={1}
                  placeholder={
                    journeyCooldown ||
                    String(
                      triggersQuery.data?.triggers.find((t) => t.key === journeyTrigger)
                        ?.defaultCooldownDays ?? 30,
                    )
                  }
                  value={journeyCooldown}
                  onChange={(event) => setJourneyCooldown(event.target.value)}
                />
              </div>

              <p className="text-xs text-muted-foreground">
                Manual-only templates are excluded here by design — discount and seasonal mail
                must be sent from a campaign.
              </p>

              <Button
                disabled={createJourney.isPending || !journeyName.trim() || !journeyTemplate}
                onClick={() => createJourney.mutate()}
              >
                {createJourney.isPending ? 'Creating…' : 'Create journey'}
              </Button>
            </div>
            {(automations.data?.rows ?? []).length === 0 && (
              <p className="text-sm text-muted-foreground">
                No journeys yet. Manual-only templates never run here â€” use a campaign.
              </p>
            )}
            {(automations.data?.rows ?? []).length > 0 && (
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
                  {(automations.data?.rows ?? []).map((row) => (
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
            {(suppressions.data?.rows ?? []).length === 0 && (
              <p className="text-sm text-muted-foreground">
                Nothing suppressed. Bounces and complaints are added automatically by Resend.
              </p>
            )}
            {(suppressions.data?.rows ?? []).length > 0 && (
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
                  {(suppressions.data?.rows ?? []).map((row) => (
                    <TableRow key={row.email}>
                      <TableCell className="break-all">{row.email}</TableCell>
                      <TableCell>{row.reason}</TableCell>
                      <TableCell className="text-muted-foreground">{row.source ?? 'â€”'}</TableCell>
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
      {tab === 'settings' && (
        <Card>
          <CardHeader>
            <CardTitle>Resend settings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Stored encrypted and applied without a redeploy. Leave a secret blank to keep the
              current value. API key:{' '}
              <strong>{mailSettings.data?.configured ? 'configured' : 'missing'}</strong> Â· webhook:{' '}
              <strong>{mailSettings.data?.webhook_configured ? 'configured' : 'missing'}</strong>
            </p>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Resend API key</div>
                <Input
                  type="password"
                  autoComplete="off"
                  placeholder={mailSettings.data?.configured ? 'stored â€” leave blank to keep' : 're_...'}
                  value={form.apiKey}
                  onChange={(event) => setForm({ ...form, apiKey: event.target.value })}
                />
              </div>
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Webhook signing secret</div>
                <Input
                  type="password"
                  autoComplete="off"
                  placeholder={
                    mailSettings.data?.webhook_configured ? 'stored â€” leave blank to keep' : 'whsec_...'
                  }
                  value={form.webhookSecret}
                  onChange={(event) => setForm({ ...form, webhookSecret: event.target.value })}
                />
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Transactional from</div>
                <Input
                  value={form.fromTransactional}
                  onChange={(event) => setForm({ ...form, fromTransactional: event.target.value })}
                  placeholder="CAMXORA <no-reply@mail.camxora.com>"
                />
              </div>
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Marketing from</div>
                <Input
                  value={form.fromCampaign}
                  onChange={(event) => setForm({ ...form, fromCampaign: event.target.value })}
                  placeholder="CAMXORA <hello@mail.camxora.com>"
                />
              </div>
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Tracking / unsubscribe base URL</div>
                <Input
                  value={form.publicBaseUrl}
                  onChange={(event) => setForm({ ...form, publicBaseUrl: event.target.value })}
                  placeholder="https://mail.camxora.com/api/mail"
                />
              </div>
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Product site (CTA target)</div>
                <Input
                  value={form.appUrl}
                  onChange={(event) => setForm({ ...form, appUrl: event.target.value })}
                  placeholder="https://music.camxora.com"
                />
              </div>
            </div>

            <Button
              disabled={saveSettings.isPending}
              onClick={() => {
                // Only send secrets that were actually typed, so an empty field
                // never wipes a stored key.
                const payload: Record<string, string> = {
                  fromTransactional: form.fromTransactional,
                  fromCampaign: form.fromCampaign,
                  publicBaseUrl: form.publicBaseUrl,
                  appUrl: form.appUrl,
                };
                if (form.apiKey.trim()) payload.apiKey = form.apiKey.trim();
                if (form.webhookSecret.trim()) payload.webhookSecret = form.webhookSecret.trim();
                saveSettings.mutate(payload);
              }}
            >
              {saveSettings.isPending ? 'Savingâ€¦' : 'Save settings'}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
