import { useState, useCallback } from 'react';
import { AlertCircle, CheckCircle2, Loader2, Plus, Sparkles, Trash2 } from 'lucide-react';

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

const CATEGORY_PLACEHOLDERS: Record<string, string> = {
  title: 'e.g., Generate 10 creative channel names for a {genre} YouTube channel. Names should be catchy, memorable, and reflect the genre aesthetic...',
  logo: 'e.g., Create a circular logo for the YouTube channel "{channel_name}". The logo should feature bold typography with a modern {genre} aesthetic...',
  cover: 'e.g., Design a YouTube channel banner for "{channel_name}". The banner should showcase the {genre} vibe with vibrant colors...',
  description: 'e.g., Write a compelling YouTube channel description for "{channel_name}". Include a call-to-action. Keep keywords and tags as separate fields.',
  keyword:
    'e.g., Generate 15-25 YouTube channel keywords for a {genre} channel named "{channel_name}". Each keyword must be 1-3 words only, correct English, no sentences, no commas inside a keyword.',
  tag: 'e.g., Generate 15-30 YouTube tags for a {genre} music channel named "{channel_name}". Each tag is 1-3 words, correct English, pasteable comma-separated into YouTube Studio (under 500 characters total).',
};

export default function ChannelSetupTab() {
  const { data: descriptions, isLoading: descriptionsLoading } = useDescriptions();
  const [selectedMatchKey, setSelectedMatchKey] = useState<string | null>(null);
  const [selectedGenreName, setSelectedGenreName] = useState<string>('');
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [savedCount, setSavedCount] = useState(0);
  const [generatingAll, setGeneratingAll] = useState(false);
  const [generatingCategory, setGeneratingCategory] = useState<string | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);

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
      const ok = results.filter(result => result.ok).length;
      const fail = results.filter(result => !result.ok).length;
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
      bundle.appendVariant(category, content);
    } catch {
      // Allow retry without noisy inline error for now.
    } finally {
      setGeneratingCategory(null);
    }
  }, [bundle, selectedGenreName, selectedMatchKey]);

  const handleGenerateAll = useCallback(async () => {
    if (!selectedMatchKey) return;
    setGeneratingAll(true);
    try {
      for (const category of bundle.categories) {
        setGeneratingCategory(category);
        const content = await bundle.generatePrompt(category, selectedGenreName, selectedMatchKey);
        bundle.appendVariant(category, content);
      }
    } catch {
      // Partial generation is still useful.
    } finally {
      setGeneratingAll(false);
      setGeneratingCategory(null);
    }
  }, [bundle, selectedGenreName, selectedMatchKey]);

  const handleDeleteVariant = useCallback(async (category: string, index: number) => {
    const variantKey = `${category}-${index}`;
    setDeletingKey(variantKey);
    try {
      await bundle.deleteVariant(category, index);
      setSaveStatus('idle');
    } finally {
      setDeletingKey(null);
    }
  }, [bundle]);

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
      <div className="space-y-2">
        <Label className="text-base font-semibold">Music Descriptions</Label>
        <p className="text-sm text-muted-foreground">
          Select a genre to manage a real onboarding prompt pool for each category.
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
                  <TableCell colSpan={4} className="py-8 text-center text-muted-foreground">
                    No music descriptions found.
                  </TableCell>
                </TableRow>
              ) : (
                genres.map(genre => {
                  const key = genre.match_key ?? genre.name;
                  const isSelected = selectedMatchKey === key;
                  return (
                    <TableRow
                      key={genre.id}
                      className={isSelected ? 'bg-muted/50' : 'cursor-pointer hover:bg-muted/30'}
                      onClick={() => handleSelectGenre(genre)}
                    >
                      <TableCell className="font-medium">{genre.name}</TableCell>
                      <TableCell className="text-muted-foreground">{key}</TableCell>
                      <TableCell className="max-w-sm truncate text-muted-foreground">
                        {genre.content || '-'}
                      </TableCell>
                      <TableCell>
                        {isSelected ? (
                          <span className="text-xs font-medium text-green-400">Selected</span>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      {selectedMatchKey ? (
        <>
          {bundle.isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-36 w-full" />
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-3 pb-2">
                <Button
                  variant="outline"
                  onClick={handleGenerateAll}
                  disabled={generatingAll || generatingCategory !== null}
                >
                  {generatingAll ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="mr-2 h-4 w-4" />
                  )}
                  Generate All Pool Variants
                </Button>
                <span className="text-xs text-muted-foreground">
                  Each click adds one fresh AI variant to every onboarding category.
                </span>
              </div>

              {bundle.categories.map(category => {
                const variants = bundle.prompts[category] ?? [];
                const isGenerating = generatingCategory === category;
                return (
                  <div key={category} className="space-y-3 rounded-lg border bg-card p-4">
                    <div className="flex items-center gap-2">
                      <Label className="text-sm font-semibold">
                        {(bundle.categoryLabels as Record<string, string>)[category] ?? category} Pool
                      </Label>
                      <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        {variants.filter(variant => variant.content.trim()).length} ready
                      </span>
                      <div className="flex-1" />
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => bundle.appendVariant(category)}
                      >
                        <Plus className="mr-1 h-3.5 w-3.5" />
                        Add Variant
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleGenerateSingle(category)}
                        disabled={generatingAll || isGenerating}
                        title={`Generate another ${(bundle.categoryLabels as Record<string, string>)[category] ?? category} prompt`}
                      >
                        {isGenerating ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Sparkles className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>

                    <p className="text-xs text-muted-foreground">
                      Onboarding rotates through this pool instead of depending on one fixed prompt.
                      {category === 'title' && ' Supports {genre} placeholder.'}
                      {(category === 'logo' || category === 'cover') && ' Supports {channel_name} and {genre} placeholders.'}
                      {category === 'description' && ' Supports {channel_name} placeholder.'}
                    </p>

                    <div className="space-y-3">
                      {variants.map((variant, index) => {
                        const variantKey = `${category}-${index}`;
                        const isDeleting = deletingKey === variantKey;
                        return (
                          <div key={variant.id ?? variantKey} className="rounded-md border border-border/70 p-3">
                            <div className="mb-2 flex items-center gap-2">
                              <span className="text-xs font-medium text-muted-foreground">
                                Variant {index + 1}
                              </span>
                              {variant.isPersisted ? (
                                <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                                  Saved
                                </span>
                              ) : (
                                <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                                  Draft
                                </span>
                              )}
                              <div className="flex-1" />
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteVariant(category, index)}
                                disabled={isDeleting || variants.length === 1}
                                title={variants.length === 1 ? 'Keep at least one slot in the pool' : 'Delete this prompt variant'}
                              >
                                {isDeleting ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <Trash2 className="h-3.5 w-3.5" />
                                )}
                              </Button>
                            </div>
                            <Textarea
                              rows={4}
                              placeholder={CATEGORY_PLACEHOLDERS[category]}
                              value={variant.content}
                              onChange={event => bundle.updateVariant(category, index, event.target.value)}
                              className="font-mono text-sm"
                            />
                            <p className="mt-2 text-right text-xs text-muted-foreground">
                              {variant.content.length} / 5000
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="flex items-center gap-4 pt-2">
            <Button
              onClick={handleSave}
              disabled={saveStatus === 'saving' || !bundle.hasContent}
              size="lg"
            >
              {saveStatus === 'saving' ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Save Prompt Pool
            </Button>

            {saveStatus === 'success' ? (
              <div className="flex items-center gap-2 text-sm text-green-400">
                <CheckCircle2 className="h-4 w-4" />
                Saved {savedCount} prompt variant{savedCount !== 1 ? 's' : ''} successfully
              </div>
            ) : null}

            {saveStatus === 'error' ? (
              <div className="flex items-center gap-2 text-sm text-red-400">
                <AlertCircle className="h-4 w-4" />
                Some prompt variants failed to save. Check your entries and try again.
              </div>
            ) : null}
          </div>
        </>
      ) : (
        <div className="py-16 text-center text-muted-foreground">
          <p className="text-lg">Select a genre from the table above to get started.</p>
          <p className="mt-2 text-sm">
            This will load the current prompt pool for that genre and let you add more variants.
          </p>
        </div>
      )}
    </div>
  );
}
