/**
 * Analyzer controller set.
 *
 * Recovered from the reference's `createControllers` block in module
 * `main~412a0a1c`: every analyzer exposes the same BASICS folder of settings,
 * with the labels, ranges, tooltips and enable-constraints below. The reference
 * shows these in the inspector when an analyzer is selected, so the same
 * descriptors are reused there.
 */

import {
  FREQUENCY_SCALES,
  WINDOW_FUNCTIONS,
  type Analyzer,
} from "./analyzers";
import {
  ContainerKind,
  PropertyKind,
  type ControllerSetups,
  type PropertyDescriptor,
} from "./types";

/** Window functions whose `windowParameter` applies. */
export const ADJUSTABLE_WINDOWS = new Set(["tukey", "kaiser", "gaussian", "power of sine"]);

const WINDOW_OPTIONS = WINDOW_FUNCTIONS;
/** Reference weighting enum: A, B, C, D and M curves, stored lowercase. */
const WEIGHTING_OPTIONS = ["a", "b", "c", "d", "m"] as const;

type Options = {
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  tooltip: string;
  constraint?: () => boolean;
};

function number(
  id: string,
  label: string,
  options: Options,
  read: () => number,
  write: (value: number) => void,
): PropertyDescriptor {
  return {
    id,
    label,
    kind: PropertyKind.Slider,
    container: ContainerKind.Controller,
    parentId: "basics",
    min: options.min,
    max: options.max,
    step: options.step ?? 1,
    unit: options.unit,
    tooltip: options.tooltip,
    constraint: options.constraint,
    animatable: true,
    read,
    write: (value) => write(Number(value)),
  };
}

function select(
  id: string,
  label: string,
  options: readonly string[],
  tooltip: string,
  read: () => string,
  write: (value: string) => void,
  constraint?: () => boolean,
): PropertyDescriptor {
  return {
    id,
    label,
    kind: PropertyKind.Select,
    container: ContainerKind.Controller,
    parentId: "basics",
    options,
    tooltip,
    constraint,
    animatable: false,
    read,
    write: (value) => write(String(value)),
  };
}

function toggle(
  id: string,
  label: string,
  tooltip: string,
  read: () => boolean,
  write: (value: boolean) => void,
): PropertyDescriptor {
  return {
    id,
    label,
    kind: PropertyKind.Boolean,
    container: ContainerKind.Controller,
    parentId: "basics",
    tooltip,
    animatable: false,
    read,
    write: (value) => write(Boolean(value)),
  };
}

/**
 * The analyzer's controllers, in the reference's order. `onChange` re-renders
 * the inspector so constraint rows enable/disable immediately.
 */
