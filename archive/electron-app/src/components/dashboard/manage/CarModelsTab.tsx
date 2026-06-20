import * as React from "react";
import type { CarModel } from "../../../../shared/app-types";
import { useAppStore } from "@/store/useAppStore";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { DataTable } from "@/components/dashboard/manage/DataTable";
import { paginate } from "@/components/dashboard/manage/paginate";
import { createId } from "@/utils/ids";
import { FileDown, Plus, RefreshCcw, Search, Trash2 } from "lucide-react";

export function CarModelsTab() {
  const { data, upsertCarModel, deleteCarModel, seedCarModels, refreshDbContent } = useAppStore();
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  const [filter, setFilter] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [page, setPage] = React.useState(0);
  const [draft, setDraft] = React.useState<CarModel | null>(null);
  const pageSize = 50;

  const rows = React.useMemo(() => {
    const q = (query || filter).toLowerCase();
    const all = data.carModels;
    if (!q) return all;
    return all.filter((x) => `${x.make} ${x.model} ${x.trim} ${x.category} ${x.year}`.toLowerCase().includes(q));
  }, [data.carModels, query, filter]);

  const pageRows = React.useMemo(() => paginate(rows, page, pageSize), [rows, page]);
  const selected = data.carModels.find((x) => x.id === selectedId) ?? null;

  React.useEffect(() => {
    setSelectedId(pageRows[0]?.id ?? null);
  }, [pageRows]);

  React.useEffect(() => {
    void refreshDbContent();
  }, [refreshDbContent]);

  async function handleCsvFile(file: File) {
    const text = await file.text();
    const lines = text.split(/\r?\n/).filter(Boolean);
    const [header, ...rest] = lines;
    const cols = header.split(",").map((x) => x.trim().toLowerCase());

    for (const line of rest.slice(0, 2000)) {
      const parts = line.split(",");
      const row: Record<string, string> = {};
      cols.forEach((c, idx) => {
        row[c] = (parts[idx] ?? "").trim();
      });
      await upsertCarModel({
        id: createId("car"),
        make: row.make || "Unknown",
        model: row.model || "Unknown",
        trim: row.trim || "",
        year: Number.parseInt(row.year || "2024", 10) || 2024,
        category: row.category || "Sedan",
        updatedAt: "",
      });
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="primary"
          onClick={() =>
            setDraft({ id: createId("car"), make: "", model: "", trim: "", year: 2024, category: "Sedan", updatedAt: "" })
          }
        >
          <Plus className="h-4 w-4" />
          Add
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            await handleCsvFile(f);
            e.target.value = "";
          }}
        />
        <Button variant="secondary" onClick={() => fileInputRef.current?.click()}>
          <FileDown className="h-4 w-4" />
          Import CSV
        </Button>
        <Button variant="secondary" onClick={() => seedCarModels(10000)}>
          Seed 10k
        </Button>
        <div className="ml-2 flex items-center gap-2">
          <div className="text-xs text-slate-300">Filter</div>
          <Input className="h-9 w-56" value={filter} onChange={(e) => setFilter(e.target.value)} />
          <Button variant="primary" onClick={() => setQuery(filter)}>
            <Search className="h-4 w-4" />
            Search
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              setFilter("");
              setQuery("");
              setPage(0);
            }}
          >
            Clear
          </Button>
        </div>
        <div className="ml-auto text-sm text-slate-200">Cars: {rows.length}</div>
      </div>

      <DataTable<CarModel>
        rows={pageRows}
        selectedId={selectedId}
        onSelect={setSelectedId}
        columns={[
          { key: "id", header: "ID", render: (r) => r.id.slice(0, 8) },
          { key: "make", header: "Make", render: (r) => r.make },
          { key: "model", header: "Model", render: (r) => r.model },
          { key: "trim", header: "Trim", render: (r) => r.trim || "-" },
          { key: "year", header: "Year", render: (r) => r.year },
          { key: "category", header: "Category", render: (r) => r.category },
        ]}
      />

      <div className="flex items-center gap-2">
        <Button variant="destructive" disabled={!selected} onClick={() => selected && deleteCarModel(selected.id)}>
          <Trash2 className="h-4 w-4" />
          Delete selected
        </Button>
        <Button variant="primary" disabled={!selected} onClick={() => selected && setDraft({ ...selected })}>
          Edit selected
        </Button>
        <Button
          variant="secondary"
          onClick={async () => {
            setPage(0);
            await refreshDbContent();
          }}
        >
          <RefreshCcw className="h-4 w-4" />
          Refresh
        </Button>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="secondary" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
            Prev
          </Button>
          <div className="px-2 text-sm text-slate-200">Page {page + 1}</div>
          <Button variant="secondary" disabled={(page + 1) * pageSize >= rows.length} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      </div>

      <Dialog open={!!draft} onOpenChange={(v) => !v && setDraft(null)}>
        <DialogContent title="Edit car model" className="max-w-xl">
          <div className="p-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="mb-1 text-xs text-slate-300">Make</div>
                <Input value={draft?.make ?? ""} onChange={(e) => setDraft((d) => (d ? { ...d, make: e.target.value } : d))} />
              </div>
              <div>
                <div className="mb-1 text-xs text-slate-300">Model</div>
                <Input value={draft?.model ?? ""} onChange={(e) => setDraft((d) => (d ? { ...d, model: e.target.value } : d))} />
              </div>
              <div>
                <div className="mb-1 text-xs text-slate-300">Trim</div>
                <Input value={draft?.trim ?? ""} onChange={(e) => setDraft((d) => (d ? { ...d, trim: e.target.value } : d))} />
              </div>
              <div>
                <div className="mb-1 text-xs text-slate-300">Year</div>
                <Input
                  type="number"
                  value={draft?.year ?? 2024}
                  onChange={(e) => setDraft((d) => (d ? { ...d, year: Number(e.target.value) } : d))}
                />
              </div>
              <div className="col-span-2">
                <div className="mb-1 text-xs text-slate-300">Category</div>
                <Input
                  value={draft?.category ?? ""}
                  onChange={(e) => setDraft((d) => (d ? { ...d, category: e.target.value } : d))}
                />
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setDraft(null)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={async () => {
                  if (!draft) return;
                  await upsertCarModel(draft);
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

