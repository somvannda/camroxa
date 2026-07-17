import { useMemo } from 'react'

import { RendererVideoPreview } from '@/features/video/RendererVideoPreview'
import type { PreviewPlaybackCommand } from '@/features/video/preview/transportClock'
import type { TemplateSettingsDraft } from '@/features/settings/settingsTemplateDraft'
import { buildTemplateDraft, type TemplateTextOverlayDraft } from '@/features/settings/settingsTemplateDraft'
import type { VideoWorkspaceState } from '@/shared/types/desktop'
import { Button } from '@/shared/ui/button'
import { AppSelect } from '@/shared/ui/app-select'
import { CompactTabs, type CompactTabOption } from '@/shared/ui/compact-tabs'
import { InlineToggle } from '@/shared/ui/inline-toggle'
import { Textarea } from '@/shared/ui/textarea'
import { cn } from '@/shared/lib/utils'
import { ANCHOR_OPTIONS, TEXT_ANIMATION_OPTIONS } from '@/features/settings/pythonVideoSettings'
import { ColorField, SelectField, SliderField } from '@/features/video/workspace/inspectorFields'

export type VideoSidePanelTabId = 'text' | 'animation' | 'export'
export type VideoTextPanelModeId = 'basic' | 'style' | 'effects'

export const TEXT_PRESET_OPTIONS: ReadonlyArray<{ label: string; value: string }> = [
  { label: 'Neon Brush Stack', value: 'neon_brush_stack' },
  { label: 'Neon Outline', value: 'neon_outline' },
  { label: 'Soft Glow', value: 'soft_glow' },
  { label: 'Dark Stroke', value: 'dark_stroke' },
]

export const TEXT_SIDE_PANEL_TABS: ReadonlyArray<CompactTabOption> = [
  { value: 'text', label: 'Text' },
  { value: 'animation', label: 'Animation' },
  { value: 'export', label: 'Export' },
]

export const TEXT_PANEL_MODE_TABS: ReadonlyArray<CompactTabOption> = [
  { value: 'basic', label: 'Basic' },
  { value: 'style', label: 'Style' },
  { value: 'effects', label: 'Effects' },
]

function NumberField(props: {
  label: string
  value: number
  step?: number
  min?: number
  max?: number
  onChange: (nextValue: number) => void
}): React.JSX.Element {
  return (
    <div className="grid gap-1.5">
      <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500">{props.label}</span>
      <input
        className="h-9 rounded-md border border-input bg-slate-950/70 px-3 py-1 text-xs ring-offset-background"
        max={props.max}
        min={props.min}
        step={props.step ?? 1}
        type="number"
        value={props.value}
        onChange={(event) => props.onChange(Number(event.target.value))}
      />
    </div>
  )
}

type TextLayerListPanelProps = {
  textOverlays: TemplateTextOverlayDraft[]
  selectedTextOverlay: TemplateTextOverlayDraft | null
  selectedTextOverlayIndex: number
  textPresetId: string
  setTextPresetId: (value: string) => void
  setSelectedTextOverlayKey: (key: string) => void
  setSidePanelTab: (tab: VideoSidePanelTabId) => void
  onAddTextOverlay: () => void
  onApplyTextPreset: (preset: string) => void
  onDuplicateTextOverlay: () => void
  onDeleteTextOverlay: () => void
  onMoveTextOverlay: (direction: -1 | 1) => void
}

