import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Router } from 'lucide-react';

import {
  useAIRoutingAssignments,
  useAIRoutingAudit,
  useAIRoutingProviders,
  useSaveAIRoutingAssignments,
} from '@/hooks/use-ai-routing';
import { useSyncRoutingPricing } from '@/hooks/use-credits';
import { toast } from '@/hooks/use-toast';
import type {
  CapabilityIssue,
  OperationAssignment,
  ProviderOption,
} from '@/types/ai-routing';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';

// --- Constants ---

const OPERATION_LABELS: Record<string, string> = {
  channel_name: 'Channel Name',
  channel_description: 'Channel Description',
  channel_keywords: 'Channel Keywords',
  channel_tags: 'Channel Tags',
  lyric: 'Lyric (Desktop / Batch)',
  web_music_lyrics: 'Music Lyric',
  title: 'Title',
  album: 'Album',
  web_music_style: 'Music Style Tags',
  channel_logo: 'Channel Logo',
  channel_cover: 'Channel Cover',
  background_image: 'Background Image',
  thumbnail_image: 'Thumbnail Image',
  music: 'Music',
};

const TEXT_OPERATION_ORDER = [
  'channel_name',
  'channel_description',
  'channel_keywords',
  'channel_tags',
  'lyric',
  'web_music_lyrics',
  'title',
  'album',
  'web_music_style',
] as const;

const SERVICE_TYPE_LABELS: Record<string, string> = {
  text_generation: 'Text Generation',
  image_generation: 'Image Generation',
  music_generation: 'Music Generation',
};

const SERVICE_TYPES = ['text_generation', 'image_generation', 'music_generation'] as const;
type ServiceType = (typeof SERVICE_TYPES)[number];

// Default providers used when no assignment exists
const DEFAULT_PROVIDERS: Record<ServiceType, string> = {
  text_generation: 'deepseek',
  image_generation: 'fal',
  music_generation: 'suno',
};

const DEFAULT_TEXT_FALLBACK_CHAIN: OperationAssignment[] = [
  { provider: 'slai', sub_model: 'xiaomi/mimo-v2.5-pro', is_active: true },
  { provider: 'deepseek', sub_model: 'deepseek-chat', is_active: true },
  { provider: 'openai', sub_model: 'gpt-4o-mini', is_active: true },
];

const DEFAULT_IMAGE_FALLBACK_CHAIN: OperationAssignment[] = [
  { provider: 'slai', sub_model: 'slai/gpt-image-2', is_active: true },
  { provider: 'fal', sub_model: 'flux-pro', is_active: true },
  { provider: 'openai', sub_model: 'gpt-image-1', is_active: true },
];

const DEFAULT_SUB_MODELS: Record<string, string> = {
  deepseek: 'deepseek-chat',
  fal: 'flux-pro',
  openai: 'gpt-4o-mini',
  slai: 'xiaomi/mimo-v2.5-pro',
  kie: 'grok-imagine-image-2-0/text-to-image',
};

// --- Helper Functions ---

function getDefaultAssignment(
  serviceType: ServiceType,
  operation?: string,
  providers: ProviderOption[] = [],
): OperationAssignment {
  const provider = DEFAULT_PROVIDERS[serviceType];
  const subModels = getSubModelsForProvider(providers, provider, operation);
  const fallbackModel = DEFAULT_SUB_MODELS[provider] ?? null;
  const subModel =
    subModels.find((model) => model === fallbackModel) ?? subModels[0] ?? fallbackModel;
  return {
    provider,
    sub_model: subModel,
    is_active: true,
  };
}

function normalizeAssignmentSubModel(
  assignment: OperationAssignment,
  _serviceType: ServiceType,
  operation: string,
  providers: ProviderOption[],
): OperationAssignment {
  if (operation === 'music') {
    return { ...assignment, sub_model: null };
  }
  const subModels = getSubModelsForProvider(providers, assignment.provider, operation);
  if (subModels.length === 0) {
    return assignment;
  }
  if (assignment.sub_model && subModels.includes(assignment.sub_model)) {
    return assignment;
  }
  return {
    ...assignment,
    sub_model: subModels[0] ?? null,
  };
}

