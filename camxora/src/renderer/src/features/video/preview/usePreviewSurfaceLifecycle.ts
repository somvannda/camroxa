import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { MutableRefObject } from 'react'

import {
  advancePreviewAdaptiveQualityState,
  createPreviewAdaptiveQualityState,
  resolveAdaptivePreviewQualityPolicy,
} from '@/features/video/preview/previewAdaptiveQuality'
import type { PreviewFrameTelemetryReport } from '@/features/video/preview/previewFrameTelemetry'
import {
  evaluatePreviewPerformanceVerification,
  type PreviewPerformanceVerification,
} from '@/features/video/preview/previewPerformanceVerification'
import {
  buildPreviewGpuCapabilityProfile,
  resolvePreviewQualityPolicy,
  type PreviewGpuCapabilityProfile,
  type PreviewQualityPolicy,
} from '@/features/video/preview/previewQualityPolicy'
import { createVideoDebugSender } from '@/features/video/videoDiagnostics'
import type { RendererPreviewCapability } from '@/features/video/useRendererVideoPreview'
import { WebGpuSpectrumRenderer } from '@/features/video/webgpu/webgpuSpectrumRenderer'

export type PreviewBounds = {
  width: number
  height: number
}

export type PreviewSurfaceStatus =
  | 'idle'
  | 'unsupported'
  | 'initializing'
  | 'ready'
  | 'recovering'
  | 'device-lost'
  | 'error'

const sendVideoPageLagDebug = createVideoDebugSender({
  sessionId: 'video-page-lag',
  runId: 'pre-fix',
})

type UsePreviewSurfaceLifecycleOptions = {
  capability: RendererPreviewCapability
}

type UsePreviewSurfaceLifecycleResult = {
  backdropCanvasRef: MutableRefObject<HTMLCanvasElement | null>
  bounds: PreviewBounds
  capabilityProfile: PreviewGpuCapabilityProfile
  containerRef: MutableRefObject<HTMLDivElement | null>
  onTelemetryReport: (report: PreviewFrameTelemetryReport) => void
  overlayCanvasRef: MutableRefObject<HTMLCanvasElement | null>
  performanceVerification: PreviewPerformanceVerification | null
  qualityPolicy: PreviewQualityPolicy
  webgpuCanvasRef: MutableRefObject<HTMLCanvasElement | null>
  webgpuErrorMessage: string | null
  webgpuRendererRef: MutableRefObject<WebGpuSpectrumRenderer | null>
  webgpuStatus: PreviewSurfaceStatus
}

