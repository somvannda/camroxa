import { applyPreviewFrameReport } from '@/features/video/preview/previewFrameReporter'

describe('applyPreviewFrameReport', () => {
  it('records GPU timings, frame timing, and the frame telemetry payload', () => {
    const recordTiming = vi.fn()
    const recordFrame = vi.fn()
    const reportFrame = vi.fn()

    vi.spyOn(performance, 'now').mockReturnValue(108)

    applyPreviewFrameReport({
      frameStart: 100,
      gpuTiming: {
        instancesMs: 3.1,
        particlesMs: 4.2,
        renderMs: 5.3,
      },
      dpr: 1.25,
      logicalWidth: 1280.2,
      logicalHeight: 719.7,
      timestamp: 2400,
      spectrumBarCount: 96,
      spectrumLayers: [{ id: 'layer-1' }] as never,
      qualityTier: 'balanced',
      adaptiveQualityLevel: 1,
      performanceScene: 'heavy-bloom',
      gpuInstances: [{ id: 'i1' }, { id: 'i2' }] as never,
      gpuParticles: [{ id: 'p1' }] as never,
      useWebGpuSpectrum: true,
      showDomPreviewBackground: true,
      showDomPreviewLogo: false,
      hasPostFx: true,
      telemetry: {
        recordTiming,
        recordFrame,
        reportFrame,
      },
    })

    expect(recordTiming).toHaveBeenCalledWith('instances', 3.1)
    expect(recordTiming).toHaveBeenCalledWith('particles', 4.2)
    expect(recordTiming).toHaveBeenCalledWith('render', 5.3)
    expect(recordFrame).toHaveBeenCalledWith(8)
    expect(reportFrame).toHaveBeenCalledWith(2400, {
      dpr: 1.25,
      width: 1280,
      height: 720,
      barCount: 96,
      layerCount: 1,
      qualityTier: 'balanced',
      adaptiveQualityLevel: 1,
      performanceScene: 'heavy-bloom',
      instanceCount: 2,
      particleCount: 1,
      useWebGpuSpectrum: true,
      showDomPreviewBackground: true,
      showDomPreviewLogo: false,
      postFx: true,
    })
  })
})
