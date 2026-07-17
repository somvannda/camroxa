export interface MarketplaceItem {
  id: string;
  name: string;
  description: string;
  version: string;
  author: string;
  kind: 'video' | 'reel';
  tags: string[];
  status: 'enabled' | 'disabled';
  price: number;
  preview_url: string;
  created_at: string;
}

export interface MarketplaceListResponse {
  items: MarketplaceItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface MarketplaceItemUpdate {
  name?: string;
  description?: string;
  tags?: string[];
  price?: number;
}
