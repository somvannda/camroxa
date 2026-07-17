import {
  analyseAudioSpectrumFrame,
  buildAudioSpectrumFrameFromFeatures,
  createAudioSpectrumLogMapping,
  type AudioSpectrumFeatures,
  type AudioSpectrumEnvelope,
} from '@/features/video/preview/audioSpectrumAnalysis'

function createEnvelope(): AudioSpectrumEnvelope {
  return {
    bassFast: 0,
    bassSlow: 0,
    kick: 0,
    drop: 0,
    level: 0,
    energyBands: null,
    slowBands: null,
    floorBands: null,
    transientBands: null,
    onsetBands: null,
    previousBands: null,
  }
}

describe('audioSpectrumAnalysis', () => {
  it('preserves localized spikes for orbital bars instead of flattening the full ring', () => {
    const mapping = createAudioSpectrumLogMapping(512)
    const frequencyData = new Uint8Array(512).fill(36)

    for (let index = 12; index <= 18; index += 1) {
      frequencyData[index] = 240
    }

    const frame = analyseAudioSpectrumFrame(
      frequencyData,
      1.2,
      1,
      1,
      0.2,
      1 / 60,
      mapping,
      createEnvelope(),
      'orbital-bars',
    )

    expect(frame).not.toBeNull()
    const values = frame?.renderValues ?? new Float32Array()
    const maxValue = Math.max(...values)
    const averageValue = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0

    expect(maxValue).toBeGreaterThan(averageValue * 2.4)
    expect(maxValue).toBeGreaterThan(0.75)
  })

  it('builds strong reactive energy on bass onset for flying glow without losing the full ring bed', () => {
    const mapping = createAudioSpectrumLogMapping(512)
    const frequencyData = new Uint8Array(512).fill(24)

    for (let index = 1; index <= 10; index += 1) {
      frequencyData[index] = 255
    }

    const envelope = createEnvelope()
    const frame = analyseAudioSpectrumFrame(
      frequencyData,
      1.4,
      1.1,
      1.15,
      1,
      1 / 60,
      mapping,
      envelope,
      'flying-glow',
    )

    expect(frame).not.toBeNull()
    expect(frame?.reactiveEnergy ?? 0).toBeGreaterThan(0.12)
    expect((frame?.renderValues[0] ?? 0) > 0 || (frame?.renderValues[10] ?? 0) > 0).toBe(true)
    expect(envelope.kick).toBeGreaterThan(0)
  })

  it('raises local onset spikes above a sustained bed without turning the full strip into one pulse', () => {
    const mapping = createAudioSpectrumLogMapping(512)
    const envelope = createEnvelope()
    const baseBed = new Uint8Array(512).fill(68)
    const onsetFrame = new Uint8Array(512).fill(68)

    for (let index = 20; index <= 26; index += 1) {
      onsetFrame[index] = 255
    }

    analyseAudioSpectrumFrame(baseBed, 1.1, 1.2, 1.25, 0.3, 1 / 60, mapping, envelope, 'straight-bars')
    const frame = analyseAudioSpectrumFrame(
      onsetFrame,
      1.1,
      1.2,
      1.25,
      0.3,
      1 / 60,
      mapping,
      envelope,
      'straight-bars',
    )

    expect(frame).not.toBeNull()
    const values = frame?.renderValues ?? new Float32Array()
    const maxValue = Math.max(...values)
    const averageValue = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0

    expect(maxValue).toBeGreaterThan(averageValue * 1.8)
    expect(maxValue).toBeGreaterThan(0.72)
  })

  it('applies onset-delta spike separation across the remaining curated spectrum families', () => {
    const mapping = createAudioSpectrumLogMapping(512)
    const styles = ['dot-matrix', 'wave-ribbon', 'liquid-mass', 'halo-stack'] as const

    for (const style of styles) {
      const envelope = createEnvelope()
      const baseBed = new Uint8Array(512).fill(70)
      const onsetFrame = new Uint8Array(512).fill(70)

      for (let index = 18; index <= 24; index += 1) {
        onsetFrame[index] = 255
      }

      analyseAudioSpectrumFrame(baseBed, 1.15, 1.1, 1.2, 0.35, 1 / 60, mapping, envelope, style)
      const frame = analyseAudioSpectrumFrame(onsetFrame, 1.15, 1.1, 1.2, 0.35, 1 / 60, mapping, envelope, style)

      expect(frame).not.toBeNull()
      const values = frame?.renderValues ?? new Float32Array()
      const maxValue = Math.max(...values)
      const averageValue = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0

      expect(maxValue, `${style} should show local onset separation`).toBeGreaterThan(averageValue * 1.3)
      expect(maxValue, `${style} should keep usable height range`).toBeGreaterThan(0.5)
    }
  })

  it('makes kick impact visibly affect rendered values across the generic curated families', () => {
    const mapping = createAudioSpectrumLogMapping(512)
    const styles = ['orbital-bars', 'dot-matrix', 'wave-ribbon', 'liquid-mass', 'halo-stack'] as const
    const bassFrame = new Uint8Array(512).fill(64)

    for (let index = 1; index <= 9; index += 1) {
      bassFrame[index] = 255
    }
    for (let index = 18; index <= 24; index += 1) {
      bassFrame[index] = 184
    }

    for (const style of styles) {
      const noKick = analyseAudioSpectrumFrame(bassFrame, 1.1, 1.1, 1.1, 0, 1 / 60, mapping, createEnvelope(), style)
      const boostedKick = analyseAudioSpectrumFrame(
        bassFrame,
        1.1,
        1.1,
        1.1,
        2,
        1 / 60,
        mapping,
        createEnvelope(),
        style,
      )

      expect(noKick).not.toBeNull()
      expect(boostedKick).not.toBeNull()

      const baseValues = noKick?.renderValues ?? new Float32Array()
      const boostedValues = boostedKick?.renderValues ?? new Float32Array()
      const baseAverage = baseValues.length ? baseValues.reduce((sum, value) => sum + value, 0) / baseValues.length : 0
      const boostedAverage = boostedValues.length
        ? boostedValues.reduce((sum, value) => sum + value, 0) / boostedValues.length
        : 0
      const baseMax = Math.max(...baseValues)
      const boostedMax = Math.max(...boostedValues)

      expect(
        boostedAverage > baseAverage + 0.01 || boostedMax > baseMax + 0.02,
        `${style} should respond visibly when Kick Impact increases`,
      ).toBe(true)
    }
  })

  it('keeps flying glow alive on a normal music bed while still flaring much harder on kick onset', () => {
    const mapping = createAudioSpectrumLogMapping(512)
    const calmEnvelope = createEnvelope()
    const kickEnvelope = createEnvelope()
    const calmFrame = new Uint8Array(512).fill(54)
    const kickFrame = new Uint8Array(512).fill(54)

    for (let index = 18; index <= 40; index += 1) {
      calmFrame[index] = 110
      kickFrame[index] = 110
    }
    for (let index = 1; index <= 8; index += 1) {
      kickFrame[index] = 255
    }

    const calm = analyseAudioSpectrumFrame(calmFrame, 1.2, 1.1, 1.15, 1, 1 / 60, mapping, calmEnvelope, 'flying-glow')
    const kick = analyseAudioSpectrumFrame(kickFrame, 1.2, 1.1, 1.15, 1, 1 / 60, mapping, kickEnvelope, 'flying-glow')

    expect(calm).not.toBeNull()
    expect(kick).not.toBeNull()

    const calmValues = calm?.renderValues ?? new Float32Array()
    const kickValues = kick?.renderValues ?? new Float32Array()
    const calmAverage = calmValues.length ? calmValues.reduce((sum, value) => sum + value, 0) / calmValues.length : 0
    const kickAverage = kickValues.length ? kickValues.reduce((sum, value) => sum + value, 0) / kickValues.length : 0
    let maxLift = 0
    for (let index = 0; index < Math.min(calmValues.length, kickValues.length); index += 1) {
      maxLift = Math.max(maxLift, (kickValues[index] ?? 0) - (calmValues[index] ?? 0))
    }

    expect(calmAverage).toBeGreaterThan(0.06)
    expect(kickAverage).toBeGreaterThan(calmAverage * 1.18)
    expect(maxLift).toBeGreaterThan(0.16)
    expect((kick?.reactiveEnergy ?? 0) - (calm?.reactiveEnergy ?? 0)).toBeGreaterThan(0.12)
    expect((kick?.styleMotionDrive ?? 0) - (calm?.styleMotionDrive ?? 0)).toBeGreaterThan(0.03)
    expect((kick?.styleTriggerDrive ?? 0) - (calm?.styleTriggerDrive ?? 0)).toBeGreaterThan(0.08)
  })

  it('lets flying glow pick up low-end bass phrasing even when there is no extreme kick spike', () => {
    const mapping = createAudioSpectrumLogMapping(512)
    const bassEnvelope = createEnvelope()
    const quietEnvelope = createEnvelope()
    const quietFrame = new Uint8Array(512).fill(34)
    const bassFrame = new Uint8Array(512).fill(34)

    for (let index = 1; index <= 12; index += 1) {
      bassFrame[index] = 168
    }
    for (let index = 13; index <= 22; index += 1) {
      bassFrame[index] = 112
    }

    const quiet = analyseAudioSpectrumFrame(quietFrame, 1.2, 1.1, 1.15, 1, 1 / 60, mapping, quietEnvelope, 'flying-glow')
    analyseAudioSpectrumFrame(bassFrame, 1.2, 1.1, 1.15, 1, 1 / 60, mapping, bassEnvelope, 'flying-glow')
    const bass = analyseAudioSpectrumFrame(bassFrame, 1.2, 1.1, 1.15, 1, 1 / 60, mapping, bassEnvelope, 'flying-glow')

    expect(quiet).not.toBeNull()
    expect(bass).not.toBeNull()
    expect((bass?.styleMotionDrive ?? 0) - (quiet?.styleMotionDrive ?? 0)).toBeGreaterThan(0.08)
    expect((bass?.reactiveEnergy ?? 0) - (quiet?.reactiveEnergy ?? 0)).toBeGreaterThan(0.04)
  })

  it('lets bass emphasis build a thicker low-end bed without flattening the whole strip', () => {
    const mapping = createAudioSpectrumLogMapping(512)
    const bassFrame = new Uint8Array(512).fill(44)

    for (let index = 1; index <= 14; index += 1) {
      bassFrame[index] = 220
    }
    for (let index = 18; index <= 30; index += 1) {
      bassFrame[index] = 104
    }

    const neutral = analyseAudioSpectrumFrame(
      bassFrame,
      1.15,
      1.05,
      1.05,
      0.8,
      1 / 60,
      mapping,
      createEnvelope(),
      'straight-bars',
      1,
      1,
      1,
      0,
    )
    const boosted = analyseAudioSpectrumFrame(
      bassFrame,
      1.15,
      1.05,
      1.05,
      0.8,
      1 / 60,
      mapping,
      createEnvelope(),
      'straight-bars',
      1,
      1.8,
      1,
      0,
    )

    expect(neutral).not.toBeNull()
    expect(boosted).not.toBeNull()

    const neutralBass = Array.from(neutral?.renderValues.slice(0, 8) ?? []).reduce((sum, value) => sum + value, 0)
    const boostedBass = Array.from(boosted?.renderValues.slice(0, 8) ?? []).reduce((sum, value) => sum + value, 0)
    const boostedUpper = Array.from(boosted?.renderValues.slice(20, 28) ?? []).reduce((sum, value) => sum + value, 0)

    expect(boostedBass).toBeGreaterThan(neutralBass * 1.08)
    expect(boostedBass / Math.max(0.0001, neutralBass)).toBeGreaterThan(
      boostedUpper / Math.max(0.0001, Array.from(neutral?.renderValues.slice(20, 28) ?? []).reduce((sum, value) => sum + value, 0)),
    )
    expect((boosted?.reactiveEnergy ?? 0)).toBeGreaterThanOrEqual(neutral?.reactiveEnergy ?? 0)
  })

  it('lets peak hold blend keep more tail after a strong onset', () => {
    const features: AudioSpectrumFeatures = {
      energyBands: new Float32Array(64).fill(0.12),
      peakHoldBands: new Float32Array(64).fill(0.46),
      transientBands: new Float32Array(64).fill(0.08),
      onsetBands: new Float32Array(64).fill(0.06),
      framePeak: 0.52,
      averageEnergy: 0.12,
      averageTransient: 0.08,
      averageOnset: 0.06,
      level: 0.18,
      kick: 0.16,
      drop: 0.12,
    }

    for (let index = 20; index <= 26; index += 1) {
      features.energyBands[index] = 0.2
      features.peakHoldBands[index] = 0.9
      features.transientBands[index] = 0.16
      features.onsetBands[index] = 0.14
    }

    const noHold = buildAudioSpectrumFrameFromFeatures(features, 1.1, 1.15, 0.7, 'wave-ribbon', 1, 1, 1, 0)
    const held = buildAudioSpectrumFrameFromFeatures(features, 1.1, 1.15, 0.7, 'wave-ribbon', 1, 1, 1, 0.7)

    expect(noHold).not.toBeNull()
    expect(held).not.toBeNull()

    const noHoldAverage =
      Array.from(noHold?.renderValues ?? []).reduce((sum, value) => sum + value, 0) / (noHold?.renderValues.length || 1)
    const heldAverage =
      Array.from(held?.renderValues ?? []).reduce((sum, value) => sum + value, 0) / (held?.renderValues.length || 1)
    expect(heldAverage).toBeGreaterThan(noHoldAverage + 0.005)
  })

  it('lets bar height raise the final rendered spectrum height directly', () => {
    const mapping = createAudioSpectrumLogMapping(512)
    const frame = new Uint8Array(512).fill(56)

    for (let index = 4; index <= 18; index += 1) {
      frame[index] = 210
    }

    const normal = analyseAudioSpectrumFrame(
      frame,
      1.2,
      1.15,
      1.1,
      0.9,
      1 / 60,
      mapping,
      createEnvelope(),
      'straight-bars',
      1,
      1,
      1,
      0,
    )
    const tall = analyseAudioSpectrumFrame(
      frame,
      1.2,
      1.15,
      1.1,
      0.9,
      1 / 60,
      mapping,
      createEnvelope(),
      'straight-bars',
      2,
      1,
      1,
      0,
    )

    expect(normal).not.toBeNull()
    expect(tall).not.toBeNull()

    const normalAverage =
      Array.from(normal?.renderValues ?? []).reduce((sum, value) => sum + value, 0) / (normal?.renderValues.length || 1)
    const tallAverage =
      Array.from(tall?.renderValues ?? []).reduce((sum, value) => sum + value, 0) / (tall?.renderValues.length || 1)

    expect(tallAverage).toBeGreaterThan(normalAverage * 1.08)
  })
})
