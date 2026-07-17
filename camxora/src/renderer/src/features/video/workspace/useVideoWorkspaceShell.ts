import { useCallback, useEffect, useRef, useState } from 'react'

import type { VideoPipelineBranch } from '@/shared/lib/videoPipelineInputs'
import type { VideoWorkspaceState } from '@/shared/types/desktop'
import type { VideoSidePanelTabId, VideoTextPanelModeId } from '@/features/video/workspace/TextPanels'
import type {
  PreviewPlaybackCommand,
  PreviewPlaybackCommandInput,
} from '@/features/video/preview/transportClock'

export type VideoTabId = 'spectrum' | 'background' | 'logo' | 'particles'

export type PreviewPlaybackState = {
  isPlaying: boolean
  isReady: boolean
  isLoading: boolean
  currentTimeSec: number
  durationSec: number
}

type UseVideoWorkspaceShellOptions = {
  workspace: VideoWorkspaceState | undefined
  previewTrackPath: string
  layerKeys: string[]
  pipelineRunKeys: string[]
  textOverlayCount: number
}

export function useVideoWorkspaceShell({
  workspace,
  previewTrackPath,
  layerKeys,
  pipelineRunKeys,
  textOverlayCount,
}: UseVideoWorkspaceShellOptions) {
  const [activeTab, setActiveTab] = useState<VideoTabId>('spectrum')
  const [selectedLayerKey, setSelectedLayerKey] = useState('')
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [selectedPipelineRunKey, setSelectedPipelineRunKey] = useState('')
  const [selectedPipelineBranch, setSelectedPipelineBranch] = useState<VideoPipelineBranch>('long')
  const [selectedTextOverlayKey, setSelectedTextOverlayKey] = useState('0')
  const [textPresetId, setTextPresetId] = useState('')
  const [sidePanelTab, setSidePanelTab] = useState<VideoSidePanelTabId>('text')
  const [textPanelMode, setTextPanelMode] = useState<VideoTextPanelModeId>('basic')
  const [backgroundPathDraft, setBackgroundPathDraft] = useState('')
  const [previewPlayback, setPreviewPlayback] = useState<PreviewPlaybackState>({
    isPlaying: false,
    isReady: false,
    isLoading: false,
    currentTimeSec: 0,
    durationSec: 0,
  })
  const [previewPlaybackCommand, setPreviewPlaybackCommand] = useState<PreviewPlaybackCommand | null>(null)
  const [pendingPreviewAutoplayPath, setPendingPreviewAutoplayPath] = useState('')
  const playbackCommandNonceRef = useRef(0)

  const issuePreviewPlaybackCommand = useCallback((command: PreviewPlaybackCommandInput) => {
    playbackCommandNonceRef.current += 1
    setPreviewPlaybackCommand({
      ...command,
      nonce: playbackCommandNonceRef.current,
    })
  }, [])

  const queuePreviewAutoplay = useCallback((targetPath: string) => {
    setPendingPreviewAutoplayPath(String(targetPath || '').trim())
  }, [])

  useEffect(() => {
    setPreviewPlayback({
      isPlaying: false,
      isReady: false,
      isLoading: Boolean(previewTrackPath),
      currentTimeSec: 0,
      durationSec: 0,
    })
    setPreviewPlaybackCommand(null)
  }, [previewTrackPath])

  useEffect(() => {
    if (!pendingPreviewAutoplayPath) {
      return
    }
    if (previewTrackPath !== pendingPreviewAutoplayPath) {
      return
    }
    if (!previewPlayback.isReady || previewPlayback.isLoading) {
      return
    }
    issuePreviewPlaybackCommand({ type: 'play' })
    setPendingPreviewAutoplayPath('')
  }, [issuePreviewPlaybackCommand, pendingPreviewAutoplayPath, previewPlayback.isLoading, previewPlayback.isReady, previewTrackPath])

  useEffect(() => {
    setSelectedTemplateId(workspace?.templateId ?? '')
  }, [workspace?.templateId])

  useEffect(() => {
    if (!pipelineRunKeys.length) {
      setSelectedPipelineRunKey('')
      return
    }
    if (!pipelineRunKeys.includes(selectedPipelineRunKey)) {
      setSelectedPipelineRunKey(pipelineRunKeys[0])
    }
  }, [pipelineRunKeys, selectedPipelineRunKey])

  useEffect(() => {
    if (!layerKeys.length) {
      setSelectedLayerKey('')
      return
    }
    if (!layerKeys.includes(selectedLayerKey)) {
      setSelectedLayerKey(layerKeys[0])
    }
  }, [layerKeys, selectedLayerKey])

  useEffect(() => {
    setBackgroundPathDraft((currentValue) => {
      const nextValue = String(workspace?.backgroundPath ?? '').trim()
      if (!nextValue || currentValue === nextValue) {
        return currentValue
      }
      return currentValue ? currentValue : nextValue
    })
  }, [workspace?.backgroundPath])

  useEffect(() => {
    if (!textOverlayCount) {
      setSelectedTextOverlayKey('0')
      return
    }
    const selectedIndex = Number(selectedTextOverlayKey)
    if (!Number.isFinite(selectedIndex) || selectedIndex < 0 || selectedIndex >= textOverlayCount) {
      setSelectedTextOverlayKey('0')
    }
  }, [selectedTextOverlayKey, textOverlayCount])

  return {
    activeTab,
    backgroundPathDraft,
    issuePreviewPlaybackCommand,
    previewPlayback,
    previewPlaybackCommand,
    queuePreviewAutoplay,
    selectedLayerKey,
    selectedPipelineBranch,
    selectedPipelineRunKey,
    selectedTemplateId,
    selectedTextOverlayKey,
    setActiveTab,
    setBackgroundPathDraft,
    setPreviewPlayback,
    setSelectedLayerKey,
    setSelectedPipelineBranch,
    setSelectedPipelineRunKey,
    setSelectedTemplateId,
    setSelectedTextOverlayKey,
    setSidePanelTab,
    setTextPanelMode,
    setTextPresetId,
    sidePanelTab,
    textPanelMode,
    textPresetId,
  }
}
