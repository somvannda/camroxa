const OPERATION_LABELS: Record<string, string> = {
  song_draft: 'Song draft',
  llm_draft: 'Song draft',
  title: 'Title',
  album: 'Album',
  lyric: 'Lyrics (Desktop / Batch)',
  lyrics: 'Lyrics (Desktop / Batch)',
  web_music_lyrics: 'Music Lyric',
  web_music_style: 'Music Style Tags',
  suno: 'Music (Suno)',
  suno_generation: 'Music (Suno)',
  image: 'Image',
  image_generation: 'Image',
  background_image: 'Background image',
  thumbnail_image: 'Thumbnail image',
  music: 'Music',
  music_generation: 'Music',
  video: 'Studio export',
  video_manual: 'Manual export',
  video_merge: 'Video merge',
  channel_setup: 'Channel setup',
  draft_generation_failed: 'Draft refund',
  credit_pack_purchase: 'Credit pack',
  style: 'Style assist',
  v3_music: 'Music',
  v3_lyric: 'Lyrics',
  v3_style: 'Style assist',
  v3_period_grant: 'Period grant',
  v3_daily_grant: 'Daily grant',
  v3_web_remaining: 'Web leftover',
  v3_pack: 'Credit pack',
  web_remaining: 'Web leftover',
  period_grant: 'Period grant',
  daily_grant: 'Daily grant',
  grant_expire: 'Grant expired',
};

export function formatOperationLabel(operation?: string | null): string {
  if (!operation) return 'All operations';
  const key = operation.trim().toLowerCase();
  if (OPERATION_LABELS[key]) return OPERATION_LABELS[key];
  const stripped = key.startsWith('v3_refund_')
    ? key.slice('v3_refund_'.length)
    : key.startsWith('v3_')
      ? key.slice(3)
      : key;
  if (OPERATION_LABELS[stripped]) return OPERATION_LABELS[stripped];
  return stripped.replace(/_/g, ' ');
}

const PROVIDER_LABELS: Record<string, string> = {
  slai: 'SLAI',
  fal: 'Fal',
  openai: 'OpenAI',
  deepseek: 'DeepSeek',
  suno: 'Suno',
  cala: 'Cala',
  kie: 'kie.ai',
  local: 'Local',
};

export function formatProviderLabel(provider?: string | null): string {
  if (!provider) return 'All providers';
  const key = provider.trim().toLowerCase();
  return PROVIDER_LABELS[key] ?? provider;
}

export function formatCredits(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1) return abs.toFixed(4).replace(/\.?0+$/, '');
  return abs.toFixed(6).replace(/0+$/, '').replace(/\.$/, '');
}

/** Convert micro-credit units to display credits when present. */
export function formatCreditUnits(units?: number | null): string | null {
  if (units == null || Number.isNaN(Number(units))) return null;
  return formatCredits(Number(units) / 10_000);
}

export type UsageBillingFields = {
  amount: number;
  direction: string;
  billing?: string | null;
  list_credit_units?: number | null;
  charged_credit_units?: number | null;
  coverage?: string | null;
  metadata?: Record<string, unknown> | null;
};

function metaBilling(row: UsageBillingFields): string | null {
  const fromField = row.billing?.trim();
  if (fromField) return fromField;
  const meta = row.metadata;
  if (meta && typeof meta.billing === 'string' && meta.billing.trim()) {
    return meta.billing.trim();
  }
  return null;
}

function metaListUnits(row: UsageBillingFields): number | null {
  if (typeof row.list_credit_units === 'number') return row.list_credit_units;
  const raw = row.metadata?.list_credit_units;
  return typeof raw === 'number' ? raw : null;
}

/**
 * Smart cost label for usage rows.
 * Historical plan_allowance stays labeled. New $0 rows are wallet or plan_included.
 * Do not rewrite historical allowance into fake wallet debits.
 */
export function formatUsageCostLabel(row: UsageBillingFields): string {
  const billing = metaBilling(row);
  const listUnits = metaListUnits(row);
  const listLabel = formatCreditUnits(listUnits);

  if (billing === 'plan_allowance') {
    if (listLabel) return `Plan allowance (list ${listLabel})`;
    return 'Plan allowance';
  }

  if (billing === 'plan_included') {
    if (listLabel) return `Plan included (0, list ${listLabel})`;
    return 'Plan included (0)';
  }

  if (billing === 'platform_absorb') {
    if (listLabel) return `Platform absorbed (list ${listLabel})`;
    return 'Platform absorbed';
  }

  if (billing === 'wallet') {
    return `Credits charged −${formatCredits(Math.abs(row.amount))}`;
  }

  const prefix = row.direction === 'debit' ? '−' : row.direction === 'refund' ? '+' : '+';
  return `${prefix}${formatCredits(Math.abs(row.amount))}`;
}

export function truncateId(id?: string | null, length = 10): string {
  if (!id) return '—';
  if (id.length <= length) return id;
  return `${id.slice(0, length)}…`;
}
