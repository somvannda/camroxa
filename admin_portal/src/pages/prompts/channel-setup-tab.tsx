import { useState, useCallback } from 'react';
import { Loader2, CheckCircle2, AlertCircle, Sparkles } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

import { useDescriptions } from '@/hooks/use-prompts';
import { useChannelPromptBundle } from '@/hooks/use-channel-prompt-bundle';

const CATEGORY_ICONS: Record<string, string> = {
  title: '📝',
  logo: '🎨',
  cover: '🖼️',
  description: '📄',
  keyword: '🔑',
  tag: '🏷️',
};

const CATEGORY_PLACEHOLDERS: Record<string, string> = {
  title: 'e.g., Generate 10 creative channel names for a {genre} YouTube channel. Names should be catchy, memorable, and reflect the genre aesthetic...',
  logo: 'e.g., Create a circular logo for the YouTube channel "{channel_name}". The logo should feature bold typography with a modern {genre} aesthetic...',
  cover: 'e.g., Design a YouTube channel banner for "{channel_name}". The banner should showcase the {genre} vibe with vibrant colors...',
  description: 'e.g., Write a compelling YouTube channel description for "{channel_name}". Include relevant keywords, genre tags, and a call-to-action...',
  keyword: 'e.g., Generate 20 SEO keywords for a {genre} YouTube channel named "{channel_name}". Include a mix of short-tail and long-tail keywords...',
  tag: 'e.g., Generate relevant YouTube tags for a {genre} music channel named "{channel_name}". Include genre-specific and trending tags...',
};

