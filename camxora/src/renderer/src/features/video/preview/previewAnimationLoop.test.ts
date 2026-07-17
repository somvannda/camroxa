import { startPreviewAnimationLoop } from '@/features/video/preview/previewAnimationLoop'

describe('startPreviewAnimationLoop', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('passes the previous timestamp into each scheduled frame', () => {
    const callbacks: FrameRequestCallback[] = []
    const requestAnimationFrameMock = vi
      .spyOn(window, 'requestAnimationFrame')
      .mockImplementation((callback: FrameRequestCallback) => {
        callbacks.push(callback)
        return callbacks.length
      })
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => undefined)

    const onFrame = vi.fn()
    startPreviewAnimationLoop({
      initialTimestamp: 100,
      onFrame,
    })

    callbacks[0]?.(116)
    callbacks[1]?.(132)

    expect(requestAnimationFrameMock).toHaveBeenCalledTimes(3)
    expect(onFrame).toHaveBeenNthCalledWith(1, {
      timestamp: 116,
      previousTimestamp: 100,
    })
    expect(onFrame).toHaveBeenNthCalledWith(2, {
      timestamp: 132,
      previousTimestamp: 116,
    })
  })

  it('cancels the most recent scheduled frame on stop', () => {
    const requestAnimationFrameMock = vi
      .spyOn(window, 'requestAnimationFrame')
      .mockImplementation(() => 7)
    const cancelAnimationFrameMock = vi
      .spyOn(window, 'cancelAnimationFrame')
      .mockImplementation(() => undefined)

    const stop = startPreviewAnimationLoop({
      initialTimestamp: 50,
      onFrame: vi.fn(),
    })
    stop()

    expect(requestAnimationFrameMock).toHaveBeenCalledTimes(1)
    expect(cancelAnimationFrameMock).toHaveBeenCalledWith(7)
  })
})
