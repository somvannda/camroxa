import {
  buildParticleMotionPresetPatch,
  PARTICLE_AUDIO_MOTION_MODE_OPTIONS,
  PARTICLE_MOTION_PRESET_FIELD_KEYS,
  PARTICLE_MOTION_PRESETS,
  PARTICLE_SPAWN_AREA_OPTIONS,
  PARTICLE_SPAWN_MODE_OPTIONS,
  PARTICLE_SPAWN_TRIGGER_OPTIONS,
  PARTICLE_STYLE_OPTIONS,
  PARTICLE_VARIANT_OPTIONS,
} from '@/features/video/domains/particles/particleSettings'
import type { ParticlesDraftSlice } from '@/features/video/workspace/templateDraftDomains'
import {
  ColorField,
  SectionCard,
  SelectField,
  ToggleField,
} from '@/features/video/workspace/inspectorFields'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'

type ParticlesInspectorProps = {
  draft: ParticlesDraftSlice
  onPatchDraft: (patch: Partial<ParticlesDraftSlice>) => void
}

function clampValue(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function quantizeValue(value: number, min: number, step: number): number {
  const normalizedStep = step > 0 ? step : 1
  const precision = normalizedStep < 1 ? String(normalizedStep).split('.')[1]?.length ?? 2 : 0
  const snapped = min + Math.round((value - min) / normalizedStep) * normalizedStep
  return Number(snapped.toFixed(precision))
}

function ParticleSliderField(props: {
  label: string
  value: number
  min: number
  max: number
  step: number
  decimals?: number
  onChange: (nextValue: number) => void
}): React.JSX.Element {
  const decimals = props.decimals ?? (props.step < 1 ? 2 : 0)
  const commitValue = (nextValue: number) => {
    props.onChange(quantizeValue(clampValue(nextValue, props.min, props.max), props.min, props.step))
  }

  return (
    <div className="grid gap-1.5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500">{props.label}</p>
        <div className="flex items-center gap-1.5">
          <Button
            className="h-7 w-7 px-0 text-xs"
            size="sm"
            type="button"
            variant="secondary"
            onClick={() => commitValue(props.value - props.step)}
          >
            -
          </Button>
          <Input
            className="h-7 w-20 bg-slate-950/70 px-2 text-right text-xs tabular-nums"
            step={props.step}
            type="number"
            value={props.value.toFixed(decimals)}
            onChange={(event) => {
              const nextValue = Number(event.target.value)
              if (!Number.isFinite(nextValue)) {
                return
              }
              commitValue(nextValue)
            }}
          />
          <Button
            className="h-7 w-7 px-0 text-xs"
            size="sm"
            type="button"
            variant="secondary"
            onClick={() => commitValue(props.value + props.step)}
          >
            +
          </Button>
        </div>
      </div>
      <input
        aria-label={props.label}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-white/10 accent-fuchsia-500"
        max={props.max}
        min={props.min}
        step={props.step}
        type="range"
        value={props.value}
        onChange={(event) => commitValue(Number(event.target.value))}
      />
    </div>
  )
}

function isParticlePresetActive(draft: ParticlesDraftSlice, presetId: (typeof PARTICLE_MOTION_PRESETS)[number]['value']): boolean {
  const presetPatch = buildParticleMotionPresetPatch(presetId)
  return PARTICLE_MOTION_PRESET_FIELD_KEYS.every((fieldKey) => draft[fieldKey] === presetPatch[fieldKey])
}

export function ParticlesInspector({
  draft,
  onPatchDraft,
}: ParticlesInspectorProps): React.JSX.Element {
  return (
    <div className="grid gap-4">
      <SectionCard title="Particles" subtitle="Control density, motion, and visual behavior for the particle system.">
        <ToggleField
          checked={draft.particlesEnabled}
          label="Particles"
          onChange={(checked) => onPatchDraft({ particlesEnabled: checked })}
        />
        <div className="grid gap-1.5">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Preset Looks</p>
            <p className="text-[10px] leading-4 text-slate-500">Quick starting looks</p>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {PARTICLE_MOTION_PRESETS.map((preset) => {
              const selected = isParticlePresetActive(draft, preset.value)
              return (
                <Button
                  key={preset.value}
                  className={cn(
                    'h-9 justify-start px-3 text-left text-[11px] font-semibold uppercase tracking-[0.12em]',
                    selected &&
                      'border-fuchsia-400/70 bg-fuchsia-500/18 text-white shadow-[0_0_0_1px_rgba(217,70,239,0.28)] hover:bg-fuchsia-500/18',
                  )}
                  size="sm"
                  type="button"
                  variant="secondary"
                  onClick={() => onPatchDraft(buildParticleMotionPresetPatch(preset.value))}
                >
                  {preset.label}
                </Button>
              )
            })}
          </div>
          <p className="text-[10px] leading-4 text-slate-500">
            Presets apply a full particle recipe. Use the video template save button to keep the current particle settings.
          </p>
        </div>
        <div className="grid gap-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Main</p>
          <SelectField
            label="Variant"
            options={PARTICLE_VARIANT_OPTIONS}
            value={draft.particlesVariant}
            onChange={(value) => onPatchDraft({ particlesVariant: value })}
          />
          <SelectField
            label="Style"
            options={PARTICLE_STYLE_OPTIONS}
            value={draft.particlesStyle}
            onChange={(value) => onPatchDraft({ particlesStyle: value })}
          />
          <SelectField
            label="Spawn Area"
            options={PARTICLE_SPAWN_AREA_OPTIONS}
            value={draft.particlesSpawnArea}
            onChange={(value) => onPatchDraft({ particlesSpawnArea: value })}
          />
          <SelectField
            label="Spawn Mode"
            options={PARTICLE_SPAWN_MODE_OPTIONS}
            value={draft.particlesSpawnMode}
            onChange={(value) => onPatchDraft({ particlesSpawnMode: value })}
          />
          <ParticleSliderField
            decimals={2}
            label="Move Speed"
            max={20}
            min={0.2}
            step={0.1}
            value={draft.particlesSpeed}
            onChange={(value) => onPatchDraft({ particlesSpeed: value })}
          />
          <ParticleSliderField
            decimals={2}
            label="Lifetime"
            max={10}
            min={0.05}
            step={0.05}
            value={draft.particlesLifetimeSec}
            onChange={(value) => onPatchDraft({ particlesLifetimeSec: value })}
          />
          <ParticleSliderField
            decimals={2}
            label="Particle Size"
            max={20}
            min={1}
            step={0.1}
            value={draft.particlesSize}
            onChange={(value) => onPatchDraft({ particlesSize: value })}
          />
          <ParticleSliderField
            decimals={2}
            label="Opacity"
            max={1}
            min={0}
            step={0.01}
            value={draft.particlesOpacity}
            onChange={(value) => onPatchDraft({ particlesOpacity: value })}
          />
          <ParticleSliderField
            decimals={2}
            label="Audio Reactivity"
            max={0.5}
            min={0.1}
            step={0.01}
            value={draft.particlesReactivity}
            onChange={(value) => onPatchDraft({ particlesReactivity: value })}
          />
          <SelectField
            label="Audio Motion"
            options={PARTICLE_AUDIO_MOTION_MODE_OPTIONS}
            value={draft.particlesAudioMotionMode}
            onChange={(value) => onPatchDraft({ particlesAudioMotionMode: value })}
          />
          {(draft.particlesAudioMotionMode === 'travel' || draft.particlesAudioMotionMode === 'both') && (
            <ParticleSliderField
              decimals={2}
              label="Audio Travel Boost"
              max={4}
              min={0}
              step={0.05}
              value={draft.particlesAudioTravelBoost}
              onChange={(value) => onPatchDraft({ particlesAudioTravelBoost: value })}
            />
          )}
          <ColorField
            label="Color"
            value={draft.particlesColor}
            onChange={(value) => onPatchDraft({ particlesColor: value })}
          />
          <ColorField
            label="React Color"
            value={draft.particlesReactColor}
            onChange={(value) => onPatchDraft({ particlesReactColor: value })}
          />
          <ParticleSliderField
            decimals={2}
            label="React Strength"
            max={1}
            min={0}
            step={0.01}
            value={draft.particlesReactStrength}
            onChange={(value) => onPatchDraft({ particlesReactStrength: value })}
          />

          <div className="border-t border-white/10 pt-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Advanced</p>
          </div>
          <ParticleSliderField
            label="Max Count"
            max={2000}
            min={200}
            step={25}
            value={draft.particlesMaxCount}
            onChange={(value) => onPatchDraft({ particlesMaxCount: value })}
          />
          <ParticleSliderField
            label="Birth Rate"
            max={1000}
            min={100}
            step={25}
            value={draft.particlesSpawnRate}
            onChange={(value) => onPatchDraft({ particlesSpawnRate: value })}
          />
          <ParticleSliderField
            decimals={2}
            label="Reaction Smoothness"
            max={0.99}
            min={0}
            step={0.01}
            value={draft.particlesSmoothing}
            onChange={(value) => onPatchDraft({ particlesSmoothing: value })}
          />
          <SelectField
            label="Spawn Trigger"
            options={PARTICLE_SPAWN_TRIGGER_OPTIONS}
            value={draft.particlesSpawnTrigger}
            onChange={(value) => onPatchDraft({ particlesSpawnTrigger: value })}
          />
          <ParticleSliderField
            decimals={2}
            label="Spawn Threshold"
            max={1}
            min={0}
            step={0.01}
            value={draft.particlesSpawnThreshold}
            onChange={(value) => onPatchDraft({ particlesSpawnThreshold: value })}
          />
          <ParticleSliderField
            decimals={2}
            label="Size Variance"
            max={1}
            min={0}
            step={0.01}
            value={draft.particlesSizeJitter}
            onChange={(value) => onPatchDraft({ particlesSizeJitter: value })}
          />
          <ParticleSliderField
            decimals={2}
            label="Drift"
            max={1}
            min={0}
            step={0.01}
            value={draft.particlesDrift}
            onChange={(value) => onPatchDraft({ particlesDrift: value })}
          />
          <ParticleSliderField
            decimals={2}
            label="Swirl"
            max={1}
            min={0}
            step={0.01}
            value={draft.particlesSwirl}
            onChange={(value) => onPatchDraft({ particlesSwirl: value })}
          />
        </div>
      </SectionCard>
    </div>
  )
}
