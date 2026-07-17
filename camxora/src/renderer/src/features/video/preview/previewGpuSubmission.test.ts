import { submitPreviewGpuFrame } from '@/features/video/preview/previewGpuSubmission'

describe('submitPreviewGpuFrame', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('submits the final frame to the WebGPU renderer and returns render timing', () => {
    const renderer = {
      render: vi.fn(),
    }

    vi.spyOn(performance, 'now')
      .mockReturnValueOnce(100)
      .mockReturnValueOnce(108.5)

    const instances = [{ id: 'instance-a' }] as never
    const particles = [{ id: 'particle-a' }] as never

    const renderMs = submitPreviewGpuFrame({
      audioSignal: { reactiveEnergy: 0.7 } as never,
      atmosphere: { haze: 0.2 } as never,
      backdropSource: { kind: 'backdrop' } as never,
      dpr: 1.5,
      fallbackScene: false,
      gradientAtlas: { width: 256, height: 1, rgba: new Uint8Array(256 * 4) } as never,
      height: 360,
      instances,
      overlaySource: { kind: 'overlay' } as never,
      particles,
      particleSimulation: { reactiveEnv: 0.5 } as never,
      postFx: { bloom: 0.4 } as never,
      renderer: renderer as never,
      width: 640,
    })

    expect(renderer.render).toHaveBeenCalledWith({
      width: 640,
      height: 360,
      dpr: 1.5,
      audioSignal: { reactiveEnergy: 0.7 },
      spectrumGradientAtlas: { width: 256, height: 1, rgba: expect.any(Uint8Array) },
      instances,
      particles,
      particleSimulation: { reactiveEnv: 0.5 },
      backdropSource: { kind: 'backdrop' },
      overlaySource: { kind: 'overlay' },
      atmosphere: { haze: 0.2 },
      fallbackScene: false,
      postFx: { bloom: 0.4 },
    })
    expect(renderMs).toBe(8.5)
  })

  it('returns zero when no renderer is available', () => {
    const renderMs = submitPreviewGpuFrame({
      audioSignal: null,
      atmosphere: null,
      backdropSource: null,
      dpr: 1,
      fallbackScene: true,
      gradientAtlas: null,
      height: 720,
      instances: [],
      overlaySource: null,
      particles: [],
      particleSimulation: null,
      postFx: null,
      renderer: null,
      width: 1280,
    })

    expect(renderMs).toBe(0)
  })
})
