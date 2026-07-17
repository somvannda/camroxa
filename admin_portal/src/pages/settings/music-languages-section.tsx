import { useMemo, useState } from 'react';

import { Languages, Loader2, Pencil, Plus, Trash2 } from 'lucide-react';



import {

  useCreateMusicLanguage,

  useDeleteMusicLanguage,

  useMusicLanguages,

  useUpdateMusicLanguage,

} from '@/hooks/use-music-languages';

import { toast } from '@/hooks/use-toast';

import { Button } from '@/components/ui/button';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

import { Input } from '@/components/ui/input';

import { Label } from '@/components/ui/label';

import { Skeleton } from '@/components/ui/skeleton';

import {

  Dialog,

  DialogContent,

  DialogFooter,

  DialogHeader,

  DialogTitle,

} from '@/components/ui/dialog';

import { ConfirmDialog } from '@/components/shared/confirm-dialog';

import type { MusicLanguage } from '@/types/music-languages';



const PRESET_LANGUAGES = [

  { code: 'en', label: 'English' },

  { code: 'de', label: 'German' },

] as const;



export function MusicLanguagesSection() {

  const { data, isLoading, isError, refetch } = useMusicLanguages();

  const createLanguage = useCreateMusicLanguage();

  const updateLanguage = useUpdateMusicLanguage();

  const deleteLanguage = useDeleteMusicLanguage();



  const [dialogOpen, setDialogOpen] = useState(false);

  const [editTarget, setEditTarget] = useState<MusicLanguage | null>(null);

  const [deleteCode, setDeleteCode] = useState<string | null>(null);

  const [code, setCode] = useState('');

  const [label, setLabel] = useState('');

  const [enabled, setEnabled] = useState(true);

  const [sortOrder, setSortOrder] = useState('0');



  const items = useMemo(() => data?.items ?? [], [data?.items]);

  const enabledItems = useMemo(() => items.filter((item) => item.enabled), [items]);

  const existingCodes = useMemo(() => new Set(items.map((item) => item.code)), [items]);



  const resetForm = () => {

    setCode('');

    setLabel('');

    setEnabled(true);

    setSortOrder(String(items.length));

    setEditTarget(null);

  };



  const openCreateDialog = () => {

    resetForm();

    setDialogOpen(true);

  };



  const openEditDialog = (item: MusicLanguage) => {

    setEditTarget(item);

    setCode(item.code);

    setLabel(item.label);

    setEnabled(item.enabled);

    setSortOrder(String(item.sort_order));

    setDialogOpen(true);

  };



  const handleSave = () => {

    if (editTarget) {

      updateLanguage.mutate(

        {

          code: editTarget.code,

          patch: {

            label: label.trim(),

            enabled,

            sort_order: Number.parseInt(sortOrder, 10) || 0,

          },

        },

        {

          onSuccess: () => {

            toast({ title: 'Language updated' });

            setDialogOpen(false);

            resetForm();

          },

          onError: (error: Error) => {

            toast({ title: 'Update failed', description: error.message, variant: 'destructive' });

          },

        },

      );

      return;

    }



    createLanguage.mutate(

      {

        code: code.trim().toLowerCase(),

        label: label.trim(),

        enabled,

        sort_order: Number.parseInt(sortOrder, 10) || 0,

      },

      {

        onSuccess: () => {

          toast({ title: 'Language added' });

          setDialogOpen(false);

          resetForm();

        },

        onError: (error: Error) => {

          toast({ title: 'Failed to add language', description: error.message, variant: 'destructive' });

        },

      },

    );

  };



  const handleToggle = (languageCode: string, nextEnabled: boolean) => {

    updateLanguage.mutate(

      { code: languageCode, patch: { enabled: nextEnabled } },

      {

        onSuccess: () => toast({ title: nextEnabled ? 'Language enabled' : 'Language disabled' }),

        onError: (error: Error) => {

          toast({ title: 'Update failed', description: error.message, variant: 'destructive' });

        },

      },

    );

  };



  const handleQuickAdd = (preset: (typeof PRESET_LANGUAGES)[number]) => {

    if (existingCodes.has(preset.code)) {

      const existing = items.find((item) => item.code === preset.code);

      if (existing && !existing.enabled) {

        handleToggle(preset.code, true);

      } else {

        toast({ title: `${preset.label} already exists` });

      }

      return;

    }



    createLanguage.mutate(

      {

        code: preset.code,

        label: preset.label,

        enabled: true,

        sort_order: items.length,

      },

      {

        onSuccess: () => toast({ title: `${preset.label} added and enabled` }),

        onError: (error: Error) => {

          toast({ title: 'Failed to add language', description: error.message, variant: 'destructive' });

        },

      },

    );

  };



  const handleDelete = () => {

    if (!deleteCode) return;

    deleteLanguage.mutate(deleteCode, {

      onSuccess: () => {

        toast({ title: `Deleted ${deleteCode}` });

        setDeleteCode(null);

      },

      onError: (error: Error) => {

        toast({ title: 'Delete failed', description: error.message, variant: 'destructive' });

      },

    });

  };



  const workspaceMode =

    enabledItems.length <= 1

      ? 'Single language dropdown in the Music workspace.'

      : 'Primary + Secondary language dropdowns in the Music workspace.';



  if (isLoading) {

    return <Skeleton className="h-64 w-full" />;

  }



  if (isError) {

    return <Button onClick={() => refetch()}>Retry loading languages</Button>;

  }



  return (

    <div className="space-y-4">

      <Card className="border-slate-800 bg-slate-900/50">

        <CardHeader className="flex flex-row items-start justify-between gap-4">

          <div>

            <CardTitle className="flex items-center gap-2 text-lg">

              <Languages className="h-5 w-5 text-blue-400" />

              Music Languages

            </CardTitle>

            <CardDescription>

              Add, edit, enable, or remove languages. Only enabled languages appear in the desktop Music workspace.

            </CardDescription>

          </div>

          <div className="flex flex-wrap gap-2">

            {PRESET_LANGUAGES.map((preset) => (

              <Button key={preset.code} variant="outline" size="sm" onClick={() => handleQuickAdd(preset)}>

                + {preset.label}

              </Button>

            ))}

            <Button onClick={openCreateDialog}>

              <Plus className="mr-2 h-4 w-4" />

              Add Language

            </Button>

          </div>

        </CardHeader>

        <CardContent className="space-y-4">

          <div className="rounded-md border border-blue-500/30 bg-blue-500/10 p-3 text-sm text-slate-200">

            <p className="font-medium text-blue-200">Workspace dropdown behavior</p>

            <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-300">

              <li>Only English enabled → one <strong>Language</strong> dropdown (English).</li>

              <li>Only German enabled → one <strong>Language</strong> dropdown (German).</li>

              <li>English + German enabled → <strong>Primary</strong> and <strong>Secondary</strong> dropdowns.</li>
              <li>Secondary set to <strong>None</strong> → single-language lyrics (Primary only).</li>
              <li>Secondary set to another language → bilingual lyrics only (title/album stay Primary).</li>

            </ul>

            <p className="mt-2 text-xs text-slate-400">

              Current: {enabledItems.length} enabled ({enabledItems.map((item) => item.label).join(', ') || 'none'}).

              {workspaceMode}

            </p>

          </div>



          {items.map((item) => (

            <div

              key={item.code}

              className="flex flex-wrap items-center gap-4 rounded-md border border-slate-700 p-3"

            >

              <div className="min-w-[120px] flex-1">

                <p className="text-sm font-medium text-slate-100">{item.label}</p>

                <p className="text-xs text-slate-400">Code: {item.code}</p>

              </div>

              <div className="text-xs text-slate-400">Sort: {item.sort_order}</div>

              <div className="flex items-center gap-2">

                <Label htmlFor={`enabled-${item.code}`} className="text-xs text-slate-300">

                  Enabled

                </Label>

                <input

                  id={`enabled-${item.code}`}

                  type="checkbox"

                  checked={item.enabled}

                  onChange={(event) => handleToggle(item.code, event.target.checked)}

                  disabled={updateLanguage.isPending}

                  className="h-4 w-4 rounded border-slate-600"

                />

              </div>

              <Button

                variant="ghost"

                size="icon"

                onClick={() => openEditDialog(item)}

                disabled={updateLanguage.isPending}

              >

                <Pencil className="h-4 w-4 text-slate-300" />

              </Button>

              <Button

                variant="ghost"

                size="icon"

                onClick={() => setDeleteCode(item.code)}

                disabled={deleteLanguage.isPending}

              >

                <Trash2 className="h-4 w-4 text-red-400" />

              </Button>

            </div>

          ))}

        </CardContent>

      </Card>



      <Dialog

        open={dialogOpen}

        onOpenChange={(open) => {

          setDialogOpen(open);

          if (!open) resetForm();

        }}

      >

        <DialogContent>

          <DialogHeader>

            <DialogTitle>{editTarget ? 'Edit Music Language' : 'Add Music Language'}</DialogTitle>

          </DialogHeader>

          <div className="space-y-4 py-2">

            <div className="space-y-2">

              <Label>Code</Label>

              <Input

                value={code}

                onChange={(e) => setCode(e.target.value)}

                placeholder="en"

                disabled={!!editTarget}

              />

            </div>

            <div className="space-y-2">

              <Label>Label</Label>

              <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="English" />

            </div>

            <div className="space-y-2">

              <Label>Sort order</Label>

              <Input value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} />

            </div>

            <label className="flex items-center gap-2 text-sm text-slate-300">

              <input

                id="language-enabled"

                type="checkbox"

                checked={enabled}

                onChange={(event) => setEnabled(event.target.checked)}

                className="h-4 w-4 rounded border-slate-600"

              />

              Enabled for users

            </label>

          </div>

          <DialogFooter>

            <Button variant="outline" onClick={() => setDialogOpen(false)}>

              Cancel

            </Button>

            <Button

              onClick={handleSave}

              disabled={!label.trim() || (!editTarget && !code.trim()) || createLanguage.isPending || updateLanguage.isPending}

            >

              {(createLanguage.isPending || updateLanguage.isPending) && (

                <Loader2 className="mr-2 h-4 w-4 animate-spin" />

              )}

              Save

            </Button>

          </DialogFooter>

        </DialogContent>

      </Dialog>



      <ConfirmDialog

        open={!!deleteCode}

        onOpenChange={(open) => {

          if (!open) setDeleteCode(null);

        }}

        title="Delete Language"

        description={`Delete "${deleteCode}"? Users will no longer be able to select it.`}

        onConfirm={handleDelete}

        variant="destructive"

        confirmText="Delete"

        isLoading={deleteLanguage.isPending}

      />

    </div>

  );

}


