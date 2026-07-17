import {
  LOGO_SHAPE_OPTIONS,
  LOGO_SPIN_DIRECTION_OPTIONS,
  LOGO_MOTION_OPTIONS,
} from '@/features/video/domains/logo/logoSettings'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import type { LogoDraftSlice } from '@/features/video/workspace/templateDraftDomains'
import {
  SectionCard,
  SelectField,
  SliderField,
  ToggleField,
} from '@/features/video/workspace/inspectorFields'

type LogoInspectorProps = {
  draft: LogoDraftSlice
  onPatchDraft: (patch: Partial<LogoDraftSlice>) => void
  onApplyLogoShape: (value: string) => void
  onApplyLogoSize: (value: number) => void
  onToggleSpectrumAttachment: (checked: boolean) => void
  onSetSpectrumLogoGap: (value: number) => void
  onSelectLogo: () => void | Promise<void>
}

export function LogoInspector({
  draft,
  onPatchDraft,
  onApplyLogoShape,
  onApplyLogoSize,
  onToggleSpectrumAttachment,
  onSetSpectrumLogoGap,
  onSelectLogo,
}: LogoInspectorProps): React.JSX.Element {
  return (
    <div className="grid gap-4">
      <SectionCard title="Logo" subtitle="Shape, scale, opacity, and logo-specific audio motion from the Python video settings route.">
        <div className="grid gap-3">
          <ToggleField
            checked={draft.logoEnabled}
            label="Logo"
            onChange={(checked) => onPatchDraft({ logoEnabled: checked })}
          />
          <ToggleField
            checked={draft.logoSpinEnabled}
            label="Spin"
            onChange={(checked) => onPatchDraft({ logoSpinEnabled: checked })}
          />
        </div>
        <div className="grid gap-3">
          <SelectField
            label="Direction"
            options={LOGO_SPIN_DIRECTION_OPTIONS}
            value={draft.logoSpinDirection}
            onChange={(value) => onPatchDraft({ logoSpinDirection: value })}
          />
          <SliderField
            label={`Speed (${Math.round(draft.logoSpinSpeed)}°/s)`}
            max={720}
            min={0}
            step={10}
            value={draft.logoSpinSpeed}
            onChange={(value) => onPatchDraft({ logoSpinSpeed: value })}
          />
        </div>
        <div className="grid gap-1.5 sm:grid-cols-[96px_minmax(0,1fr)] sm:items-center">
          <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500">File</p>
          <div className="grid grid-cols-[1fr_auto] items-center gap-2">
            <Input
              className="h-9 bg-slate-950/70 text-xs"
              placeholder="C:/path/to/logo.png"
              readOnly
              value={draft.logoPath}
              onChange={() => undefined}
            />
            <Button size="sm" type="button" variant="secondary" onClick={() => void onSelectLogo()}>
              Select Logo
            </Button>
          </div>
        </div>
        <div className="grid gap-3">
          <SelectField
            label="Shape"
            options={LOGO_SHAPE_OPTIONS}
            value={draft.logoShape}
            onChange={onApplyLogoShape}
          />
          <SliderField
            label="Size"
            max={10}
            min={1}
            step={0.05}
            value={draft.logoSizeStep}
            format={(value) => `${value.toFixed(2)} => ${Math.round(value * 100)}px`}
            onChange={onApplyLogoSize}
          />
          <ToggleField
            checked={draft.spectrumAttachToLogo}
            label="Attach to Logo"
            description="Keep the spectrum ring locked outside the logo when both layers are active."
            onChange={onToggleSpectrumAttachment}
          />
          <SliderField
            label={`Spectrum Outer Gap (${draft.spectrumLogoGap.toFixed(1)}px)`}
            description="Controls the space between the logo edge and the first spectrum ring while attached."
            max={96}
            min={0}
            step={0.5}
            value={draft.spectrumLogoGap}
            onChange={onSetSpectrumLogoGap}
          />
        </div>
        <div className="grid gap-3">
          <SliderField
            label={`Opacity (${draft.logoOpacity.toFixed(2)})`}
            max={1}
            min={0}
            step={0.01}
            value={draft.logoOpacity}
            onChange={(value) => onPatchDraft({ logoOpacity: value })}
          />
          <SliderField
            label={`Audio Reactivity (${draft.logoReactivity.toFixed(2)})`}
            max={2}
            min={0}
            step={0.01}
            value={draft.logoReactivity}
            onChange={(value) => onPatchDraft({ logoReactivity: value })}
          />
          <SliderField
            label={`Reaction Smoothness (${draft.logoSmoothing.toFixed(2)})`}
            max={0.99}
            min={0}
            step={0.01}
            value={draft.logoSmoothing}
            onChange={(value) => onPatchDraft({ logoSmoothing: value })}
          />
        </div>
        <div className="grid gap-3">
          <SelectField
            label="Motion"
            options={LOGO_MOTION_OPTIONS}
            value={draft.logoMotionMode}
            onChange={(value) => onPatchDraft({ logoMotionMode: value })}
          />
          <SliderField
            label={`Zoom Strength (${draft.logoMotionZoomStrength.toFixed(2)})`}
            max={20}
            min={0}
            step={0.05}
            value={draft.logoMotionZoomStrength}
            onChange={(value) => onPatchDraft({ logoMotionZoomStrength: value })}
          />
          <SliderField
            label={`Vibrate Strength (${draft.logoMotionVibrateStrength.toFixed(2)})`}
            max={20}
            min={0}
            step={0.05}
            value={draft.logoMotionVibrateStrength}
            onChange={(value) => onPatchDraft({ logoMotionVibrateStrength: value })}
          />
          <SliderField
            label={`Motion Speed (${draft.logoMotionSpeed.toFixed(2)})`}
            max={20}
            min={0}
            step={0.05}
            value={draft.logoMotionSpeed}
            onChange={(value) => onPatchDraft({ logoMotionSpeed: value })}
          />
        </div>
      </SectionCard>
    </div>
  )
}
