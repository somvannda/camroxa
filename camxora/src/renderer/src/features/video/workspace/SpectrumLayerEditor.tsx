import { useId } from 'react'

import { Button } from '@/shared/ui/button'
import { AppSelect } from '@/shared/ui/app-select'
import { InlineToggle } from '@/shared/ui/inline-toggle'
import { Input } from '@/shared/ui/input'
import {
  buildSpectrumGradientPresetValue,
  extractSpectrumLayerColorModel,
  getSpectrumLayerColorFallback,
  normalizeSpectrumGradientColors,
  SPECTRUM_GRADIENT_PRESET_OPTIONS,
} from '@/features/video/domains/spectrum/spectrumColorEngine'
import { tryParseColorToNormalizedRgb } from '@/features/video/preview/previewUtils'
import {
  SectionCard,
  SelectField,
  SliderField,
} from '@/features/video/workspace/inspectorFields'
import type { SpectrumDraftSlice } from '@/features/video/workspace/templateDraftDomains'

const MAX_GRADIENT_COLOR_STOPS = 5

function toHexChannel(value: number): string {
  const channel = Math.round(Math.max(0, Math.min(1, value)) * 255)
  return channel.toString(16).padStart(2, '0')
}

function toPickerColorValue(value: string, fallback = '#ffffff'): string {
  const parsed =
    tryParseColorToNormalizedRgb(value) ??
    tryParseColorToNormalizedRgb(fallback)

  if (!parsed) {
    return '#ffffff'
  }

  return `#${toHexChannel(parsed.red)}${toHexChannel(parsed.green)}${toHexChannel(parsed.blue)}`
}

function TextField(props: {
  label: string
  value: string
  placeholder?: string
  onChange: (nextValue: string) => void
}): React.JSX.Element {
  const fieldId = useId()

  return (
    <div className="grid min-w-0 gap-1.5">
      <label className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500" htmlFor={fieldId}>
        {props.label}
      </label>
      <Input
        className="h-9 min-w-0 bg-slate-950/70 text-xs"
        id={fieldId}
        placeholder={props.placeholder}
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
      />
    </div>
  )
}

function ColorPickField(props: {
  label: string
  value: string
  disabled?: boolean
  onChange: (nextValue: string) => void
  onChangeCommitted?: (nextValue: string) => void
}): React.JSX.Element {
  const inputId = useId()
  const pickerValue = toPickerColorValue(props.value)
  const handleCommittedChange = (value: string) => {
    props.onChangeCommitted?.(value)
  }

  return (
    <div className="grid min-w-0 gap-1.5">
      <label className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500" htmlFor={inputId}>
        {props.label}
      </label>
      <div className="flex min-w-0 items-center gap-3">
        <div className="relative h-6 w-6 shrink-0">
          <div className="h-6 w-6 rounded-full border border-white/10" style={{ backgroundColor: props.value }} />
          <input
            aria-label={`${props.label} color`}
            className="absolute inset-0 h-6 w-6 cursor-pointer opacity-0 disabled:cursor-not-allowed"
            disabled={props.disabled}
            type="color"
            value={pickerValue}
            onChange={(event) => props.onChange(event.target.value)}
            onBlur={(event) => handleCommittedChange(event.target.value)}
          />
        </div>
        <Input
          disabled={props.disabled}
          id={inputId}
          className="h-9 min-w-0 flex-1 bg-slate-950/70 text-xs"
          value={props.value}
          onChange={(event) => props.onChange(event.target.value)}
          onBlur={(event) => handleCommittedChange(event.target.value)}
        />
      </div>
    </div>
  )
}

function LayerSection(props: {
  title: string
  children: React.ReactNode
  description?: React.ReactNode
}): React.JSX.Element {
  return (
    <section className="grid gap-2.5 border-t border-white/10 pt-3 first:border-t-0 first:pt-0">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{props.title}</p>
        {props.description ? <div className="mt-1.5 text-[10px] leading-4 text-slate-400">{props.description}</div> : null}
      </div>
      {props.children}
    </section>
  )
}

export type SpectrumLayerInspectorState = {
  layerName: string
  colorMode: string
  solidColor: string
  gradientDirection: string
  gradientColors: string[]
  gradientPresetValue: string
  opacitySlider: number
}