function getSubModelsForProvider(
  providers: ProviderOption[],
  providerName: string,
  operation?: string,
): string[] {
  const found = providers.find((p) => p.provider === providerName);
  if (!found) return [];
  const models = found.sub_models ?? [];
  if (!operation) return models;
  return models.filter((model) => modelSupportsOperation(found, model, operation));
}

function modelSupportsOperation(
  provider: ProviderOption,
  modelName: string,
  operation: string,
): boolean {
  const detail = provider.sub_models_detail?.find((d) => d.name === modelName);
  if (detail?.operations?.length) {
    return detail.operations.includes(operation);
  }
  return true;
}

function formatUsdCost(amount: number): string {
  if (amount === 0) return '$0';
  if (amount < 0.01) {
    return `$${amount.toFixed(6).replace(/0+$/, '').replace(/\.$/, '')}`;
  }
  if (amount < 1) return `$${amount.toFixed(4)}`;
  return `$${amount.toFixed(2)}`;
}

function getCostDisplayForModel(
  providers: ProviderOption[],
  providerName: string,
  modelName: string,
  operation?: string,
): string {
  const found = providers.find((p) => p.provider === providerName);
  const detail = found?.sub_models_detail?.find((d) => d.name === modelName);
  if (!detail) return '';

  if (operation && detail.cost_usd_by_operation?.[operation] != null) {
    return formatUsdCost(detail.cost_usd_by_operation[operation]);
  }
  if (detail.cost_usd != null) {
    return formatUsdCost(detail.cost_usd);
  }
  return detail.cost_tier ?? '';
}

function formatModelLabel(model: string, costDisplay: string): string {
  if (!costDisplay) return model;
  return `${model} (${costDisplay})`;
}

function capitalizeProvider(provider: string): string {
  if (provider === 'fal') return 'FAL';
  if (provider === 'slai') return 'SLAI';
  return provider.charAt(0).toUpperCase() + provider.slice(1);
}

// --- Component ---

