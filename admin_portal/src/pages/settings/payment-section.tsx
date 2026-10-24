import { useEffect, useMemo, useState } from 'react';

import {
  useChmabaBillingConfig,
  useUpdateChmabaBillingConfig,
} from '@/hooks/use-billing-chmaba';
import {
  useCutluyBillingConfig,
  useUpdateCutluyBillingConfig,
} from '@/hooks/use-billing-cutluy';
import { useSystemSettings, useUpsertSetting } from '@/hooks/use-settings';
import { toast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const BILLING_ACTIVE_PROVIDER_KEY = 'billing.active_provider';
const BILLING_PORTAL_BASE_URL_KEY = 'billing.portal_base_url';

const KHQR_PROVIDERS = [
  {
    id: 'mock',
    label: 'Mock Checkout',
    description: 'Development checkout simulator for testing onboarding and payment flows.',
  },
  {
    id: 'cutluy',
    label: 'CutLuy KHQR',
    description: 'Hosted KHQR checkout via CutLuy.',
  },
  {
    id: 'chmaba',
    label: 'ChmabaPay KHQR',
    description: 'Direct KHQR / ABA PayWay checkout via pay.chmaba.com.',
  },
] as const;

function enabledKey(providerId: string) {
  return `billing.provider.${providerId}.enabled`;
}

function parseEnabled(raw: string | undefined, fallback: boolean) {
  if (raw === undefined) return fallback;
  const normalized = raw.trim().toLowerCase();
  if (['true', '1', 'yes', 'on'].includes(normalized)) return true;
  if (['false', '0', 'no', 'off'].includes(normalized)) return false;
  return fallback;
}

export function PaymentSection() {
  const { data } = useSystemSettings();
  const { data: cutluyConfig, isLoading: cutluyLoading } = useCutluyBillingConfig();
  const { data: chmabaConfig, isLoading: chmabaLoading } = useChmabaBillingConfig();
  const upsertSetting = useUpsertSetting();
  const updateCutluy = useUpdateCutluyBillingConfig();
  const updateChmaba = useUpdateChmabaBillingConfig();

  const settingsMap = useMemo(() => {
    return new Map((data?.settings ?? []).map((item) => [item.key, item.value]));
  }, [data?.settings]);

  const providerStates = useMemo(
    () =>
      KHQR_PROVIDERS.map((provider) => ({
        ...provider,
        // Default disabled: the backend only allows Mock in debug, so the UI
        // must not present it as enabled when no setting exists.
        enabled: parseEnabled(settingsMap.get(enabledKey(provider.id)), false),
      })),
    [settingsMap],
  );

  const enabledProviders = providerStates.filter((provider) => provider.enabled);
  const configuredProvider = settingsMap.get(BILLING_ACTIVE_PROVIDER_KEY) ?? (enabledProviders[0]?.id ?? 'none');
  const configuredPortalBaseUrl = settingsMap.get(BILLING_PORTAL_BASE_URL_KEY) ?? 'http://localhost:3001';

  const [provider, setProvider] = useState(configuredProvider);
  const [portalBaseUrl, setPortalBaseUrl] = useState(configuredPortalBaseUrl);
  const [cutluyApiBaseUrl, setCutluyApiBaseUrl] = useState('https://cutluy.com');
  const [cutluyPaymentLinkId, setCutluyPaymentLinkId] = useState('');
  const [cutluySecretKey, setCutluySecretKey] = useState('');
  const [cutluyWebhookSecret, setCutluyWebhookSecret] = useState('');
  const [chmabaApiBaseUrl, setChmabaApiBaseUrl] = useState('https://pay.chmaba.com');
  const [chmabaStoreId, setChmabaStoreId] = useState('');
  const [chmabaApiKey, setChmabaApiKey] = useState('');
  const [chmabaWebhookSecret, setChmabaWebhookSecret] = useState('');

  useEffect(() => {
    setProvider(configuredProvider);
  }, [configuredProvider]);

  useEffect(() => {
    setPortalBaseUrl(configuredPortalBaseUrl);
  }, [configuredPortalBaseUrl]);

  useEffect(() => {
    if (!cutluyConfig) return;
    setCutluyApiBaseUrl(cutluyConfig.api_base_url || 'https://cutluy.com');
    setCutluyPaymentLinkId(cutluyConfig.payment_link_id || '');
    setCutluySecretKey('');
    setCutluyWebhookSecret('');
  }, [cutluyConfig]);

  useEffect(() => {
    if (!chmabaConfig) return;
    setChmabaApiBaseUrl(chmabaConfig.api_base_url || 'https://pay.chmaba.com');
    setChmabaStoreId(chmabaConfig.store_id || '');
    setChmabaApiKey('');
    setChmabaWebhookSecret('');
  }, [chmabaConfig]);

  const saveProvider = () => {
    upsertSetting.mutate(
      { key: BILLING_ACTIVE_PROVIDER_KEY, value: provider },
      {
        onSuccess: () =>
          toast({
            title:
              provider === 'none'
                ? 'Paid checkout turned off'
                : `Active billing provider set to ${provider}`,
          }),
      },
    );
  };

  const savePortalBaseUrl = () => {
    upsertSetting.mutate(
      { key: BILLING_PORTAL_BASE_URL_KEY, value: portalBaseUrl.trim() },
      {
        onSuccess: () => toast({ title: 'Billing portal URL updated' }),
      },
    );
  };

  const saveCutluyConfig = () => {
    updateCutluy.mutate(
      {
        api_base_url: cutluyApiBaseUrl.trim() || 'https://cutluy.com',
        payment_link_id: cutluyPaymentLinkId.trim(),
        secret_key: cutluySecretKey.trim() || undefined,
        webhook_secret: cutluyWebhookSecret.trim() || undefined,
      },
      {
        onSuccess: () => {
          setCutluySecretKey('');
          setCutluyWebhookSecret('');
          toast({ title: 'CutLuy credentials saved' });
        },
        onError: (error: Error) => {
          toast({
            variant: 'destructive',
            title: 'Failed to save CutLuy credentials',
            description: error.message,
          });
        },
      },
    );
  };

  const saveChmabaConfig = () => {
    updateChmaba.mutate(
      {
        api_base_url: chmabaApiBaseUrl.trim() || 'https://pay.chmaba.com',
        store_id: chmabaStoreId.trim(),
        api_key: chmabaApiKey.trim() || undefined,
        webhook_secret: chmabaWebhookSecret.trim() || undefined,
      },
      {
        onSuccess: () => {
          setChmabaApiKey('');
          setChmabaWebhookSecret('');
          toast({ title: 'ChmabaPay credentials saved' });
        },
        onError: (error: Error) => {
          toast({
            variant: 'destructive',
            title: 'Failed to save ChmabaPay credentials',
            description: error.message,
          });
        },
      },
    );
  };

  const setProviderEnabled = (providerId: string, enabled: boolean) => {
    upsertSetting.mutate(
      { key: enabledKey(providerId), value: String(enabled) },
      {
        onSuccess: () => {
          toast({ title: `${providerId} ${enabled ? 'enabled' : 'disabled'}` });
          if (!enabled && provider === providerId) {
            setProvider('none');
          }
        },
      },
    );
  };

  const portalBase = portalBaseUrl.trim().replace(/\/$/, '') || 'https://account.camxora.com';

  return (
    <div className="grid gap-6">
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-lg">KHQR Providers</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          {providerStates.map((providerState) => (
            <div key={providerState.id} className="rounded-lg border border-slate-800 bg-slate-950/70 p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-slate-100">{providerState.label}</div>
                  <div className="mt-1 text-xs text-slate-400">{providerState.description}</div>
                </div>
                <div className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">
                  {providerState.enabled ? 'ON' : 'OFF'}
                </div>
              </div>

              <div className="mt-4 flex gap-3">
                <Button
                  type="button"
                  variant={providerState.enabled ? 'outline' : 'default'}
                  onClick={() => setProviderEnabled(providerState.id, !providerState.enabled)}
                  disabled={upsertSetting.isPending}
                >
                  {providerState.enabled ? 'Turn Off' : 'Turn On'}
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-lg">CutLuy API</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          <p className="text-xs text-slate-400">
            Store CutLuy credentials here instead of editing server <code className="text-slate-200">.env</code>{' '}
            files. Values in this form override <code className="text-slate-200">PLATFORM_CUTLUY_*</code> environment
            variables when present.
          </p>

          <div className="rounded-lg border border-amber-900/50 bg-amber-950/30 p-4 text-xs text-slate-300">
            <div className="font-medium text-amber-100">CutLuy store setup (dashboard)</div>
            <ol className="mt-2 list-decimal space-y-2 pl-5 text-slate-400">
              <li>
                In the CutLuy dashboard, create a <span className="text-slate-200">payment link</span>. The
                &quot;payment link&quot; field expects a CutLuy-hosted URL such as{' '}
                <code className="text-slate-200">https://cutluy.com/pay/…</code> — not your Camxora site (
                <code className="text-slate-200">sandbox.camxora.com</code> or{' '}
                <code className="text-slate-200">app.sandbox.camxora.com</code>).
              </li>
              <li>
                Copy the <span className="text-slate-200">payment link ID</span> from CutLuy (the slug after{' '}
                <code className="text-slate-200">/pay/</code>) and paste it into the Payment link ID field below.
                Leave blank to let CutLuy create dynamic checkouts per plan price.
              </li>
              <li>
                Under CutLuy <span className="text-slate-200">Store settings</span>, set both checkout redirects to
                your user portal onboarding page (for example{' '}
                <code className="text-slate-200">https://app.sandbox.camxora.com/onboarding</code>). CutLuy appends{' '}
                <code className="text-slate-200">?status=success|failed&amp;payment_id=…&amp;reference_id=…</code>.
              </li>
              <li>
                Under CutLuy <span className="text-slate-200">Webhooks</span>, set the callback URL to{' '}
                <code className="text-slate-200">https://api.sandbox.camxora.com/api/v3/webhooks/cutluy</code>{' '}
                (music CutLuy) or{' '}
                <code className="text-slate-200">https://api.sandbox.camxora.com/api/v3/billing/webhooks/cutluy</code>{' '}
                (desktop billing).
                (production: replace <code className="text-slate-200">api.sandbox</code> with your API host).
              </li>
              <li>
                Paste your CutLuy <span className="text-slate-200">API secret key</span> and{' '}
                <span className="text-slate-200">webhook signing secret</span> from the CutLuy dashboard into the
                fields below, then save.
              </li>
            </ol>
          </div>

          {cutluyLoading ? (
            <div className="text-sm text-slate-400">Loading CutLuy configuration…</div>
          ) : (
            <>
              <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">
                {cutluyConfig?.secret_key_configured ? (
                  <>
                    API key configured
                    {cutluyConfig.secret_key_masked ? (
                      <>
                        {' '}
                        (<span className="font-mono text-slate-100">{cutluyConfig.secret_key_masked}</span>)
                      </>
                    ) : null}
                    {cutluyConfig.secret_source ? (
                      <span className="text-slate-500"> · source: {cutluyConfig.secret_source}</span>
                    ) : null}
                  </>
                ) : (
                  <span className="text-amber-300">No CutLuy API key configured yet.</span>
                )}
              </div>

              <div className="grid gap-2">
                <Label>CutLuy API base URL</Label>
                <Input
                  value={cutluyApiBaseUrl}
                  onChange={(event) => setCutluyApiBaseUrl(event.target.value)}
                  className="border-slate-700 bg-slate-950 text-slate-100"
                  placeholder="https://cutluy.com"
                />
              </div>

              <div className="grid gap-2">
                <Label>Payment link ID</Label>
                <Input
                  value={cutluyPaymentLinkId}
                  onChange={(event) => setCutluyPaymentLinkId(event.target.value)}
                  className="border-slate-700 bg-slate-950 text-slate-100"
                  placeholder="e.g. abc123 from cutluy.com/pay/abc123"
                />
                <p className="text-xs text-slate-500">
                  The ID from your CutLuy payment link URL — not the Camxora website URL.
                </p>
              </div>

              <div className="grid gap-2">
                <Label>API secret key</Label>
                <Input
                  type="password"
                  value={cutluySecretKey}
                  onChange={(event) => setCutluySecretKey(event.target.value)}
                  className="border-slate-700 bg-slate-950 text-slate-100"
                  placeholder={
                    cutluyConfig?.secret_key_configured
                      ? 'Leave blank to keep the current key'
                      : 'Paste your CutLuy API key'
                  }
                  autoComplete="off"
                />
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">
                {cutluyConfig?.webhook_secret_configured ? (
                  <>
                    Webhook signing secret configured
                    {cutluyConfig.webhook_secret_masked ? (
                      <>
                        {' '}
                        (<span className="font-mono text-slate-100">{cutluyConfig.webhook_secret_masked}</span>)
                      </>
                    ) : null}
                    {cutluyConfig.webhook_secret_source ? (
                      <span className="text-slate-500"> · source: {cutluyConfig.webhook_secret_source}</span>
                    ) : null}
                  </>
                ) : (
                  <span className="text-amber-300">
                    No webhook signing secret yet — plan fulfillment webhooks will reject until set.
                  </span>
                )}
              </div>

              <div className="grid gap-2">
                <Label>Webhook signing secret</Label>
                <Input
                  type="password"
                  value={cutluyWebhookSecret}
                  onChange={(event) => setCutluyWebhookSecret(event.target.value)}
                  className="border-slate-700 bg-slate-950 text-slate-100"
                  placeholder={
                    cutluyConfig?.webhook_secret_configured
                      ? 'Leave blank to keep the current webhook secret'
                      : 'From CutLuy Dashboard → Webhooks'
                  }
                  autoComplete="off"
                />
                <p className="text-xs text-slate-500">
                  In CutLuy Dashboard → Webhooks, set URL to{' '}
                  <code className="text-slate-300">https://api.sandbox.camxora.com/api/v3/webhooks/cutluy</code>{' '}
                  (music) or{' '}
                  <code className="text-slate-300">https://api.sandbox.camxora.com/api/v3/billing/webhooks/cutluy</code>{' '}
                  (desktop billing). Legacy v1 webhook paths remain dual-mounted during transition.
                </p>
              </div>

              <div className="flex justify-end">
                <Button onClick={saveCutluyConfig} disabled={updateCutluy.isPending}>
                  {updateCutluy.isPending ? 'Saving…' : 'Save CutLuy Credentials'}
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-lg">ChmabaPay (pay.chmaba.com)</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          <p className="text-xs text-slate-400">
            Live KHQR / ABA PayWay credentials. Values here override the{' '}
            <code className="text-slate-200">PLATFORM_CHMABA_*</code> environment variables. There is no
            sandbox — every key moves real money.
          </p>

          <div className="rounded-lg border border-amber-900/50 bg-amber-950/30 p-4 text-xs text-slate-300">
            <div className="font-medium text-amber-100">ChmabaPay store setup</div>
            <ol className="mt-2 list-decimal space-y-2 pl-5 text-slate-400">
              <li>
                In the ChmabaPay dashboard, create (or reuse) a <span className="text-slate-200">store</span>{' '}
                and copy its <span className="text-slate-200">store id</span> (
                <code className="text-slate-200">st_…</code>). Payouts go straight to the ABA PayWay link
                attached to that store.
              </li>
              <li>
                Copy the live API key (<code className="text-slate-200">ck_live_…</code>) and paste it below.
              </li>
              <li>
                Under <span className="text-slate-200">Webhooks</span>, set the URL to{' '}
                <code className="text-slate-200">https://api.camxora.com/api/v3/billing/webhooks/chmaba</code>{' '}
                and copy the signing secret (<code className="text-slate-200">whsec_…</code>). One URL handles
                both plan checkout and music-web credit top-ups.
              </li>
              <li>
                Turn <span className="text-slate-200">ChmabaPay KHQR</span> ON above, choose it as the active
                provider, then keep CutLuy OFF so a store cannot be charged twice.
              </li>
            </ol>
          </div>

          {chmabaLoading ? (
            <div className="text-sm text-slate-400">Loading ChmabaPay configuration…</div>
          ) : (
            <>
              <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">
                {chmabaConfig?.ready ? (
                  <span className="text-emerald-300">Checkout is ready: API key and store id are set.</span>
                ) : (
                  <span className="text-amber-300">
                    Not ready yet.
                    {!chmabaConfig?.api_key_configured ? ' API key missing.' : ''}
                    {!chmabaConfig?.store_id ? ' Store id missing.' : ''}
                  </span>
                )}
              </div>

              <div className="grid gap-2">
                <Label>API base URL</Label>
                <Input
                  value={chmabaApiBaseUrl}
                  onChange={(event) => setChmabaApiBaseUrl(event.target.value)}
                  className="border-slate-700 bg-slate-950 text-slate-100"
                  placeholder="https://pay.chmaba.com"
                />
              </div>

              <div className="grid gap-2">
                <Label>Store id</Label>
                <Input
                  value={chmabaStoreId}
                  onChange={(event) => setChmabaStoreId(event.target.value)}
                  className="border-slate-700 bg-slate-950 text-slate-100"
                  placeholder="st_…"
                />
                {chmabaConfig?.store_source ? (
                  <p className="text-xs text-slate-500">source: {chmabaConfig.store_source}</p>
                ) : null}
              </div>

              <div className="grid gap-2">
                <Label>API key</Label>
                <Input
                  type="password"
                  value={chmabaApiKey}
                  onChange={(event) => setChmabaApiKey(event.target.value)}
                  className="border-slate-700 bg-slate-950 text-slate-100"
                  placeholder={
                    chmabaConfig?.api_key_configured
                      ? `Leave blank to keep the current key (${chmabaConfig.api_key_masked})`
                      : 'Paste the ChmabaPay live key (ck_live_…)'
                  }
                  autoComplete="off"
                />
              </div>

              <div className="grid gap-2">
                <Label>Webhook signing secret</Label>
                <Input
                  type="password"
                  value={chmabaWebhookSecret}
                  onChange={(event) => setChmabaWebhookSecret(event.target.value)}
                  className="border-slate-700 bg-slate-950 text-slate-100"
                  placeholder={
                    chmabaConfig?.webhook_secret_configured
                      ? `Leave blank to keep the current secret (${chmabaConfig.webhook_secret_masked})`
                      : 'Paste the whsec_… signing secret'
                  }
                  autoComplete="off"
                />
                <p className="text-xs text-slate-500">
                  Required before any webhook is accepted. Until it is set, ChmabaPay deliveries are
                  rejected and only the status poll can settle a payment.
                </p>
              </div>

              <div className="flex justify-end">
                <Button onClick={saveChmabaConfig} disabled={updateChmaba.isPending}>
                  {updateChmaba.isPending ? 'Saving…' : 'Save ChmabaPay Credentials'}
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-lg">Active Provider</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-2">
            <Label>Current paid checkout provider</Label>
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger className="border-slate-700 bg-slate-950 text-slate-100">
                <SelectValue placeholder="Select provider" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Off</SelectItem>
                {enabledProviders.map((providerOption) => (
                  <SelectItem key={providerOption.id} value={providerOption.id}>
                    {providerOption.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-slate-400">
              Turn providers ON or OFF above, then choose which enabled provider should power paid checkout.
            </p>
          </div>

          <div className="flex justify-end">
            <Button onClick={saveProvider} disabled={upsertSetting.isPending}>
              Save Active Provider
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-lg">User Portal URLs</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-2">
            <Label>Portal base URL</Label>
            <Input
              value={portalBaseUrl}
              onChange={(event) => setPortalBaseUrl(event.target.value)}
              className="border-slate-700 bg-slate-950 text-slate-100"
              placeholder="https://account.camxora.com"
            />
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">
            <div className="font-medium text-white">How checkout URLs work</div>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-xs text-slate-400">
              <li>
                Onboarding starts at{' '}
                <span className="font-medium text-slate-200">{portalBase}/onboarding</span>
              </li>
              <li>
                <span className="font-medium text-slate-200">CutLuy (optional):</span> users pay on{' '}
                <span className="font-medium text-slate-200">cutluy.com</span>, then CutLuy redirects back
                using the store success/failure URLs below.
              </li>
              <li>
                <span className="font-medium text-slate-200">ChmabaPay (optional):</span> users scan the KHQR
                shown in the app; the payment settles into your ABA PayWay link and the webhook credits the
                account.
              </li>
              <li>
                <span className="font-medium text-slate-200">CutLuy success redirect:</span>{' '}
                <span className="font-medium text-slate-200">{portalBase}/onboarding</span>
              </li>
              <li>
                <span className="font-medium text-slate-200">CutLuy failure redirect:</span>{' '}
                <span className="font-medium text-slate-200">{portalBase}/onboarding</span>
              </li>
              <li>
                <span className="font-medium text-slate-200">Mock (dev only):</span>{' '}
                <span className="font-medium text-slate-200">{portalBase}/checkout/mock/:paymentId</span>
              </li>
              <li>
                <span className="font-medium text-slate-200">100% discount codes:</span>{' '}
                <span className="font-medium text-slate-200">{portalBase}/onboarding?payment_id=…</span>
              </li>
            </ul>
          </div>

          <div className="flex justify-end">
            <Button onClick={savePortalBaseUrl} disabled={upsertSetting.isPending || !portalBaseUrl.trim()}>
              Save Portal URL
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
