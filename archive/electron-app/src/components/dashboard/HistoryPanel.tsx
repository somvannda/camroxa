import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Switch } from "@/components/ui/Switch";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/utils";
import type { Song } from "../../../shared/app-types";
import { FolderOpen } from "lucide-react";

export type HistoryRow =
  | { kind: "separator"; batchId: string; album: string; createdAt: string }
  | { kind: "song"; song: Song };

function formatDateTime(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(d);
}

function formatBatchLabel(batchId: string) {
  const raw = String(batchId || "");
  if (raw.startsWith("batch-")) {
    const iso = raw.slice(6);
    const d = new Date(iso);
    if (!Number.isNaN(d.getTime())) {
      return `Batch ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(d)}`;
    }
  }
  return `Batch ${raw}`;
}

export function HistoryPanel(props: {
  lastBatchOnly: boolean;
  onLastBatchOnlyChange: (v: boolean) => void;
  fromDate: string;
  toDate: string;
  onFromDateChange: (v: string) => void;
  onToDateChange: (v: string) => void;
  onShowAll: () => void;
  onSelectRow: (songId: string) => void;
  onRetrySuno: (song: Song) => void;
  onOpenSongFolder: (song: Song) => void;
  selectedSongId: string | null;
  rows: HistoryRow[];
}) {
  return (
    <Card className="flex min-h-0 flex-1 flex-col">
      <CardHeader>
        <CardTitle>History</CardTitle>
        <div className="flex items-center gap-2 overflow-x-auto whitespace-nowrap">
          <div className="flex items-center gap-2 rounded-md border border-slate-200/10 bg-slate-950/30 px-2 py-1">
            <div className="text-xs text-slate-300">From</div>
            <Input className="h-8 w-36" type="date" value={props.fromDate} onChange={(e) => props.onFromDateChange(e.target.value)} />
            <div className="text-xs text-slate-300">To</div>
            <Input className="h-8 w-36" type="date" value={props.toDate} onChange={(e) => props.onToDateChange(e.target.value)} />
          </div>
          <div className="flex items-center gap-2 rounded-md border border-slate-200/10 bg-slate-950/30 px-2 py-1">
            <div className="text-xs text-slate-200">Last batch</div>
            <Switch checked={props.lastBatchOnly} onCheckedChange={props.onLastBatchOnlyChange} />
          </div>
          <Button variant="secondary" size="sm" onClick={props.onShowAll}>
            Show all
          </Button>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1">
        <div className="h-full overflow-hidden rounded-lg border border-slate-200/10">
          <div data-testid="history-scroll" className="h-full overflow-x-auto overflow-y-auto bg-[#0b142b]">
            <div className="min-w-[1400px]">
              <div className="sticky top-0 z-10 grid grid-cols-[56px_minmax(0,200px)_minmax(0,320px)_minmax(0,180px)_minmax(0,180px)_minmax(0,220px)_72px_150px] bg-slate-950/70 px-3 py-2 text-xs text-slate-300">
                <div>No</div>
                <div>Album</div>
                <div>Title</div>
                <div>Desc</div>
                <div>Struct</div>
                <div>Channel</div>
                <div>Suno</div>
                <div>Created</div>
              </div>
            {props.rows.length === 0 ? (
              <div className="px-3 py-10 text-center text-sm text-slate-400">No history yet.</div>
            ) : (
              (() => {
                let songNo = 0;
                return props.rows.map((row) => {
                  if (row.kind === "separator") {
                    return (
                      <div
                        key={`sep-${row.batchId}-${row.createdAt}`}
                        className="sticky top-[32px] z-0 border-t border-slate-200/10 bg-slate-950/55 px-3 py-1 text-[11px] text-slate-200"
                      >
                        {formatBatchLabel(row.batchId)} · Album: {row.album || "(empty)"} · {formatDateTime(row.createdAt)}
                      </div>
                    );
                  }

                  songNo += 1;
                  const s = row.song;
                  return (
                    <div
                      key={s.id}
                      className={cn(
                      "grid cursor-pointer grid-cols-[56px_minmax(0,200px)_minmax(0,320px)_minmax(0,180px)_minmax(0,180px)_minmax(0,220px)_72px_150px] items-center gap-2 border-t border-slate-200/10 px-3 py-1 text-xs",
                        props.selectedSongId === s.id ? "bg-blue-600/15" : "hover:bg-slate-950/30",
                      )}
                      onClick={() => props.onSelectRow(s.id)}
                    >
                      <div className="truncate text-left font-mono text-[11px] text-slate-200">{songNo}</div>
                      <div className="truncate text-left text-slate-100" title={s.album}>
                        {s.album}
                      </div>
                      <div className="truncate text-left text-slate-100" title={s.title}>
                        {s.title}
                      </div>
                      <div className="truncate text-left text-slate-100" title={s.songDescriptionTitle || ""}>
                        {s.songDescriptionTitle || "-"}
                      </div>
                      <div className="truncate text-left text-slate-100" title={s.songStructureTitle || ""}>
                        {s.songStructureTitle || "-"}
                      </div>
                      <div
                        className="truncate text-left text-slate-100"
                        title={`${s.profileOkName || s.profileOkId || ""}${s.profileAltName || s.profileAltId ? ` / ${s.profileAltName || s.profileAltId}` : ""}`}
                      >
                        {s.profileOkName || s.profileOkId ? `${s.profileOkName || s.profileOkId}` : "-"}
                        {s.profileAltName || s.profileAltId ? ` / ${s.profileAltName || s.profileAltId}` : ""}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="secondary"
                            className="h-7 px-2 text-[11px]"
                            onClick={(e) => {
                              e.stopPropagation();
                              props.onRetrySuno(s);
                            }}
                          >
                            Retry
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            className="h-7 w-7 px-0"
                            title="Open folder"
                            onClick={(e) => {
                              e.stopPropagation();
                              props.onOpenSongFolder(s);
                            }}
                          >
                            <FolderOpen className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                      <div className="truncate text-[11px] text-slate-300">{formatDateTime(s.createdAt)}</div>
                    </div>
                  );
                });
              })()
            )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
