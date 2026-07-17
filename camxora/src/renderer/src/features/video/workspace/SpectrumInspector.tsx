import {
  ANCHOR_OPTIONS,
} from '@/features/settings/pythonVideoSettings'
import { SPECTRUM_PRESET_OPTIONS } from '@/features/video/domains/spectrum/spectrumStyleRegistry'
import { AppSelect } from '@/shared/ui/app-select'
import { Button } from '@/shared/ui/button'
import type { SpectrumDraftSlice } from '@/features/video/workspace/templateDraftDomains'
import {
  SectionCard,
  SelectField,
  SliderField,
  ToggleField,
} from '@/features/video/workspace/inspectorFields'

const SPECTRUM_AUDIO_DIAL_MAX = 20
const FLYING_GLOW_WING_SPEED_DIAL_MAX = 100

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function toSpectrumAudioDial(value: number, min: number, max: number, dialMax = SPECTRUM_AUDIO_DIAL_MAX): number {
  if (max <= min) {
    return 0
  }
  return Math.round(((clamp(value, min, max) - min) / (max - min)) * dialMax)
}

function fromSpectrumAudioDial(dial: number, min: number, max: number, dialMax = SPECTRUM_AUDIO_DIAL_MAX): number {
  if (max <= min) {
    return min
  }
  return min + (clamp(dial, 0, dialMax) / dialMax) * (max - min)
}

type SpectrumInspectorProps = {
  draft: SpectrumDraftSlice
  onPatchDraft: (patch: Partial<SpectrumDraftSlice>) => void
  onApplyPreset: (preset: string) => void
  renderLayersCard: () => React.JSX.Element
}