export function buildSpectrumLayerInspectorState(
  selectedLayerItemIndex: number | undefined,
  selectedLayerRecord: Record<string, unknown> | null,
): SpectrumLayerInspectorState {
  const idx = selectedLayerItemIndex ?? 0
  const layerName = String(selectedLayerRecord?.name ?? '').trim() || `Layer ${idx + 1}`
  const colorModel = extractSpectrumLayerColorModel(
    selectedLayerRecord,
    getSpectrumLayerColorFallback(idx),
  )
  const colorMode = colorModel.mode
  const solidColor = colorModel.solidColor
  const gradientDirection = colorModel.gradientDirection
  const gradientColors = colorModel.gradientColors
  const gradientPresetValue = buildSpectrumGradientPresetValue(gradientColors)
  const opacityRaw = Number(selectedLayerRecord?.opacity ?? 1)
  const opacitySlider = Math.round(Math.max(0, Math.min(1, opacityRaw)) * 100)

  return {
    layerName,
    colorMode,
    solidColor,
    gradientDirection,
    gradientColors,
    gradientPresetValue,
    opacitySlider,
  }
}

type SpectrumLayerEditorProps = {
  spectrumDraft: SpectrumDraftSlice
  layerOptions: Array<{ label: string; value: string }>
  selectedLayerIndexValue: string
  layerCount: number
  selectedLayerRecord: Record<string, unknown> | null
  inspectorState: SpectrumLayerInspectorState
  attachedToLogo: boolean
  onPatchSpectrumDraft: (patch: Partial<SpectrumDraftSlice>) => void
  onSelectLayer: (value: string) => void
  onAddLayer: () => void
  onDuplicateLayer: () => void
  onDeleteLayer: () => void
  onPatchLayer: (patch: Record<string, unknown>, deferPersistence?: boolean) => void
  onPatchLayerColor: (patch: Record<string, unknown>, deferPersistence?: boolean) => void
  onFlushLayerCommit: () => void
}

