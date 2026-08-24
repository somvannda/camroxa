import { useState } from 'react';
import { Database, Loader2, Plus, Settings2, Trash2 } from 'lucide-react';

import { useSystemSettings, useUpsertSetting, useDeleteSetting } from '@/hooks/use-settings';
import { toast } from '@/hooks/use-toast';
import { AIRoutingSection } from './ai-routing-section';
import { ImageGenerationSection } from './image-generation-section';
import { MusicLanguagesSection } from './music-languages-section';
import { SunoBlocklistSection } from './suno-blocklist-section';
import { FailAbsorbSection } from './fail-absorb-section';
import { MusicWebCreditsNote } from '@/pages/settings/music-web-credits-note';
import { PaymentSection } from './payment-section';
import { StreamingStorageSection } from './streaming-section';
import { UserDataManagementSection } from './user-data-section';
import { YouTubeOAuthSection } from './youtube-oauth-section';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function SettingsPage() {
  const { data, isLoading, isError, refetch } = useSystemSettings();
  const upsertSetting = useUpsertSetting();
  const deleteSetting = useDeleteSetting();

  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [editKey, setEditKey] = useState('');
  const [editValue, setEditValue] = useState('');
  const [activeTab, setActiveTab] = useState('ai-routing');

  const settings = data?.settings ?? [];

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
          <p className="text-sm text-slate-400">Manage AI routing, streaming storage, YouTube OAuth, and other system settings</p>
        </div>
        {activeTab === 'custom' ? (
          <Button onClick={() => setAddDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Custom Setting
          </Button>
        ) : (
          <div className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2 text-xs text-slate-400">
            Admin-only integration controls
          </div>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="border border-slate-800 bg-slate-900/60">
          <TabsTrigger value="ai-routing">AI Routing</TabsTrigger>
          <TabsTrigger value="image-generation">Image Generation</TabsTrigger>
          <TabsTrigger value="music-languages">Music Languages</TabsTrigger>
          <TabsTrigger value="suno-blocklist">Suno Blocklist</TabsTrigger>
          <TabsTrigger value="billing">Billing</TabsTrigger>
          <TabsTrigger value="music-web">Music Web</TabsTrigger>
          <TabsTrigger value="fail-absorb">Fail / Retry Absorb</TabsTrigger>
          <TabsTrigger value="streaming">Streaming</TabsTrigger>
          <TabsTrigger value="youtube-oauth">YouTube OAuth</TabsTrigger>
          <TabsTrigger value="user-data">
            <Database className="mr-2 h-4 w-4" />
            User Data
          </TabsTrigger>
          <TabsTrigger value="custom">
            <Settings2 className="mr-2 h-4 w-4" />
            Custom Settings
          </TabsTrigger>
        </TabsList>

        <TabsContent value="ai-routing" className="mt-6">
          <AIRoutingSection />
        </TabsContent>

        <TabsContent value="image-generation" className="mt-6">
          <ImageGenerationSection />
        </TabsContent>

        <TabsContent value="music-languages" className="mt-6">
          <MusicLanguagesSection />
        </TabsContent>

        <TabsContent value="suno-blocklist" className="mt-6">
          <SunoBlocklistSection />
        </TabsContent>

        <TabsContent value="billing" className="mt-6">
          <PaymentSection />
        </TabsContent>

        <TabsContent value="music-web" className="mt-6">
          <MusicWebCreditsNote />
        </TabsContent>

        <TabsContent value="fail-absorb" className="mt-6">
          <FailAbsorbSection />
        </TabsContent>

        <TabsContent value="streaming" className="mt-6">
          <StreamingStorageSection />
        </TabsContent>

        <TabsContent value="youtube-oauth" className="mt-6">
          <YouTubeOAuthSection />
        </TabsContent>

        <TabsContent value="user-data" className="mt-6">
          <UserDataManagementSection />
        </TabsContent>

        <TabsContent value="custom" className="mt-6">
          {settings.length > 0 ? (
            <Card className="border-slate-800 bg-slate-900/50">
              <CardHeader>
                <CardTitle className="text-lg">Custom Settings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {settings.map(setting => (
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
          ) : (
            <Card className="border-slate-800 bg-slate-900/50">
              <CardContent className="p-6 text-sm text-slate-400">
                No custom settings saved yet.
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

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
