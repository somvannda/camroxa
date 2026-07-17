import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { flushSync } from 'react-dom'

import type { VideoTemplateDraft } from '@/features/video/core/contracts/videoTemplateDraft'
import { RendererVideoPreview } from '@/features/video/RendererVideoPreview'
import type { PreviewManualRenderFrameOptions } from '@/features/video/preview/previewProviderContract'
import { createVideoDebugSender } from '@/features/video/videoDiagnostics'
import type { PreviewLifecycleState } from '@/features/video/preview/previewLifecycleState'
import type { PreviewPlaybackCommand } from '@/features/video/preview/transportClock'
import { getDesktopApi } from '@/shared/api/desktop'
import type {
  VideoExportHostCommandPayload,
  VideoSerializableRenderSceneRequest,
  VideoWorkspaceState,
} from '@/shared/types/desktop'

const idlePlaybackState: VideoWorkspaceState['playback'] = {
  isPlaying: false,
  isReady: false,
  isLoading: false,
  currentTimeSec: 0,
  durationSec: 0,
}

const sendExportSpeedDebug = createVideoDebugSender({
  sessionId: 'manual-export-black-video',
  runId: 'pre-fix',
  endpoint: 'http://127.0.0.1:7780/event',
})

function buildSampledPixelStats(pixelData: Uint8Array): Record<string, unknown> {
  const totalPixels = Math.floor(pixelData.byteLength / 4)
  if (totalPixels <= 0) {
    return {
      totalPixels: 0,
      sampledPixels: 0,
      avgRgb: 0,
      avgAlpha: 0,
      maxChannel: 0,
      nonZeroColorSamples: 0,
      nonZeroAlphaSamples: 0,
      signature: '',
    }
  }

  const sampleTarget = 64
  const stridePixels = Math.max(1, Math.floor(totalPixels / sampleTarget))
  let sampledPixels = 0
  let redSum = 0
  let greenSum = 0
  let blueSum = 0
  let alphaSum = 0
  let maxChannel = 0
  let nonZeroColorSamples = 0
  let nonZeroAlphaSamples = 0
  const signatureParts: string[] = []

  for (let pixelIndex = 0; pixelIndex < totalPixels; pixelIndex += stridePixels) {
    const offset = pixelIndex * 4
    const blue = pixelData[offset] ?? 0
    const green = pixelData[offset + 1] ?? 0
    const red = pixelData[offset + 2] ?? 0
    const alpha = pixelData[offset + 3] ?? 0
    sampledPixels += 1
    redSum += red
    greenSum += green
    blueSum += blue
    alphaSum += alpha
    if (red > 0 || green > 0 || blue > 0) {
      nonZeroColorSamples += 1
    }
    if (alpha > 0) {
      nonZeroAlphaSamples += 1
    }
    maxChannel = Math.max(maxChannel, red, green, blue, alpha)
    if (signatureParts.length < 8) {
      signatureParts.push(`${red}-${green}-${blue}-${alpha}`)
    }
  }

  const sampledColorValues = sampledPixels * 3
  return {
    totalPixels,
    sampledPixels,
    avgRgb: sampledColorValues > 0 ? Number(((redSum + greenSum + blueSum) / sampledColorValues).toFixed(2)) : 0,
    avgAlpha: sampledPixels > 0 ? Number((alphaSum / sampledPixels).toFixed(2)) : 0,
    maxChannel,
    nonZeroColorSamples,
    nonZeroAlphaSamples,
    signature: signatureParts.join('|'),
  }
}

function buildIdleWorkspaceState(): Pick<VideoWorkspaceState, 'previewAspectRatio' | 'playback'> {
  return {
    previewAspectRatio: {
      width: 16,
      height: 9,
    },
    playback: idlePlaybackState,
  }
}

function createPlaybackCommand(
  command: VideoExportHostCommandPayload,
  nonce: number,
): PreviewPlaybackCommand {
  return {
    ...command,
    nonce,
  }
}

