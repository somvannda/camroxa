import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { RefreshCcw } from "lucide-react";
import { Input } from "@/components/ui/Input";
import type { VideoExportSettings, VideoMergeItemStatus } from "../../../shared/app-types";
import { X } from "lucide-react";

export function ThumbnailPanel(props: {
  imageUrl: string | null;
  statusText: string;
  pickInfo: { sample: string; car: string; template: string } | null;
  resolution: "1920x1080" | "1080x1920";
  onResolutionChange: (v: "1920x1080" | "1080x1920") => void;
  onRegenerate: () => void;
  onGenerateThumbnail: () => void;
  regenerating: boolean;
  thumbnailing: boolean;
  canThumbnail: boolean;
  videoMergeDirs: string[];
  videoExport: VideoExportSettings;
  onVideoExportChange: (patch: Partial<VideoExportSettings>) => void;
  onSelectVideoMergeDirs: () => void;
  onRemoveVideoMergeDir: (dir: string) => void;
  onClearVideoMergeDirs: () => void;
  onMergeVideos: () => void;
  mergeRunning: boolean;
  mergeProgress: { done: number; total: number };
  mergeRows: Array<{ directory: string; status: VideoMergeItemStatus; message: string; outputPath?: string }>;
}) {
  const aspectClass = props.resolution === "1080x1920" ? "aspect-[9/16]" : "aspect-[16/9]";
  return (
    <Card className="flex min-h-0 flex-1 flex-col">
      <CardHeader>
        <div className="flex min-w-0 items-center justify-between gap-3">
          <CardTitle>Background</CardTitle>
          <div className="flex items-center gap-2">
            <Select value={props.resolution} onChange={(e) => props.onResolutionChange(e.target.value as "1920x1080" | "1080x1920")}
              className="h-8"
            >
              <option value="1920x1080">1920×1080</option>
              <option value="1080x1920">1080×1920</option>
            </Select>
            <Button size="sm" variant="secondary" onClick={props.onRegenerate} disabled={props.regenerating}>
              <RefreshCcw className="h-4 w-4" />
              {props.regenerating ? "Regenerating" : "Regenerate"}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-auto">
        <div className="flex flex-col gap-2">
          <div className={`w-full overflow-hidden rounded-lg border border-slate-200/10 bg-slate-950/30 ${aspectClass}`}>
            <div className="flex h-full w-full items-center justify-center">
              {props.imageUrl ? (
                <img src={props.imageUrl} alt="Background" className="max-h-full max-w-full object-contain" />
              ) : (
                <div className="text-sm text-slate-400">No background yet</div>
              )}
            </div>
          </div>
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0 flex-1 truncate text-[11px] text-slate-300" title={props.statusText || ""}>
              {props.statusText}
            </div>
          <div className="flex justify-end">
            <Button
              size="sm"
              variant="primary"
              onClick={props.onGenerateThumbnail}
              disabled={!props.canThumbnail || props.thumbnailing || props.regenerating}
            >
              {props.thumbnailing ? "Generating thumbnail" : "Generate Thumbnail"}
            </Button>
          </div>
          </div>

          {props.pickInfo ? (
            <div className="rounded-lg border border-slate-200/10 bg-slate-950/20 p-2 text-[11px] text-slate-200">
              <div className="truncate" title={props.pickInfo.sample}>Sample: {props.pickInfo.sample}</div>
              <div className="truncate" title={props.pickInfo.car}>Car: {props.pickInfo.car}</div>
              <div className="truncate" title={props.pickInfo.template}>Template: {props.pickInfo.template}</div>
            </div>
          ) : null}

          <div className="rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
            <div className="text-sm font-semibold text-slate-100">Video Merge</div>
            <div className="mt-2 rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
              <div className="text-xs font-semibold text-slate-200">Export settings</div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <div className="text-[11px] text-slate-300">Resolution</div>
                  <Select
                    value={props.videoExport.resolution}
                    onChange={(e) => props.onVideoExportChange({ resolution: e.target.value as VideoExportSettings["resolution"] })}
                    className="h-8"
                  >
                    <option value="1920x1080">1920×1080</option>
                    <option value="1080x1920">1080×1920</option>
                    <option value="1280x720">1280×720</option>
                    <option value="2560x1440">2560×1440 (2K)</option>
                    <option value="3840x2160">3840×2160 (4K)</option>
                  </Select>
                </div>
                <div className="space-y-1">
                  <div className="text-[11px] text-slate-300">FPS</div>
                  <Select
                    value={String(props.videoExport.fps)}
                    onChange={(e) => props.onVideoExportChange({ fps: Number(e.target.value) as VideoExportSettings["fps"] })}
                    className="h-8"
                  >
                    <option value="24">24</option>
                    <option value="30">30</option>
                    <option value="60">60</option>
                  </Select>
                </div>
                <div className="space-y-1">
                  <div className="text-[11px] text-slate-300">Preset</div>
                  <Select
                    value={props.videoExport.preset}
                    onChange={(e) => props.onVideoExportChange({ preset: e.target.value as VideoExportSettings["preset"] })}
                    className="h-8"
                  >
                    <option value="fast">fast</option>
                    <option value="medium">medium</option>
                    <option value="slow">slow</option>
                  </Select>
                </div>
                <div className="space-y-1">
                  <div className="text-[11px] text-slate-300">Quality (CRF)</div>
                  <Input
                    value={String(props.videoExport.crf)}
                    onChange={(e) => props.onVideoExportChange({ crf: Number(e.target.value) })}
                    className="h-8"
                  />
                </div>
                <div className="space-y-1">
                  <div className="text-[11px] text-slate-300">Audio bitrate</div>
                  <Select
                    value={String(props.videoExport.audioBitrateKbps)}
                    onChange={(e) =>
                      props.onVideoExportChange({ audioBitrateKbps: Number(e.target.value) as VideoExportSettings["audioBitrateKbps"] })
                    }
                    className="h-8"
                  >
                    <option value="128">128k</option>
                    <option value="192">192k</option>
                    <option value="256">256k</option>
                  </Select>
                </div>
              </div>
            </div>

            <div className="mt-2 flex items-center justify-between gap-2">
              <div className="text-xs font-semibold text-slate-200">Selected directories</div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="secondary" onClick={props.onClearVideoMergeDirs} disabled={props.mergeRunning || !props.videoMergeDirs.length}>
                  Clear
                </Button>
              </div>
            </div>

            <div className="mt-2 max-h-32 overflow-auto rounded-lg border border-slate-200/10 bg-slate-950/20">
              {props.videoMergeDirs.length ? (
                <div className="divide-y divide-slate-200/10">
                  {props.videoMergeDirs.map((dir) => (
                    <div key={dir} className="flex items-center gap-2 px-2 py-1">
                      <div className="min-w-0 flex-1 truncate text-[11px] text-slate-200" title={dir}>
                        {dir}
                      </div>
                      <Button
                        size="sm"
                        variant="secondary"
                        className="h-7 px-2"
                        onClick={() => props.onRemoveVideoMergeDir(dir)}
                        disabled={props.mergeRunning}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="px-2 py-2 text-[11px] text-slate-400">No directories selected</div>
              )}
            </div>

            <div className="mt-2 flex items-center justify-between gap-2">
              <Button size="sm" variant="secondary" onClick={props.onSelectVideoMergeDirs} disabled={props.mergeRunning}>
                Select directories
              </Button>
              <Button
                size="sm"
                variant="primary"
                onClick={props.onMergeVideos}
                disabled={props.mergeRunning || !props.videoMergeDirs.length}
              >
                {props.mergeRunning ? "Merging..." : "Merge Videos"}
              </Button>
            </div>

            <div className="mt-3 rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
              <div className="flex items-center justify-between gap-2">
                <div className="text-[11px] text-slate-200">
                  Merged {props.mergeProgress.done} / {props.mergeProgress.total} directories
                </div>
                <div className="text-[11px] tabular-nums text-slate-400">
                  {props.mergeProgress.total
                    ? `${Math.round((props.mergeProgress.done / props.mergeProgress.total) * 100)}%`
                    : "0%"}
                </div>
              </div>
              <div className="mt-1 h-1.5 w-full rounded-full bg-slate-800/70" aria-hidden>
                <div
                  className="h-1.5 rounded-full bg-blue-500"
                  style={{
                    width: `${
                      props.mergeProgress.total ? Math.max(0, Math.min(100, (props.mergeProgress.done / props.mergeProgress.total) * 100)) : 0
                    }%`,
                  }}
                />
              </div>
              <div className="mt-2 max-h-32 overflow-auto rounded border border-slate-200/10">
                {props.mergeRows.length ? (
                  <div className="divide-y divide-slate-200/10">
                    {props.mergeRows.map((r) => (
                      <div key={r.directory} className="px-2 py-1 text-[11px] text-slate-200">
                        <div className="flex items-center justify-between gap-2">
                          <div className="min-w-0 flex-1 truncate" title={r.directory}>
                            {r.directory}
                          </div>
                          <div className="shrink-0 text-slate-400">{r.status}</div>
                        </div>
                        <div className="text-slate-300" title={r.outputPath || r.message}>
                          {r.message}
                          {r.outputPath ? ` · ${r.outputPath}` : ""}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="px-2 py-2 text-[11px] text-slate-400">No merge activity yet</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
