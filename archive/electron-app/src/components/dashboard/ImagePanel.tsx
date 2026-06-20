import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { RefreshCcw } from "lucide-react";

export type ImagePanelItem = {
  filePath: string;
  fileUrl: string;
  label: string;
  mtimeMs: number;
};

export function ImagePanel(props: {
  contextLabel: string;
  backgroundPreviewUrl: string | null;
  backgroundItems: ImagePanelItem[];
  selectedBackgroundPath: string | null;
  onSelectBackground: (filePath: string) => void;
  backgroundLogs: string[];
  thumbnailPreviewUrl: string | null;
  thumbnailItems: ImagePanelItem[];
  selectedThumbnailPath: string | null;
  onSelectThumbnail: (filePath: string) => void;
  thumbnailLogs: string[];
  manualGenerateBoth: boolean;
  onManualGenerateBothChange: (v: boolean) => void;
  canManualGenerateBoth: boolean;
  manualIncludeThumbnail: boolean;
  onManualIncludeThumbnailChange: (v: boolean) => void;
  onRunManual: () => void;
  onRegenerateBackground: () => void;
  thumbnailActionLabel: string;
  onThumbnailAction: () => void;
  onPickThumbnailSource: () => void;
  thumbnailSourceLabel: string;
  running: boolean;
  canRun: boolean;
  canRegenerateBackground: boolean;
  canThumbnailAction: boolean;
}) {
  return (
    <div className="grid h-full min-h-0 grid-cols-2 gap-3">
      <Card className="flex min-h-0 flex-1 flex-col">
        <CardHeader>
          <div className="flex min-w-0 items-center justify-between gap-3">
            <CardTitle>Background</CardTitle>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => props.onManualGenerateBothChange(!props.manualGenerateBoth)}
                disabled={!props.canManualGenerateBoth || props.running}
              >
                {props.manualGenerateBoth ? "OK+ALT" : "OK only"}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => props.onManualIncludeThumbnailChange(!props.manualIncludeThumbnail)}
                disabled={props.running}
              >
                {props.manualIncludeThumbnail ? "BG+Thumb" : "BG only"}
              </Button>
              <Button size="sm" variant="secondary" onClick={props.onRunManual} disabled={!props.canRun || props.running}>
                <RefreshCcw className="h-4 w-4" />
                {props.running ? "Running" : "Run Manual"}
              </Button>
              <Button size="sm" variant="secondary" onClick={props.onRegenerateBackground} disabled={!props.canRegenerateBackground || props.running}>
                Regenerate
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="min-h-0 flex-1 overflow-hidden">
          <div className="flex min-h-0 flex-1 flex-col gap-2">
            <div className="text-[11px] text-slate-300">{props.contextLabel}</div>
            <div className="w-full overflow-hidden rounded-lg border border-slate-200/10 bg-slate-950/30 aspect-[16/9]">
              <div className="flex h-full w-full items-center justify-center">
                {props.backgroundPreviewUrl ? (
                  <img src={props.backgroundPreviewUrl} alt="Background" className="max-h-full max-w-full object-contain" />
                ) : (
                  <div className="text-sm text-slate-400">No background yet</div>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 overflow-x-auto rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
              {props.backgroundItems.length ? (
                props.backgroundItems.map((it) => (
                  <button
                    key={it.filePath}
                    type="button"
                    onClick={() => props.onSelectBackground(it.filePath)}
                    className={`h-12 w-20 flex-none overflow-hidden rounded border ${
                      props.selectedBackgroundPath === it.filePath ? "border-blue-500/60" : "border-slate-200/10"
                    } bg-slate-950/30`}
                    title={`${it.label}\n${it.filePath}`}
                  >
                    <img src={it.fileUrl} alt={it.label} className="h-full w-full object-cover" />
                  </button>
                ))
              ) : (
                <div className="text-[11px] text-slate-400">No images</div>
              )}
            </div>

            <div className="min-h-0 rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
              <div className="text-[11px] font-semibold text-slate-200">Log</div>
              <div className="mt-1 max-h-28 overflow-auto font-mono text-[10px] leading-4 text-slate-200">
                {props.backgroundLogs.length ? props.backgroundLogs.map((l, idx) => <div key={idx}>{l}</div>) : <div className="text-slate-400">Idle</div>}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="flex min-h-0 flex-1 flex-col">
        <CardHeader>
          <div className="flex min-w-0 items-center justify-between gap-3">
            <CardTitle>Thumbnail</CardTitle>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="primary" onClick={props.onThumbnailAction} disabled={!props.canThumbnailAction || props.running}>
                {props.thumbnailActionLabel}
              </Button>
              <Button size="sm" variant="secondary" onClick={props.onPickThumbnailSource} disabled={props.running}>
                Select Image
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="min-h-0 flex-1 overflow-hidden">
          <div className="flex min-h-0 flex-1 flex-col gap-2">
            <div className="text-[11px] text-slate-300">{props.contextLabel}</div>
            <div className="text-[11px] text-slate-400">Source: {props.thumbnailSourceLabel || "(none)"}</div>
            <div className="w-full overflow-hidden rounded-lg border border-slate-200/10 bg-slate-950/30 aspect-[16/9]">
              <div className="flex h-full w-full items-center justify-center">
                {props.thumbnailPreviewUrl ? (
                  <img src={props.thumbnailPreviewUrl} alt="Thumbnail" className="max-h-full max-w-full object-contain" />
                ) : (
                  <div className="text-sm text-slate-400">No thumbnail yet</div>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 overflow-x-auto rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
              {props.thumbnailItems.length ? (
                props.thumbnailItems.map((it) => (
                  <button
                    key={it.filePath}
                    type="button"
                    onClick={() => props.onSelectThumbnail(it.filePath)}
                    className={`h-12 w-20 flex-none overflow-hidden rounded border ${
                      props.selectedThumbnailPath === it.filePath ? "border-blue-500/60" : "border-slate-200/10"
                    } bg-slate-950/30`}
                    title={`${it.label}\n${it.filePath}`}
                  >
                    <img src={it.fileUrl} alt={it.label} className="h-full w-full object-cover" />
                  </button>
                ))
              ) : (
                <div className="text-[11px] text-slate-400">No images</div>
              )}
            </div>

            <div className="min-h-0 rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
              <div className="text-[11px] font-semibold text-slate-200">Log</div>
              <div className="mt-1 max-h-28 overflow-auto font-mono text-[10px] leading-4 text-slate-200">
                {props.thumbnailLogs.length ? props.thumbnailLogs.map((l, idx) => <div key={idx}>{l}</div>) : <div className="text-slate-400">Idle</div>}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
