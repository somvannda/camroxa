/**
 * Built-in plugin DSP for the Studio chain.
 *
 * Maps a `PluginChainEntry` onto Web Audio nodes. Every effect exposes the same
 * contract so the editor can rebuild a chain without knowing which plugin it is:
 *
 *   const node = createPluginAudio(ctx, entry);
 *   source.connect(node.input);
 *   node.output.connect(next.input);
 *   node.update(params);       // live parameter change
 *   node.dispose();            // tear down (disconnect + stop modulators)
 *
 * Design rules:
 * - Never mutate the entry; `update` takes a plain parameter map.
 * - Unknown keys are ignored (the registry already sanitises them).
 * - Effects that the browser cannot implement faithfully (gate) still return a
 *   pass-through with `approximate: true` so the chain stays connected and the UI
 *   can say so, instead of silently changing the sound.
 */

import {
  getPlugin,
  sanitizeParams,
  type PluginChainEntry,
  type PluginId,
} from "@/lib/studio-plugins";

export type PluginAudioNode = {
  input: AudioNode;
  output: AudioNode;
  /** True when the implementation is an approximation of the reference effect. */
  approximate?: boolean;
  update: (params: Record<string, number>) => void;
  dispose: () => void;
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function makeCurve(amount: number): Float32Array<ArrayBuffer> {
  const samples = 1024;
  const curve = new Float32Array(new ArrayBuffer(samples * 4));
  const k = Math.max(0.001, amount) * 100;
  for (let i = 0; i < samples; i += 1) {
    const x = (i * 2) / samples - 1;
    curve[i] = ((1 + k) * x) / (1 + k * Math.abs(x));
  }
  return curve;
}

function makeImpulse(ctx: BaseAudioContext, seconds: number, decay: number): AudioBuffer {
  const rate = ctx.sampleRate;
  const length = Math.max(1, Math.floor(rate * clamp(seconds, 0.1, 10)));
  const buffer = ctx.createBuffer(2, length, rate);
  for (let channel = 0; channel < 2; channel += 1) {
    const data = buffer.getChannelData(channel);
    for (let i = 0; i < length; i += 1) {
      const t = i / length;
      data[i] = (Math.random() * 2 - 1) * Math.pow(1 - t, clamp(decay, 0.5, 8));
    }
  }
  return buffer;
}

/** Wet/dry mixer shared by delay, reverb, chorus and convolution. */
function wetDry(ctx: BaseAudioContext, mixPercent: number) {
  const input = ctx.createGain();
  const output = ctx.createGain();
  const dry = ctx.createGain();
  const wet = ctx.createGain();
  input.connect(dry).connect(output);
  const setMix = (percent: number) => {
    const wetAmount = clamp(percent, 0, 100) / 100;
    dry.gain.value = 1 - wetAmount;
    wet.gain.value = wetAmount;
  };
  setMix(mixPercent);
  return { input, output, dry, wet, setMix };
}

function bypass(ctx: BaseAudioContext): PluginAudioNode {
  const node = ctx.createGain();
  return { input: node, output: node, update: () => {}, dispose: () => node.disconnect() };
}

export function createPluginAudio(
  ctx: BaseAudioContext,
  entry: PluginChainEntry
): PluginAudioNode {
  const plugin = getPlugin(entry.pluginId);
  if (!plugin) return bypass(ctx);
  const params = sanitizeParams(entry.pluginId as PluginId, entry.params);
  const id = entry.pluginId;

  if (id === "compressor" || id === "limiter") {
    const comp = ctx.createDynamicsCompressor();
    const makeup = ctx.createGain();
    comp.connect(makeup);

    const apply = (p: Record<string, number>) => {
      if (id === "compressor") {
        comp.threshold.value = clamp(p.threshold ?? -18, -100, 0);
        comp.ratio.value = clamp(p.ratio ?? 4, 1, 20);
        comp.knee.value = clamp(p.knee ?? 6, 0, 40);
        comp.attack.value = clamp((p.attack ?? 10) / 1000, 0, 1);
        comp.release.value = clamp((p.release ?? 120) / 1000, 0, 1);
        makeup.gain.value = Math.pow(10, clamp(p.gain ?? 0, -24, 24) / 20);
      } else {
        comp.threshold.value = clamp(p.preGain != null ? -1 : -1, -100, 0);
        comp.ratio.value = 20;
        comp.knee.value = 0;
        comp.attack.value = clamp((p.attack ?? 1) / 1000, 0, 1);
        comp.release.value = clamp((p.release ?? 60) / 1000, 0, 1);
        makeup.gain.value = Math.pow(10, clamp(p.preGain ?? 0, -24, 24) / 20);
      }
    };

    apply(params);
    return {
      input: comp,
      output: makeup,
      update: apply,
      dispose: () => {
        comp.disconnect();
        makeup.disconnect();
      },
    };
  }

  if (id === "eq") {
    const band = ctx.createBiquadFilter();
    band.type = "peaking";
    const apply = (p: Record<string, number>) => {
      band.frequency.value = clamp(p["band1.freq"] ?? 1000, 20, 20000);
      band.Q.value = clamp(p["band1.q"] ?? 1, 0.0001, 30);
      band.gain.value = clamp(p["band1.gain"] ?? 0, -40, 40);
    };
    apply(params);
    return {
      input: band,
      output: band,
      update: apply,
      dispose: () => band.disconnect(),
    };
  }

  if (id === "distortion") {
    const shaper = ctx.createWaveShaper();
    const tone = ctx.createBiquadFilter();
    tone.type = "lowpass";
    shaper.connect(tone);
    const apply = (p: Record<string, number>) => {
      shaper.curve = makeCurve(clamp((p.drive ?? 30) / 100, 0, 1));
      shaper.oversample = "4x";
      tone.frequency.value = clamp(p.freq ?? 8000, 200, 20000);
    };
    apply(params);
    return {
      input: shaper,
      output: tone,
      update: apply,
      dispose: () => {
        shaper.disconnect();
        tone.disconnect();
      },
    };
  }

  if (id === "delay") {
    const mix = wetDry(ctx, params.mix ?? 25);
    const delay = ctx.createDelay(5);
    const feedback = ctx.createGain();
    const lowCut = ctx.createBiquadFilter();
    const highCut = ctx.createBiquadFilter();
    lowCut.type = "highpass";
    highCut.type = "lowpass";

    mix.input.connect(delay);
    delay.connect(lowCut).connect(highCut).connect(feedback).connect(delay);
    highCut.connect(mix.wet).connect(mix.output);

    const apply = (p: Record<string, number>) => {
      delay.delayTime.value = clamp((p.time ?? 350) / 1000, 0.001, 5);
      feedback.gain.value = clamp((p.feedback ?? 35) / 100, 0, 0.95);
      lowCut.frequency.value = clamp(p.lowCut ?? 120, 20, 20000);
      highCut.frequency.value = clamp(p.highCut ?? 12000, 100, 20000);
      mix.setMix(p.mix ?? 25);
    };
    apply(params);
    return {
      input: mix.input,
      output: mix.output,
      update: apply,
      dispose: () => {
        [delay, feedback, lowCut, highCut, mix.input, mix.output].forEach((n) => n.disconnect());
      },
    };
  }

  if (id === "reverb" || id === "convolution") {
    const mix = wetDry(ctx, params.mix ?? 25);
    const convolver = ctx.createConvolver();
    const lowCut = ctx.createBiquadFilter();
    const highCut = ctx.createBiquadFilter();
    lowCut.type = "highpass";
    highCut.type = "lowpass";

    mix.input.connect(convolver).connect(lowCut).connect(highCut).connect(mix.wet).connect(mix.output);

    let renderedFor = -1;
    const apply = (p: Record<string, number>) => {
      const seconds = p.time ?? 2.4;
      if (Math.abs(seconds - renderedFor) > 0.05) {
        convolver.buffer = makeImpulse(ctx, seconds, 3);
        renderedFor = seconds;
      }
      lowCut.frequency.value = clamp(p.lowCut ?? 120, 20, 20000);
      highCut.frequency.value = clamp(p.highCut ?? 14000, 100, 20000);
      mix.setMix(p.mix ?? 25);
    };
    apply(params);
    return {
      input: mix.input,
      output: mix.output,
      approximate: id === "reverb",
      update: apply,
      dispose: () => {
        [convolver, lowCut, highCut, mix.input, mix.output].forEach((n) => n.disconnect());
      },
    };
  }

  if (id === "chorus") {
    const mix = wetDry(ctx, params.mix ?? 30);
    const delay = ctx.createDelay(0.1);
    const lfo = ctx.createOscillator();
    const depth = ctx.createGain();
    lfo.type = "sine";
    lfo.connect(depth).connect(delay.delayTime);
    mix.input.connect(delay).connect(mix.wet).connect(mix.output);
    lfo.start();

    const apply = (p: Record<string, number>) => {
      lfo.frequency.value = clamp(p.rate ?? 0.8, 0.05, 10);
      depth.gain.value = (clamp(p.depth ?? 40, 0, 100) / 100) * 0.005;
      delay.delayTime.value = 0.02;
      mix.setMix(p.mix ?? 30);
    };
    apply(params);
    return {
      input: mix.input,
      output: mix.output,
      update: apply,
      dispose: () => {
        try {
          lfo.stop();
        } catch {
          /* already stopped */
        }
        [delay, depth, mix.input, mix.output].forEach((n) => n.disconnect());
      },
    };
  }

  // Gate has no native node; keep the chain connected and state the limitation.
  return { ...bypass(ctx), approximate: true };
}

/** Build a full chain: source → plugin[0] → … → plugin[n] → destination. */
export function buildPluginChain(
  ctx: BaseAudioContext,
  entries: PluginChainEntry[]
): { input: AudioNode; output: AudioNode; update: (entryId: string, params: Record<string, number>) => void; dispose: () => void } {
  const nodes = entries
    .filter((entry) => !entry.bypassed)
    .map((entry) => ({ entry, node: createPluginAudio(ctx, entry) }));

  if (!nodes.length) {
    const pass = ctx.createGain();
    return { input: pass, output: pass, update: () => {}, dispose: () => pass.disconnect() };
  }

  for (let i = 0; i < nodes.length - 1; i += 1) {
    nodes[i].node.output.connect(nodes[i + 1].node.input);
  }

  return {
    input: nodes[0].node.input,
    output: nodes[nodes.length - 1].node.output,
    update: (entryId, params) => {
      const match = nodes.find((n) => n.entry.entryId === entryId);
      match?.node.update(params);
    },
    dispose: () => nodes.forEach((n) => n.node.dispose()),
  };
}
