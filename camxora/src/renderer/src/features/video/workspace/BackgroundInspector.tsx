import { Button } from '@/shared/ui/button'
import {
  BACKGROUND_FIT_OPTIONS,
  BACKGROUND_MOTION_OPTIONS,
} from '@/features/video/domains/background/backgroundSettings'
import type { BackgroundDraftSlice } from '@/features/video/workspace/templateDraftDomains'
import {
  ColorField,
  SectionCard,
  SelectField,
  SliderField,
  ToggleField,
} from '@/features/video/workspace/inspectorFields'

type BackgroundInspectorProps = {
  draft: BackgroundDraftSlice
  onPatchDraft: (patch: Partial<BackgroundDraftSlice>) => void
  onResetTransform: () => void
}

export function BackgroundInspector({
  draft,
  onPatchDraft,
  onResetTransform,
}: BackgroundInspectorProps): React.JSX.Element {
  return (
    <div className="grid gap-4">
      <SectionCard title="Background" subtitle="Reactive image treatment for the current background.">
        <ToggleField
          checked={draft.backgroundEnabled}
          label="Background Image"
          onChange={(checked) => onPatchDraft({ backgroundEnabled: checked })}
        />
        {draft.backgroundEnabled ? (
          <>
            <SelectField
              label="Fit"
              options={BACKGROUND_FIT_OPTIONS}
              value={draft.backgroundFitMode}
              onChange={(value) => onPatchDraft({ backgroundFitMode: value })}
            />
            <SliderField
              label={`Scale (${Math.round(draft.backgroundUserScale * 100)}%)`}
              max={4}
              min={0.1}
              step={0.05}
              value={draft.backgroundUserScale}
              onChange={(value) => onPatchDraft({ backgroundUserScale: value })}
            />
            <div className="flex items-center justify-end">
              <Button size="sm" type="button" variant="secondary" onClick={onResetTransform}>
                Reset transform
              </Button>
            </div>
            <SliderField
              label={`Brightness (${draft.backgroundBrightness.toFixed(2)})`}
              max={2}
              min={0}
              step={0.01}
              value={draft.backgroundBrightness}
              onChange={(value) => onPatchDraft({ backgroundBrightness: value })}
            />
            <SliderField
              label={`Audio Reactivity (${draft.backgroundReactivity.toFixed(2)})`}
              max={20}
              min={0}
              step={0.05}
              value={draft.backgroundReactivity}
              onChange={(value) => onPatchDraft({ backgroundReactivity: value })}
            />
            <SliderField
              label={`Reaction Smoothness (${draft.backgroundSmoothing.toFixed(2)})`}
              max={0.99}
              min={0}
              step={0.01}
              value={draft.backgroundSmoothing}
              onChange={(value) => onPatchDraft({ backgroundSmoothing: value })}
            />
            <SelectField
              label="Motion"
              options={BACKGROUND_MOTION_OPTIONS}
              value={draft.backgroundMotionMode}
              onChange={(value) => onPatchDraft({ backgroundMotionMode: value })}
            />
            <SliderField
              label={`Zoom Strength (${draft.backgroundMotionZoomStrength.toFixed(2)})`}
              max={20}
              min={0}
              step={0.05}
              value={draft.backgroundMotionZoomStrength}
              onChange={(value) => onPatchDraft({ backgroundMotionZoomStrength: value })}
            />
            <SliderField
              label={`Vibrate Strength (${draft.backgroundMotionVibrateStrength.toFixed(2)})`}
              max={20}
              min={0}
              step={0.05}
              value={draft.backgroundMotionVibrateStrength}
              onChange={(value) => onPatchDraft({ backgroundMotionVibrateStrength: value })}
            />
            <SliderField
              label={`Motion Speed (${draft.backgroundMotionSpeed.toFixed(2)})`}
              max={20}
              min={0}
              step={0.05}
              value={draft.backgroundMotionSpeed}
              onChange={(value) => onPatchDraft({ backgroundMotionSpeed: value })}
            />
          </>
        ) : null}
      </SectionCard>

      <SectionCard title="Corner Effects" subtitle="Add subtle vignette or smoky corners for a more cinematic frame.">
        <div className="grid gap-3">
          <div className="grid gap-3">
            <ToggleField
              checked={draft.vignetteEnabled}
              label="Vignette"
              onChange={(checked) => onPatchDraft({ vignetteEnabled: checked })}
            />
            <SliderField
              label="Strength"
              max={1}
              min={0}
              step={0.01}
              value={draft.vignetteStrength}
              onChange={(value) => onPatchDraft({ vignetteStrength: value })}
            />
            <SliderField
              label="Feather"
              max={1}
              min={0}
              step={0.01}
              value={draft.vignetteFeather}
              onChange={(value) => onPatchDraft({ vignetteFeather: value })}
            />
            <SliderField
              label="Opacity"
              max={1}
              min={0}
              step={0.01}
              value={draft.vignetteOpacity}
              onChange={(value) => onPatchDraft({ vignetteOpacity: value })}
            />
            <ColorField
              label="Color"
              value={draft.vignetteColor}
              onChange={(value) => onPatchDraft({ vignetteColor: value })}
            />
          </div>
          <div className="grid gap-3">
            <ToggleField
              checked={draft.smokeEnabled}
              label="Smoke"
              onChange={(checked) => onPatchDraft({ smokeEnabled: checked })}
            />
            <SliderField
              label="Strength"
              max={1}
              min={0}
              step={0.01}
              value={draft.smokeStrength}
              onChange={(value) => onPatchDraft({ smokeStrength: value })}
            />
            <SliderField
              label="Blur"
              max={1}
              min={0}
              step={0.01}
              value={draft.smokeBlur}
              onChange={(value) => onPatchDraft({ smokeBlur: value })}
            />
            <SliderField
              label="Noise"
              max={1}
              min={0}
              step={0.01}
              value={draft.smokeNoise}
              onChange={(value) => onPatchDraft({ smokeNoise: value })}
            />
            <SliderField
              label="Motion Speed"
              max={2}
              min={0}
              step={0.01}
              value={draft.smokeSpeed}
              onChange={(value) => onPatchDraft({ smokeSpeed: value })}
            />
            <SliderField
              label="Opacity"
              max={1}
              min={0}
              step={0.01}
              value={draft.smokeOpacity}
              onChange={(value) => onPatchDraft({ smokeOpacity: value })}
            />
            <ColorField
              label="Color"
              value={draft.smokeColor}
              onChange={(value) => onPatchDraft({ smokeColor: value })}
            />
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
