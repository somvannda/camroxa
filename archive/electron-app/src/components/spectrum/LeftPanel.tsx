import React, { useState, useEffect } from "react";
import { useSpectrumTemplateStore } from "@/store/spectrumTemplateStore";
import { Select } from "@/components/ui/Select";
import { Slider } from "@/components/ui/Slider";
import { Save, Download } from "lucide-react";
import { useAppStore } from "@/store/useAppStore";

export const LeftPanel: React.FC = () => {
  const { template, updateTemplate, setTemplate } = useSpectrumTemplateStore();
  const { setFooterStatus } = useAppStore();
  const [saveName, setSaveName] = useState(template.templateName || "My Template");

  const [templateList, setTemplateList] = useState<any[]>([]);

  const fetchTemplates = async () => {
    if (!(window as any).mgApi?.videoTemplatesList) return;
    const listResult = await (window as any).mgApi.videoTemplatesList();
    if (!("message" in listResult) && listResult.items) {
      setTemplateList(listResult.items);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, []);

  const handleSave = async () => {
    if (!(window as any).mgApi?.videoTemplatesSave) return;
    const finalName = saveName.trim() || "My Template";
    const toSave = { ...template, templateName: finalName };
    const r = await (window as any).mgApi.videoTemplatesSave({
      label: finalName,
      template: toSave
    });
    if ("message" in r) {
      setFooterStatus(`Failed to save: ${r.message}`, null);
    } else {
      setFooterStatus(`Saved template: ${finalName}`, null);
      updateTemplate({ templateName: finalName });
      fetchTemplates(); // Refresh the list
    }
  };

  const handleLoad = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const path = e.target.value;
    if (!path) return;
    if (!(window as any).mgApi?.videoTemplatesRead) return;
    
    const r = await (window as any).mgApi.videoTemplatesRead({ path });
    if (!("message" in r) && r.template) {
      setTemplate(r.template);
      setSaveName(r.template.templateName || "Loaded Template");
      setFooterStatus(`Loaded template: ${r.template.templateName || "Loaded"}`, null);
    } else if ("message" in r) {
      setFooterStatus(`Failed to load: ${r.message}`, null);
    }
    
    // Reset the select back to default option so the user can re-select if needed
    e.target.value = "";
  };

  return (
    <div className="w-80 h-full border-r border-slate-800 bg-slate-900 overflow-y-auto flex flex-col p-4 space-y-6">
      {/* Save/Load Header */}
      <div className="space-y-3 pb-4 border-b border-slate-800">
        <input 
          type="text"
          className="w-full h-9 rounded-md border border-slate-200/10 bg-slate-950/40 px-3 text-sm text-slate-100 focus:outline-none"
          value={saveName}
          onChange={(e) => setSaveName(e.target.value)}
          placeholder="Template Name..."
        />
        <div className="flex items-center gap-2">
          <button 
            className="flex-1 flex items-center justify-center gap-2 h-9 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors"
            onClick={handleSave}
          >
            <Save size={14} /> Save
          </button>
          <div className="flex-1 relative">
            <div className="absolute inset-y-0 left-0 flex items-center pl-2 pointer-events-none text-slate-200">
              <Download size={14} />
            </div>
            <select
              className="w-full h-9 pl-7 pr-3 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors appearance-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500/60"
              onChange={handleLoad}
              defaultValue=""
            >
              <option value="" disabled>Load Template...</option>
              {templateList.map((t) => (
                <option key={t.path} value={t.path}>
                  {t.label} {t.source === 'builtin' ? '(Built-in)' : ''}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Spectrum Engine</h2>
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-200">Style Preset</label>
            <Select 
              value={template.style} 
              onChange={(e: any) => updateTemplate({ style: e.target.value })}
              className="w-full"
            >
              <option value="classic-vertical">Classic Vertical Bars</option>
              <option value="thin-lines">Thin Frequency Lines</option>
              <option value="dot-matrix">Dot Matrix Bars</option>
              <option value="symmetrical-bars">Symmetrical Bars</option>
              <option value="soft-waveform">Continuous Waveform</option>
              <option value="mountain">Filled Mountain</option>
              <option value="liquid">Liquid Plasma</option>
              <option value="pixel-bars">Pixel Bars</option>
              <option value="neon-pulse">Neon Pulse Bars</option>
              <option value="floating-blocks">Floating Blocks</option>
            </Select>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-slate-300 mb-3 uppercase tracking-wider">Audio Reactivity</h3>
        <div className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs text-slate-400">Sensitivity ({template.audioSettings.sensitivity.toFixed(2)})</label>
            <Slider 
              min={0} max={2} step={0.01} 
              value={template.audioSettings.sensitivity} 
              onValueChange={(v) => updateTemplate({ audioSettings: { ...template.audioSettings, sensitivity: v } })}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-400">Smoothing ({template.audioSettings.smoothing.toFixed(2)})</label>
            <Slider 
              min={0} max={0.99} step={0.01} 
              value={template.audioSettings.smoothing} 
              onValueChange={(v) => updateTemplate({ audioSettings: { ...template.audioSettings, smoothing: v } })}
            />
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-slate-300 mb-3 uppercase tracking-wider">Positioning</h3>
        <div className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-bold text-slate-200 uppercase">Spectrum Position</label>
              <button 
                className="text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-0.5 rounded transition-colors"
                onClick={() => updateTemplate({ position: { anchor: 'center', x: 0, y: 0 } })}
              >
                Reset Center
              </button>
            </div>
            <div className="space-y-2">
              <label className="text-xs text-slate-400">Anchor</label>
              <Select 
                value={template.position.anchor} 
                onChange={(e: any) => updateTemplate({ position: { anchor: e.target.value, x: 0, y: 0 } })}
                className="w-full"
              >
                <option value="top-left">Top Left</option>
                <option value="top-center">Top Center</option>
                <option value="top-right">Top Right</option>
                <option value="center">Center</option>
                <option value="bottom-left">Bottom Left</option>
                <option value="bottom-center">Bottom Center</option>
                <option value="bottom-right">Bottom Right</option>
              </Select>
            </div>
            <div className="flex gap-4">
              <div className="space-y-1 flex-1">
                <label className="text-xs text-slate-400">X Offset ({template.position.x})</label>
                <Slider min={-1000} max={1000} step={1} value={template.position.x} onValueChange={(v) => updateTemplate({ position: { ...template.position, x: v } })} />
              </div>
              <div className="space-y-1 flex-1">
                <label className="text-xs text-slate-400">Y Offset ({template.position.y})</label>
                <Slider min={-1000} max={1000} step={1} value={template.position.y} onValueChange={(v) => updateTemplate({ position: { ...template.position, y: v } })} />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-slate-300 mb-3 uppercase tracking-wider">Background Settings</h3>
        <div className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs text-slate-400">Brightness ({template.backgroundSettings.brightness.toFixed(2)})</label>
            <Slider 
              min={0} max={2} step={0.01} 
              value={template.backgroundSettings.brightness} 
              onValueChange={(v) => updateTemplate({ backgroundSettings: { ...template.backgroundSettings, brightness: v } })}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-400">Audio Reactivity ({template.backgroundSettings.reactivity.toFixed(2)})</label>
            <Slider 
              min={0} max={2} step={0.01} 
              value={template.backgroundSettings.reactivity} 
              onValueChange={(v) => updateTemplate({ backgroundSettings: { ...template.backgroundSettings, reactivity: v } })}
            />
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-slate-300 mb-3 uppercase tracking-wider">Logo Settings</h3>
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-xs text-slate-400">Shape</label>
            <Select 
              value={template.logoSettings.circleMask ? "circle" : "square"} 
              onChange={(e: any) => updateTemplate({ logoSettings: { ...template.logoSettings, circleMask: e.target.value === "circle" } })}
              className="w-full"
            >
              <option value="circle">Circle Crop</option>
              <option value="square">Original Image</option>
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-400">Size ({template.logoSettings.size})</label>
            <Slider 
              min={1} max={130} step={1} 
              value={template.logoSettings.size} 
              onValueChange={(v) => updateTemplate({ logoSettings: { ...template.logoSettings, size: v } })}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-400">Opacity ({template.logoSettings.opacity.toFixed(2)})</label>
            <Slider 
              min={0} max={1} step={0.01} 
              value={template.logoSettings.opacity} 
              onValueChange={(v) => updateTemplate({ logoSettings: { ...template.logoSettings, opacity: v } })}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-400">Audio Reactivity ({template.logoSettings.reactivity.toFixed(2)})</label>
            <Slider 
              min={0} max={2} step={0.01} 
              value={template.logoSettings.reactivity} 
              onValueChange={(v) => updateTemplate({ logoSettings: { ...template.logoSettings, reactivity: v } })}
            />
          </div>
          
          {/* Logo Position controls removed - Logo now shares Spectrum Position */}
        </div>
      </div>
      <div>
        <h3 className="text-sm font-medium text-slate-300 mb-3 uppercase tracking-wider">Particles Engine</h3>
        <div className="space-y-4">
          <div className="space-y-2 flex items-center justify-between">
            <label className="text-xs font-bold text-slate-200 uppercase">Enable Particles</label>
            <input 
              type="checkbox" 
              checked={template.particlesSettings.enabled} 
              onChange={(e) => updateTemplate({ particlesSettings: { ...template.particlesSettings, enabled: e.target.checked } })}
              className="rounded border-slate-700 bg-slate-900"
            />
          </div>
          {template.particlesSettings.enabled && (
            <>
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Max Count ({template.particlesSettings.maxCount})</label>
                <Slider 
                  min={200} max={2000} step={50} 
                  value={template.particlesSettings.maxCount} 
                  onValueChange={(v) => updateTemplate({ particlesSettings: { ...template.particlesSettings, maxCount: v } })}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Birth Rate ({template.particlesSettings.spawnRate})</label>
                <Slider 
                  min={100} max={1000} step={100} 
                  value={template.particlesSettings.spawnRate} 
                  onValueChange={(v) => updateTemplate({ particlesSettings: { ...template.particlesSettings, spawnRate: v } })}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Lifetime ({template.particlesSettings.lifetimeSec.toFixed(2)}s)</label>
                <Slider 
                  min={0.05} max={10} step={0.01} 
                  value={template.particlesSettings.lifetimeSec} 
                  onValueChange={(v) => updateTemplate({ particlesSettings: { ...template.particlesSettings, lifetimeSec: v } })}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Base Speed ({template.particlesSettings.speed})</label>
                <Slider 
                  min={1} max={15} step={0.1} 
                  value={template.particlesSettings.speed} 
                  onValueChange={(v) => updateTemplate({ particlesSettings: { ...template.particlesSettings, speed: v } })}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Audio Reactivity ({template.particlesSettings.reactivity.toFixed(2)})</label>
                <Slider 
                  min={0.1} max={0.5} step={0.01} 
                  value={template.particlesSettings.reactivity} 
                  onValueChange={(v) => updateTemplate({ particlesSettings: { ...template.particlesSettings, reactivity: v } })}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Particle Size ({template.particlesSettings.size})</label>
                <Slider 
                  min={1} max={10} step={0.5} 
                  value={template.particlesSettings.size} 
                  onValueChange={(v) => updateTemplate({ particlesSettings: { ...template.particlesSettings, size: v } })}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Opacity ({template.particlesSettings.opacity.toFixed(2)})</label>
                <Slider 
                  min={0} max={1} step={0.01} 
                  value={template.particlesSettings.opacity} 
                  onValueChange={(v) => updateTemplate({ particlesSettings: { ...template.particlesSettings, opacity: v } })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs text-slate-400">Color</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={template.particlesSettings.color}
                    onChange={(e) => updateTemplate({ particlesSettings: { ...template.particlesSettings, color: e.target.value } })}
                    className="h-8 w-10 rounded border border-slate-200/10 bg-transparent"
                  />
                  <input 
                    type="text"
                    className="flex-1 h-8 rounded-md border border-slate-200/10 bg-slate-950/40 px-3 text-sm text-slate-100 focus:outline-none"
                    value={template.particlesSettings.color} 
                    onChange={(e) => updateTemplate({ particlesSettings: { ...template.particlesSettings, color: e.target.value } })}
                  />
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
