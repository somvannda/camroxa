import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";

export function VideoRenderPanel(props: {
  mode: "manual" | "auto";
  mp3Path: string;
  templatePath: string;
  templates: Array<{ label: string; path: string; source: "builtin" | "user" }>;
  backgroundPath: string;
  outputDir: string;
  running: boolean;
  message: string;
  progress: number | null;
  outputPath: string | null;
  onChangeMode: (v: "manual" | "auto") => void;
  onChangeMp3Path: (v: string) => void;
  onPickMp3Path: () => void;
  onChangeTemplatePath: (v: string) => void;
  onReloadTemplates: () => void;
  onChangeBackgroundPath: (v: string) => void;
  onPickBackgroundPath: () => void;
  onChangeOutputDir: (v: string) => void;
  onPickOutputDir: () => void;
  onStart: () => void;
  onShowOutput: () => void;
}) {
  const pct = typeof props.progress === "number" ? Math.max(0, Math.min(1, props.progress)) : null;

  return (
    <Card className="flex min-h-0 flex-1 flex-col">
      <CardHeader>
        <div className="flex min-w-0 items-center justify-between gap-3">
          <CardTitle>Video</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-auto">
        <div className="rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
          <div className="text-sm font-semibold text-slate-100">Phase 1 Renderer</div>

          <div className="mt-2 grid grid-cols-1 gap-2">
            <div className="space-y-1">
              <div className="text-[11px] text-slate-300">Mode</div>
              <div className="flex items-center gap-2">
                <Select
                  value={props.mode}
                  onChange={(e) => props.onChangeMode(e.target.value === "auto" ? "auto" : "manual")}
                  className="h-8 flex-1"
                >
                  <option value="manual">Manual (Pick)</option>
                  <option value="auto">Auto (Latest batch)</option>
                </Select>
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-[11px] text-slate-300">Paths</div>
              <div className="text-[11px] text-slate-500">
                FFmpeg and Python are read from Settings → Paths.
              </div>
            </div>

            {props.mode === "manual" ? (
              <>
                <div className="space-y-1">
                  <div className="text-[11px] text-slate-300">MP3 file</div>
                  <div className="flex items-center gap-2">
                    <Input value={props.mp3Path} onChange={(e) => props.onChangeMp3Path(e.target.value)} className="h-8" />
                    <Button size="sm" variant="secondary" onClick={props.onPickMp3Path} disabled={props.running}>
                      Pick
                    </Button>
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="text-[11px] text-slate-300">Background image</div>
                  <div className="flex items-center gap-2">
                    <Input value={props.backgroundPath} onChange={(e) => props.onChangeBackgroundPath(e.target.value)} className="h-8" />
                    <Button size="sm" variant="secondary" onClick={props.onPickBackgroundPath} disabled={props.running}>
                      Pick
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <div className="space-y-1">
                <div className="text-[11px] text-slate-300">Auto source</div>
                <div className="text-[11px] text-slate-500">
                  Renders the latest batch and uses each batch folder’s background.png. Outputs to &lt;runDir&gt;\video\.
                </div>
              </div>
            )}

            <div className="space-y-1">
              <div className="text-[11px] text-slate-300">Template (optional)</div>
              <div className="grid grid-cols-1 gap-2">
                <div className="flex items-center gap-2">
                  <Select
                    value={props.templatePath || ""}
                    onChange={(e) => props.onChangeTemplatePath(e.target.value)}
                    className="h-8 flex-1"
                  >
                    <option value="">None</option>
                    {props.templates.map((t) => (
                      <option key={t.path} value={t.path}>
                        {t.label} {t.source === "user" ? "(User)" : ""}
                      </option>
                    ))}
                  </Select>
                  <Button size="sm" variant="secondary" onClick={props.onReloadTemplates} disabled={props.running}>
                    Reload
                  </Button>
                </div>
              </div>
            </div>

            {props.mode === "manual" ? (
              <div className="space-y-1">
                <div className="text-[11px] text-slate-300">Output directory</div>
                <div className="flex items-center gap-2">
                  <Input value={props.outputDir} onChange={(e) => props.onChangeOutputDir(e.target.value)} className="h-8" />
                  <Button size="sm" variant="secondary" onClick={props.onPickOutputDir} disabled={props.running}>
                    Pick
                  </Button>
                </div>
              </div>
            ) : null}
          </div>

          <div className="mt-2 flex items-center justify-between gap-2">
            <Button
              size="sm"
              variant="primary"
              onClick={props.onStart}
              disabled={props.running || (props.mode === "manual" && (!props.mp3Path || !props.backgroundPath || !props.outputDir))}
            >
              {props.running ? "Rendering..." : props.mode === "manual" ? "Render MP4" : "Render latest batch"}
            </Button>
            <Button size="sm" variant="secondary" onClick={props.onShowOutput} disabled={!props.outputPath}>
              Show output
            </Button>
          </div>

          <div className="mt-3 rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
            <div className="flex items-center justify-between gap-2">
              <div className="text-[11px] text-slate-200">{props.message || "Ready"}</div>
              <div className="text-[11px] tabular-nums text-slate-400">{pct === null ? "" : `${Math.round(pct * 100)}%`}</div>
            </div>
            <div className="mt-1 h-1.5 w-full rounded-full bg-slate-800/70" aria-hidden>
              <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${pct === null ? 0 : pct * 100}%` }} />
            </div>
            {props.outputPath ? (
              <div className="mt-2 truncate text-[11px] text-slate-500" title={props.outputPath}>
                {props.outputPath}
              </div>
            ) : null}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