export function usePreviewSurfaceLifecycle({
  capability,
}: UsePreviewSurfaceLifecycleOptions): UsePreviewSurfaceLifecycleResult {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const webgpuCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const backdropCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const webgpuRendererRef = useRef<WebGpuSpectrumRenderer | null>(null)
  const hasInitializedRef = useRef(false)
  const [capabilityProfile, setCapabilityProfile] = useState<PreviewGpuCapabilityProfile>(() => {
    return buildPreviewGpuCapabilityProfile({
      rendererCapability: capability,
    })
  })
  const [baseQualityPolicy, setBaseQualityPolicy] = useState<PreviewQualityPolicy>(() =>
    resolvePreviewQualityPolicy(
      buildPreviewGpuCapabilityProfile({
        rendererCapability: capability,
      }),
    ),
  )
  const [adaptiveQualityState, setAdaptiveQualityState] = useState(() =>
    createPreviewAdaptiveQualityState(),
  )
  const [performanceVerification, setPerformanceVerification] =
    useState<PreviewPerformanceVerification | null>(null)
  const baseQualityPolicyRef = useRef(baseQualityPolicy)
  const [bounds, setBounds] = useState<PreviewBounds>({ width: 960, height: 540 })
  const [webgpuStatus, setWebgpuStatus] = useState<PreviewSurfaceStatus>('idle')
  const [webgpuErrorMessage, setWebgpuErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    baseQualityPolicyRef.current = baseQualityPolicy
  }, [baseQualityPolicy])

  const qualityPolicy = useMemo(
    () => resolveAdaptivePreviewQualityPolicy(baseQualityPolicy, adaptiveQualityState.level),
    [adaptiveQualityState.level, baseQualityPolicy],
  )

  const onTelemetryReport = useCallback((report: PreviewFrameTelemetryReport) => {
    // #region debug-point C:telemetry-report
    sendVideoPageLagDebug({
      hypothesisId: 'C',
      location: 'usePreviewSurfaceLifecycle:onTelemetryReport',
      msg: '[DEBUG] preview telemetry report received',
      data: {
        avgFrameMs: report.avgFrameMs,
        maxFrameMs: report.maxFrameMs,
        renderAvgMs: report.renderAvgMs,
        canvas2dAvgMs: report.canvas2dAvgMs,
        audioAvgMs: report.audioAvgMs,
        instancesAvgMs: report.instancesAvgMs,
        particlesAvgMs: report.particlesAvgMs,
        qualityTier: report.qualityTier,
        adaptiveQualityLevel: report.adaptiveQualityLevel,
        performanceScene: report.performanceScene,
      },
    })
    // #endregion
    setPerformanceVerification(
      evaluatePreviewPerformanceVerification(report, baseQualityPolicyRef.current),
    )
    setAdaptiveQualityState((current) => {
      const next = advancePreviewAdaptiveQualityState(current, report, baseQualityPolicyRef.current)
      if (
        next.level === current.level &&
        next.slowReports === current.slowReports &&
        next.healthyReports === current.healthyReports
      ) {
        return current
      }
      return next
    })
  }, [])

  useEffect(() => {
    const node = containerRef.current
    if (!node) {
      return
    }

    const updateBounds = () => {
      const rect = node.getBoundingClientRect()
      if (rect.width < 1 || rect.height < 1) {
        return
      }
      setBounds({
        width: Math.max(1, rect.width),
        height: Math.max(1, rect.height),
      })
    }

    updateBounds()

    const resizeObserver =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(() => {
            updateBounds()
          })
        : null

    resizeObserver?.observe(node)
    window.addEventListener('resize', updateBounds)
    return () => {
      resizeObserver?.disconnect()
      window.removeEventListener('resize', updateBounds)
    }
  }, [])

  useEffect(() => {
    const canvas = webgpuCanvasRef.current
    if (!canvas) {
      // #region debug-point B:lifecycle-no-canvas
      sendVideoPageLagDebug({
        hypothesisId: 'B',
        location: 'usePreviewSurfaceLifecycle:effect',
        msg: '[DEBUG] preview surface lifecycle reset without canvas',
        data: {
          capability,
        },
      })
      // #endregion
      const nextProfile = buildPreviewGpuCapabilityProfile({
        rendererCapability: capability,
      })
      setCapabilityProfile(nextProfile)
      setBaseQualityPolicy(resolvePreviewQualityPolicy(nextProfile))
      setAdaptiveQualityState(createPreviewAdaptiveQualityState())
      setPerformanceVerification(null)
      setWebgpuStatus('idle')
      setWebgpuErrorMessage(null)
      return
    }

    webgpuRendererRef.current?.destroy()
    webgpuRendererRef.current = null

    if (capability !== 'webgpu') {
      // #region debug-point B:lifecycle-unsupported
      sendVideoPageLagDebug({
        hypothesisId: 'B',
        location: 'usePreviewSurfaceLifecycle:effect',
        msg: '[DEBUG] preview surface lifecycle entered unsupported path',
        data: {
          capability,
        },
      })
      // #endregion
      const nextProfile = buildPreviewGpuCapabilityProfile({
        rendererCapability: capability,
      })
      setCapabilityProfile(nextProfile)
      setBaseQualityPolicy(resolvePreviewQualityPolicy(nextProfile))
      setAdaptiveQualityState(createPreviewAdaptiveQualityState())
      setPerformanceVerification(null)
      setWebgpuStatus('unsupported')
      setWebgpuErrorMessage('WebGPU is not available in this renderer process.')
      return
    }

    let cancelled = false
    const renderer = new WebGpuSpectrumRenderer()
    const initializeStart = performance.now()
    setWebgpuErrorMessage(null)
    setWebgpuStatus(hasInitializedRef.current ? 'recovering' : 'initializing')
    // #region debug-point B:lifecycle-initialize-start
    sendVideoPageLagDebug({
      hypothesisId: 'B',
      location: 'usePreviewSurfaceLifecycle:initialize:start',
      msg: '[DEBUG] preview surface initialization started',
      data: {
        capability,
        recovering: hasInitializedRef.current,
      },
    })
    // #endregion

    void renderer
      .initialize(canvas, {
        onDeviceLost: (message) => {
          if (cancelled) {
            return
          }
          // #region debug-point B:lifecycle-device-lost
          sendVideoPageLagDebug({
            hypothesisId: 'B',
            location: 'usePreviewSurfaceLifecycle:initialize:onDeviceLost',
            msg: '[DEBUG] preview surface device lost',
            data: {
              elapsedMs: Number((performance.now() - initializeStart).toFixed(2)),
              message,
            },
          })
          // #endregion
          if (webgpuRendererRef.current === renderer) {
            webgpuRendererRef.current = null
          }
          renderer.destroy()
          setWebgpuErrorMessage(message)
          setWebgpuStatus('device-lost')
        },
      })
      .then((result) => {
        if (cancelled) {
          renderer.destroy()
          return
        }
        // #region debug-point B:lifecycle-initialize-success
        sendVideoPageLagDebug({
          hypothesisId: 'B',
          location: 'usePreviewSurfaceLifecycle:initialize:success',
          msg: '[DEBUG] preview surface initialization resolved',
          data: {
            elapsedMs: Number((performance.now() - initializeStart).toFixed(2)),
            qualityTier: result.qualityPolicy.tier,
            targetFrameRate: result.qualityPolicy.targetFrameRate,
            maxDpr: result.qualityPolicy.maxDpr,
            maxRenderPixels: result.qualityPolicy.maxRenderPixels,
            maxSpectrumBars: result.qualityPolicy.maxSpectrumBars,
            maxParticleCount: result.qualityPolicy.maxParticleCount,
          },
        })
        // #endregion
        webgpuRendererRef.current = renderer
        hasInitializedRef.current = true
        setCapabilityProfile(result.capabilityProfile)
        setBaseQualityPolicy(result.qualityPolicy)
        setAdaptiveQualityState(createPreviewAdaptiveQualityState())
        setPerformanceVerification(null)
        setWebgpuErrorMessage(null)
        setWebgpuStatus('ready')
      })
      .catch((error) => {
        if (cancelled) {
          renderer.destroy()
          return
        }
        // #region debug-point B:lifecycle-initialize-error
        sendVideoPageLagDebug({
          hypothesisId: 'B',
          location: 'usePreviewSurfaceLifecycle:initialize:error',
          msg: '[DEBUG] preview surface initialization failed',
          data: {
            elapsedMs: Number((performance.now() - initializeStart).toFixed(2)),
            error: error instanceof Error ? error.message : String(error),
          },
        })
        // #endregion
        renderer.destroy()
        setWebgpuErrorMessage(error instanceof Error ? error.message : 'Unable to initialize the WebGPU compositor.')
        setWebgpuStatus('error')
      })

    return () => {
      cancelled = true
      // #region debug-point B:lifecycle-cleanup
      sendVideoPageLagDebug({
        hypothesisId: 'B',
        location: 'usePreviewSurfaceLifecycle:cleanup',
        msg: '[DEBUG] preview surface lifecycle cleanup',
        data: {
          capability,
          hadRenderer: webgpuRendererRef.current === renderer,
        },
      })
      // #endregion
      if (webgpuRendererRef.current === renderer) {
        webgpuRendererRef.current = null
      }
      renderer.destroy()
    }
  }, [capability])

  return {
    backdropCanvasRef,
    bounds,
    capabilityProfile,
    containerRef,
    onTelemetryReport,
    overlayCanvasRef,
    performanceVerification,
    qualityPolicy,
    webgpuCanvasRef,
    webgpuErrorMessage,
    webgpuRendererRef,
    webgpuStatus,
  }
}
