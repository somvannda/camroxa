export type VideoDebugPayload = Record<string, unknown>

type CreateVideoDebugSenderOptions = {
  sessionId: string
  runId: string
  endpoint?: string
}

const DEFAULT_DEBUG_ENDPOINT = 'http://127.0.0.1:7777/event'

export function createVideoDebugSender({
  sessionId,
  runId,
  endpoint = DEFAULT_DEBUG_ENDPOINT,
}: CreateVideoDebugSenderOptions): (payload: VideoDebugPayload) => void {
  return (payload: VideoDebugPayload) => {
    if (typeof fetch !== 'function') {
      return
    }

    fetch(endpoint, {
      method: 'POST',
      body: JSON.stringify({
        sessionId,
        runId,
        ts: Date.now(),
        ...payload,
      }),
    }).catch(() => undefined)
  }
}
