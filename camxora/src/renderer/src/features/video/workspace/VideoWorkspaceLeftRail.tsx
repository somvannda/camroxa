import { AppSelect } from '@/shared/ui/app-select'
import { Button } from '@/shared/ui/button'
import { Card } from '@/shared/ui/card'
import { CompactTabs, type CompactTabOption } from '@/shared/ui/compact-tabs'
import { Input } from '@/shared/ui/input'
import type { VideoTabId } from '@/features/video/workspace/useVideoWorkspaceShell'
import { WorkspaceBadge } from '@/features/video/workspace/workspaceShellPrimitives'

type VideoWorkspaceLeftRailProps = {
  activeTab: VideoTabId
  activeTabDirty: boolean
  activeTabPanel: React.ReactNode
  diagnosticsPanel: React.ReactNode
  deleteTemplatePending: boolean
  isLoading: boolean
  patchTemplatePending: boolean
  saveTemplatePending: boolean
  selectedTemplateId: string
  settingsTabs: ReadonlyArray<CompactTabOption>
  templateNameDraft: string
  templates: ReadonlyArray<{ id: string; name: string }>
  workspaceDirty: boolean
  onActiveTabChange: (value: VideoTabId) => void
  onDelete: () => void
  onSave: () => void
  onTemplateNameChange: (value: string) => void
  onTemplateSelectionChange: (value: string) => void
}

export function VideoWorkspaceLeftRail({
  activeTab,
  activeTabDirty,
  activeTabPanel,
  diagnosticsPanel,
  deleteTemplatePending,
  isLoading,
  patchTemplatePending,
  saveTemplatePending,
  selectedTemplateId,
  settingsTabs,
  templateNameDraft,
  templates,
  workspaceDirty,
  onActiveTabChange,
  onDelete,
  onSave,
  onTemplateNameChange,
  onTemplateSelectionChange,
}: VideoWorkspaceLeftRailProps): React.JSX.Element {
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex h-full min-h-0 flex-col">
        <div className="border-b border-white/10 p-3">
          <div className="grid gap-3">
            <div className="rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(17,24,39,0.92),rgba(8,16,40,0.96))] p-3 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.03)]">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Template</p>
                  <h2 className="mt-1 text-base font-semibold text-white">Video Controls</h2>
                </div>
                <WorkspaceBadge label={activeTab} tone={activeTabDirty ? 'warning' : 'ready'} />
              </div>
              <div className="mt-3">
                <Input
                  className="h-9 bg-slate-950/70 text-xs"
                  value={templateNameDraft}
                  onChange={(event) => onTemplateNameChange(event.target.value)}
                />
              </div>
              <div className="mt-2.5 grid grid-cols-2 gap-2">
                <Button
                  className="w-full"
                  disabled={patchTemplatePending || !workspaceDirty || !templateNameDraft.trim()}
                  size="sm"
                  type="button"
                  onClick={onSave}
                >
                  Save
                </Button>
                <Button
                  aria-label="Delete selected template"
                  className="w-full border-rose-500/20 text-rose-200 hover:border-rose-500/30 hover:bg-rose-500/10"
                  disabled={!selectedTemplateId || patchTemplatePending || saveTemplatePending || deleteTemplatePending}
                  size="sm"
                  type="button"
                  variant="secondary"
                  onClick={onDelete}
                >
                  Delete
                </Button>
              </div>
              <div className="mt-2.5">
                <AppSelect
                  disabled={!templates.length || saveTemplatePending}
                  options={templates.map((template) => ({ label: template.name, value: template.id }))}
                  placeholder="No templates available"
                  triggerClassName="h-9 bg-slate-950/70 text-xs"
                  value={selectedTemplateId}
                  onChange={onTemplateSelectionChange}
                />
              </div>
            </div>

            <CompactTabs justify options={settingsTabs} value={activeTab} onChange={(value) => onActiveTabChange((value as VideoTabId) || 'spectrum')} />
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          <div className="grid gap-3 pt-3">
            {isLoading ? <p className="text-sm text-slate-400">Loading video workspace...</p> : activeTabPanel}

            <details className="group rounded-2xl border border-white/10 bg-[#081028]">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Diagnostics & Recovery</p>
                  <p className="mt-1 text-xs text-slate-400">Open only when the preview needs recovery or verification.</p>
                </div>
                <span className="rounded-full border border-white/10 bg-slate-950/70 px-2 py-1 text-[10px] font-medium tracking-[0.14em] text-slate-300 transition group-open:rotate-180">
                  ˅
                </span>
              </summary>
              <div className="border-t border-white/10 p-3">{diagnosticsPanel}</div>
            </details>
          </div>
        </div>
      </div>
    </Card>
  )
}
