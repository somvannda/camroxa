import * as React from "react";
import type { TextStyle } from "../../../../shared/app-types";
import { useAppStore } from "@/store/useAppStore";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { DataTable } from "@/components/dashboard/manage/DataTable";
import { createId } from "@/utils/ids";
import { Plus, RefreshCcw, Trash2 } from "lucide-react";
import { paginate } from "@/components/dashboard/manage/paginate";
import { TEXT_STYLE_PALETTES, TEXT_STYLE_PRESETS, buildTextStylePrompt } from "@/services/textStylePresets";

export function TextStylesTab() {
  const { data, upsertTextStyle, deleteTextStyle, replaceTextStyles, setFooterStatus } = useAppStore();
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [draft, setDraft] = React.useState<TextStyle | null>(null);
  const [page, setPage] = React.useState(0);
  const pageSize = 80;

  const pagedRows = React.useMemo(() => paginate(data.textStyles, page, pageSize), [data.textStyles, page]);
  const pageCount = Math.max(1, Math.ceil(data.textStyles.length / pageSize));

  function buildPresetName(presetName: string, paletteName: string) {
    return `${presetName} · ${paletteName}`;
  }

  function generatePresetPack(): TextStyle[] {
    const out: TextStyle[] = [];
    let i = 0;
    for (const preset of TEXT_STYLE_PRESETS) {
      for (const palette of TEXT_STYLE_PALETTES) {
        i += 1;
        const name = buildPresetName(preset.name, palette.name);
        out.push({
          id: `style-${String(i).padStart(5, "0")}`,
          name,
          presetId: preset.id,
          paletteId: palette.id,
          title: "BASS",
          subtitle: "Car Music",
          subtitle2: "2026",
          prompt: buildTextStylePrompt({ name, palettePrompt: palette.palettePrompt, preset }),
          opacity: preset.defaultOpacity,
          position: preset.defaultPosition,
          updatedAt: "",
        });
      }
    }
    return out;
  }

  function generateStyles(count: number): TextStyle[] {
    const names = [
      "Neon Glow",
      "Chrome Bevel",
      "Holographic Gradient",
      "Cyberpunk Purple",
      "Laser Magenta",
      "Electric Blue Edge",
      "Vaporwave Sunset",
      "Aurora Blend",
      "Iridescent Foil",
      "Glossy Black Shadow",
      "Hot Pink Stroke",
      "Blue Ember Core",
      "Silver Mirror",
      "Neon Tube Outline",
      "Plasma Glow Duo",
      "Candy Chrome",
      "Deep Purple Luxe",
      "Hyper Pink Bloom",
      "Royal Blue Glow",
      "Ultraviolet Beam",
      "Fuchsia Flame",
      "Aqua Neon Rim",
      "Sapphire Shine",
      "Pink-Blue Split",
      "Glitch RGB",
      "Prismatic Edge",
      "Luminous Ice",
      "Electric Orchid",
      "Galaxy Sheen",
      "Steel Neon Mix",
      "Hyper Glow Core",
      "Cyan Pulse",
      "Rose Gold Shine",
      "Magenta Bloom Edge",
      "Blue Fire Stroke",
      "Ultra Chrome",
      "Neon Fog Glow",
      "Haze Gradient",
      "Abyss Purple",
      "Night Rider Neon",
      "Vivid Spectrum",
      "Pearl Chrome",
      "Neon Rimlight",
      "Electric Fade",
      "Violet Heat",
      "Cobalt Beam",
      "Pink Aura",
      "Neon Ribbon",
      "Digital Chrome",
      "Vapor Chrome",
      "Plasma Pink Edge",
      "Moonlit Blue",
      "Prism Shift",
      "Turbo Neon",
      "Black Ice Glow",
      "Electric Violet Steel",
      "Hyper Foil",
      "Pulse Beam",
      "Neon Mist",
      "Cyan Magenta Flux",
      "Lazerline Outline",
      "Glassy Chrome",
      "Glowcore Duo",
      "Ultra Magenta",
      "Satin Steel",
      "Neon Gel",
      "Aqua Beam Edge",
      "Royal Neon",
      "Spectrum Chrome",
      "Noir Glow",
      "Ultralume Pink",
      "Blue Neon Crest",
      "Chrome Burst",
      "Deepwave Glow",
      "Magenta Edgeglass",
      "Cobalt Spark",
      "Violet Plasma",
      "Neon Depth",
      "Radial Glow",
      "Haze Chrome",
      "Pulse Outline",
      "Diamond Sheen",
      "Neon Velvet",
      "Blue Pink Bloom",
      "Cyber Steel",
      "Frosted Glow",
      "Ion Beam",
      "Lustrous Chrome",
      "Neon Echo",
      "Cobalt Velvet",
      "Hyperline Stroke",
      "Violet Chrome",
      "Electric Gloss",
      "Neon Prism",
      "Steel Bloom",
      "Pulse Chrome",
      "Abyss Glow",
      "Luminous Steel",
      "Magenta Crest",
      "Neon Supreme",
    ];
    const opacities = [
      0.9, 0.92, 0.94, 0.88, 0.93, 0.9, 0.89, 0.95, 0.91, 0.87,
      0.92, 0.94, 0.96, 0.86, 0.93, 0.95, 0.9, 0.92, 0.94, 0.91,
      0.9, 0.89, 0.95, 0.92, 0.88, 0.93, 0.96, 0.91, 0.94, 0.92,
      0.93, 0.9, 0.95, 0.92, 0.89, 0.97, 0.9, 0.91, 0.88, 0.93,
      0.94, 0.96, 0.89, 0.9, 0.92, 0.91, 0.93, 0.88, 0.95, 0.94,
      0.92, 0.9, 0.93, 0.91, 0.89, 0.94, 0.96, 0.9, 0.88, 0.93,
      0.86, 0.95, 0.92, 0.91, 0.94, 0.9, 0.92, 0.93, 0.95, 0.88,
      0.91, 0.92, 0.96, 0.9, 0.94, 0.93, 0.92, 0.89, 0.9, 0.95,
      0.87, 0.96, 0.92, 0.93, 0.94, 0.91, 0.9, 0.97, 0.89, 0.92,
      0.86, 0.95, 0.94, 0.93, 0.92, 0.96, 0.9, 0.95, 0.92, 0.97,
    ];

    const palettes = [
      "neon magenta, fuchsia, purple, electric blue, cyan",
      "pink-to-cyan gradient with violet midtones",
      "cyan-to-lavender gradient with magenta highlights",
      "deep purple + hot pink + ice blue rimlight",
      "ultraviolet + aqua + rose glow",
      "teal + neon pink with chrome highlights",
      "electric blue + neon purple with white specular",
      "magenta + sapphire + cyan underglow",
      "pink neon + cyan neon with black shadow",
      "violet haze + cyan beam + fuchsia bloom",
      "teal + electric blue + neon violet",
      "hot pink + cobalt + cyan highlights",
      "cyan + aqua + lavender haze",
      "purple noir + neon rimlight + chrome shine",
      "magenta flame + cyan edge glow",
      "ultraviolet beam + teal reflection + rose bloom",
      "aqua neon + fuchsia accents + deep blue shadows",
      "blue ember + pink sparkle + purple fog",
      "sapphire shine + violet heat + cyan mist",
      "prismatic rainbow foil on dark background",
    ];
    const line1Styles = [
      "thick brush-script, dramatic swashes, slight italic, beveled 3D look, neon gradient fill",
      "hand-lettered brush, chunky strokes, glossy highlights, neon rim glow",
      "bold script with paint splatter edges, strong outer glow, subtle grunge texture",
      "smooth modern script, high contrast stroke, neon tube outline effect",
      "retro brush logo, chrome bevel, soft bloom, cinematic glow",
      "brush lettering with sharp focus, neon inner highlights, subtle shadow",
      "thick graffiti-inspired brush, energetic strokes, glow bloom",
      "luxury calligraphic script, glossy chrome edges, neon rimlight",
    ];
    const line2Styles = [
      "cursive brush script, smaller, tight tracking, soft glow",
      "smooth italic script, medium weight, subtle inner shine",
      "handwritten neon sign style, thin stroke with glow",
      "elegant brush cursive, gentle gradient, minimal bloom",
      "clean italic wordmark, soft neon rimlight",
      "condensed script, slightly slanted, satin glow",
      "simple cursive, pink-to-lilac gradient, soft shadow",
    ];
    const line3Styles = [
      "ultra-bold italic display, rounded corners, bevel edges, metallic neon gradient",
      "heavy sans display, forward-leaning, thick stroke, strong rim light",
      "blocky neon display with motion streak underline and glow",
      "bold chrome numbers with cyan-to-pink gradient and drop shadow",
      "thick futuristic numbers, glossy highlights, neon underglow",
      "wide italic numbers, bevel highlight, neon rimlight",
      "chunky display numbers with paint streaks and spark particles",
    ];
    const effects = [
      "outer glow (pink/cyan), inner highlights, subtle shadow",
      "volumetric glow, bloom, soft fog light spill",
      "rimlight, spark particles, light streaks around text",
      "paint streak underline, glossy specular, sharp edges",
      "chrome bevel, reflective shine, neon edge glow",
      "subtle grain, filmic glow, high contrast",
      "electric glow bloom, halo behind line 1",
    ];
    const accents = [
      "diagonal baseline slant rising left-to-right for line 1",
      "paint-streak underline beneath line 3 extending left/right",
      "glow halo behind line 1 and line 3",
      "neon stroke outline around line 1 and line 3",
      "subtle grunge edges + paint splatter micro-texture",
      "thin neon underline and motion streaks",
      "chromatic aberration micro-edge and glossy highlight",
    ];

    const out: TextStyle[] = [];
    for (let i = 0; i < count; i += 1) {
      const baseName = names[i % names.length] ?? `Neon Style ${i + 1}`;
      const p = palettes[i % palettes.length]!;
      const l1 = line1Styles[(i * 7) % line1Styles.length]!;
      const l2 = line2Styles[(i * 11 + 2) % line2Styles.length]!;
      const l3 = line3Styles[(i * 13 + 1) % line3Styles.length]!;
      const e = effects[(i * 5 + 3) % effects.length]!;
      const a = accents[(i * 17 + 4) % accents.length]!;
      const name =
        count <= 100
          ? `${baseName} ${String(i + 1).padStart(3, "0")}`
          : `${baseName} ${String(i + 1).padStart(5, "0")}`;
      out.push({
        id: `style-${String(i + 1).padStart(5, "0")}`,
        name,
        title: "BASS",
        subtitle: "Car Music",
        subtitle2: "2026",
        prompt:
          `Typography overlay style (${name}): Center-aligned 3-line stacked logo. Color palette: ${p}. Line 1 ("BASS") style: ${l1}. Line 2 ("Car Music") style: ${l2}. Line 3 ("2026") style: ${l3}. Effects: ${e}. Accents: ${a}. Keep text sharp, readable, neon glow, high contrast against dark background.`,
        opacity: opacities[i % opacities.length] ?? 0.92,
        position: "center",
        updatedAt: "",
      });
    }
    return out;
  }

  React.useEffect(() => {
    setSelectedId(data.textStyles[0]?.id ?? null);
  }, [data.textStyles]);

  const selected = data.textStyles.find((x) => x.id === selectedId) ?? null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          onClick={async () => {
            const count = TEXT_STYLE_PRESETS.length * TEXT_STYLE_PALETTES.length;
            setFooterStatus(`Generating ${count} preset text styles…`, 30);
            await replaceTextStyles(generatePresetPack());
            setFooterStatus(`Saved ${count} preset text styles`, 100);
            setTimeout(() => setFooterStatus("Ready", null), 1200);
          }}
        >
          Generate Preset Pack
        </Button>
        <Button
          variant="secondary"
          onClick={async () => {
            setFooterStatus("Generating 100 text styles…", 30);
            await replaceTextStyles(generateStyles(100));
            setFooterStatus("Saved 100 text styles", 100);
            setTimeout(() => setFooterStatus("Ready", null), 1200);
          }}
        >
          Generate 100
        </Button>
        <Button
          variant="secondary"
          onClick={async () => {
            setFooterStatus("Generating 10,000 text styles…", 20);
            await replaceTextStyles(generateStyles(10_000));
            setFooterStatus("Saved 10,000 text styles", 100);
            setTimeout(() => setFooterStatus("Ready", null), 1200);
          }}
        >
          Generate 10,000
        </Button>
        <Button
          variant="primary"
          onClick={() =>
            setDraft({
              id: createId("style"),
              name: "New Style",
              title: "{title}",
              subtitle: "{subtitle}",
              subtitle2: "{subtitle2}",
              prompt: "{prompt}",
              opacity: 0.9,
              position: "bottom",
              updatedAt: "",
            })
          }
        >
          <Plus className="h-4 w-4" />
          Add
        </Button>
      </div>

      <DataTable<TextStyle>
        rows={pagedRows}
        selectedId={selectedId}
        onSelect={setSelectedId}
        columns={[
          { key: "id", header: "ID", render: (r) => r.id.slice(0, 8) },
          { key: "name", header: "Name", render: (r) => r.name },
          { key: "title", header: "Title", render: (r) => r.title },
          { key: "subtitle", header: "Subtitle", render: (r) => r.subtitle },
          { key: "subtitle2", header: "Subtitle 2", render: (r) => r.subtitle2 },
          { key: "presetId", header: "Preset", render: (r) => r.presetId ?? "" },
          { key: "paletteId", header: "Palette", render: (r) => r.paletteId ?? "" },
          { key: "prompt", header: "Prompt", render: (r) => r.prompt, span: 3 },
          { key: "opacity", header: "Opacity", render: (r) => r.opacity.toFixed(2) },
          { key: "position", header: "Position", render: (r) => r.position },
        ]}
      />

      <div className="flex items-center justify-between gap-2">
        <div className="text-xs text-slate-400">{data.textStyles.length.toLocaleString()} styles</div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" disabled={page <= 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
            Prev
          </Button>
          <div className="text-xs text-slate-300">
            Page {page + 1} / {pageCount}
          </div>
          <Button variant="secondary" size="sm" disabled={page + 1 >= pageCount} onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}>
            Next
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button variant="destructive" disabled={!selected} onClick={() => selected && deleteTextStyle(selected.id)}>
          <Trash2 className="h-4 w-4" />
          Delete selected
        </Button>
        <Button variant="primary" disabled={!selected} onClick={() => selected && setDraft({ ...selected })}>
          Edit selected
        </Button>
        <Button variant="secondary" onClick={() => {}}>
          <RefreshCcw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      <Dialog open={!!draft} onOpenChange={(v) => !v && setDraft(null)}>
        <DialogContent title="Edit text style" className="max-w-xl h-[680px] flex flex-col">
          <div className="min-h-0 flex-1 overflow-auto p-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <div className="mb-1 text-xs text-slate-300">Name</div>
                <Input value={draft?.name ?? ""} onChange={(e) => setDraft((d) => (d ? { ...d, name: e.target.value } : d))} />
              </div>
              <div className="col-span-2">
                <div className="mb-1 text-xs text-slate-300">Title</div>
                <Input value={draft?.title ?? ""} onChange={(e) => setDraft((d) => (d ? { ...d, title: e.target.value } : d))} />
              </div>
              <div className="col-span-2">
                <div className="mb-1 text-xs text-slate-300">Subtitle</div>
                <Input value={draft?.subtitle ?? ""} onChange={(e) => setDraft((d) => (d ? { ...d, subtitle: e.target.value } : d))} />
              </div>
              <div className="col-span-2">
                <div className="mb-1 text-xs text-slate-300">Subtitle 2</div>
                <Input value={draft?.subtitle2 ?? ""} onChange={(e) => setDraft((d) => (d ? { ...d, subtitle2: e.target.value } : d))} />
              </div>
              <div className="col-span-2">
                <div className="mb-1 text-xs text-slate-300">Style prompt</div>
                <textarea
                  value={draft?.prompt ?? ""}
                  onChange={(e) => setDraft((d) => (d ? { ...d, prompt: e.target.value } : d))}
                  className="min-h-32 w-full resize-none rounded-md border border-slate-200/10 bg-slate-950/40 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/60"
                />
              </div>
              <div>
                <div className="mb-1 text-xs text-slate-300">Preset</div>
                <Select
                  value={draft?.presetId ?? ""}
                  onChange={(e) => {
                    const presetId = String(e.target.value || "");
                    setDraft((d) => {
                      if (!d) return d;
                      const preset = TEXT_STYLE_PRESETS.find((p) => p.id === presetId);
                      const palette = TEXT_STYLE_PALETTES.find((p) => p.id === (d.paletteId ?? "")) ?? TEXT_STYLE_PALETTES[0];
                      if (!preset || !palette) return { ...d, presetId: presetId || undefined };
                      const name = buildPresetName(preset.name, palette.name);
                      return {
                        ...d,
                        name,
                        presetId: preset.id,
                        opacity: preset.defaultOpacity,
                        position: preset.defaultPosition,
                        prompt: buildTextStylePrompt({ name, palettePrompt: palette.palettePrompt, preset }),
                      };
                    });
                  }}
                >
                  <option value="">(none)</option>
                  {TEXT_STYLE_PRESETS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <div className="mb-1 text-xs text-slate-300">Palette</div>
                <Select
                  value={draft?.paletteId ?? ""}
                  onChange={(e) => {
                    const paletteId = String(e.target.value || "");
                    setDraft((d) => {
                      if (!d) return d;
                      const palette = TEXT_STYLE_PALETTES.find((p) => p.id === paletteId);
                      const preset = TEXT_STYLE_PRESETS.find((p) => p.id === (d.presetId ?? "")) ?? TEXT_STYLE_PRESETS[0];
                      if (!preset || !palette) return { ...d, paletteId: paletteId || undefined };
                      const name = buildPresetName(preset.name, palette.name);
                      return {
                        ...d,
                        name,
                        paletteId: palette.id,
                        prompt: buildTextStylePrompt({ name, palettePrompt: palette.palettePrompt, preset }),
                      };
                    });
                  }}
                >
                  <option value="">(none)</option>
                  {TEXT_STYLE_PALETTES.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <div className="mb-1 text-xs text-slate-300">Opacity</div>
                <Input
                  type="number"
                  step="0.05"
                  min={0}
                  max={1}
                  value={draft?.opacity ?? 0.9}
                  onChange={(e) => setDraft((d) => (d ? { ...d, opacity: Number(e.target.value) } : d))}
                />
              </div>
              <div>
                <div className="mb-1 text-xs text-slate-300">Position</div>
                <Select
                  value={draft?.position ?? "bottom"}
                  onChange={(e) => setDraft((d) => (d ? { ...d, position: e.target.value as TextStyle["position"] } : d))}
                >
                  <option value="top">top</option>
                  <option value="center">center</option>
                  <option value="bottom">bottom</option>
                </Select>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2 border-t border-slate-200/10 px-4 py-3">
              <Button variant="secondary" onClick={() => setDraft(null)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={async () => {
                  if (!draft) return;
                  await upsertTextStyle(draft);
                  setDraft(null);
                }}
              >
                Save
              </Button>
            </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

