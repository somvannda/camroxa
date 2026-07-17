export type PreviewGpuAudioSignalFrame = {
  timeSec: number
  reactiveEnergy: number
  kick: number
  drop: number
  averageEnergy: number
  averageTransient: number
  averageOnset: number
  styleMotionDrive: number
  styleTriggerDrive: number
  renderValues: number[]
  mirroredRenderValues: number[]
  peakHoldValues: number[]
  mirroredPeakHoldValues: number[]
  energyBands: Float32Array
  peakHoldBands: Float32Array
  transientBands: Float32Array
  onsetBands: Float32Array
}
