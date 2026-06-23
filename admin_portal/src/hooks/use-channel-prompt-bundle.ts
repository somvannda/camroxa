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

interface BundlePromptState {
  id: string | null;
  content: string;
  category: string;
  name: string;
}

type BundleState = Record<string, BundlePromptState>;

function makeEntry(cat: string): BundlePromptState {
  return { id: null, content: '', category: cat, name: CATEGORY_DEFAULT_NAMES[cat] ?? cat };
}

function emptyBundle(): BundleState {
  const state: BundleState = {};
  for (const cat of CATEGORIES) {
    state[cat] = makeEntry(cat);
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
      for (const p of matched) {
        if (next[p.category]) {
          next[p.category] = { id: p.id, content: p.content, category: p.category, name: p.name };
        }
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

  const updateField = useCallback((category: string, content: string) => {
    setPrompts(prev => {
      const next = { ...prev };
      const existing = next[category];
      if (existing) {
        next[category] = { ...existing, content };
      }
      return next;
    });
  }, []);

  const saveAll = useCallback(async (key: string) => {
    const results: { ok: boolean; category: string }[] = [];

    for (const cat of CATEGORIES) {
      const p = prompts[cat];
      if (!p || !p.content.trim()) continue;

      try {
        if (p.id) {
          await httpClient.put(`/api/v1/channel-prompts/${p.id}`, {
            content: p.content.trim(),
          });
        } else {
          const created = await httpClient.post<ChannelPrompt>('/api/v1/channel-prompts', {
            name: p.name,
            content: p.content.trim(),
            category: p.category,
            match_key: key,
            is_active: true,
          });
          setPrompts(prev => {
            const next = { ...prev };
            const existing = next[cat];
            if (existing) {
              next[cat] = { ...existing, id: created.id };
            }
            return next;
          });
        }
        results.push({ ok: true, category: cat });
      } catch {
        results.push({ ok: false, category: cat });
      }
    }

    queryClient.invalidateQueries({ queryKey: ['channel-prompts'] });
    return results;
  }, [prompts, queryClient]);

  const hasContent = Object.values(prompts).some(p => p.content.trim().length > 0);

  const generatePrompt = useCallback(async (category: string, genre: string, matchKey?: string | null) => {
    const resp = await httpClient.post<{ content: string; category: string }>(
      '/api/v1/channel-prompts/generate',
      { category, genre, match_key: matchKey ?? null },
    );
    return resp.content;
  }, []);

  return {
    prompts,
    isLoading,
    updateField,
    saveAll,
    generatePrompt,
    hasContent,
    categories: CATEGORIES,
    categoryLabels: CATEGORY_LABELS,
  };
}
