import { useMemo } from 'react'
import { useMutation, type QueryClient } from '@tanstack/react-query'

import type { DesktopApi, VideoWorkspaceState } from '@/shared/types/desktop'
import { emitShellStatus } from '@/shared/lib/shellStatus'
import { buildVideoTemplateDraft, type VideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import {
  cloneLayerRecords,
} from '@/features/video/workspace/videoWorkspaceDraftStore'
import {
  buildAppliedEffectPackDraftState,
  buildClearedEffectPackDraftState,
} from '@/features/video/workspace/effectPackDraftState'
import { useEffectPackCatalogQuery } from '@/shared/hooks/useEffectPackCatalogQuery'
import type {
  EffectPackCatalogItem,
  EffectPackDomain,
  EffectPackSelectionStatus,
} from '@shared/effectPacks/effectPackContracts'
import {
  buildEffectPackCatalogOptions,
  parseEffectPackCatalogValue,
  resolveEffectPackSelectionStatus,
} from '@shared/effectPacks/effectPackRuntime'

type DomainEffectPackControls = {
  options: Array<{ value: string; label: string }>
  selectedValue: string
  status: EffectPackSelectionStatus
  onApply: (value: string) => void
  onClear: () => void
  onInstallFromFile: () => void | Promise<void>
  onReloadCatalog: () => void | Promise<unknown>
  onToggleEnabled: () => void | Promise<void>
  onActivateVersion: () => void | Promise<void>
  onRemoveVersion: () => void | Promise<void>
  isBusy: boolean
}

type UseEffectPackManagerOptions = {
  desktopApi: DesktopApi
  queryClient: QueryClient
  workspace: VideoWorkspaceState | undefined
  currentTemplate: Record<string, unknown>
  templateDraft: VideoTemplateDraft | null
  setTemplateDraft: (draft: VideoTemplateDraft) => void
  commitSpectrumSessionDraft: (draft: VideoTemplateDraft, layers?: Record<string, unknown>[]) => void
}

function selectionToValue(selection: EffectPackSelectionStatus['selection']): string {
  return selection ? `${selection.packId}::${selection.version}` : ''
}

function resolveCatalogItem(
  domain: EffectPackDomain,
  value: string,
  items: EffectPackCatalogItem[],
): EffectPackCatalogItem | null {
  const selection = parseEffectPackCatalogValue(value)
  if (!selection) {
    return null
  }
  return (
    items.find(
      (item) =>
        item.domain === domain &&
        item.packId === selection.packId &&
        item.version === selection.version &&
        (item.status === 'ready' || item.status === 'available'),
    ) ?? null
  )
}

export function useEffectPackManager({
  desktopApi,
  queryClient,
  workspace,
  currentTemplate,
  templateDraft,
  setTemplateDraft,
  commitSpectrumSessionDraft,
}: UseEffectPackManagerOptions): Record<EffectPackDomain, DomainEffectPackControls> {
  const effectPackCatalogQuery = useEffectPackCatalogQuery()
  const catalogItems = useMemo(
    () => (effectPackCatalogQuery.data?.items ?? []) as EffectPackCatalogItem[],
    [effectPackCatalogQuery.data?.items],
  )

  const invalidateCatalog = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['effect-pack-catalog'] }),
      queryClient.invalidateQueries({ queryKey: ['video-workspace'] }),
    ])
  }

  const installFromFileMutation = useMutation({
    mutationFn: async () => {
      const zipPath = await desktopApi.files.selectFile({
        title: 'Select effect pack zip',
        filters: [{ name: 'Zip archives', extensions: ['zip'] }],
      })
      if (!zipPath) {
        return null
      }
      const result = await desktopApi.effectPacks.installFromFile({ zipPath })
      if (!result.ok) {
        throw new Error(result.error || 'Unable to install effect pack.')
      }
      return result.item
    },
    onSuccess: async (item) => {
      if (!item) {
        return
      }
      emitShellStatus({
        tone: 'success',
        message: `Installed ${item.name} (${item.version}) for ${item.domain}.`,
      })
      await invalidateCatalog()
    },
    onError: (error) => {
      emitShellStatus({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Unable to install effect pack.',
      })
    },
  })

  const toggleEnabledMutation = useMutation({
    mutationFn: async (item: EffectPackCatalogItem) => {
      const result = await desktopApi.effectPacks.setEnabled({
        packId: item.packId,
        enabled: !item.enabled,
      })
      if (!result.ok) {
        throw new Error(result.error || 'Unable to update effect pack state.')
      }
      return { enabled: !item.enabled, item }
    },
    onSuccess: async ({ enabled, item }) => {
      emitShellStatus({
        tone: 'success',
        message: `${enabled ? 'Enabled' : 'Disabled'} ${item.name} (${item.version}).`,
      })
      await invalidateCatalog()
    },
    onError: (error) => {
      emitShellStatus({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Unable to update effect pack state.',
      })
    },
  })

  const activateVersionMutation = useMutation({
    mutationFn: async (item: EffectPackCatalogItem) => {
      const result = await desktopApi.effectPacks.activateVersion({
        packId: item.packId,
        version: item.version,
      })
      if (!result.ok) {
        throw new Error(result.error || 'Unable to activate effect pack version.')
      }
      return item
    },
    onSuccess: async (item) => {
      emitShellStatus({
        tone: 'success',
        message: `Activated ${item.name} (${item.version}).`,
      })
      await invalidateCatalog()
    },
    onError: (error) => {
      emitShellStatus({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Unable to activate effect pack version.',
      })
    },
  })

  const removeVersionMutation = useMutation({
    mutationFn: async (item: EffectPackCatalogItem) => {
      const result = await desktopApi.effectPacks.removeVersion({
        packId: item.packId,
        version: item.version,
      })
      if (!result.ok) {
        throw new Error(result.error || 'Unable to remove effect pack version.')
      }
      return item
    },
    onSuccess: async (item) => {
      emitShellStatus({
        tone: 'success',
        message: `Removed ${item.name} (${item.version}).`,
      })
      await invalidateCatalog()
    },
    onError: (error) => {
      emitShellStatus({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Unable to remove effect pack version.',
      })
    },
  })

  return useMemo(() => {
    const domains: EffectPackDomain[] = ['spectrum', 'background', 'logo', 'particles']

    return domains.reduce(
      (accumulator, domain) => {
        const selection = templateDraft?.effectPacks[domain] ?? null
        const status = resolveEffectPackSelectionStatus(domain, selection, catalogItems)
        const options = buildEffectPackCatalogOptions(domain, catalogItems)

        const applyPack = (value: string) => {
          if (!templateDraft || !workspace) {
            return
          }
          const item = resolveCatalogItem(domain, value, catalogItems)
          if (!item) {
            emitShellStatus({
              tone: 'error',
              message: `Selected ${domain} pack is unavailable.`,
            })
            return
          }

          const { nextDraft, nextLayers } = buildAppliedEffectPackDraftState({
            currentDraft: templateDraft,
            currentTemplate,
            workspace,
            domain,
            item,
          })

          if (domain === 'spectrum') {
            commitSpectrumSessionDraft(nextDraft, nextLayers ?? cloneLayerRecords(currentTemplate.layers))
            emitShellStatus({
              tone: 'success',
              message: `Previewing ${item.name} (${item.version}) in the local workspace draft.`,
            })
            return
          }

          setTemplateDraft(nextDraft)
          emitShellStatus({
            tone: 'success',
            message: `Applied ${item.name} (${item.version}) to the local ${domain} draft.`,
          })
        }

        const clearPack = () => {
          if (!templateDraft || !workspace) {
            return
          }

          if (domain === 'spectrum') {
            const restoredDraft = buildVideoTemplateDraft(currentTemplate, workspace)
            commitSpectrumSessionDraft(restoredDraft, cloneLayerRecords(currentTemplate.layers))
            emitShellStatus({
              tone: 'success',
              message: 'Restored the saved spectrum pack selection.',
            })
            return
          }

          const { nextDraft } = buildClearedEffectPackDraftState({
            currentDraft: templateDraft,
            domain,
          })
          setTemplateDraft(nextDraft)
          emitShellStatus({
            tone: 'success',
            message: `Cleared the local ${domain} pack reference.`,
          })
        }

        const targetItem = status.item
        accumulator[domain] = {
          options,
          selectedValue: selectionToValue(status.selection),
          status,
          onApply: applyPack,
          onClear: clearPack,
          onInstallFromFile: () => installFromFileMutation.mutate(),
          onReloadCatalog: () => effectPackCatalogQuery.refetch(),
          onToggleEnabled: () => {
            if (targetItem) {
              toggleEnabledMutation.mutate(targetItem)
            }
          },
          onActivateVersion: () => {
            if (targetItem) {
              activateVersionMutation.mutate(targetItem)
            }
          },
          onRemoveVersion: () => {
            if (targetItem) {
              removeVersionMutation.mutate(targetItem)
            }
          },
          isBusy:
            effectPackCatalogQuery.isFetching ||
            installFromFileMutation.isPending ||
            toggleEnabledMutation.isPending ||
            activateVersionMutation.isPending ||
            removeVersionMutation.isPending,
        }
        return accumulator
      },
      {} as Record<EffectPackDomain, DomainEffectPackControls>,
    )
  }, [
    activateVersionMutation,
    catalogItems,
    commitSpectrumSessionDraft,
    currentTemplate,
    effectPackCatalogQuery,
    installFromFileMutation,
    removeVersionMutation,
    setTemplateDraft,
    templateDraft,
    toggleEnabledMutation,
    workspace,
  ])
}
