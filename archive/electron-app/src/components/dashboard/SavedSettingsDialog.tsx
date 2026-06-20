import * as React from "react";
import { Dialog, DialogContent } from "@/components/ui/Dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { useAppStore } from "@/store/useAppStore";

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
};

function yesNo(v: boolean) {
  return v ? "Yes" : "No";
}

function configured(v: string) {
  return v && v.trim() ? "Configured" : "Empty";
}

export function SavedSettingsDialog({ open, onOpenChange }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Saved settings" className="max-w-4xl h-[680px] flex flex-col">
        <SavedSettingsPanel />
      </DialogContent>
    </Dialog>
  );
}

export function SavedSettingsPanel() {
  const { data } = useAppStore();
  const s = data.settings;

  return (
    <div className="min-h-0 flex-1 overflow-auto p-4">
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Generation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm text-slate-200">
            <div>Language: {s.language}</div>
            <div>Creativity: {s.creativity}</div>
            <div>Default song count: {s.defaultSongCount}</div>
            <div>Unique opening: {yesNo(s.uniqueOpening)}</div>
            <div>Strict level: {s.strictLevel}</div>
            <div>History window: {s.uniquenessHistoryWindow}</div>
            <div>Shuffle description: {yesNo(s.shuffleDescription)}</div>
            <div>Shuffle structure: {yesNo(s.shuffleStructure)}</div>
            <div>Description enabled: {s.enabledDescriptionIds.length}</div>
            <div>Structure enabled: {s.enabledStructureIds.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>API</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm text-slate-200">
            <div>DeepSeek key: {configured(s.deepseekApiKey)}</div>
            <div>OpenAI key: {configured(s.openaiApiKey)}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Paths</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm text-slate-200">
            <div>FFmpeg: {s.ffmpegPath || "(empty)"}</div>
            <div>Downloads: {s.downloadsDir || "(empty)"}</div>
            <div>Merged: {s.mergedDir || "(empty)"}</div>
            <div>Image output: {s.imageOutputDir || "(empty)"}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Image</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm text-slate-200">
            <div>Resolution: {s.imageResolution}</div>
            <div>Style strength: {s.styleStrength}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>SUNO</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm text-slate-200">
            <div>Suno key: {configured(s.sunoApiKey)}</div>
            <div>Output dir: {s.sunoOutputDir || "(empty)"}</div>
            <div>Callback: {s.sunoCallbackUrl || "(empty)"}</div>
            <div>Default version: {s.sunoDefaultVersion}</div>
            <div>Merge enabled: {yesNo(s.sunoMergeEnabled)}</div>
            <div>Merge group size: {s.sunoMergeGroupSize}</div>
            <div>Timeout (ms): {s.sunoTimeoutMs}</div>
            <div>Retry count: {s.sunoRetryCount}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Database</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm text-slate-200">
            <div>Host: {s.dbHost}</div>
            <div>Port: {s.dbPort}</div>
            <div>User: {s.dbUser}</div>
            <div>Database: {s.dbName}</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
