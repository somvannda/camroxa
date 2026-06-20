import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Switch } from "@/components/ui/Switch";
import { Slider } from "@/components/ui/Slider";
import { Button } from "@/components/ui/Button";

export function VideoEffectsPanel(props: {
  bloomEnabled: boolean;
  bloomStrength: number;
  bloomBlurRadius: number;
  bloomThreshold: number;
  bloomOpacity: number;
  rgbEnabled: boolean;
  rgbOpacity: number;
  shakeEnabled: boolean;
  shakeIntensity: number;
  shakeSmoothing: number;
  saveLabel: string;
  onChangeBloomEnabled: (v: boolean) => void;
  onChangeBloomStrength: (v: number) => void;
  onChangeBloomBlurRadius: (v: number) => void;
  onChangeBloomThreshold: (v: number) => void;
  onChangeBloomOpacity: (v: number) => void;
  onChangeRgbEnabled: (v: boolean) => void;
  onChangeRgbOpacity: (v: number) => void;
  onChangeShakeEnabled: (v: boolean) => void;
  onChangeShakeIntensity: (v: number) => void;
  onChangeShakeSmoothing: (v: number) => void;
  onSave: () => void;
}) {
  return (
    <Card className="flex min-h-0 flex-1 flex-col">
      <CardHeader>
        <CardTitle>Effects</CardTitle>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-auto">
        <div className="rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
          <div className="text-sm font-semibold text-slate-100">Post Processing</div>

          <div className="mt-3 rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs font-semibold text-slate-200">Bloom</div>
              <Switch checked={props.bloomEnabled} onCheckedChange={props.onChangeBloomEnabled} />
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <div className="text-[11px] text-slate-300">Strength: {props.bloomStrength.toFixed(2)}</div>
                <Slider value={Math.round(props.bloomStrength * 100)} min={0} max={300} step={1} onValueChange={(v) => props.onChangeBloomStrength(v / 100)} />
              </div>
              <div className="space-y-1">
                <div className="text-[11px] text-slate-300">Blur radius: {props.bloomBlurRadius}</div>
                <Slider value={props.bloomBlurRadius} min={1} max={61} step={2} onValueChange={props.onChangeBloomBlurRadius} />
              </div>
              <div className="space-y-1">
                <div className="text-[11px] text-slate-300">Threshold: {props.bloomThreshold.toFixed(2)}</div>
                <Slider value={Math.round(props.bloomThreshold * 100)} min={0} max={100} step={1} onValueChange={(v) => props.onChangeBloomThreshold(v / 100)} />
              </div>
              <div className="space-y-1">
                <div className="text-[11px] text-slate-300">Opacity: {props.bloomOpacity.toFixed(2)}</div>
                <Slider value={Math.round(props.bloomOpacity * 100)} min={0} max={100} step={1} onValueChange={(v) => props.onChangeBloomOpacity(v / 100)} />
              </div>
            </div>
          </div>

          <div className="mt-3 rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs font-semibold text-slate-200">RGB Split</div>
              <Switch checked={props.rgbEnabled} onCheckedChange={props.onChangeRgbEnabled} />
            </div>
            <div className="mt-2">
              <div className="text-[11px] text-slate-300">Opacity: {props.rgbOpacity.toFixed(2)}</div>
              <Slider value={Math.round(props.rgbOpacity * 100)} min={0} max={100} step={1} onValueChange={(v) => props.onChangeRgbOpacity(v / 100)} />
            </div>
          </div>

          <div className="mt-3 rounded-lg border border-slate-200/10 bg-slate-950/20 p-2">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs font-semibold text-slate-200">Camera Shake</div>
              <Switch checked={props.shakeEnabled} onCheckedChange={props.onChangeShakeEnabled} />
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <div className="text-[11px] text-slate-300">Intensity: {props.shakeIntensity.toFixed(1)}</div>
                <Slider value={Math.round(props.shakeIntensity * 10)} min={0} max={300} step={1} onValueChange={(v) => props.onChangeShakeIntensity(v / 10)} />
              </div>
              <div className="space-y-1">
                <div className="text-[11px] text-slate-300">Smoothing: {props.shakeSmoothing.toFixed(2)}</div>
                <Slider value={Math.round(props.shakeSmoothing * 100)} min={0} max={99} step={1} onValueChange={(v) => props.onChangeShakeSmoothing(v / 100)} />
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

