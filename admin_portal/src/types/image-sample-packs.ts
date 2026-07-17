export type ImageSamplePackCategory = 'background' | 'thumbnail';

export type ImageSamplePackRecord = {
  id: string;
  category: string;
  name: string;
  source_type: string;
  source_value: string;
  is_active: boolean;
  sort_order: number;
  version_label: string | null;
  notes: string | null;
  asset_count?: number;
  storage_path?: string | null;
};

export type ImageSamplePackListResponse = {
  items: ImageSamplePackRecord[];
};

export type ImageSamplePackCreateRequest = {
  category: ImageSamplePackCategory;
  name: string;
  source_type?: string;
  source_value?: string;
  is_active: boolean;
  sort_order: number;
  version_label?: string | null;
  notes?: string | null;
};

export type ImageSamplePackUpdateRequest = {
  category?: ImageSamplePackCategory;
  name?: string;
  source_type?: string;
  source_value?: string;
  is_active?: boolean;
  sort_order?: number;
  version_label?: string | null;
  notes?: string | null;
};

