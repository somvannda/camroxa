export interface MusicLanguage {
  code: string;
  label: string;
  enabled: boolean;
  sort_order: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface MusicLanguageListResponse {
  items: MusicLanguage[];
}

export interface CreateMusicLanguageRequest {
  code: string;
  label: string;
  enabled?: boolean;
  sort_order?: number;
}

export interface UpdateMusicLanguageRequest {
  label?: string;
  enabled?: boolean;
  sort_order?: number;
}
