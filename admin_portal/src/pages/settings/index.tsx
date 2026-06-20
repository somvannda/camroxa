import { useState } from 'react';
import { Loader2, Plus, Trash2, Eye, EyeOff, Settings2 } from 'lucide-react';

import { useSystemSettings, useUpsertSetting, useDeleteSetting } from '@/hooks/use-settings';
import { toast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';

// Predefined API key settings with descriptions
const API_KEY_TEMPLATES = [
  { key: 'suno_api_key', label: 'Suno API Key', description: 'API key for Suno music generation service' },
  { key: 'suno_api_url', label: 'Suno API URL', description: 'Base URL for Suno API' },
  { key: 'fal_api_key', label: 'FAL.ai API Key', description: 'API key for FAL.ai image generation' },
  { key: 'openai_api_key', label: 'OpenAI API Key', description: 'API key for OpenAI (GPT models, DALL-E)' },
  { key: 'openai_model', label: 'OpenAI Model', description: 'Default model (e.g., gpt-4o, gpt-4o-mini)' },
  { key: 'slai_api_key', label: 'Slai API Key', description: 'API key for Slai service' },
  { key: 'youtube_api_key', label: 'YouTube API Key', description: 'API key for YouTube upload integration' },
  { key: 'facebook_api_key', label: 'Facebook API Key', description: 'API key for Facebook/Instagram integration' },
];

function isSensitiveKey(key: string): boolean {
  return key.includes('key') || key.includes('secret') || key.includes('token') || key.includes('password');
}

function maskValue(value: string): string {
  if (value.length <= 8) return '••••••••';
  return value.slice(0, 4) + '••••••••' + value.slice(-4);
}

export default function SettingsPage() {
  const { data, isLoading, isError, refetch } = useSystemSettings();
  const upsertSetting = useUpsertSetting();
  const deleteSetting = useDeleteSetting();

  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [editKey, setEditKey] = useState('');
  const [editValue, setEditValue] = useState('');
  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set());

  const settings = data?.settings ?? [];
  const settingsMap = new Map(settings.map(s => [s.key, s]));

  const toggleReveal = (key: string) => {
    setRevealedKeys(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleSave = (key: string, value: string) => {
    upsertSetting.mutate(
      { key, value },
      {
        onSuccess: () => toast({ title: `Setting "${key}" saved` }),
      },
    );
  };

  const handleDelete = () => {
    if (!deleteTarget) return;
    deleteSetting.mutate(deleteTarget, {
      onSuccess: () => {
        toast({ title: `Setting "${deleteTarget}" deleted` });
        setDeleteTarget(null);
      },
    });
  };

  const handleAddCustom = () => {
    if (!editKey.trim()) return;
    upsertSetting.mutate(
      { key: editKey.trim(), value: editValue },
      {
        onSuccess: () => {
          toast({ title: `Setting "${editKey}" added` });
          setAddDialogOpen(false);
          setEditKey('');
          setEditValue('');
        },
      },
    );
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-6">
        <h1 className="mb-6 text-2xl font-bold text-slate-100">Settings</h1>
        <Button onClick={() => refetch()}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Settings</h1>
          <p className="text-sm text-slate-400">Manage API keys, model configurations, and service settings</p>
        </div>
        <Button onClick={() => setAddDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Custom Setting
        </Button>
      </div>

      {/* API Keys & Service Config */}
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Settings2 className="h-5 w-5" />
            API Keys & Service Configuration
          </CardTitle>
          <CardDescription className="text-slate-400">
            Configure API keys for external services. Values are stored securely in the database.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {API_KEY_TEMPLATES.map(template => {
            const existing = settingsMap.get(template.key);
            const isRevealed = revealedKeys.has(template.key);
            const isSensitive = isSensitiveKey(template.key);

            return (
              <ApiKeyRow
                key={template.key}
                label={template.label}
                description={template.description}
                settingKey={template.key}
                currentValue={existing?.value ?? ''}
                isRevealed={isRevealed}
                isSensitive={isSensitive}
                onToggleReveal={() => toggleReveal(template.key)}
                onSave={(value) => handleSave(template.key, value)}
                onDelete={() => setDeleteTarget(template.key)}
                hasValue={!!existing}
                isPending={upsertSetting.isPending}
              />
            );
          })}
        </CardContent>
      </Card>

      {/* Custom/Other Settings */}
      {settings.filter(s => !API_KEY_TEMPLATES.some(t => t.key === s.key)).length > 0 && (
        <Card className="border-slate-800 bg-slate-900/50">
          <CardHeader>
            <CardTitle className="text-lg">Custom Settings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {settings
              .filter(s => !API_KEY_TEMPLATES.some(t => t.key === s.key))
              .map(setting => (
                <div key={setting.key} className="flex items-center gap-4 rounded-md border border-slate-700 p-3">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-200">{setting.key}</p>
                    <p className="text-xs text-slate-400">{setting.value}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setDeleteTarget(setting.key)}
                  >
                    <Trash2 className="h-4 w-4 text-red-400" />
                  </Button>
                </div>
              ))}
          </CardContent>
        </Card>
      )}

      {/* Add Custom Setting Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Custom Setting</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Key</Label>
              <Input
                value={editKey}
                onChange={(e) => setEditKey(e.target.value)}
                placeholder="e.g., custom_service_url"
              />
            </div>
            <div className="space-y-2">
              <Label>Value</Label>
              <Input
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                placeholder="Value"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleAddCustom} disabled={!editKey.trim() || upsertSetting.isPending}>
              {upsertSetting.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
        title="Delete Setting"
        description={`Are you sure you want to delete "${deleteTarget}"? This cannot be undone.`}
        onConfirm={handleDelete}
        variant="destructive"
        confirmText="Delete"
        isLoading={deleteSetting.isPending}
      />
    </div>
  );
}

// --- API Key Row Component ---
interface ApiKeyRowProps {
  label: string;
  description: string;
  settingKey: string;
  currentValue: string;
  isRevealed: boolean;
  isSensitive: boolean;
  onToggleReveal: () => void;
  onSave: (value: string) => void;
  onDelete: () => void;
  hasValue: boolean;
  isPending: boolean;
}

function ApiKeyRow({
  label,
  description,
  currentValue,
  isRevealed,
  isSensitive,
  onToggleReveal,
  onSave,
  onDelete,
  hasValue,
  isPending,
}: ApiKeyRowProps) {
  const [editing, setEditing] = useState(false);
  const [inputValue, setInputValue] = useState(currentValue);

  const handleStartEdit = () => {
    setInputValue(currentValue);
    setEditing(true);
  };

  const handleSave = () => {
    onSave(inputValue);
    setEditing(false);
  };

  const handleCancel = () => {
    setInputValue(currentValue);
    setEditing(false);
  };

  return (
    <div className="flex items-center gap-4 rounded-md border border-slate-700 p-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-slate-200">{label}</p>
          {hasValue ? (
            <Badge className="border-green-500/30 bg-green-500/10 text-green-400 text-xs">Configured</Badge>
          ) : (
            <Badge className="border-slate-500/30 bg-slate-500/10 text-slate-400 text-xs">Not Set</Badge>
          )}
        </div>
        <p className="text-xs text-slate-500 mt-0.5">{description}</p>

        {editing ? (
          <div className="mt-2 flex items-center gap-2">
            <Input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              type={isSensitive && !isRevealed ? 'password' : 'text'}
              className="text-sm"
              placeholder={`Enter ${label}`}
            />
            <Button size="sm" onClick={handleSave} disabled={isPending}>Save</Button>
            <Button size="sm" variant="ghost" onClick={handleCancel}>Cancel</Button>
          </div>
        ) : hasValue ? (
          <p className="text-xs text-slate-400 mt-1 font-mono">
            {isSensitive && !isRevealed ? maskValue(currentValue) : currentValue}
          </p>
        ) : null}
      </div>

      <div className="flex items-center gap-1">
        {hasValue && isSensitive && (
          <Button variant="ghost" size="icon" onClick={onToggleReveal} className="h-8 w-8">
            {isRevealed ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </Button>
        )}
        {!editing && (
          <Button variant="outline" size="sm" onClick={handleStartEdit}>
            {hasValue ? 'Edit' : 'Set'}
          </Button>
        )}
        {hasValue && (
          <Button variant="ghost" size="icon" onClick={onDelete} className="h-8 w-8">
            <Trash2 className="h-4 w-4 text-red-400" />
          </Button>
        )}
      </div>
    </div>
  );
}