export default function ChannelSetupTab() {
  const { data: descriptions, isLoading: descriptionsLoading } = useDescriptions();
  const [selectedMatchKey, setSelectedMatchKey] = useState<string | null>(null);
  const [selectedGenreName, setSelectedGenreName] = useState<string>('');
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [savedCount, setSavedCount] = useState(0);
  const [generatingAll, setGeneratingAll] = useState(false);
  const [generatingCategory, setGeneratingCategory] = useState<string | null>(null);

  const bundle = useChannelPromptBundle(selectedMatchKey);

  const genres = descriptions ?? [];

  function handleSelectGenre(genre: { id: string; name: string; match_key?: string | null }) {
    const key = genre.match_key ?? genre.name;
    setSelectedMatchKey(key);
    setSelectedGenreName(genre.name);
    setSaveStatus('idle');
  }

  async function handleSave() {
    if (!selectedMatchKey) return;
    setSaveStatus('saving');
    try {
      const results = await bundle.saveAll(selectedMatchKey);
      const ok = results.filter(r => r.ok).length;
      const fail = results.filter(r => !r.ok).length;
      setSavedCount(ok);
      setSaveStatus(fail > 0 ? 'error' : 'success');
    } catch {
      setSaveStatus('error');
    }
  }

  const handleGenerateSingle = useCallback(async (category: string) => {
    if (!selectedMatchKey) return;
    setGeneratingCategory(category);
    try {
      const content = await bundle.generatePrompt(category, selectedGenreName, selectedMatchKey);
      bundle.updateField(category, content);
    } catch {
      // silently fail — user can retry
    } finally {
      setGeneratingCategory(null);
    }
  }, [selectedMatchKey, selectedGenreName, bundle]);

  const handleGenerateAll = useCallback(async () => {
    if (!selectedMatchKey) return;
    setGeneratingAll(true);
    try {
      for (const cat of bundle.categories) {
        setGeneratingCategory(cat);
        const content = await bundle.generatePrompt(cat, selectedGenreName, selectedMatchKey);
        bundle.updateField(cat, content);
      }
    } catch {
      // partial failure is fine — some fields may have been filled
    } finally {
      setGeneratingAll(false);
      setGeneratingCategory(null);
    }
  }, [selectedMatchKey, selectedGenreName, bundle]);

  if (descriptionsLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-32 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Genre list */}
      <div className="space-y-2">
        <Label className="text-base font-semibold">Music Descriptions</Label>
        <p className="text-sm text-muted-foreground">
          Select a genre to configure all channel onboarding prompts at once.
        </p>
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Match Key</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {genres.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                    No music descriptions found.
                  </TableCell>
                </TableRow>
              ) : (
                genres.map(g => {
                  const key = g.match_key ?? g.name;
                  const isSelected = selectedMatchKey === key;
                  return (
                    <TableRow
                      key={g.id}
                      className={isSelected ? 'bg-muted/50' : 'cursor-pointer hover:bg-muted/30'}
                      onClick={() => handleSelectGenre(g)}
                    >
                      <TableCell className="font-medium">{g.name}</TableCell>
                      <TableCell className="text-muted-foreground">{key}</TableCell>
                      <TableCell className="text-muted-foreground max-w-sm truncate">
                        {g.content || '—'}
                      </TableCell>
                      <TableCell>
                        {isSelected && (
                          <span className="text-xs text-green-400 font-medium">Selected</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Prompt fields */}
      {selectedMatchKey && (
        <>
          {bundle.isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-36 w-full" />
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              {/* Generate All button */}
              <div className="flex items-center gap-3 pb-2">
                <Button
                  variant="outline"
                  onClick={handleGenerateAll}
                  disabled={generatingAll || generatingCategory !== null}
                >
                  {generatingAll ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Sparkles className="h-4 w-4 mr-2" />
                  )}
                  Generate All with AI
                </Button>
                <span className="text-xs text-muted-foreground">
                  Uses DeepSeek to generate all 6 prompts for this genre
                </span>
              </div>

              {bundle.categories.map(cat => {
                const field = bundle.prompts[cat];
                const hasExisting = !!field?.id;
                const isGenerating = generatingCategory === cat;
                return (
                  <div
                    key={cat}
                    className="border rounded-lg p-4 space-y-2 bg-card"
                  >
                    <div className="flex items-center gap-2">
                      <span>{CATEGORY_ICONS[cat]}</span>
                      <Label className="text-sm font-semibold">
                        {(bundle.categoryLabels as Record<string, string>)[cat] ?? cat} Prompt
                      </Label>
                      {hasExisting && (
                        <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                          Exists
                        </span>
                      )}
                      <div className="flex-1" />
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleGenerateSingle(cat)}
                        disabled={generatingAll || isGenerating}
                        title={`Generate ${bundle.categoryLabels[cat] ?? cat} prompt with AI`}
                      >
                        {isGenerating ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Sparkles className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Used when generating {((bundle.categoryLabels as Record<string, string>)[cat] ?? cat).toLowerCase()} during channel onboarding.
                      {cat === 'title' && ' Supports {genre} placeholder.'}
                      {(cat === 'logo' || cat === 'cover') && ' Supports {channel_name} and {genre} placeholders.'}
                      {cat === 'description' && ' Supports {channel_name} placeholder.'}
                    </p>
                    <Textarea
                      rows={4}
                      placeholder={CATEGORY_PLACEHOLDERS[cat]}
                      value={field?.content ?? ''}
                      onChange={e => bundle.updateField(cat, e.target.value)}
                      className="font-mono text-sm"
                    />
                    <p className="text-xs text-muted-foreground text-right">
                      {(field?.content ?? '').length} / 5000
                    </p>
                  </div>
                );
              })}
            </div>
          )}

          {/* Save button + status */}
          <div className="flex items-center gap-4 pt-2">
            <Button
              onClick={handleSave}
              disabled={saveStatus === 'saving' || !bundle.hasContent}
              size="lg"
            >
              {saveStatus === 'saving' && (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              )}
              Save All Prompts
            </Button>

            {saveStatus === 'success' && (
              <div className="flex items-center gap-2 text-green-400 text-sm">
                <CheckCircle2 className="h-4 w-4" />
                Saved {savedCount} prompt{savedCount !== 1 ? 's' : ''} successfully
              </div>
            )}

            {saveStatus === 'error' && (
              <div className="flex items-center gap-2 text-red-400 text-sm">
                <AlertCircle className="h-4 w-4" />
                Some prompts failed to save. Check your entries and try again.
              </div>
            )}
          </div>
        </>
      )}

      {/* Empty state */}
      {!selectedMatchKey && (
        <div className="text-center py-16 text-muted-foreground">
          <p className="text-lg">Select a genre from the table above to get started.</p>
          <p className="text-sm mt-2">
            This will load any existing prompts for that genre, or show empty fields for new setup.
          </p>
        </div>
      )}
    </div>
  );
}
