export interface VizzyButterchurnVisualizer {
  loadPreset(preset: unknown, blendTime?: number): void | Promise<void>;
  render(options: {
    audioLevels: {
      timeByteArray: Uint8Array;
      timeByteArrayL: Uint8Array;
      timeByteArrayR: Uint8Array;
    };
    elapsedTime: number;
  }): void;
  setRendererSize(width: number, height: number): void;
  setOutputAA(enabled: boolean): void;
  renderer?: {
    gl?: WebGLRenderingContext;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

declare const Butterchurn: {
  createVisualizer(
    audioContext: AudioContext | null,
    canvas: HTMLCanvasElement,
    options: { width: number; height: number },
  ): VizzyButterchurnVisualizer;
};

export default Butterchurn;
