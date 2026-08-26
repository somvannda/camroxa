export const V3_PLAN_OPS = [
  'lyric',
  'title',
  'album',
  'music',
  'style',
  'image',
  'video',
  'merge',
] as const;

export type V3PlanOp = (typeof V3_PLAN_OPS)[number];

export type V3Plan = {
  id: string;
  name: string;
  price_cents: number;
  billing_cycle_days: number | null;
  profile_allowance: number;
  monthly_song_limit: number | null;
  monthly_credits: number;
  daily_credits: number;
  is_public: boolean;
  is_active: boolean;
  plan_kind?: string;
  plan_type?: string;
  lyric_credits: number | null;
  title_credits: number | null;
  album_credits: number | null;
  music_credits: number | null;
  style_credits: number | null;
  image_credits: number | null;
  video_credits: number | null;
  merge_credits: number | null;
  pricing_features?: string[];
  pricing_credit_lines?: string[];
};

export type V3PlanPatch = {
  monthly_credits?: number;
  daily_credits?: number;
  is_public?: boolean;
  is_active?: boolean;
  lyric_credits?: number | null;
  title_credits?: number | null;
  album_credits?: number | null;
  music_credits?: number | null;
  style_credits?: number | null;
  image_credits?: number | null;
  video_credits?: number | null;
  merge_credits?: number | null;
  pricing_features?: string[];
  pricing_credit_lines?: string[];
};

export const CREDITS_ONLY_V3_CHARGE_SETTING_KEY = 'credits_only_v3_charge';

export type V3WalletLot = {
  id: string;
  tag: string;
  amount_credits: number;
  remaining_credits: number;
  expires_at?: string | null;
  period_start?: string | null;
};

export type V3WalletView = {
  user_id: string;
  balance_credits: number;
  balance_units: number;
  grant_remaining_credits: number;
  grant_remaining_units: number;
  plan?: {
    id?: string;
    name?: string;
    monthly_credits?: number;
    daily_credits?: number;
  } | null;
  lots: V3WalletLot[];
};