export function AIRoutingSection() {
  const {
    data: assignmentsData,
    isLoading: assignmentsLoading,
    isError: assignmentsError,
  } = useAIRoutingAssignments();

  const { data: providersData, isLoading: providersLoading } =
    useAIRoutingProviders();

  const { data: auditData, isLoading: auditLoading } = useAIRoutingAudit();

  const saveMutation = useSaveAIRoutingAssignments();
  const syncPricingMutation = useSyncRoutingPricing();

  // Local state: flat map of operation → assignment
  const [localAssignments, setLocalAssignments] = useState<
    Record<string, OperationAssignment>
  >({});
  const [textFallbackChain, setTextFallbackChain] = useState<OperationAssignment[]>(
    DEFAULT_TEXT_FALLBACK_CHAIN,
  );
  const [imageFallbackChain, setImageFallbackChain] = useState<OperationAssignment[]>(
    DEFAULT_IMAGE_FALLBACK_CHAIN,
  );
  const [initialized, setInitialized] = useState(false);

  // Initialize local state from fetched assignments
  useEffect(() => {
    if (assignmentsData && providersData && !initialized) {
      const flat: Record<string, OperationAssignment> = {};

      for (const serviceType of SERVICE_TYPES) {
        const operations = assignmentsData[serviceType] ?? {};
        const operationKeys = Object.keys(OPERATION_LABELS).filter(
          (op) => op in operations || getServiceTypeForOperation(op) === serviceType,
        );

        for (const op of operationKeys) {
          if (operations[op]) {
            const assignment = {
              ...operations[op],
              is_active: operations[op].is_active !== false,
              ...(op === 'music' ? { sub_model: null } : {}),
            };
            flat[op] = normalizeAssignmentSubModel(
              assignment,
              serviceType,
              op,
              providersData?.[serviceType] ?? [],
            );
          } else {
            flat[op] = getDefaultAssignment(
              serviceType,
              op,
              providersData?.[serviceType] ?? [],
            );
          }
        }
      }

      setLocalAssignments(flat);
      setTextFallbackChain(
        assignmentsData.text_fallback_chain?.length
          ? assignmentsData.text_fallback_chain.map((item) => ({
              ...item,
              is_active: item.is_active !== false,
            }))
          : DEFAULT_TEXT_FALLBACK_CHAIN,
      );
      setImageFallbackChain(
        assignmentsData.image_fallback_chain?.length
          ? assignmentsData.image_fallback_chain.map((item) => ({
              ...item,
              is_active: item.is_active !== false,
            }))
          : DEFAULT_IMAGE_FALLBACK_CHAIN,
      );
      setInitialized(true);
    }
  }, [assignmentsData, providersData, initialized]);

  const handleProviderChange = (
    operation: string,
    serviceType: ServiceType,
    newProvider: string,
  ) => {
    const providers = providersData?.[serviceType] ?? [];
    const subModels = getSubModelsForProvider(providers, newProvider, operation);
    const firstSubModel = subModels.length > 0 ? subModels[0] : null;
    const userSelectsModel = operation === 'music';

    setLocalAssignments((prev) => ({
      ...prev,
      [operation]: {
        provider: newProvider,
        sub_model: userSelectsModel ? null : (firstSubModel ?? null),
        is_active: prev[operation]?.is_active !== false,
      },
    }));
  };

  const handleSubModelChange = (operation: string, newSubModel: string) => {
    setLocalAssignments((prev) => {
      const current = prev[operation];
      return {
        ...prev,
        [operation]: {
          provider: current?.provider ?? '',
          sub_model: newSubModel,
          is_active: current?.is_active !== false,
        },
      };
    });
  };

  const handleActiveChange = (operation: string, isActive: boolean) => {
    setLocalAssignments((prev) => {
      const current = prev[operation];
      if (!current) return prev;
      return {
        ...prev,
        [operation]: {
          ...current,
          is_active: isActive,
        },
      };
    });
  };

  const handleSave = () => {
    saveMutation.mutate(
      {
        assignments: localAssignments,
        text_fallback_chain: textFallbackChain,
        image_fallback_chain: imageFallbackChain,
      },
      {
            onSuccess: (data) => {
              const created = data?.pricing_sync?.created_count ?? 0;
              if (created > 0) {
                toast({
                  title: 'AI routing saved',
                  description: `${created} draft price(s) created on Credits — review margins and approve.`,
                });
              } else {
                toast({ title: 'AI routing assignments saved successfully' });
              }
            },
            onError: () => {
              toast({
                title: 'Failed to save assignments',
                description: 'Please try again.',
                variant: 'destructive',
              });
            },
          },
        );
  };

  // Loading state
  if (assignmentsLoading || providersLoading || auditLoading) {
    return (
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-64" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (assignmentsError) {
    return (
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Router className="h-5 w-5" />
            AI Routing
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-red-400">
            Failed to load AI routing assignments. Please refresh the page.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-slate-800 bg-slate-900/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Router className="h-5 w-5" />
          AI Routing
        </CardTitle>
        <CardDescription className="text-slate-400">
          Configure which AI model handles each operation. Text and image calls try
          the operation primary first, then the fallback priority below. Credits are
          charged for whichever provider actually succeeds. Suno is only for music
          generation.{' '}
          <Link to="/credits" className="text-blue-400 hover:underline">
            Credit costs are configured on the Credits page →
          </Link>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <RoutingAuditPanel
          issues={auditData?.issues ?? []}
          ready={auditData?.ready ?? true}
          draftPricingCount={auditData?.draft_pricing_count ?? 0}
          onSyncPricing={() => {
            syncPricingMutation.mutate(undefined, {
              onSuccess: (data) => {
                const created = data?.created_count ?? 0;
                toast({
                  title: created
                    ? `Created ${created} draft price(s) on Credits`
                    : 'Pricing already up to date',
                });
              },
              onError: () => {
                toast({
                  variant: 'destructive',
                  title: 'Failed to sync draft pricing',
                });
              },
            });
          }}
          syncPending={syncPricingMutation.isPending}
        />

        <FallbackChainEditor
          title="Text fallback priority"
          description="Used when the primary text model times out or fails. Inactive entries are skipped (use this to disable expensive fallbacks until needed). Applies to all text operations."
          chain={textFallbackChain}
          providers={providersData?.text_generation ?? []}
          onChange={setTextFallbackChain}
        />

        <FallbackChainEditor
          title="Image fallback priority"
          description="Used when the primary image model times out or fails. Inactive entries are skipped (use this to disable expensive fallbacks until needed). Applies to all image operations."
          chain={imageFallbackChain}
          providers={providersData?.image_generation ?? []}
          onChange={setImageFallbackChain}
        />

        {SERVICE_TYPES.map((serviceType) => (
          <ServiceTypeGroup
            key={serviceType}
            serviceType={serviceType}
            providers={providersData?.[serviceType] ?? []}
            assignments={localAssignments}
            onProviderChange={(op, provider) =>
              handleProviderChange(op, serviceType, provider)
            }
            onSubModelChange={handleSubModelChange}
            onActiveChange={handleActiveChange}
          />
        ))}

        <div className="flex justify-end pt-2">
          <Button
            onClick={handleSave}
            disabled={saveMutation.isPending}
          >
            {saveMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save All Assignments
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function RoutingAuditPanel({
  issues,
  ready,
  draftPricingCount,
  onSyncPricing,
  syncPending,
}: {
  issues: CapabilityIssue[];
  ready: boolean;
  draftPricingCount: number;
  onSyncPricing: () => void;
  syncPending: boolean;
}) {
  const errors = issues.filter((issue) => issue.severity === 'error');
  const warnings = issues.filter(
    (issue) => issue.severity === 'warning' && issue.code !== 'draft_pricing',
  );
  const draftIssues = issues.filter((issue) => issue.code === 'draft_pricing');
  const draftCount = draftPricingCount || draftIssues.length;

  if (ready && issues.length === 0) {
    return (
      <div className="rounded-lg border border-emerald-800/60 bg-emerald-950/20 p-4 text-sm text-emerald-300">
        Capabilities and credit pricing look complete for the current routing setup.
      </div>
    );
  }

  if (ready && errors.length === 0 && draftCount === 0 && warnings.length === 0) {
    return (
      <div className="rounded-lg border border-emerald-800/60 bg-emerald-950/20 p-4 text-sm text-emerald-300">
        Capabilities and credit pricing look complete for the current routing setup.
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded-lg border border-amber-800/60 bg-amber-950/20 p-4">
      <div>
        <h3 className="text-sm font-semibold text-amber-200">Routing health check</h3>
        <p className="mt-1 text-xs text-amber-100/80">
          Saving routing auto-creates missing credit prices as drafts on the Credits page.
          Review margins there, then approve.{' '}
          <Link to="/credits?filter=needs_review" className="text-blue-400 hover:underline">
            Open Credits review queue →
          </Link>
        </p>
      </div>
      {draftCount > 0 && errors.length === 0 && (
        <div className="rounded-md border border-red-800/50 bg-red-950/30 p-3 text-sm text-red-200">
          <span className="font-medium">{draftCount} draft price(s)</span> need margin review on
          the Credits page before you approve them.
        </div>
      )}
      {errors.length > 0 && (
        <>
          <IssueList title="Missing or invalid configuration" items={errors} tone="error" />
          {errors.some((issue) => issue.code === 'missing_pricing') && (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={syncPending}
                onClick={onSyncPricing}
              >
                {syncPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create draft prices from saved routing
              </Button>
              <span className="text-xs text-amber-100/70">
                Uses routing already saved on the server (save first if you changed assignments).
              </span>
            </div>
          )}
        </>
      )}
      {warnings.length > 0 && (
        <IssueList title="Warnings" items={warnings} tone="warning" />
      )}
      {ready && errors.length === 0 && draftCount > 0 && (
        <p className="text-xs text-emerald-300">
          Routing is operational — finish reviewing draft prices on Credits when you can.
        </p>
      )}
    </div>
  );
}

function IssueList({
  title,
  items,
  tone,
}: {
  title: string;
  items: CapabilityIssue[];
  tone: 'error' | 'warning';
}) {
  const textClass = tone === 'error' ? 'text-red-300' : 'text-amber-200';
  return (
    <div>
      <p className={`mb-1 text-xs font-medium uppercase tracking-wide ${textClass}`}>
        {title}
      </p>
      <ul className={`space-y-1 text-sm ${textClass}`}>
        {items.map((issue, index) => (
          <li key={`${issue.code}-${issue.operation ?? 'global'}-${index}`}>
            {issue.message}
            {issue.pricing_ai_service && issue.pricing_operation_type ? (
              <span className="block text-xs opacity-80">
                Add pricing: {issue.pricing_ai_service} / {issue.pricing_operation_type}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

// --- Fallback priority editor ---

interface FallbackChainEditorProps {
  title: string;
  description: string;
  chain: OperationAssignment[];
  providers: ProviderOption[];
  onChange: (chain: OperationAssignment[]) => void;
}

function FallbackChainEditor({
  title,
  description,
  chain,
  providers,
  onChange,
}: FallbackChainEditorProps) {
  const updateEntry = (index: number, next: OperationAssignment) => {
    onChange(chain.map((item, i) => (i === index ? next : item)));
  };

  const moveEntry = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= chain.length) return;
    const next = [...chain];
    const currentEntry = next[index];
    const targetEntry = next[target];
    if (!currentEntry || !targetEntry) return;
    [next[index], next[target]] = [targetEntry, currentEntry];
    onChange(next);
  };

  return (
    <div className="rounded-lg border border-slate-700 p-4">
      <h3 className="mb-1 text-sm font-semibold text-slate-200">{title}</h3>
      <p className="mb-3 text-xs text-slate-400">{description}</p>
      <div className="space-y-2">
        {chain.map((entry, index) => (
          <div
            key={`fallback-${index}`}
            className={`flex items-center gap-3 rounded-md p-1 ${
              entry.is_active === false ? 'opacity-50' : ''
            }`}
          >
            <span className="w-8 shrink-0 text-xs text-slate-500">#{index + 1}</span>
            <Select
              value={entry.provider}
              onValueChange={(provider) => {
                const subModels = getSubModelsForProvider(providers, provider);
                updateEntry(index, {
                  provider,
                  sub_model: subModels[0] ?? null,
                  is_active: entry.is_active,
                });
              }}
            >
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Provider" />
              </SelectTrigger>
              <SelectContent>
                {providers.map((p) => (
                  <SelectItem key={p.provider} value={p.provider}>
                    {capitalizeProvider(p.provider)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {getSubModelsForProvider(providers, entry.provider).length > 0 && (
              <Select
                value={entry.sub_model ?? ''}
                onValueChange={(subModel) =>
                  updateEntry(index, { ...entry, sub_model: subModel })
                }
              >
                <SelectTrigger className="w-52">
                  <SelectValue placeholder="Model" />
                </SelectTrigger>
                <SelectContent>
                  {getSubModelsForProvider(providers, entry.provider).map((model) => (
                    <SelectItem key={model} value={model}>
                      {formatModelLabel(
                        model,
                        getCostDisplayForModel(providers, entry.provider, model),
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <label className="ml-auto flex shrink-0 items-center gap-1.5 text-xs text-slate-400">
              <input
                type="checkbox"
                checked={entry.is_active !== false}
                onChange={(e) =>
                  updateEntry(index, { ...entry, is_active: e.target.checked })
                }
              />
              Active
            </label>
            <div className="flex gap-1">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={index === 0}
                onClick={() => moveEntry(index, -1)}
              >
                Up
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={index === chain.length - 1}
                onClick={() => moveEntry(index, 1)}
              >
                Down
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Service Type Group ---

interface ServiceTypeGroupProps {
  serviceType: ServiceType;
  providers: ProviderOption[];
  assignments: Record<string, OperationAssignment>;
  onProviderChange: (operation: string, provider: string) => void;
  onSubModelChange: (operation: string, subModel: string) => void;
  onActiveChange: (operation: string, isActive: boolean) => void;
}

function ServiceTypeGroup({
  serviceType,
  providers,
  assignments,
  onProviderChange,
  onSubModelChange,
  onActiveChange,
}: ServiceTypeGroupProps) {
  const operations =
    serviceType === 'text_generation'
      ? TEXT_OPERATION_ORDER.filter((op) => getServiceTypeForOperation(op) === serviceType)
      : Object.keys(OPERATION_LABELS).filter((op) => getServiceTypeForOperation(op) === serviceType);

  if (operations.length === 0) return null;

  return (
    <div className="rounded-lg border border-slate-700 p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-200">
        {SERVICE_TYPE_LABELS[serviceType]}
      </h3>
      {serviceType === 'text_generation' ? (
        <p className="mb-3 text-xs text-slate-400">
          <strong className="font-medium text-slate-300">Lyric (Desktop / Batch)</strong> uses Suno&apos;s
          lyrics API when routed to Suno. <strong className="font-medium text-slate-300">Music Lyric</strong>{' '}
          is for the web music portal auto-generate button and uses chat LLMs only (SLAI, OpenAI, DeepSeek).
        </p>
      ) : null}
      {serviceType === 'music_generation' ? (
        <p className="mb-3 text-xs text-slate-400">
          Suno is the only music provider. Users choose the Suno model version in
          their app settings (v5 / v5.5). Add multiple Suno API keys in the Key
          Pool to spread load across accounts when traffic grows.
        </p>
      ) : null}
      <div className="space-y-3">
        {operations.map((operation) => (
          <OperationRow
            key={operation}
            operation={operation}
            assignment={assignments[operation]}
            providers={providers}
            onProviderChange={(provider) => onProviderChange(operation, provider)}
            onSubModelChange={(subModel) => onSubModelChange(operation, subModel)}
            onActiveChange={(isActive) => onActiveChange(operation, isActive)}
          />
        ))}
      </div>
    </div>
  );
}

// --- Operation Row ---

interface OperationRowProps {
  operation: string;
  assignment: OperationAssignment | undefined;
  providers: ProviderOption[];
  onProviderChange: (provider: string) => void;
  onSubModelChange: (subModel: string) => void;
  onActiveChange: (isActive: boolean) => void;
}

function OperationRow({
  operation,
  assignment,
  providers,
  onProviderChange,
  onSubModelChange,
  onActiveChange,
}: OperationRowProps) {
  const currentProvider = assignment?.provider ?? '';
  const currentSubModel = assignment?.sub_model ?? '';
  const isActive = assignment?.is_active !== false;
  const subModels = getSubModelsForProvider(providers, currentProvider, operation);
  const hasSubModels = subModels.length > 0;
  const hideSubModel = operation === 'music';
  const selectedSubModel =
    currentSubModel && subModels.includes(currentSubModel)
      ? currentSubModel
      : (subModels[0] ?? '');

  return (
    <div className={`flex items-center gap-4 ${!isActive ? 'opacity-50' : ''}`}>
      <Label className="w-40 shrink-0 text-sm text-slate-300">
        {OPERATION_LABELS[operation] ?? operation}
      </Label>

      <label className="flex w-20 shrink-0 items-center gap-1.5 text-xs text-slate-400">
        <input
          type="checkbox"
          checked={isActive}
          onChange={(e) => onActiveChange(e.target.checked)}
        />
        Active
      </label>

      {/* Provider dropdown */}
      <Select value={currentProvider} onValueChange={onProviderChange}>
        <SelectTrigger className="w-40">
          <SelectValue placeholder="Select provider" />
        </SelectTrigger>
        <SelectContent>
          {providers.map((p) => (
            <SelectItem key={p.provider} value={p.provider}>
              {capitalizeProvider(p.provider)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Sub-model dropdown (conditional) with cost tier annotations */}
      {hasSubModels && !hideSubModel && (
        <Select value={selectedSubModel} onValueChange={onSubModelChange}>
          <SelectTrigger className="w-52">
            <SelectValue placeholder="Select model" />
          </SelectTrigger>
          <SelectContent>
            {subModels.map((model) => {
              const costDisplay = getCostDisplayForModel(
                providers,
                currentProvider,
                model,
                operation,
              );
              return (
                <SelectItem key={model} value={model}>
                  {formatModelLabel(model, costDisplay)}
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
      )}
    </div>
  );
}

// --- Utility: map operation → service type ---

const OPERATION_TO_SERVICE_TYPE: Record<string, ServiceType> = {
  channel_name: 'text_generation',
  channel_description: 'text_generation',
  channel_keywords: 'text_generation',
  channel_tags: 'text_generation',
  lyric: 'text_generation',
  title: 'text_generation',
  album: 'text_generation',
  web_music_style: 'text_generation',
  web_music_lyrics: 'text_generation',
  channel_logo: 'image_generation',
  channel_cover: 'image_generation',
  background_image: 'image_generation',
  thumbnail_image: 'image_generation',
  music: 'music_generation',
};

function getServiceTypeForOperation(operation: string): ServiceType | undefined {
  return OPERATION_TO_SERVICE_TYPE[operation];
}
