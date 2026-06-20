import React from "react";
import { useSpectrumTemplateStore } from "@/store/spectrumTemplateStore";
import { Slider } from "@/components/ui/Slider";
import { Select } from "@/components/ui/Select";

export const RightPanel: React.FC = () => {
  const { template, updateLayer } = useSpectrumTemplateStore();

  // For now, just show the settings of the first layer
  const layer = template.layers[0];

  if (!layer) {
    return (
      <div className="w-80 h-full border-l border-slate-800 bg-slate-900 p-4">
        <p className="text-slate-400 text-sm">No layers found.</p>
      </div>
    );
  }

  const updateColor = (updates: any) => {
    updateLayer(layer.id, { color: { ...layer.color, ...updates } });
  };

  return (
    <div className="w-80 h-full border-l border-slate-800 bg-slate-900 overflow-y-auto flex flex-col p-4 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1">Layer Inspector</h2>
        <p className="text-xs text-slate-400 mb-4">Editing: {layer.name}</p>
        
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-xs text-slate-400">Gravity / Anchor</label>
            <Select 
              value={layer.gravity || "bottom"} 
              onChange={(e: any) => updateLayer(layer.id, { gravity: e.target.value })}
              className="w-full"
            >
              <option value="bottom">Bottom (Rabbit Ears on Top)</option>
              <option value="top">Top</option>
              <option value="left">Left</option>
              <option value="right">Right</option>
            </Select>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-200">Curve (180° Half Circle)</label>
              <input 
                type="checkbox" 
                checked={layer.curved} 
                onChange={(e) => updateLayer(layer.id, { curved: e.target.checked })}
                className="rounded border-slate-700 bg-slate-900"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-200">Mirror (360° or Symmetry)</label>
              <input 
                type="checkbox" 
                checked={layer.mirrored} 
                onChange={(e) => updateLayer(layer.id, { mirrored: e.target.checked })}
                className="rounded border-slate-700 bg-slate-900"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-200">Fill Circle</label>
              <input 
                type="checkbox" 
                checked={layer.fillCircle} 
                onChange={(e) => updateLayer(layer.id, { fillCircle: e.target.checked })}
                className="rounded border-slate-700 bg-slate-900"
              />
            </div>
            {layer.fillCircle && (
              <div className="space-y-2">
                <label className="text-xs text-slate-400">Fill Color</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={layer.fillColor}
                    onChange={(e) => updateLayer(layer.id, { fillColor: e.target.value })}
                    className="h-8 w-10 rounded border border-slate-200/10 bg-transparent"
                  />
                  <input 
                    type="text"
                    className="flex-1 h-8 rounded-md border border-slate-200/10 bg-slate-950/40 px-3 text-sm text-slate-100 focus:outline-none"
                    value={layer.fillColor} 
                    onChange={(e) => updateLayer(layer.id, { fillColor: e.target.value })}
                  />
                </div>
              </div>
            )}
          </div>

          <div className="space-y-1">
            <label className="text-xs text-slate-400">Bar Width / Stroke ({layer.barWidth})</label>
            <Slider 
              min={1} max={50} step={1} 
              value={layer.barWidth} 
              onValueChange={(v) => updateLayer(layer.id, { barWidth: v })}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-400">Spike Height / Length ({layer.thickness})</label>
            <Slider 
              min={1} max={30} step={1} 
              value={layer.thickness} 
              onValueChange={(v) => updateLayer(layer.id, { thickness: v })}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-400">Opacity ({layer.opacity.toFixed(2)})</label>
            <Slider 
              min={0} max={1} step={0.01} 
              value={layer.opacity} 
              onValueChange={(v) => updateLayer(layer.id, { opacity: v })}
            />
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-slate-300 mb-3 uppercase tracking-wider">Color Engine</h3>
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-xs text-slate-400">Mode</label>
            <Select 
              value={layer.color.mode} 
              onChange={(e: any) => updateColor({ mode: e.target.value })}
              className="w-full"
            >
              <option value="solid">Solid Color</option>
              <option value="gradient">Gradient</option>
            </Select>
          </div>

          {layer.color.mode === "solid" ? (
            <div className="space-y-2">
              <label className="text-xs text-slate-400">Color</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={layer.color.solidColor}
                  onChange={(e) => updateColor({ solidColor: e.target.value })}
                  className="h-8 w-10 rounded border border-slate-200/10 bg-transparent"
                />
                <input 
                  type="text"
                  className="flex-1 h-8 rounded-md border border-slate-200/10 bg-slate-950/40 px-3 text-sm text-slate-100 focus:outline-none"
                  value={layer.color.solidColor} 
                  onChange={(e) => updateColor({ solidColor: e.target.value })}
                />
              </div>
            </div>
          ) : (
            <>
              <div className="space-y-2">
                <label className="text-xs text-slate-400">Direction</label>
                <Select 
                  value={layer.color.gradientDirection} 
                  onChange={(e: any) => updateColor({ gradientDirection: e.target.value })}
                  className="w-full"
                >
                  <option value="left-to-right">Left to Right</option>
                  <option value="top-to-bottom">Top to Bottom</option>
                  <option value="diagonal">Diagonal</option>
                  <option value="radial">Radial</option>
                  <option value="circular">Circular</option>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-xs text-slate-400">Preset Gradients</label>
                <Select 
                  value={layer.color.gradientColors.join(",")} 
                  onChange={(e: any) => updateColor({ gradientColors: e.target.value.split(",") })}
                  className="w-full"
                >
                  <option value="#ff00ff,#00ffff">Cyber Blue</option>
                  <option value="#ff8800,#ff0000">EDM Fire</option>
                  <option value="#00ff00,#ffff00">Toxic</option>
                  <option value="#8a2be2,#4b0082">Galaxy</option>
                  <option value="#00ffff,#ffffff">Ice</option>
                  <option value="#ff4500,#ff1493">Lava</option>
                  <option value="#ff8c00,#ff69b4">Sunset</option>
                  <option value="#ff0000,#00ff00,#0000ff">RGB Flow</option>
                </Select>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
