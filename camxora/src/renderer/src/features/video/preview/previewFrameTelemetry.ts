export type PreviewFrameTelemetryReport = {
  frames: number
  avgFrameMs: number
  maxFrameMs: number
  layoutAvgMs: number
  audioAvgMs: number
  spectrumAvgMs: number
  instancesAvgMs: number
  particlesAvgMs: number
  canvas2dAvgMs: number
  renderAvgMs: number
  dpr: number
  width: number
  height: number
  barCount: number
  layerCount: number
  qualityTier: 'compatibility' | 'balanced' | 'performance'
  adaptiveQualityLevel: 0 | 1 | 2
  performanceScene: 'baseline' | 'max-layers' | 'heavy-bloom' | 'high-particles' | 'text-overlay-pressure'
  instanceCount: number
  particleCount: number
  useWebGpuSpectrum: boolean
  showDomPreviewBackground: boolean
  showDomPreviewLogo: boolean
  postFx: boolean
}

type CreatePreviewFrameTelemetryOptions = {
  reportIntervalMs?: number
  send: (report: PreviewFrameTelemetryReport) => void
}

type ReportFrameOptions = Omit<
  PreviewFrameTelemetryReport,
  | 'frames'
  | 'avgFrameMs'
  | 'maxFrameMs'
  | 'layoutAvgMs'
  | 'audioAvgMs'
  | 'spectrumAvgMs'
  | 'instancesAvgMs'
  | 'particlesAvgMs'
  | 'canvas2dAvgMs'
  | 'renderAvgMs'
>

type TimingBucket =
  | 'layout'
  | 'audio'
  | 'spectrum'
  | 'instances'
  | 'particles'
  | 'canvas2d'
  | 'render'

export type PreviewFrameTelemetry = {
  recordTiming: (bucket: TimingBucket, durationMs: number) => void
  recordFrame: (frameMs: number) => void
  reportFrame: (timestamp: number, options: ReportFrameOptions) => void
}

export function createPreviewFrameTelemetry({
  reportIntervalMs = 1000,
  send,
}: CreatePreviewFrameTelemetryOptions): PreviewFrameTelemetry {
  let reportAt = performance.now()
  let frames = 0
  let frameTotalMs = 0
  let frameMaxMs = 0
  let layoutTotalMs = 0
  let audioTotalMs = 0
  let spectrumTotalMs = 0
  let instancesTotalMs = 0
  let particlesTotalMs = 0
  let canvas2dTotalMs = 0
  let renderTotalMs = 0

  const reset = (): void => {
    frames = 0
    frameTotalMs = 0
    frameMaxMs = 0
    layoutTotalMs = 0
    audioTotalMs = 0
    spectrumTotalMs = 0
    instancesTotalMs = 0
    particlesTotalMs = 0
    canvas2dTotalMs = 0
    renderTotalMs = 0
  }

  return {
    recordTiming(bucket, durationMs) {
      switch (bucket) {
        case 'layout':
          layoutTotalMs += durationMs
          break
        case 'audio':
          audioTotalMs += durationMs
          break
        case 'spectrum':
          spectrumTotalMs += durationMs
          break
        case 'instances':
          instancesTotalMs += durationMs
          break
        case 'particles':
          particlesTotalMs += durationMs
          break
        case 'canvas2d':
          canvas2dTotalMs += durationMs
          break
        case 'render':
          renderTotalMs += durationMs
          break
      }
    },
    recordFrame(frameMs) {
      frames += 1
      frameTotalMs += frameMs
      frameMaxMs = Math.max(frameMaxMs, frameMs)
    },
    reportFrame(timestamp, options) {
      if (timestamp - reportAt < reportIntervalMs || frames <= 0) {
        return
      }

      send({
        frames,
        avgFrameMs: Number((frameTotalMs / frames).toFixed(2)),
        maxFrameMs: Number(frameMaxMs.toFixed(2)),
        layoutAvgMs: Number((layoutTotalMs / frames).toFixed(2)),
        audioAvgMs: Number((audioTotalMs / frames).toFixed(2)),
        spectrumAvgMs: Number((spectrumTotalMs / frames).toFixed(2)),
        instancesAvgMs: Number((instancesTotalMs / frames).toFixed(2)),
        particlesAvgMs: Number((particlesTotalMs / frames).toFixed(2)),
        canvas2dAvgMs: Number((canvas2dTotalMs / frames).toFixed(2)),
        renderAvgMs: Number((renderTotalMs / frames).toFixed(2)),
        ...options,
      })

      reportAt = timestamp
      reset()
    },
  }
}
