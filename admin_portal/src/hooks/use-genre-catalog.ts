import { useQuery } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';

export type GenreCatalogItem = {
  name: string;
  slug: string;
  category: string;
  aliases: string[];
};

export type GenreCatalogResponse = {
  items: GenreCatalogItem[];
  categories: string[];
};

export function useGenreCatalogSearch(query: string, category?: string) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: ['genre-catalog', trimmed, category ?? ''],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (trimmed) params.set('q', trimmed);
      if (category) params.set('category', category);
      params.set('limit', '30');
      return httpClient.get<GenreCatalogResponse>(
        `/api/v1/prompts/genre-catalog?${params.toString()}`,
      );
    },
    staleTime: 60_000,
  });
}

export function useGenreCatalogCategories() {
  return useQuery({
    queryKey: ['genre-catalog-categories'],
    queryFn: () =>
      httpClient.get<GenreCatalogResponse>('/api/v1/prompts/genre-catalog?limit=1').then(
        (response) => response.categories,
      ),
    staleTime: 300_000,
  });
}