export function TextLayerListPanel({
  textOverlays,
  selectedTextOverlay,
  selectedTextOverlayIndex,
  textPresetId,
  setTextPresetId,
  setSelectedTextOverlayKey,
  setSidePanelTab,
  onAddTextOverlay,
  onApplyTextPreset,
  onDuplicateTextOverlay,
  onDeleteTextOverlay,
  onMoveTextOverlay,
}: TextLayerListPanelProps): React.JSX.Element {
  return (
    <div className="grid gap-2.5">
      <div className="flex flex-nowrap items-center gap-2 overflow-x-auto pr-1">
        <Button className="h-8 shrink-0 px-3 text-xs" size="sm" type="button" onClick={onAddTextOverlay}>
          Add
        </Button>
        <AppSelect
          options={TEXT_PRESET_OPTIONS}
          placeholder="Presets"
          triggerClassName="h-8 w-[132px] shrink-0 bg-slate-950/70 text-xs"
          value={textPresetId}
          onChange={(value) => {
            setTextPresetId(value)
            onApplyTextPreset(value)
            setTextPresetId('')
          }}
        />
        <Button
          className="h-8 shrink-0 px-3 text-xs"
          disabled={!selectedTextOverlay}
          size="sm"
          type="button"
          variant="secondary"
          onClick={onDuplicateTextOverlay}
        >
          Duplicate
        </Button>
        <Button
          className="h-8 shrink-0 px-3 text-xs"
          disabled={!selectedTextOverlay}
          size="sm"
          type="button"
          variant="secondary"
          onClick={onDeleteTextOverlay}
        >
          Delete
        </Button>
        <Button
          className="h-8 shrink-0 px-3 text-xs"
          disabled={!selectedTextOverlay || selectedTextOverlayIndex <= 0}
          size="sm"
          type="button"
          variant="secondary"
          onClick={() => onMoveTextOverlay(-1)}
        >
          Up
        </Button>
        <Button
          className="h-8 shrink-0 px-3 text-xs"
          disabled={!selectedTextOverlay || selectedTextOverlayIndex >= textOverlays.length - 1}
          size="sm"
          type="button"
          variant="secondary"
          onClick={() => onMoveTextOverlay(1)}
        >
          Down
        </Button>
      </div>
      {textOverlays.length ? (
        <div className="rounded-2xl border border-white/10 bg-[#081028] p-2.5">
          <div className="max-h-[320px] overflow-y-auto pr-1">
            <div className="grid gap-1">
              {textOverlays.map((overlay, index) => {
                const active = index === selectedTextOverlayIndex
                const title = overlay.text.trim().split('\n')[0]?.trim() || `Text ${index + 1}`
                return (
                  <button
                    className={cn(
                      'flex w-full items-start gap-2 rounded-xl border px-2 py-1.5 text-left text-[11px] transition',
                      active
                        ? 'border-fuchsia-500/40 bg-fuchsia-500/10 text-white'
                        : 'border-white/10 bg-slate-950/40 text-slate-300 hover:bg-white/5',
                    )}
                    key={`text-layer-${index}`}
                    type="button"
                    onClick={() => {
                      setSelectedTextOverlayKey(String(index))
                      setSidePanelTab('text')
                    }}
                  >
                    <span
                      className={cn(
                        'mt-1 h-2 w-2 shrink-0 rounded-full border',
                        overlay.enabled ? 'border-emerald-300 bg-emerald-300' : 'border-slate-500 bg-transparent',
                      )}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium leading-4 text-slate-100">{title}</span>
                      <span className="mt-0.5 block text-[10px] leading-4 text-slate-500">
                        {Math.round(overlay.startSec)}s · {Math.round(overlay.durationSec)}s · {Math.round(overlay.fontSize)}px
                      </span>
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-white/10 bg-[#081028] p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Text Layers</p>
          <p className="mt-2 text-xs text-slate-400">No text layers yet. Use Add or Presets to create one.</p>
        </div>
      )}
    </div>
  )
}

type TextInspectorPanelProps = {
  backgroundPath: string
  logoPath: string
  playbackCommand: PreviewPlaybackCommand | null
  previewTemplate: Record<string, unknown>
  selectedMp3Path: string
  selectedTextOverlay: TemplateTextOverlayDraft | null
  selectedTextOverlayIndex: number
  sidePanelTab: VideoSidePanelTabId
  templateDraft: TemplateSettingsDraft | null
  textPanelMode: VideoTextPanelModeId
  workspace: Pick<VideoWorkspaceState, 'playback' | 'previewAspectRatio'>
  setTextPanelMode: (mode: VideoTextPanelModeId) => void
  getTextAnchorAlignment: (anchor: string) => 'left' | 'center' | 'right'
  updateTextOverlay: (index: number, nextOverlay: TemplateTextOverlayDraft) => void
  applyTextAnchorAlignment: (alignment: 'left' | 'center' | 'right') => void
  applyTextCase: (mode: 'upper' | 'lower' | 'title') => void
  applyTextPreset: (preset: string) => void
}

function ParticlePreviewCard({
  backgroundPath,
  logoPath,
  playbackCommand,
  previewTemplate,
  selectedMp3Path,
  templateDraft,
  workspace,
}: {
  backgroundPath: string
  logoPath: string
  playbackCommand: PreviewPlaybackCommand | null
  previewTemplate: Record<string, unknown>
  selectedMp3Path: string
  templateDraft: TemplateSettingsDraft | null
  workspace: Pick<VideoWorkspaceState, 'playback' | 'previewAspectRatio'>
}): React.JSX.Element {
  const particlePreviewDraft = useMemo<TemplateSettingsDraft>(
    () =>
      ({
        ...(templateDraft ?? buildTemplateDraft(previewTemplate, { logoPath })),
        spectrumEnabled: false,
        logoEnabled: false,
        textOverlays: [],
      }) as TemplateSettingsDraft,
    [logoPath, previewTemplate, templateDraft],
  )

  return (
    <div className="rounded-2xl border border-white/10 bg-[#081028] p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Particle Preview</p>
          <p className="mt-1 text-xs leading-5 text-slate-300">
            Small WebGPU preview for particles only, mounted under the text tools.
          </p>
          <p className="mt-1 text-[10px] leading-4 text-slate-500">
            {workspace.playback.isPlaying ? 'Playback: Playing' : 'Playback: Paused'} · React Strength:{' '}
            {Number(particlePreviewDraft.particlesReactStrength ?? 0).toFixed(2)} · Color:{' '}
            {String(particlePreviewDraft.particlesColor ?? '')} → {String(particlePreviewDraft.particlesReactColor ?? '')}
          </p>
          {Number(particlePreviewDraft.particlesReactStrength ?? 0) <= 0.001 && (
            <p className="mt-1 text-[10px] leading-4 text-amber-300/90">
              React Strength is 0, so React Color will not show. Increase it in the Particles panel.
            </p>
          )}
        </div>
        <span
          className={cn(
            'rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]',
            particlePreviewDraft.particlesEnabled
              ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-100'
              : 'border-slate-500/25 bg-slate-500/10 text-slate-300',
          )}
        >
          {particlePreviewDraft.particlesEnabled ? 'Live' : 'Disabled'}
        </span>
      </div>
      <div className="mt-3 overflow-hidden rounded-2xl border border-white/10 bg-slate-950/60 p-2">
        <div className="relative aspect-video overflow-hidden rounded-xl border border-white/10 bg-[radial-gradient(circle_at_top,_rgba(217,70,239,0.12),_transparent_45%),linear-gradient(180deg,rgba(8,16,40,0.95),rgba(3,7,18,1))]">
          <RendererVideoPreview
            backgroundPath={backgroundPath}
            logoPath={logoPath}
            playbackCommand={playbackCommand}
            previewVolume={0.0001}
            selectedMp3Path={selectedMp3Path}
            selectedTextOverlayIndex={0}
            template={previewTemplate}
            templateDraft={particlePreviewDraft}
            workspace={workspace}
          />
        </div>
      </div>
    </div>
  )
}

export function TextInspectorPanel({
  backgroundPath,
  logoPath,
  playbackCommand,
  previewTemplate,
  selectedMp3Path,
  selectedTextOverlay,
  selectedTextOverlayIndex,
  sidePanelTab,
  templateDraft,
  textPanelMode,
  workspace,
  setTextPanelMode,
  getTextAnchorAlignment,
  updateTextOverlay,
  applyTextAnchorAlignment,
  applyTextCase,
  applyTextPreset,
}: TextInspectorPanelProps): React.JSX.Element {
  const particlePreview = selectedTextOverlay ? (
    <ParticlePreviewCard
      backgroundPath={backgroundPath}
      logoPath={logoPath}
      playbackCommand={playbackCommand}
      previewTemplate={previewTemplate}
      selectedMp3Path={selectedMp3Path}
      templateDraft={templateDraft}
      workspace={workspace}
    />
  ) : null

  if (!selectedTextOverlay) {
    return (
      <div className="grid gap-3 rounded-2xl border border-dashed border-white/10 bg-[#081028] p-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Text Inspector</p>
          <p className="mt-2 text-sm font-medium text-white">No text layer is selected yet.</p>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Select a text layer from the stage list below the preview, or add one first if this template does not have any text yet.
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2.5">
            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Next Step</p>
            <p className="mt-1 text-xs text-slate-200">Use `Add` or `Presets` under `Text Layers` to create a layer.</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2.5">
            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Inspector Scope</p>
            <p className="mt-1 text-xs text-slate-200">The `Text` and `Animation` tabs stay empty until a concrete layer is selected.</p>
          </div>
        </div>
      </div>
    )
  }

  const activeAlignment = getTextAnchorAlignment(selectedTextOverlay.anchor)
  const styleButtons = [
    {
      value: 'neon_outline',
      label: 'Aa',
      className: 'bg-[#201230] text-white shadow-[0_0_18px_rgba(255,79,216,0.35)]',
    },
    {
      value: 'soft_glow',
      label: 'Aa',
      className: 'bg-[#dff6ff] text-slate-900 shadow-[0_0_18px_rgba(223,246,255,0.35)]',
    },
    {
      value: 'dark_stroke',
      label: 'Aa',
      className: 'bg-white text-black shadow-[inset_0_0_0_2px_rgba(0,0,0,0.85)]',
    },
    {
      value: 'neon_brush_stack',
      label: 'FX',
      className: 'bg-[linear-gradient(135deg,#38bdf8,#ff4fd8)] text-white',
    },
  ]

  if (sidePanelTab === 'animation') {
    return (
      <div className="grid gap-3">
        <div className="rounded-2xl border border-white/10 bg-[#081028] p-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-300">Animation</p>
            <InlineToggle
              showLabel={false}
              className="h-7 rounded-lg px-2 text-[10px]"
              label="Enable"
              pressed={selectedTextOverlay.enabled}
              onPressedChange={(pressed) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, enabled: pressed })}
            />
          </div>
          <div className="mt-3 grid gap-2.5">
            <SelectField
              label="Preset"
              options={TEXT_ANIMATION_OPTIONS}
              value={selectedTextOverlay.animation}
              onChange={(value) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, animation: value })}
            />
            <div className="grid gap-2.5 sm:grid-cols-2">
              <NumberField
                label="Start (sec)"
                max={36000}
                min={0}
                step={1}
                value={selectedTextOverlay.startSec}
                onChange={(value) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, startSec: value })}
              />
              <NumberField
                label="Duration"
                max={36000}
                min={1}
                step={1}
                value={selectedTextOverlay.durationSec}
                onChange={(value) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, durationSec: value })}
              />
            </div>
            <SelectField
              label="Anchor"
              options={ANCHOR_OPTIONS}
              value={selectedTextOverlay.anchor}
              onChange={(value) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, anchor: value })}
            />
            <SliderField
              label={`X Offset (${Math.round(selectedTextOverlay.x)}px)`}
              max={1000}
              min={-1000}
              value={selectedTextOverlay.x}
              onChange={(value) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, x: value })}
            />
            <SliderField
              label={`Y Offset (${Math.round(selectedTextOverlay.y)}px)`}
              max={1000}
              min={-1000}
              value={selectedTextOverlay.y}
              onChange={(value) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, y: value })}
            />
            <SliderField
              label={`Shadow (${selectedTextOverlay.shadow.toFixed(2)})`}
              max={1}
              min={0}
              step={0.01}
              value={selectedTextOverlay.shadow}
              onChange={(value) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, shadow: value })}
            />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-3">
      {particlePreview}
      <div className="rounded-2xl border border-white/10 bg-[#081028] p-3">
        <CompactTabs
          justify
          options={TEXT_PANEL_MODE_TABS}
          value={textPanelMode}
          onChange={(value) => setTextPanelMode((value as VideoTextPanelModeId) || 'basic')}
        />
        <div className="mt-3 grid gap-3">
          {textPanelMode === 'basic' ? (
            <>
              <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-2.5">
                <label className="block text-[11px] font-medium text-slate-100">Default text</label>
                <Textarea
                  className="mt-2 min-h-[72px] text-xs"
                  value={selectedTextOverlay.text}
                  onChange={(event) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, text: event.target.value })}
                />
              </div>
              <SliderField
                label={`Font Size (${Math.round(selectedTextOverlay.fontSize)}px)`}
                max={320}
                min={8}
                value={selectedTextOverlay.fontSize}
                onChange={(value) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, fontSize: value })}
              />
              <div className="grid gap-2">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Case</p>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" type="button" variant="secondary" onClick={() => applyTextCase('upper')}>
                    TT
                  </Button>
                  <Button size="sm" type="button" variant="secondary" onClick={() => applyTextCase('lower')}>
                    tt
                  </Button>
                  <Button size="sm" type="button" variant="secondary" onClick={() => applyTextCase('title')}>
                    Tt
                  </Button>
                </div>
              </div>
              <ColorField
                label="Color"
                value={selectedTextOverlay.color}
                onChange={(value) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, color: value })}
              />
              <div className="grid gap-2">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Alignment</p>
                <div className="grid grid-cols-3 gap-2">
                  {(['left', 'center', 'right'] as const).map((alignment) => (
                    <Button
                      key={alignment}
                      size="sm"
                      type="button"
                      variant={activeAlignment === alignment ? 'primary' : 'secondary'}
                      onClick={() => applyTextAnchorAlignment(alignment)}
                    >
                      {alignment}
                    </Button>
                  ))}
                </div>
              </div>
            </>
          ) : null}

          {textPanelMode === 'style' ? (
            <>
              <ColorField
                label="Fill"
                value={selectedTextOverlay.color}
                onChange={(value) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, color: value })}
              />
              <ColorField
                label="Stroke"
                value={selectedTextOverlay.strokeColor}
                onChange={(value) =>
                  updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, strokeColor: value })
                }
              />
              <SliderField
                label={`Stroke Width (${selectedTextOverlay.strokeWidth.toFixed(1)})`}
                max={12}
                min={0}
                step={0.1}
                value={selectedTextOverlay.strokeWidth}
                onChange={(value) =>
                  updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, strokeWidth: value })
                }
              />
              <div className="grid gap-2">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Preset style</p>
                <div className="grid grid-cols-4 gap-2">
                  {styleButtons.map((preset) => (
                    <button
                      className={cn(
                        'flex h-12 items-center justify-center rounded-xl border border-white/10 text-lg font-black transition hover:border-fuchsia-500/50',
                        preset.className,
                      )}
                      key={preset.value}
                      type="button"
                      onClick={() => applyTextPreset(preset.value)}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : null}

          {textPanelMode === 'effects' ? (
            <>
              <SliderField
                label={`Shadow (${selectedTextOverlay.shadow.toFixed(2)})`}
                max={1}
                min={0}
                step={0.01}
                value={selectedTextOverlay.shadow}
                onChange={(value) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, shadow: value })}
              />
              <SliderField
                label={`Scale (${Math.round((selectedTextOverlay.fontSize / 46) * 100)}%)`}
                max={400}
                min={20}
                step={1}
                value={Math.round((selectedTextOverlay.fontSize / 46) * 100)}
                onChange={(value) =>
                  updateTextOverlay(selectedTextOverlayIndex, {
                    ...selectedTextOverlay,
                    fontSize: Math.max(8, (46 * value) / 100),
                  })
                }
              />
              <div className="grid gap-2.5 sm:grid-cols-2">
                <NumberField
                  label="X"
                  max={1000}
                  min={-1000}
                  value={selectedTextOverlay.x}
                  onChange={(value) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, x: value })}
                />
                <NumberField
                  label="Y"
                  max={1000}
                  min={-1000}
                  value={selectedTextOverlay.y}
                  onChange={(value) => updateTextOverlay(selectedTextOverlayIndex, { ...selectedTextOverlay, y: value })}
                />
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}
