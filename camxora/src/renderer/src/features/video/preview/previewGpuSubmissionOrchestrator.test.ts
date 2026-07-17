import { orchestratePreviewGpuSubmission } from '@/features/video/preview/previewGpuSubmissionOrchestrator'

const mockBuildPreviewGpuExecutionPlan = vi.fn()
const mockSubmitPreviewGpuFrame = vi.fn()
const mockBuildPreviewGpuRuntimeResult = vi.fn()

vi.mock('@/features/video/preview/previewGpuExecutionPlan', () => ({
  buildPreviewGpuExecutionPlan: (...args: unknown[]) => mockBuildPreviewGpuExecutionPlan(...args),
}))

vi.mock('@/features/video/preview/previewGpuSubmission', () => ({
  submitPreviewGpuFrame: (...args: unknown[]) => mockSubmitPreviewGpuFrame(...args),
}))

vi.mock('@/features/video/preview/previewGpuRuntimeResult', () => ({
  buildPreviewGpuRuntimeResult: (...args: unknown[]) => mockBuildPreviewGpuRuntimeResult(...args),
}))

describe('orchestratePreviewGpuSubmission', () => {
  beforeEach(() => {
    mockBuildPreviewGpuExecutionPlan.mockReset()
    mockSubmitPreviewGpuFrame.mockReset()
    mockBuildPreviewGpuRuntimeResult.mockReset()
  })

  it('builds a submission plan, submits it, and returns the packaged GPU result', () => {
    const webgpuRenderer = {
      render: vi.fn(),
    }

    const domainResult = {
      audioSignal: { reactiveEnergy: 0.7 },
      gradientAtlas: { width: 256, height: 1, rgba: new Uint8Array(256 * 4) },
      gpuInstances: [{ id: 'instance-a' }],
      gpuParticles: [{ id: 'particle-a' }],
      gpuParticleSimulation: { reactiveEnv: 0.5 },
      atmosphere: { haze: 0.2 },
      postFx: { bloom: 0.4 },
      hasPostFx: true,
      timing: {
        instancesMs: 3.2,
        particlesMs: 4.6,
      },
    }

    mockBuildPreviewGpuExecutionPlan.mockReturnValue({
      audioSignal: { reactiveEnergy: 0.7 },
      atmosphere: { haze: 0.2 },
      backdropSource: { kind: 'backdrop' },
      dpr: 1.5,
      fallbackScene: false,
      gradientAtlas: { width: 256, height: 1, rgba: expect.any(Uint8Array) },
      height: 360,
      instances: [{ id: 'instance-a' }],
      overlaySource: { kind: 'overlay' },
      particles: [{ id: 'particle-a' }],
      particleSimulation: { reactiveEnv: 0.5 },
      postFx: { bloom: 0.4 },
      width: 640,
    })
    mockSubmitPreviewGpuFrame.mockReturnValue(6.7)
    mockBuildPreviewGpuRuntimeResult.mockReturnValue({
      gpuInstances: [{ id: 'instance-a' }],
      gpuParticles: [{ id: 'particle-a' }],
      gpuParticleSimulation: { reactiveEnv: 0.5 },
      hasPostFx: true,
      timing: {
        instancesMs: 3.2,
        particlesMs: 4.6,
        renderMs: 6.7,
      },
    })

    const result = orchestratePreviewGpuSubmission({
      backdropSource: { kind: 'backdrop' } as never,
      dpr: 1.5,
      domainResult: domainResult as never,
      gpuNode: {
        atmosphereEnabled: true,
        submitFallbackScene: false,
        submitSpectrumInstances: true,
      },
      logicalHeight: 360,
      logicalWidth: 640,
      overlaySource: { kind: 'overlay' } as never,
      webgpuRenderer: webgpuRenderer as never,
    })

    expect(mockBuildPreviewGpuExecutionPlan).toHaveBeenCalledWith({
      audioSignal: { reactiveEnergy: 0.7 },
      atmosphere: { haze: 0.2 },
      backdropSource: { kind: 'backdrop' },
      dpr: 1.5,
      logicalHeight: 360,
      logicalWidth: 640,
      overlaySource: { kind: 'overlay' },
      particles: [{ id: 'particle-a' }],
      particleSimulation: { reactiveEnv: 0.5 },
      postFx: { bloom: 0.4 },
      spectrumGradientAtlas: { width: 256, height: 1, rgba: expect.any(Uint8Array) },
      submitFallbackScene: false,
      submitSpectrumInstances: true,
      spectrumInstances: [{ id: 'instance-a' }],
    })
    expect(mockSubmitPreviewGpuFrame).toHaveBeenCalledWith({
      audioSignal: { reactiveEnergy: 0.7 },
      atmosphere: { haze: 0.2 },
      backdropSource: { kind: 'backdrop' },
      dpr: 1.5,
      fallbackScene: false,
      gradientAtlas: { width: 256, height: 1, rgba: expect.any(Uint8Array) },
      height: 360,
      instances: [{ id: 'instance-a' }],
      overlaySource: { kind: 'overlay' },
      particles: [{ id: 'particle-a' }],
      particleSimulation: { reactiveEnv: 0.5 },
      postFx: { bloom: 0.4 },
      renderer: webgpuRenderer,
      width: 640,
    })
    expect(mockBuildPreviewGpuRuntimeResult).toHaveBeenCalledWith({
      gpuInstances: [{ id: 'instance-a' }],
      gpuParticles: [{ id: 'particle-a' }],
      gpuParticleSimulation: { reactiveEnv: 0.5 },
      hasPostFx: true,
      instancesMs: 3.2,
      particlesMs: 4.6,
      renderMs: 6.7,
    })
    expect(result.timing.renderMs).toBe(6.7)
  })
})
