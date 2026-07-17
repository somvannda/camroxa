import { createVideoDebugSender } from '@/features/video/videoDiagnostics'

describe('createVideoDebugSender', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('posts debug events to the configured endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('fetch', fetchMock)
    vi.spyOn(Date, 'now').mockReturnValue(123456)

    const send = createVideoDebugSender({
      sessionId: 'preview-slow-performance',
      runId: 'post-fix',
    })

    send({
      hypothesisId: 'A',
      msg: '[DEBUG] preview frame timing sample',
    })

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:7777/event', {
      method: 'POST',
      body: JSON.stringify({
        sessionId: 'preview-slow-performance',
        runId: 'post-fix',
        ts: 123456,
        hypothesisId: 'A',
        msg: '[DEBUG] preview frame timing sample',
      }),
    })
  })

  it('swallows transport failures without throwing', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('offline'))
    vi.stubGlobal('fetch', fetchMock)

    const send = createVideoDebugSender({
      sessionId: 'spectrum-preset-reset',
      runId: 'pre-fix',
      endpoint: 'http://127.0.0.1:9999/event',
    })

    expect(() =>
      send({
        hypothesisId: 'B',
      }),
    ).not.toThrow()
  })
})