export function SpectrumInspector({
  draft,
  onPatchDraft,
  onApplyPreset,
  renderLayersCard,
}: SpectrumInspectorProps): React.JSX.Element {
  return (
    <div className="grid gap-4">
      <SectionCard title="Spectrum" subtitle="One curated preset selector with distinct line-based renderer families.">
        <ToggleField
          checked={draft.spectrumEnabled}
          label="Spectrum"
          onChange={(checked) => {
            onPatchDraft({ spectrumEnabled: checked })
          }}
        />
        <div className="grid gap-1.5">
          <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500">Preset</p>
          <div className="grid gap-2">
            <AppSelect
              options={SPECTRUM_PRESET_OPTIONS}
              placeholder="Spectrum Preset"
              triggerClassName="h-9 bg-slate-950/70 text-xs"
              value={draft.style}
              onChange={(value) => onApplyPreset(String(value || 'straight-bars'))}
            />
            <p className="text-[10px] leading-4 text-slate-500">
              Selecting a preset applies its full renderer recipe immediately. Each preset keeps a clean line-bar
              foundation first, then adds its own shading, motion feel, and compositing character.
            </p>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Audio" subtitle="">
        <div className="grid gap-3">
          <SliderField
            label={`Input Gain (${toSpectrumAudioDial(draft.audioInputGain, 1, 10)})`}
            max={20}
            min={0}
            step={1}
            value={toSpectrumAudioDial(draft.audioInputGain, 1, 10)}
            onChange={(raw) => {
              onPatchDraft({ audioInputGain: fromSpectrumAudioDial(raw, 1, 10) })
            }}
          />
          <SliderField
            label={`Kick Impact (${toSpectrumAudioDial(draft.audioKickImpact, 0, 5)})`}
            max={20}
            min={0}
            step={1}
            value={toSpectrumAudioDial(draft.audioKickImpact, 0, 5)}
            onChange={(raw) => {
              onPatchDraft({ audioKickImpact: fromSpectrumAudioDial(raw, 0, 5) })
            }}
          />
          <SliderField
            label={`Bass Emphasis (${toSpectrumAudioDial(draft.audioBassEmphasis, 0.35, 4)})`}
            max={20}
            min={0}
            step={1}
            value={toSpectrumAudioDial(draft.audioBassEmphasis, 0.35, 4)}
            onChange={(raw) => {
              onPatchDraft({ audioBassEmphasis: fromSpectrumAudioDial(raw, 0.35, 4) })
            }}
          />
          <details className="group rounded-xl border border-white/10 bg-slate-950/50 px-2.5 py-2">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
              <div>
                <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400">Advanced</p>
                <p className="mt-1 text-[10px] leading-4 text-slate-500">
                  Separation, shimmer, tail, and smoothing controls.
                </p>
              </div>
              <span className="text-[10px] uppercase tracking-[0.14em] text-slate-500 transition group-open:rotate-180">
                v
              </span>
            </summary>
            <div className="mt-3 grid gap-3">
              <SliderField
                label={`Band Contrast (${toSpectrumAudioDial(draft.audioBandContrast, 0.35, 5)})`}
                max={20}
                min={0}
                step={1}
                value={toSpectrumAudioDial(draft.audioBandContrast, 0.35, 5)}
                onChange={(raw) => {
                  onPatchDraft({ audioBandContrast: fromSpectrumAudioDial(raw, 0.35, 5) })
                }}
              />
              <SliderField
                label={`Transient Focus (${toSpectrumAudioDial(draft.audioTransientFocus, 0.35, 4)})`}
                max={20}
                min={0}
                step={1}
                value={toSpectrumAudioDial(draft.audioTransientFocus, 0.35, 4)}
                onChange={(raw) => {
                  onPatchDraft({ audioTransientFocus: fromSpectrumAudioDial(raw, 0.35, 4) })
                }}
              />
              <SliderField
                label={`Treble Shimmer (${toSpectrumAudioDial(draft.audioTrebleShimmer, 0.35, 4)})`}
                max={20}
                min={0}
                step={1}
                value={toSpectrumAudioDial(draft.audioTrebleShimmer, 0.35, 4)}
                onChange={(raw) => {
                  onPatchDraft({ audioTrebleShimmer: fromSpectrumAudioDial(raw, 0.35, 4) })
                }}
              />
              <SliderField
                label={`Peak Hold Blend (${toSpectrumAudioDial(draft.audioPeakHoldBlend, 0, 1)})`}
                max={20}
                min={0}
                step={1}
                value={toSpectrumAudioDial(draft.audioPeakHoldBlend, 0, 1)}
                onChange={(raw) => {
                  onPatchDraft({ audioPeakHoldBlend: fromSpectrumAudioDial(raw, 0, 1) })
                }}
              />
              <SliderField
                label={`Motion Smoothing (${toSpectrumAudioDial(draft.audioMotionSmoothing, 0, 0.99)})`}
                max={20}
                min={0}
                step={1}
                value={toSpectrumAudioDial(draft.audioMotionSmoothing, 0, 0.99)}
                onChange={(raw) => {
                  onPatchDraft({ audioMotionSmoothing: fromSpectrumAudioDial(raw, 0, 0.99) })
                }}
              />
              {draft.style === 'flying-glow' ? (
                <>
                  <SliderField
                    label={`Flying Glow Wing Speed (${toSpectrumAudioDial(draft.flyingGlowWingMotionSpeed, 0.5, 20, FLYING_GLOW_WING_SPEED_DIAL_MAX)})`}
                    max={FLYING_GLOW_WING_SPEED_DIAL_MAX}
                    min={0}
                    step={1}
                    value={toSpectrumAudioDial(draft.flyingGlowWingMotionSpeed, 0.5, 20, FLYING_GLOW_WING_SPEED_DIAL_MAX)}
                    onChange={(raw) => {
                      onPatchDraft({
                        flyingGlowWingMotionSpeed: fromSpectrumAudioDial(
                          raw,
                          0.5,
                          20,
                          FLYING_GLOW_WING_SPEED_DIAL_MAX,
                        ),
                      })
                    }}
                  />
                  <SliderField
                    label={`Flying Glow Wing Release (${toSpectrumAudioDial(draft.flyingGlowWingRelease, 0, 4)})`}
                    max={20}
                    min={0}
                    step={1}
                    value={toSpectrumAudioDial(draft.flyingGlowWingRelease, 0, 4)}
                    onChange={(raw) => {
                      onPatchDraft({ flyingGlowWingRelease: fromSpectrumAudioDial(raw, 0, 4) })
                    }}
                  />
                </>
              ) : null}
            </div>
          </details>
        </div>
      </SectionCard>

      <SectionCard title="Positioning" subtitle="Move the spectrum and logo anchor around the preview.">
        <div className="flex items-center gap-2">
          <p className="text-xs font-medium text-slate-300">Spectrum Position</p>
          <div className="ml-auto">
            <Button
              size="sm"
              type="button"
              variant="secondary"
              onClick={() => {
                onPatchDraft({ anchor: 'center', positionX: 0, positionY: 0 })
              }}
            >
              Reset Center
            </Button>
          </div>
        </div>
        <SelectField
          label="Anchor"
          options={ANCHOR_OPTIONS}
          value={draft.anchor}
          onChange={(value) => {
            onPatchDraft({ anchor: value })
          }}
        />
        <div className="grid gap-3">
          <SliderField
            label={`X Offset (${Math.round(draft.positionX)})`}
            max={1000}
            min={-1000}
            step={1}
            value={draft.positionX}
            onChange={(value) => {
              onPatchDraft({ positionX: value })
            }}
          />
          <SliderField
            label={`Y Offset (${Math.round(draft.positionY)})`}
            max={1000}
            min={-1000}
            step={1}
            value={draft.positionY}
            onChange={(value) => {
              onPatchDraft({ positionY: value })
            }}
          />
        </div>
      </SectionCard>

      {renderLayersCard()}
    </div>
  )
}