export function VideoExportHostPage(): React.JSX.Element {
  const desktopApi = getDesktopApi()
  const playbackCommandNonceRef = useRef(0)
  const manualRenderFrameRef = useRef<((options: PreviewManualRenderFrameOptions) => void) | null>(null)
  const previousRenderTimestampMsRef = useRef<number | null>(null)
  const playbackStateRef = useRef<VideoWorkspaceState['playback']>(idlePlaybackState)
  const readbackFrameCaptureRef = useRef<(() => Promise<Uint8Array | null>) | null>(null)
  const sceneRef = useRef<VideoSerializableRenderSceneRequest | null>(null)
  const [scene, setScene] = useState<VideoSerializableRenderSceneRequest | null>(null)
  const [sceneVersion, setSceneVersion] = useState(0)
  const [playbackState, setPlaybackState] = useState<VideoWorkspaceState['playback']>(idlePlaybackState)
  const [playbackCommand, setPlaybackCommand] = useState<PreviewPlaybackCommand | null>(null)

  useEffect(() => {
    const unsubscribeScene = desktopApi.videoExportHost.onScene((nextScene) => {
      sceneRef.current = nextScene
      setScene(nextScene)
      setSceneVersion((current) => current + 1)
      setPlaybackState(idlePlaybackState)
      playbackStateRef.current = idlePlaybackState
      previousRenderTimestampMsRef.current = null
      playbackCommandNonceRef.current += 1
      setPlaybackCommand(createPlaybackCommand({ type: 'stop' }, playbackCommandNonceRef.current))
      void desktopApi.videoExportHost.setStatus({
        status: 'initializing',
        message: 'Manual WebGPU export scene received. Booting the hidden preview surface.',
      })
    })
    const unsubscribeCommand = desktopApi.videoExportHost.onCommand((command) => {
      if (command.type === 'capture-frame') {
        void (async () => {
          const captureStartedAt = Date.now()
          const captureFrame = readbackFrameCaptureRef.current
          const manualRenderFrame = manualRenderFrameRef.current
          const activeScene = sceneRef.current
          if (!captureFrame || !manualRenderFrame || !activeScene) {
            await desktopApi.videoExportHost.setStatus({
              status: 'error',
              message: 'Manual WebGPU export capture was requested before the GPU readback surface was ready.',
            })
            return
          }
          // #region debug-point C:host-capture-request
          sendExportSpeedDebug({
            hypothesisId: 'C',
            location: 'VideoExportHostPage:capture-frame:request',
            msg: '[DEBUG] export capture request received in hidden host',
            data: {
              requestId: command.requestId,
              width: activeScene.output.width,
              height: activeScene.output.height,
            },
          })
          // #endregion
          const targetTimeSec = Math.max(0, Number(command.timeSec) || 0)
          const nextPlaybackState: VideoWorkspaceState['playback'] = {
            ...playbackStateRef.current,
            currentTimeSec: targetTimeSec,
            isLoading: false,
            isPlaying: false,
          }
          playbackStateRef.current = nextPlaybackState
          flushSync(() => {
            setPlaybackState(nextPlaybackState)
          })
          const targetTimestampMs = targetTimeSec * 1000
          const previousTimestampMs =
            previousRenderTimestampMsRef.current ??
            Math.max(0, targetTimestampMs - 1000 / Math.max(1, activeScene.output.fps || 60))
          manualRenderFrame({
            previousTimestampMs,
            timestampMs: targetTimestampMs,
            playbackTimeSec: targetTimeSec,
          })
          previousRenderTimestampMsRef.current = targetTimestampMs
          let pixelData = await captureFrame()
          let pollCount = 0
          while (!pixelData && pollCount < 60) {
            await new Promise<void>((resolve) => {
              window.setTimeout(resolve, 16)
            })
            pixelData = await captureFrame()
            pollCount += 1
          }
          if (!pixelData) {
            // #region debug-point C:host-capture-empty
            sendExportSpeedDebug({
              hypothesisId: 'C',
              location: 'VideoExportHostPage:capture-frame:empty',
              msg: '[DEBUG] export capture frame was not ready in hidden host',
              data: {
                requestId: command.requestId,
                elapsedMs: Date.now() - captureStartedAt,
                polls: pollCount,
              },
            })
            // #endregion
            await desktopApi.videoExportHost.setStatus({
              status: 'error',
              message: 'Manual WebGPU export GPU readback did not return a frame buffer.',
            })
            return
          }
          // #region debug-point C:host-capture-response
          sendExportSpeedDebug({
            hypothesisId: 'C',
            location: 'VideoExportHostPage:capture-frame:response',
            msg: '[DEBUG] export capture frame ready in hidden host',
            data: {
              requestId: command.requestId,
              elapsedMs: Date.now() - captureStartedAt,
              bytes: pixelData.byteLength,
              ...buildSampledPixelStats(pixelData),
            },
          })
          // #endregion
          const accepted = await desktopApi.videoExportHost.setCaptureFrame({
            requestId: command.requestId,
            width: activeScene.output.width,
            height: activeScene.output.height,
            pixelData,
          })
          // #region debug-point C:host-capture-ack
          sendExportSpeedDebug({
            hypothesisId: 'C',
            location: 'VideoExportHostPage:capture-frame:ack',
            msg: '[DEBUG] export capture frame sent from hidden host to main',
            data: {
              requestId: command.requestId,
              accepted,
            },
          })
          // #endregion
        })()
        return
      }
      playbackCommandNonceRef.current += 1
      setPlaybackCommand(createPlaybackCommand(command, playbackCommandNonceRef.current))
    })
    void desktopApi.videoExportHost.ready()
    return () => {
      unsubscribeCommand()
      unsubscribeScene()
    }
  }, [desktopApi])

  useEffect(() => {
    if (!playbackCommand) {
      return
    }
    const timer = window.setTimeout(() => {
      setPlaybackCommand(null)
    }, 0)
    return () => window.clearTimeout(timer)
  }, [playbackCommand])

  useEffect(() => {
    playbackStateRef.current = playbackState
  }, [playbackState])

  useEffect(() => {
    void desktopApi.videoExportHost.setPlayback(playbackState)
  }, [desktopApi, playbackState])

  const workspace = useMemo(() => {
    if (!scene) {
      return buildIdleWorkspaceState()
    }
    return {
      previewAspectRatio: {
        width: Math.max(1, scene.output.width),
        height: Math.max(1, scene.output.height),
      },
      playback: playbackState,
    }
  }, [playbackState, scene])

  const handleLifecycleStateChange = async (state: PreviewLifecycleState) => {
    await desktopApi.videoExportHost.setStatus({
      status: state.status,
      message: state.message,
    })
  }

  const handleExportPlaybackStateChange = useCallback((nextPlaybackState: VideoWorkspaceState['playback']) => {
    const mergedPlaybackState: VideoWorkspaceState['playback'] = {
      ...nextPlaybackState,
      currentTimeSec: playbackStateRef.current.currentTimeSec,
    }
    playbackStateRef.current = mergedPlaybackState
    setPlaybackState(mergedPlaybackState)
  }, [])

  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        background: '#000',
      }}
    >
      {scene ? (
        <RendererVideoPreview
          key={`export-scene-${sceneVersion}`}
          template={scene.template}
          workspace={workspace}
          templateDraft={scene.draft as unknown as VideoTemplateDraft}
          backgroundPath={scene.assets.backgroundPath ?? ''}
          logoPath={scene.assets.logoPath ?? ''}
          selectedMp3Path={scene.assets.audioPath ?? ''}
          previewVolume={0}
          selectedTextOverlayIndex={-1}
          playbackCommand={playbackCommand}
          runtimeMode="manual-export"
          onManualRenderFrameReady={(renderFrame) => {
            manualRenderFrameRef.current = renderFrame
          }}
          onReadbackFrameCaptureReady={(captureFrame) => {
            readbackFrameCaptureRef.current = captureFrame
          }}
          onPlaybackStateChange={handleExportPlaybackStateChange}
          onLifecycleStateChange={handleLifecycleStateChange}
        />
      ) : null}
    </div>
  )
}
