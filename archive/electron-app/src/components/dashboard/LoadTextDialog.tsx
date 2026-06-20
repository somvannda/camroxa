import * as React from "react";
import type { SavedText } from "../../../shared/app-types";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent } from "@/components/ui/Dialog";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: string;
  items: SavedText[];
  onLoad: (item: SavedText) => void;
  onDelete: (id: string) => void;
  enabledIds: string[];
  onSaveEnabledIds: (ids: string[]) => void;
};

export function LoadTextDialog({ open, onOpenChange, title, items, onLoad, onDelete, enabledIds, onSaveEnabledIds }: Props) {
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [localEnabled, setLocalEnabled] = React.useState<string[]>([]);

  React.useEffect(() => {
    if (!open) return;
    setSelectedId(items[0]?.id ?? null);
    setLocalEnabled(enabledIds);
  }, [open, items, enabledIds]);

  const selected = items.find((x) => x.id === selectedId) ?? null;
  const enabledSet = React.useMemo(() => new Set(localEnabled), [localEnabled]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={title} className="max-w-5xl h-[680px] flex flex-col">
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 p-4">
            <div className="grid h-full min-h-0 grid-cols-[320px_1fr] gap-4">
              <Card className="flex min-h-0 flex-col overflow-hidden">
                <div className="px-4 py-3 text-sm font-semibold text-slate-100">Saved</div>
                <div className="flex min-h-0 flex-1 flex-col border-t border-slate-200/10">
                  <div className="grid grid-cols-[26px_1fr_120px] px-4 py-2 text-xs text-slate-300">
                    <div />
                    <div>Name</div>
                    <div>Updated</div>
                  </div>
                  <div className="min-h-0 flex-1 overflow-auto">
                    {items.length === 0 ? (
                      <div className="px-4 py-6 text-sm text-slate-400">No saved entries.</div>
                    ) : (
                      items.map((row) => (
                        <button
                          key={row.id}
                          type="button"
                          onClick={() => setSelectedId(row.id)}
                          className={cn(
                            "grid w-full grid-cols-[26px_1fr_120px] items-center gap-2 border-t border-slate-200/10 px-4 py-2 text-left text-sm",
                            row.id === selectedId ? "bg-blue-600/20" : "hover:bg-slate-800/40",
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={enabledSet.has(row.id)}
                            onChange={(e) => {
                              e.stopPropagation();
                              setLocalEnabled((prev) =>
                                prev.includes(row.id) ? prev.filter((x) => x !== row.id) : [...prev, row.id],
                              );
                            }}
                            className="h-4 w-4 rounded border border-slate-200/20 bg-slate-950/40"
                          />
                          <div className="text-slate-100">{row.name}</div>
                          <div className="truncate text-xs text-slate-300">{row.updatedAt.slice(0, 19)}</div>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              </Card>

              <Card className="flex min-h-0 flex-col overflow-hidden">
                <div className="px-4 py-3 text-sm font-semibold text-slate-100">Preview</div>
                <div className="min-h-0 flex-1 overflow-auto border-t border-slate-200/10 px-4 py-3 text-sm leading-relaxed text-slate-100 whitespace-pre-wrap">
                  {selected ? selected.content : "Select an item to preview."}
                </div>
              </Card>
            </div>
          </div>

          <div className="flex items-center justify-between border-t border-slate-200/10 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="md"
                variant="secondary"
                onClick={() => {
                  const all = items.map((x) => x.id);
                  const next = localEnabled.length === items.length ? [] : all;
                  setLocalEnabled(next);
                }}
              >
                Select all
              </Button>
              <Button
                size="md"
                variant="primary"
                onClick={() => {
                  onSaveEnabledIds(localEnabled);
                }}
              >
                Save
              </Button>
              <Button
                size="md"
                variant="primary"
                disabled={!selected}
                onClick={() => {
                  if (!selected) return;
                  onLoad(selected);
                  onOpenChange(false);
                }}
              >
                Load
              </Button>
              <Button
                size="md"
                variant="destructive"
                disabled={!selected}
                onClick={() => {
                  if (!selected) return;
                  onDelete(selected.id);
                }}
              >
                Delete
              </Button>
            </div>
            <Button size="md" variant="secondary" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

