declare module "butterchurn" {
  const butterchurn: {
    createVisualizer(context: AudioContext | null, canvas: HTMLCanvasElement, options: { width: number; height: number }): any;
  };
  export default butterchurn;
}

declare module "butterchurn-presets" {
  const presets: { getPresets(): Record<string, unknown> };
  export default presets;
}
