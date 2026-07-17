import { buildPreviewGpuAudioSignalFrame } from '@/features/video/preview/previewGpuAudioSignal'

describe('buildPreviewGpuAudioSignalFrame', () => {
  it('builds one reusable per-frame audio signal payload for GPU submission and spectrum reuse', () => {
    const result = buildPreviewGpuAudioSignalFrame({
      features: {
        energyBands: new Float32Array(64).fill(0.25),
        peakHoldBands: new Float32Array(64).fill(0.4),
        transientBands: new Float32Array(64).fill(0.1),
        onsetBands: new Float32Array(64).fill(0.2),
        framePeak: 0.9,
        averageEnergy: 0.25,
        averageTransient: 0.1,
        averageOnset: 0.2,
        level: 0.7,
        kick: 0.55,
        drop: 0.33,
      },
      frame: {
        renderValues: new Float32Array([0.1, 0.5, 0.9, 0.3]),
        peakHoldValues: new Float32Array([0.2, 0.6, 1, 0.4]),
        reactiveEnergy: 0.8,
        styleMotionDrive: 0.44,
        styleTriggerDrive: 0.7,
      },
      reactiveEnergy: 0.8,
      spectrumBarCount: 4,
      timeSec: 1.25,
    })

    expect(result).not.toBeNull()
    expect(result?.renderValues.map((value) => Number(value.toFixed(3)))).toEqual([0.1, 0.5, 0.9, 0.3])
    expect(result?.mirroredRenderValues.map((value) => Number(value.toFixed(3)))).toEqual([0.5, 0.1, 0.1, 0.5])
    expect(result?.peakHoldValues.map((value) => Number(value.toFixed(3)))).toEqual([0.2, 0.6, 1, 0.4])
    expect(result?.kick).toBe(0.55)
    expect(result?.styleMotionDrive).toBe(0.44)
    expect(result?.energyBands.length).toBe(64)
    expect(result?.peakHoldBands[0]).toBeCloseTo(0.4, 5)
  })

  it('returns null when there is no analyzed frame or usable feature data', () => {
    expect(
      buildPreviewGpuAudioSignalFrame({
        features: null,
        frame: null,
        reactiveEnergy: 0,
        spectrumBarCount: 64,
        timeSec: 0,
      }),
    ).toBeNull()
  })
})
