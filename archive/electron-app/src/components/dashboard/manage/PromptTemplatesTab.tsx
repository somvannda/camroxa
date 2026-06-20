import * as React from "react";
import type { PromptTemplate } from "../../../../shared/app-types";
import { useAppStore } from "@/store/useAppStore";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { DataTable } from "@/components/dashboard/manage/DataTable";
import { createId } from "@/utils/ids";
import { Plus, RefreshCcw, Trash2 } from "lucide-react";

export function PromptTemplatesTab() {
  const { data, upsertPromptTemplate, deletePromptTemplate } = useAppStore();
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [draft, setDraft] = React.useState<PromptTemplate | null>(null);
  const [showStructure, setShowStructure] = React.useState(false);

  React.useEffect(() => {
    setSelectedId(data.promptTemplates[0]?.id ?? null);
  }, [data.promptTemplates]);

  const selected = data.promptTemplates.find((x) => x.id === selectedId) ?? null;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-center gap-2">
        <Button
          variant="primary"
          onClick={() =>
            setDraft({
              id: createId("tpl"),
              name: "Default",
              scene: "Futuristic city environment at night, cinematic lighting, strong reflections, high contrast, neon palette (purple/blue/pink), wet streets, volumetric fog, bokeh lights, dramatic atmosphere.",
              negativePrompt: "No text, no typography, no watermark, no logos, no letters, no numbers.",
              updatedAt: "",
            })
          }
        >
          <Plus className="h-4 w-4" />
          Add
        </Button>
      </div>

      <div className="min-h-0 flex-1">
        <DataTable<PromptTemplate>
          rows={data.promptTemplates}
          selectedId={selectedId}
          onSelect={setSelectedId}
          fill
          columns={[
            { key: "id", header: "ID", render: (r) => r.id.slice(0, 8) },
            { key: "name", header: "Name", render: (r) => r.name },
            { key: "scene", header: "Scene", render: (r) => r.scene, span: 4 },
            { key: "negative", header: "Negative", render: (r) => r.negativePrompt, span: 3 },
            { key: "updated", header: "Updated", render: (r) => (r.updatedAt ? r.updatedAt.slice(0, 19) : "-") },
          ]}
        />
      </div>

      <div className="flex items-center gap-2">
        <Button variant="destructive" disabled={!selected} onClick={() => selected && deletePromptTemplate(selected.id)}>
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
        <DialogContent title="Edit prompt template" className="max-w-2xl">
          <div className="p-4">
            <div className="space-y-3">
              <div>
                <div className="mb-1 text-xs text-slate-300">Name</div>
                <Input value={draft?.name ?? ""} onChange={(e) => setDraft((d) => (d ? { ...d, name: e.target.value } : d))} />
              </div>
              <div>
                <div className="mb-1 text-xs text-slate-300">Scene</div>
                <textarea
                  value={draft?.scene ?? ""}
                  onChange={(e) => setDraft((d) => (d ? { ...d, scene: e.target.value } : d))}
                  className="min-h-40 w-full resize-none rounded-md border border-slate-200/10 bg-slate-950/40 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/60"
                />
              </div>
              <div>
                <div className="mb-1 text-xs text-slate-300">Negative prompt</div>
                <textarea
                  value={draft?.negativePrompt ?? ""}
                  onChange={(e) => setDraft((d) => (d ? { ...d, negativePrompt: e.target.value } : d))}
                  className="min-h-40 w-full resize-none rounded-md border border-slate-200/10 bg-slate-950/40 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/60"
                />
              </div>
              <div className="flex items-center justify-between gap-2">
                <Button variant="secondary" onClick={() => setShowStructure((v) => !v)}>
                  {showStructure ? "Hide structure" : "Show structure"}
                </Button>
              </div>
              {showStructure ? (
                <div className="rounded-md border border-slate-200/10 bg-slate-950/30 p-3 text-xs text-slate-200 whitespace-pre-wrap">
                  {`Photorealistic cinematic car background.
Car: (picked from Car Catalog)
Scene: ${draft?.scene ?? ""}

Constraints: no text, no logos, keep some clean negative space for typography overlay.
Negative prompt: ${draft?.negativePrompt ?? ""}`.trim()}
                </div>
              ) : null}
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setDraft(null)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={async () => {
                  if (!draft) return;
                  setShowStructure(false);
                  await upsertPromptTemplate(draft);
                  setDraft(null);
                }}
              >
                Save
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

