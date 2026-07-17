import { TextInspectorPanel, TEXT_SIDE_PANEL_TABS, type VideoSidePanelTabId, type VideoTextPanelModeId } from '@/features/video/workspace/TextPanels'
import type { PreviewPlaybackCommand } from '@/features/video/preview/transportClock'
import type { TemplateSettingsDraft } from '@/features/settings/settingsTemplateDraft'
import { WorkspaceBadge } from '@/features/video/workspace/workspaceShellPrimitives'
import type { TemplateTextOverlayDraft } from '@/features/settings/settingsTemplateDraft'
import type { VideoWorkspaceState } from '@/shared/types/desktop'
import { Card } from '@/shared/ui/card'
import { CompactTabs } from '@/shared/ui/compact-tabs'

type VideoWorkspaceRightRailProps = {
  backgroundPath: string
  logoPath: string
  playbackCommand: PreviewPlaybackCommand | null
  previewTemplate: Record<string, unknown>
  selectedMp3Path: string
  rightPanelSubtitle: string
  selectedLayerLabel: string
  selectedTextOverlay: TemplateTextOverlayDraft | null
  selectedTextOverlayIndex: number
  sidePanelTab: VideoSidePanelTabId
  templateDraft: TemplateSettingsDraft | null
  textPanelMode: VideoTextPanelModeId
  workspace: Pick<VideoWorkspaceState, 'playback' | 'previewAspectRatio'>
  exportPanel: React.ReactNode
  updateTextOverlay: (index: number, nextOverlay: TemplateTextOverlayDraft) => void
  applyTextAnchorAlignment: (alignment: 'left' | 'center' | 'right') => void
  applyTextCase: (mode: 'upper' | 'lower' | 'title') => void
  applyTextPreset: (preset: string) => void
  getTextAnchorAlignment: (anchor: string) => 'left' | 'center' | 'right'
  onSetSidePanelTab: (tab: VideoSidePanelTabId) => void
  onSetTextPanelMode: (mode: VideoTextPanelModeId) => void
}

export function VideoWorkspaceRightRail({
  backgroundPath,
  logoPath,
  playbackCommand,
  previewTemplate,
  selectedMp3Path,
  exportPanel,
  rightPanelSubtitle,
  selectedLayerLabel,
  selectedTextOverlay,
  selectedTextOverlayIndex,
  sidePanelTab,
  templateDraft,
  textPanelMode,
  workspace,
  updateTextOverlay,
  applyTextAnchorAlignment,
  applyTextCase,
  applyTextPreset,
  getTextAnchorAlignment,
  onSetSidePanelTab,
  onSetTextPanelMode,
}: VideoWorkspaceRightRailProps): React.JSX.Element {
  const selectedLayerTone = sidePanelTab === 'export' ? 'neutral' : selectedTextOverlay ? 'ready' : 'neutral'

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex h-full min-h-0 flex-col">
        <div className="border-b border-white/10 p-3">
          <div className="grid gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">Inspector</h2>
              <p className="mt-1 text-xs leading-5 text-slate-400">{rightPanelSubtitle}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <WorkspaceBadge label={selectedLayerLabel} tone={selectedLayerTone} />
            </div>
            <CompactTabs
              justify
              options={TEXT_SIDE_PANEL_TABS}
              value={sidePanelTab}
              onChange={(value) => onSetSidePanelTab((value as VideoSidePanelTabId) || 'text')}
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          {sidePanelTab === 'export' ? (
            exportPanel
          ) : (
            <TextInspectorPanel
              applyTextAnchorAlignment={applyTextAnchorAlignment}
              applyTextCase={applyTextCase}
              applyTextPreset={applyTextPreset}
              backgroundPath={backgroundPath}
              getTextAnchorAlignment={getTextAnchorAlignment}
              logoPath={logoPath}
              playbackCommand={playbackCommand}
              previewTemplate={previewTemplate}
              selectedMp3Path={selectedMp3Path}
              selectedTextOverlay={selectedTextOverlay}
              selectedTextOverlayIndex={selectedTextOverlayIndex}
              setTextPanelMode={onSetTextPanelMode}
              sidePanelTab={sidePanelTab}
              templateDraft={templateDraft}
              textPanelMode={textPanelMode}
              updateTextOverlay={updateTextOverlay}
              workspace={workspace}
            />
          )}
        </div>
      </div>
    </Card>
  )
}
