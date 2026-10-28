export type RemixStaffPick = {
  id: string;
  provider_clip_id: string;
  title: string;
  image_url?: string | null;
  styles?: string | null;
  model?: string | null;
  account_id?: string | null;
  sort_order: number;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

export type RemixStaffPickListResponse = {
  items: RemixStaffPick[];
};

export type RemixStaffPickInput = {
  provider_clip_id: string;
  title: string;
  image_url?: string | null;
  styles?: string | null;
  model?: string | null;
  account_id?: string | null;
  sort_order?: number;
  is_active?: boolean;
};