export function analyzerControllerSetups(
  analyzer: Analyzer,
  onChange: () => void = () => void 0,
): ControllerSetups {
  const filterBank = () => analyzer.sampleProvider === "filter bank";
  const goertzel = () => analyzer.sampleProvider === "goertzel";
  const adjustable = () => ADJUSTABLE_WINDOWS.has(analyzer.windowFunction);
  const cqtAdjustable = () => ADJUSTABLE_WINDOWS.has(analyzer.cqtWindowFunction ?? "hann");
  const hzFactor = () =>
    analyzer.frequencyScale === "sinh" || analyzer.frequencyScale === "nth root";

  return {
    containers: [{ id: "basics", label: "Basics", kind: ContainerKind.Folder }],
    controllers: [
      {
        id: "basics.name",
        label: "Name",
        kind: PropertyKind.Text,
        container: ContainerKind.Controller,
        parentId: "basics",
        animatable: false,
        read: () => analyzer.name,
        write: (value) => {
          analyzer.name = String(value);
          onChange();
        },
      },
      select(
        "sampleProvider",
        "Sample provider",
        ["filter bank", "goertzel"],
        "Algorithm used to calculate spectrum. Goertzel is more performance heavy.",
        () => analyzer.sampleProvider,
        (value) => {
          analyzer.sampleProvider = value === "filter bank" ? "filter bank" : "goertzel";
          onChange();
        },
      ),
      number(
        "outputMultiplier",
        "Output multiplier",
        { min: 0, max: 120, tooltip: "Boosts or attenuate output values by dB" },
        () => analyzer.outputMultiplier,
        (value) => {
          analyzer.outputMultiplier = value;
        },
      ),
      number(
        "sampleOutCount",
        "Samples out",
        {
          min: 16,
          max: 256,
          step: 4,
          tooltip:
            "Number of bands (number of bars if using spectrum bars). Higher values make the spectrum more detailed",
        },
        () => analyzer.sampleOutCount,
        (value) => {
          analyzer.sampleOutCount = Math.round(value);
        },
      ),
      number(
        "audioDuration",
        "Audio duration",
        {
          min: 0,
          max: 1000,
          tooltip: "Audio duration in milliseconds. Higher values make the waves thinner",
        },
        () => analyzer.audioDuration,
        (value) => {
          analyzer.audioDuration = value;
        },
      ),
      number(
        "audioOffset",
        "Audio offset",
        {
          min: -1000,
          max: 1000,
          tooltip:
            "Audio offset in milliseconds. Shifts reaction by a number. Negative values make the audio react later",
        },
        () => analyzer.audioOffset,
        (value) => {
          analyzer.audioOffset = value;
        },
      ),
      number(
        "audioReactionAlignment",
        "Reaction alignment",
        {
          min: -1,
          max: 1,
          step: 0.01,
          tooltip: "Shifts reaction to audio by a factor proportional to audio duration",
        },
        () => analyzer.audioReactionAlignment ?? -1,
        (value) => {
          analyzer.audioReactionAlignment = value;
        },
      ),
      {
        id: "frequencyRange",
        label: "Frequency range",
        kind: PropertyKind.Range,
        container: ContainerKind.Controller,
        parentId: "basics",
        min: 1,
        max: 2000,
        step: 1,
        tooltip: "A low frequency range is for bass heavy sounds.",
        animatable: false,
        read: () => analyzer.frequencyRange[0],
        write: (value) => {
          analyzer.frequencyRange = [
            Math.max(1, Math.min(Number(value), analyzer.frequencyRange[1])),
            analyzer.frequencyRange[1],
          ];
        },
        readRange: () => [analyzer.frequencyRange[0], analyzer.frequencyRange[1]],
        writeRange: (low, high) => {
          const clampedLow = Math.max(1, Math.min(low, high));
          const clampedHigh = Math.min(2000, Math.max(high, low));
          analyzer.frequencyRange = [clampedLow, clampedHigh];
        },
      },
      number(
        "smoothingTimeConstant",
        "Smoothing Time Constant",
        {
          min: 0,
          max: 1,
          step: 0.01,
          tooltip: "Audio reaction smoothness. Higher values make audio spectrum reacts slower",
        },
        () => analyzer.smoothingTimeConstant ?? 0,
        (value) => {
          analyzer.smoothingTimeConstant = value;
        },
      ),
      select(
        "windowFunction",
        "Window function",
        WINDOW_OPTIONS,
        "A window function is zero-valued outside of some chosen interval.",
        () => analyzer.windowFunction,
        (value) => {
          analyzer.windowFunction = value;
          onChange();
        },
      ),
      number(
        "windowParameter",
        "Window parameter",
        {
          min: 0,
          max: 10,
          step: 0.1,
          tooltip:
            "Parameter of the adjustable window functions (Tukey, Kaiser, Gaussian and Power of Sine)",
          constraint: adjustable,
        },
        () => analyzer.windowParameter ?? 1,
        (value) => {
          analyzer.windowParameter = value;
        },
      ),
      number(
        "windowSkew",
        "Window skew",
        {
          min: -2,
          max: 2,
          step: 0.1,
          tooltip: "Positive values skew the window towards earlier parts of the waveform",
        },
        () => analyzer.windowSkew ?? 0,
        (value) => {
          analyzer.windowSkew = value;
        },
      ),
      number(
        "cqtBandwidth",
        "CQT Bandwidth",
        {
          min: 2,
          max: 16,
          tooltip: "Constant-Q bandwidth, used by the filter bank",
          constraint: filterBank,
        },
        () => analyzer.cqtBandwidth ?? 8,
        (value) => {
          analyzer.cqtBandwidth = Math.round(value);
        },
      ),
      select(
        "cqtWindowFunction",
        "CQT Window function",
        WINDOW_OPTIONS,
        "Window function for the constant-Q transform",
        () => analyzer.cqtWindowFunction ?? "hann",
        (value) => {
          analyzer.cqtWindowFunction = value;
          onChange();
        },
        filterBank,
      ),
      number(
        "cqtWindowParameter",
        "CQT Window Parameter",
        {
          min: 0,
          max: 10,
          step: 0.1,
          tooltip: "CQT kernel window parameter",
          constraint: () => filterBank() && cqtAdjustable(),
        },
        () => analyzer.cqtWindowParameter ?? 1,
        (value) => {
          analyzer.cqtWindowParameter = value;
        },
      ),
      number(
        "cqtWindowSkew",
        "CQT Window skew",
        {
          min: -2,
          max: 2,
          step: 0.1,
          tooltip: "Positive values skew the window towards earlier parts of the waveform",
          constraint: filterBank,
        },
        () => analyzer.cqtWindowSkew ?? 0,
        (value) => {
          analyzer.cqtWindowSkew = value;
        },
      ),
      number(
        "perBinFrequencyTilt",
        "Per-bin frequency tilt",
        {
          min: -12,
          max: 12,
          tooltip: "Tilts frequency spectrum by dB per octave, applied to each FFT bin",
          constraint: goertzel,
        },
        () => analyzer.perBinFrequencyTilt ?? 0,
        (value) => {
          analyzer.perBinFrequencyTilt = value;
        },
      ),
      number(
        "perBandFrequencyTilt",
        "Frequency tilt",
        {
          min: -12,
          max: 12,
          tooltip: "Tilts frequency spectrum by dB per octaves. Lower values make bass react more.",
        },
        () => analyzer.perBandFrequencyTilt ?? 0,
        (value) => {
          analyzer.perBandFrequencyTilt = value;
        },
      ),
      number(
        "perBandWeightingAmount",
        "Frequency tilt amount",
        {
          min: 0,
          max: 0.1,
          step: 0.001,
          tooltip: "Strength of the frequency weighting, applied to each frequency band",
        },
        () => analyzer.perBandWeightingAmount ?? 0,
        (value) => {
          analyzer.perBandWeightingAmount = value;
        },
      ),
      select(
        "perBandWeighting",
        "Frequency weighting",
        WEIGHTING_OPTIONS,
        "Type of frequency weighting, applied to each frequency band",
        () => analyzer.perBandWeighting ?? "a",
        (value) => {
          analyzer.perBandWeighting = value;
        },
      ),
      select(
        "frequencyScale",
        "Frequency Scale",
        FREQUENCY_SCALES,
        "Frequency scales dictate the frequency bands distribution",
        () => analyzer.frequencyScale ?? "linear",
        (value) => {
          analyzer.frequencyScale = value;
          onChange();
        },
      ),
      number(
        "hzLinearFactor",
        "Hz Linear Factor",
        {
          min: 0,
          max: 1,
          step: 0.01,
          tooltip:
            "Controls the distribution of frequencies, lower values make low frequencies more dominant",
          constraint: hzFactor,
        },
        () => analyzer.hzLinearFactor ?? 0.5,
        (value) => {
          analyzer.hzLinearFactor = value;
        },
      ),
      toggle(
        "downSample",
        "Downsample",
        "Downsample increases performance but makes the analysis less precise",
        () => analyzer.downSample ?? true,
        (value) => {
          analyzer.downSample = value;
        },
      ),
    ],
  };
}
