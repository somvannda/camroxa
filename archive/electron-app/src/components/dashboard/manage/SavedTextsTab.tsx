import * as React from "react";
import type { SavedText } from "../../../../shared/app-types";
import { useAppStore } from "@/store/useAppStore";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { DataTable } from "@/components/dashboard/manage/DataTable";
import { createId, nowIso } from "@/utils/ids";
import { Trash2 } from "lucide-react";

function newItem(kind: "descriptions" | "structures") {
  const id = createId(kind === "descriptions" ? "desc" : "struct");
  return { id, name: "", content: "", matchKey: "", updatedAt: nowIso() } satisfies SavedText;
}

export function SavedTextsTab(props: { kind: "descriptions" | "structures"; title: string; onLoad?: (text: string) => void }) {
  const { data, upsertText, deleteText, updateSettings } = useAppStore();
  const rows = data[props.kind];
  const [selectedId, setSelectedId] = React.useState<string | null>(rows[0]?.id ?? null);
  const selected = React.useMemo(() => rows.find((x) => x.id === selectedId) ?? null, [rows, selectedId]);
  const [draft, setDraft] = React.useState<SavedText>(() => (selected ? { ...selected } : newItem(props.kind)));

  const activeIds = props.kind === "descriptions" ? data.settings.activeDescriptionIds : data.settings.activeStructureIds;

  React.useEffect(() => {
    if (!selectedId && rows[0]?.id) setSelectedId(rows[0].id);
  }, [rows, selectedId]);

  React.useEffect(() => {
    if (selected) setDraft({ ...selected });
    else setDraft(newItem(props.kind));
  }, [props.kind, selected]);

  return (
    <div className="grid grid-cols-[1fr_1fr] gap-3">
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            onClick={() => {
              const item = newItem(props.kind);
              upsertText(props.kind, item);
              setSelectedId(item.id);
            }}
          >
            Add new
          </Button>
          <Button
            variant="destructive"
            disabled={!selected}
            onClick={() => {
              if (!selected) return;
              deleteText(props.kind, selected.id);
              setSelectedId(null);
            }}
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
          <Button
            variant="secondary"
            disabled={!selected}
            onClick={() => {
              if (!selected) return;
              if (props.kind === "descriptions") {
                const exists = data.settings.activeDescriptionIds.includes(selected.id);
                const next = exists
                  ? data.settings.activeDescriptionIds.filter((id) => id !== selected.id)
                  : [...data.settings.activeDescriptionIds, selected.id];
                updateSettings({
                  activeDescriptionIds: next,
                  shuffle: false,
                  shuffleDescription: false,
                  enabledDescriptionIds: next,
                });
              } else {
                const exists = data.settings.activeStructureIds.includes(selected.id);
                const next = exists
                  ? data.settings.activeStructureIds.filter((id) => id !== selected.id)
                  : [...data.settings.activeStructureIds, selected.id];
                updateSettings({
                  activeStructureIds: next,
                  shuffle: false,
                  shuffleStructure: false,
                  enabledStructureIds: next,
                });
              }
              props.onLoad?.(selected.content || "");
            }}
          >
            Set active
          </Button>
          <Button
            variant="secondary"
            disabled={!selected}
            onClick={() => {
              if (!selected) return;
              props.onLoad?.(selected.content || "");
            }}
          >
            Load
          </Button>
        </div>

        <DataTable<SavedText>
          rows={rows}
          selectedId={selectedId}
          onSelect={setSelectedId}
          columns={[
            {
              key: "name",
              header: "Name",
              render: (r) => (
                <div className="flex items-center gap-2">
                  <div className="truncate">{r.name || "(unnamed)"}</div>
                  {activeIds.includes(r.id) ? (
                    <div className="rounded bg-emerald-600/20 px-2 py-0.5 text-[11px] text-emerald-200">Active</div>
                  ) : null}
                </div>
              ),
              span: 2,
            },
            { key: "updated", header: "Updated", render: (r) => (r.updatedAt ? r.updatedAt.slice(0, 19) : "-"), span: 2 },
          ]}
          maxHeightClassName="max-h-[460px]"
        />
      </div>

      <div className="space-y-3">
        <div className="text-sm font-semibold text-slate-100">{props.title}</div>
        <div className="space-y-1">
          <div className="text-xs text-slate-300">Name</div>
          <Input value={draft.name} onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))} />
        </div>
        {props.kind === "descriptions" ? (
          <div className="space-y-1">
            <div className="text-xs text-slate-300">Match structure</div>
            <Select value={draft.matchKey ?? ""} onChange={(e) => setDraft((d) => ({ ...d, matchKey: e.target.value }))}>
              <option value="">(no match)</option>
              {data.structures.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name || "(unnamed)"}
                </option>
              ))}
            </Select>
          </div>
        ) : null}
        <div className="space-y-1">
          <div className="text-xs text-slate-300">Text</div>
          <Textarea className="h-[320px]" value={draft.content} onChange={(e) => setDraft((d) => ({ ...d, content: e.target.value }))} />
        </div>
        <div className="flex justify-end">
          <Button
            variant="primary"
            onClick={async () => {
              await upsertText(props.kind, { ...draft, name: draft.name.trim() || "(unnamed)" });
            }}
          >
            Save
          </Button>
        </div>
      </div>
    </div>
  );
}
