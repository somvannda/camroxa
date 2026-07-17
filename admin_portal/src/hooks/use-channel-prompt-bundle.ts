import { useState, useEffect, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type { ChannelPrompt } from '@/types/models';

const CATEGORIES = ['title', 'logo', 'cover', 'description', 'keyword', 'tag'] as const;

const CATEGORY_LABELS: Record<string, string> = {
  title: 'Channel Name',
  logo: 'Logo',
  cover: 'Cover Art',
  description: 'Description',
  keyword: 'Keywords',
  tag: 'Tags',
};

const CATEGORY_DEFAULT_NAMES: Record<string, string> = {
  title: 'Channel Name',
  logo: 'Channel Logo',
  cover: 'Channel Cover',
  description: 'Channel Description',
  keyword: 'Channel Keywords',
  tag: 'Channel Tags',
};

export interface PromptVariantState {
  id: string | null;
  content: string;
  category: string;
  name: string;
  isPersisted: boolean;
}

type BundleState = Record<string, PromptVariantState[]>;

function makeVariantName(category: string, key: string, index: number): string {
  const base = CATEGORY_DEFAULT_NAMES[category] ?? category;
  const safeKey = key
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^a-zA-Z0-9-_]/g, '')
    .slice(0, 24) || 'pool';
  const suffix = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID().slice(0, 8)
    : `${Date.now()}-${index + 1}`;
  return `${base} ${safeKey} ${index + 1} ${suffix}`.slice(0, 100);
}

function makeEntry(category: string): PromptVariantState {
  return {
    id: null,
    content: '',
    category,
    name: CATEGORY_DEFAULT_NAMES[category] ?? category,
    isPersisted: false,
  };
}

function emptyBundle(): BundleState {
  const state = {} as BundleState;
  for (const category of CATEGORIES) {
    state[category] = [makeEntry(category)];
  }
  return state;
}

export function useChannelPromptBundle(matchKey: string | null) {
  const [prompts, setPrompts] = useState<BundleState>(emptyBundle);
  const [isLoading, setIsLoading] = useState(false);
  const queryClient = useQueryClient();

  const load = useCallback(async (key: string) => {
    setIsLoading(true);
    try {
      const all = await httpClient.get<ChannelPrompt[]>('/api/v1/channel-prompts');
      const matched = all.filter(p => p.match_key === key);
      const next = emptyBundle();

      for (const category of CATEGORIES) {
        const variants = matched
          .filter(prompt => prompt.category === category)
          .map(prompt => ({
            id: prompt.id,
            content: prompt.content,
            category: prompt.category,
            name: prompt.name,
            isPersisted: true,
          }));

        next[category] = variants.length > 0 ? variants : [makeEntry(category)];
      }

      setPrompts(next);
    } catch {
      setPrompts(emptyBundle());
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (matchKey) {
      load(matchKey);
    } else {
      setPrompts(emptyBundle());
    }
  }, [matchKey, load]);

  const updateVariant = useCallback((category: string, index: number, content: string) => {
    setPrompts(prev => {
      const variants = prev[category];
      if (!variants || !variants[index]) {
        return prev;
      }

      const nextVariants = [...variants];
      const current = nextVariants[index];
      if (!current) {
        return prev;
      }
      nextVariants[index] = {
        id: current.id,
        content,
        category: current.category,
        name: current.name,
        isPersisted: current.isPersisted,
      };
      return { ...prev, [category]: nextVariants };
    });
  }, []);

  const appendVariant = useCallback((category: string, content = '') => {
    setPrompts(prev => {
      const variants = prev[category] ?? [makeEntry(category)];
      const nextVariant = makeEntry(category);
      nextVariant.content = content;
      return { ...prev, [category]: [...variants, nextVariant] };
    });
  }, []);

  const deleteVariant = useCallback(async (category: string, index: number) => {
    const variant = prompts[category]?.[index];
    if (!variant) {
      return;
    }

    if (variant.id) {
      await httpClient.delete(`/api/v1/channel-prompts/${variant.id}`);
    }

    setPrompts(prev => {
      const variants = [...(prev[category] ?? [])];
      variants.splice(index, 1);
      return {
        ...prev,
        [category]: variants.length > 0 ? variants : [makeEntry(category)],
      };
    });

    queryClient.invalidateQueries({ queryKey: ['channel-prompts'] });
  }, [prompts, queryClient]);

  const saveAll = useCallback(async (key: string) => {
    const results: { ok: boolean; category: string; index: number }[] = [];

    for (const category of CATEGORIES) {
      const variants = prompts[category] ?? [];

      for (let index = 0; index < variants.length; index += 1) {
        const variant = variants[index];
        if (!variant || !variant.content.trim()) {
          continue;
        }

        try {
          if (variant.id) {
            await httpClient.put(`/api/v1/channel-prompts/${variant.id}`, {
              content: variant.content.trim(),
            });
          } else {
            const created = await httpClient.post<ChannelPrompt>('/api/v1/channel-prompts', {
              name: makeVariantName(category, key, index),
              content: variant.content.trim(),
              category: variant.category,
              match_key: key,
              is_active: true,
            });

            setPrompts(prev => {
              const nextVariants = [...(prev[category] ?? [])];
              if (!nextVariants[index]) {
                return prev;
              }

              const current = nextVariants[index];
              if (!current) {
                return prev;
              }
              nextVariants[index] = {
                id: created.id,
                content: current.content,
                category: current.category,
                name: created.name,
                isPersisted: true,
              };

              return { ...prev, [category]: nextVariants };
            });
          }

          results.push({ ok: true, category, index });
        } catch {
          results.push({ ok: false, category, index });
        }
      }
    }

    queryClient.invalidateQueries({ queryKey: ['channel-prompts'] });
    return results;
  }, [prompts, queryClient]);

  const generatePrompt = useCallback(async (category: string, genre: string, currentMatchKey?: string | null) => {
    const response = await httpClient.post<{ content: string; category: string }>(
      '/api/v1/channel-prompts/generate',
      { category, genre, match_key: currentMatchKey ?? null },
    );
    return response.content;
  }, []);

  const hasContent = Object.values(prompts).some(variants =>
    variants.some(variant => variant.content.trim().length > 0),
  );

  return {
    prompts,
    isLoading,
    updateVariant,
    appendVariant,
    deleteVariant,
    saveAll,
    generatePrompt,
    hasContent,
    categories: CATEGORIES,
    categoryLabels: CATEGORY_LABELS,
  };
}