export function SpectrumLayerEditor({
  spectrumDraft,
  layerOptions,
  selectedLayerIndexValue,
  layerCount,
  selectedLayerRecord,
  inspectorState,
  attachedToLogo,
  onPatchSpectrumDraft,
  onSelectLayer,
  onAddLayer,
  onDuplicateLayer,
  onDeleteLayer,
  onPatchLayer,
  onPatchLayerColor,
  onFlushLayerCommit,
}: SpectrumLayerEditorProps): React.JSX.Element {
  const { layerName, colorMode, solidColor, gradientDirection, gradientColors, gradientPresetValue, opacitySlider } =
    inspectorState

  return (
    <SectionCard title="Layers" subtitle="Presets start with one layer. Add or duplicate layers only when you want a stacked look.">
      <div className="grid gap-3">
        <LayerSection title="Layer">
          <div className="mt-2.5">
            <AppSelect
              disabled={!layerOptions.length}
              options={layerOptions}
              placeholder="No layers available"
              triggerClassName="h-9 bg-slate-950/70 text-xs"
              value={selectedLayerIndexValue}
              onChange={onSelectLayer}
            />
          </div>
          <div className="mt-2.5 grid gap-2 sm:grid-cols-3">
            <Button size="sm" type="button" onClick={onAddLayer}>
              Add
            </Button>
            <Button size="sm" type="button" variant="secondary" onClick={onDuplicateLayer}>
              Duplicate
            </Button>
            <Button disabled={layerCount < 2} size="sm" type="button" variant="secondary" onClick={onDeleteLayer}>
              Delete
            </Button>
          </div>
          <div className="mt-2.5 grid gap-2.5">
            <TextField label="Layer Name" value={layerName} onChange={(value) => onPatchLayer({ name: value })} />
            <SelectField
              label="Gravity"
              options={[
                { value: 'bottom', label: 'Bottom (Rabbit Ears on Top)' },
                { value: 'top', label: 'Top' },
                { value: 'left', label: 'Left' },
                { value: 'right', label: 'Right' },
              ]}
              value={String(selectedLayerRecord?.gravity ?? 'bottom')}
              onChange={(value) => onPatchLayer({ gravity: value })}
            />
            <SelectField
              label="Blend"
              options={[
                { value: 'normal', label: 'Normal' },
                { value: 'add', label: 'Additive' },
                { value: 'screen', label: 'Screen' },
              ]}
              value={String(selectedLayerRecord?.blend_mode ?? 'normal')}
              onChange={(value) => onPatchLayer({ blend_mode: value })}
            />
          </div>
        </LayerSection>

        <LayerSection
          title="Bar Shape / Geometry"
          description={
            attachedToLogo ? (
              <p className="text-cyan-200/80">
              Spectrum is attached to the logo core. Use `Spectrum Outer Gap` in the Logo tab to control the shared
              outer radius.
              </p>
            ) : undefined
          }
        >
          <div className="mt-2.5 grid gap-2 sm:grid-cols-3">
            <InlineToggle
              className="w-full"
              label="Curve 180"
              pressed={Boolean(selectedLayerRecord?.curved)}
              onPressedChange={(pressed) => onPatchLayer({ curved: pressed })}
            />
            <InlineToggle
              className="w-full"
              label="Mirror 360"
              pressed={Boolean(selectedLayerRecord?.mirrored)}
              onPressedChange={(pressed) => onPatchLayer({ mirrored: pressed })}
            />
            <InlineToggle
              className="w-full"
              label="Fill Circle"
              pressed={Boolean(selectedLayerRecord?.fillCircle)}
              onPressedChange={(pressed) => onPatchLayer({ fillCircle: pressed })}
            />
            <InlineToggle
              className="w-full"
              label="Solid Band"
              pressed={Boolean(selectedLayerRecord?.solidBand)}
              onPressedChange={(pressed) => onPatchLayer({ solidBand: pressed })}
            />
          </div>
          <div className="mt-3 grid gap-3">
            <SliderField
              label={`Bar Height (${Number(spectrumDraft.audioBarHeight.toFixed(2))})`}
              max={6}
              min={0.5}
              step={0.05}
              value={spectrumDraft.audioBarHeight}
              onChange={(value) => onPatchSpectrumDraft({ audioBarHeight: Number(value.toFixed(2)) })}
            />
            <SliderField
              label={`Bar Width (${Number(selectedLayerRecord?.barWidth ?? 4)})`}
              max={120}
              min={1}
              step={0.25}
              value={Number(selectedLayerRecord?.barWidth ?? 4)}
              onChange={(value) => onPatchLayer({ barWidth: Number(value.toFixed(2)) }, true)}
              onChangeCommitted={onFlushLayerCommit}
            />
            <SliderField
              label={`Spike Height (${Number(selectedLayerRecord?.thickness ?? 30)})`}
              max={220}
              min={1}
              step={0.25}
              value={Number(selectedLayerRecord?.thickness ?? 30)}
              onChange={(value) => onPatchLayer({ thickness: Number(value.toFixed(2)) }, true)}
              onChangeCommitted={onFlushLayerCommit}
            />
            <SliderField
              label={`Layer Gap (${Number(selectedLayerRecord?.radiusOffset ?? 0)})`}
              max={400}
              min={0}
              step={0.5}
              value={Number(selectedLayerRecord?.radiusOffset ?? 0)}
              onChange={(value) => onPatchLayer({ radiusOffset: Number(value.toFixed(2)) }, true)}
              onChangeCommitted={onFlushLayerCommit}
            />
            <SliderField
              label={`Opacity (${(opacitySlider / 100).toFixed(2)})`}
              max={100}
              min={0}
              step={1}
              value={opacitySlider}
              onChange={(value) => onPatchLayer({ opacity: Math.max(0, Math.min(1, value / 100)) }, true)}
              onChangeCommitted={onFlushLayerCommit}
            />
          </div>
        </LayerSection>

        <LayerSection title="Blend / Glow">
          <div className="mt-3 grid gap-3">
            <SliderField
              label={`Glow Strength (${Number(selectedLayerRecord?.glow ?? 0)})`}
              max={100}
              min={0}
              step={1}
              value={Number(selectedLayerRecord?.glow ?? 0)}
              onChange={(value) => onPatchLayer({ glow: Math.round(value) }, true)}
              onChangeCommitted={onFlushLayerCommit}
            />
            <SliderField
              label={`Glow Softness (${Number(selectedLayerRecord?.blur ?? 0)})`}
              max={30}
              min={0}
              step={1}
              value={Number(selectedLayerRecord?.blur ?? 0)}
              onChange={(value) => onPatchLayer({ blur: Math.round(value) }, true)}
              onChangeCommitted={onFlushLayerCommit}
            />
          </div>
        </LayerSection>

        <LayerSection
          title="Color Engine"
          description={
            <p>
              Choose <span className="font-medium text-slate-200">Solid Color</span> for one clean tone or{' '}
              <span className="font-medium text-slate-200">Gradient</span> for multi-stop color.
            </p>
          }
        >
          <div className="mt-3 grid gap-3">
            <SelectField
              label="Color Style"
              options={[
                { value: 'solid', label: 'Solid Color' },
                { value: 'gradient', label: 'Gradient' },
              ]}
              value={colorMode}
              onChange={(value) =>
                onPatchLayerColor(
                  value === 'gradient'
                    ? {
                        mode: value,
                        gradientColors: normalizeSpectrumGradientColors(gradientColors, solidColor),
                      }
                    : { mode: value },
                )
              }
            />
            {colorMode === 'gradient' ? (
              <div className="grid gap-3">
                <SelectField
                  label="Direction"
                  options={[
                    { value: 'left-to-right', label: 'Left to Right' },
                    { value: 'top-to-bottom', label: 'Top to Bottom' },
                    { value: 'diagonal', label: 'Diagonal' },
                    { value: 'radial', label: 'Radial' },
                    { value: 'circular', label: 'Circular' },
                  ]}
                  value={gradientDirection}
                  onChange={(value) => onPatchLayerColor({ gradientDirection: value })}
                />
                <SelectField
                  label="Preset"
                  options={SPECTRUM_GRADIENT_PRESET_OPTIONS}
                  value={gradientPresetValue}
                  onChange={(value) =>
                    onPatchLayerColor({
                      gradientColors: normalizeSpectrumGradientColors(
                        String(value || '').split(','),
                        solidColor,
                      ),
                    })
                  }
                />
                <div className="min-w-0 border-t border-white/10 pt-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Gradient Stops</p>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        disabled={gradientColors.length >= MAX_GRADIENT_COLOR_STOPS}
                        size="sm"
                        type="button"
                        variant="secondary"
                        onClick={() =>
                          onPatchLayerColor(
                            {
                              gradientColors: normalizeSpectrumGradientColors(
                                [...gradientColors, gradientColors[gradientColors.length - 1] ?? solidColor],
                                solidColor,
                              ),
                            },
                            true,
                          )
                        }
                      >
                        Add Color
                      </Button>
                      <Button
                        disabled={gradientColors.length <= 2}
                        size="sm"
                        type="button"
                        variant="secondary"
                        onClick={() =>
                          onPatchLayerColor(
                            {
                              gradientColors: normalizeSpectrumGradientColors(
                                gradientColors.slice(0, -1),
                                solidColor,
                              ),
                            },
                            true,
                          )
                        }
                      >
                        Remove Last
                      </Button>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2">
                    {gradientColors.map((stopColor, stopIndex) => (
                      <ColorPickField
                        key={`gradient-stop-${stopIndex}`}
                        label={`Stop ${stopIndex + 1}`}
                        value={stopColor}
                        onChange={(value) =>
                          onPatchLayerColor(
                            {
                              gradientColors: gradientColors.map((currentColor, currentIndex) =>
                                currentIndex === stopIndex ? value : currentColor,
                              ),
                            },
                            true,
                          )
                        }
                        onChangeCommitted={onFlushLayerCommit}
                      />
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <ColorPickField
                label="Color"
                value={solidColor}
                onChange={(value) => onPatchLayerColor({ solidColor: value }, true)}
                onChangeCommitted={onFlushLayerCommit}
              />
            )}
          </div>
        </LayerSection>
      </div>
    </SectionCard>
  )
}
