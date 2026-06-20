import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Switch } from "@/components/ui/Switch";
import { Slider } from "@/components/ui/Slider";

export function VideoParticlesPanel(props: {
  enabled: boolean;
  maxCount: number;
  spawnRate: number;
  lifetimeSec: number;
  size: number;
  opacity: number;
  color: string;
  speed: number;
  saveLabel: string;
  onChangeEnabled: (v: boolean) => void;
  onChangeMaxCount: (v: number) => void;
  onChangeSpawnRate: (v: number) => void;
  onChangeLifetimeSec: (v: number) => void;
  onChangeSize: (v: number) => void;
  onChangeOpacity: (v: number) => void;
  onChangeColor: (v: string) => void;
  onChangeSpeed: (v: number) => void;
  onSave: () => void;
}) {
  return (
    <Card className="flex min-h-0 flex-1 flex-col">
      <CardHeader>
        <CardTitle>Particles</CardTitle>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-auto">
        <div className="rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-slate-100">Particle Engine</div>
            <Switch checked={props.enabled} onCheckedChange={props.onChangeEnabled} />
          </div>

          <div className="mt-3 grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <div className="text-[11px] text-slate-300">Max count: {props.maxCount}</div>
              <Slider value={props.maxCount} min={0} max={5000} step={10} onValueChange={props.onChangeMaxCount} />
            </div>
            <div className="space-y-1">
              <div className="text-[11px] text-slate-300">Spawn rate: {Math.round(props.spawnRate)}</div>
              <Slider value={props.spawnRate} min={0} max={500} step={1} onValueChange={props.onChangeSpawnRate} />
            </div>
            <div className="space-y-1">
              <div className="text-[11px] text-slate-300">Lifetime: {props.lifetimeSec.toFixed(1)}s</div>
              <Slider value={Math.round(props.lifetimeSec * 10)} min={1} max={100} step={1} onValueChange={(v) => props.onChangeLifetimeSec(v / 10)} />
            </div>
            <div className="space-y-1">
              <div className="text-[11px] text-slate-300">Speed: {Math.round(props.speed)}</div>
              <Slider value={props.speed} min={0} max={500} step={1} onValueChange={props.onChangeSpeed} />
            </div>
            <div className="space-y-1">
              <div className="text-[11px] text-slate-300">Size: {props.size.toFixed(1)}</div>
              <Slider value={Math.round(props.size * 10)} min={1} max={100} step={1} onValueChange={(v) => props.onChangeSize(v / 10)} />
            </div>
            <div className="space-y-1">
              <div className="text-[11px] text-slate-300">Opacity: {props.opacity.toFixed(2)}</div>
              <Slider value={Math.round(props.opacity * 100)} min={0} max={100} step={1} onValueChange={(v) => props.onChangeOpacity(v / 100)} />
            </div>
            <div className="space-y-1">
              <div className="text-[11px] text-slate-300">Color</div>
              <div className="flex items-center gap-2">
                <input type="color" value={props.color} onChange={(e) => props.onChangeColor(e.target.value)} className="h-8 w-10 rounded border border-slate-200/10 bg-transparent" />
                <div className="text-[11px] text-slate-400">{props.color}</div>
              </div>
            </div>
          </div>

          <div className="mt-3 flex justify-end">
            <Button size="sm" variant="primary" onClick={props.onSave} disabled={!props.saveLabel.trim()}>
              Save
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
