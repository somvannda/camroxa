import { buildPreviewGpuRuntimeResult } from '@/features/video/preview/previewGpuRuntimeResult'

describe('buildPreviewGpuRuntimeResult', () => {
  it('packages the GPU runtime result and timing buckets', () => {
    const result = buildPreviewGpuRuntimeResult({
      gpuInstances: [{ id: 'instance-a' }] as never,
      gpuParticles: [{ id: 'particle-a' }] as never,
      gpuParticleSimulation: { reactiveEnv: 0.5 } as never,
      hasPostFx: true,
      instancesMs: 3.2,
      particlesMs: 4.6,
      renderMs: 6.7,
    })

    expect(result).toEqual({
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
  })
})
