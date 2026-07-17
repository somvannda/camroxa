export type PreviewAnimationLoopFrame = {
  timestamp: number
  previousTimestamp: number
}

type StartPreviewAnimationLoopOptions = {
  initialTimestamp?: number
  onFrame: (frame: PreviewAnimationLoopFrame) => void
}

export function startPreviewAnimationLoop({
  initialTimestamp = performance.now(),
  onFrame,
}: StartPreviewAnimationLoopOptions): () => void {
  let animationFrameId = 0
  let previousTimestamp = initialTimestamp

  const renderFrame = (timestamp: number) => {
    const frame = {
      timestamp,
      previousTimestamp,
    }
    previousTimestamp = timestamp
    onFrame(frame)
    animationFrameId = window.requestAnimationFrame(renderFrame)
  }

  animationFrameId = window.requestAnimationFrame(renderFrame)
  return () => {
    window.cancelAnimationFrame(animationFrameId)
  }
}
