import * as React from "react";
import { useAppStore } from "@/store/useAppStore";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { DataTable } from "@/components/dashboard/manage/DataTable";
import { Dialog, DialogContent } from "@/components/ui/Dialog";

type DbCfg = { host: string; port: number; user: string; password: string; database: string };

function useDbCfg(): DbCfg {
  const { data } = useAppStore();
  const s = data.settings;
  return React.useMemo(
    () => ({ host: s.dbHost, port: s.dbPort, user: s.dbUser, password: s.dbPassword, database: s.dbName }),
    [s.dbHost, s.dbPort, s.dbUser, s.dbPassword, s.dbName],
  );
}

type TitleRow = { id: string; text: string; usedCount: number; createdAt: string };
type OpeningRow = { id: string; line1: string; line2: string; usedCount: number; createdAt: string };

export function PhrasePoolsTab() {
  const { clearSongs, setFooterStatus } = useAppStore();
  const db = useDbCfg();
  const [tab, setTab] = React.useState<"openings" | "titles" | "albums">("openings");
  const [busy, setBusy] = React.useState(false);
  const [count, setCount] = React.useState(10000);
  const [pageSize, setPageSize] = React.useState(100);
  const [page, setPage] = React.useState(0);
  const [confirmClearOpen, setConfirmClearOpen] = React.useState(false);
  const [confirmClearPool, setConfirmClearPool] = React.useState<null | "openings" | "titles" | "albums">(null);
  const [clearing, setClearing] = React.useState<null | "songs" | "openings" | "titles" | "albums">(null);

  const [stats, setStats] = React.useState<null | {
    openings: { total: number; unused: number };
    titles: { total: number; unused: number };
    albums: { total: number; unused: number };
  }>(null);

  const [openings, setOpenings] = React.useState<OpeningRow[]>([]);
  const [titles, setTitles] = React.useState<TitleRow[]>([]);
  const [albums, setAlbums] = React.useState<TitleRow[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    if (!window.mgApi?.poolsList) return;
    setBusy(true);
    try {
      if (window.mgApi?.poolsStats) {
        const s = await window.mgApi.poolsStats(db);
        setStats(s);
      }
      const res = await window.mgApi.poolsList({ kind: tab, limit: pageSize, offset: page * pageSize, cfg: db });
      if (res.kind === "openings") {
        setOpenings(res.rows.map((r) => ({ id: String(r.id), line1: r.line1, line2: r.line2, usedCount: r.usedCount, createdAt: r.createdAt })));
        setSelectedId(String(res.rows[0]?.id ?? ""));
      } else if (res.kind === "titles") {
        setTitles(res.rows.map((r) => ({ id: String(r.id), text: r.text, usedCount: r.usedCount, createdAt: r.createdAt })));
        setSelectedId(String(res.rows[0]?.id ?? ""));
      } else {
        setAlbums(res.rows.map((r) => ({ id: String(r.id), text: r.text, usedCount: r.usedCount, createdAt: r.createdAt })));
        setSelectedId(String(res.rows[0]?.id ?? ""));
      }
    } finally {
      setBusy(false);
    }
  }, [db, page, pageSize, tab]);

  React.useEffect(() => {
    setPage(0);
  }, [tab]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  async function generate(kind: "openings" | "titles" | "albums") {
    if (!window.mgApi?.poolsGenerate) return;
    setBusy(true);
    try {
      await window.mgApi.poolsGenerate({ kind, count, cfg: db });
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function importFile(kind: "openings" | "titles" | "albums") {
    if (!window.mgApi?.poolsImport || !window.mgApi?.pickPath) return;
    const pick = await window.mgApi.pickPath({ kind: "file", title: "Select a text file" });
    if (!("path" in pick) || !pick.path) return;
    setBusy(true);
    try {
      await window.mgApi.poolsImport({ kind, filePath: pick.path, cfg: db });
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  function withTimeout<T>(p: Promise<T>, ms: number) {
    return Promise.race([
      p,
      new Promise<T>((_r, rej) => {
        const t = setTimeout(() => {
          clearTimeout(t);
          rej(new Error("Timed out"));
        }, ms);
      }),
    ]);
  }

  async function clearDb() {
    if (!window.mgApi?.clearGenerated) return;
    setBusy(true);
    setClearing("songs");
    try {
      setFooterStatus("Clearing Postgres...", 20);
      try {
        const res = await withTimeout(window.mgApi.clearGenerated(db), 20000);
        if (res.ok) {
          await clearSongs();
          setFooterStatus("Cleared songs + history", 100);
        } else if ("message" in res) {
          setFooterStatus(res.message, null);
        }
        await refresh();
      } catch (e) {
        setFooterStatus(e instanceof Error ? e.message : "Clear failed", null);
      }
    } finally {
      setTimeout(() => setFooterStatus("Ready", null), 1800);
      setClearing(null);
      setBusy(false);
    }
  }

  async function clearPool(kind: "openings" | "titles" | "albums") {
    if (!window.mgApi?.poolsClear) return;
    setBusy(true);
    setClearing(kind);
    try {
      setFooterStatus(`Clearing ${kind}...`, 20);
      try {
        const res = await withTimeout(window.mgApi.poolsClear({ kind, cfg: db }), 20000);
        if (res.ok) {
          setFooterStatus(`Cleared ${kind}`, 100);
        } else if ("message" in res) {
          setFooterStatus(res.message, null);
        }
        setPage(0);
        await refresh();
      } catch (e) {
        setFooterStatus(e instanceof Error ? e.message : "Clear failed", null);
      }
    } finally {
      setTimeout(() => setFooterStatus("Ready", null), 1800);
      setClearing(null);
      setBusy(false);
    }
  }

  const selectedOpening = openings.find((x) => x.id === selectedId) ?? null;
  const selectedText = (tab === "titles" ? titles : albums).find((x) => x.id === selectedId) ?? null;

  const totalForTab =
    tab === "openings" ? stats?.openings.total ?? 0 : tab === "titles" ? stats?.titles.total ?? 0 : stats?.albums.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalForTab / pageSize));
  const pageLabel = `${Math.min(totalPages, page + 1)} / ${totalPages}`;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden">
      <div className="grid grid-cols-4 gap-3">
        <div className="rounded-lg border border-slate-200/10 bg-slate-950/20 p-3">
          <div className="text-xs text-slate-400">Openings</div>
          <div className="mt-1 text-lg font-semibold text-slate-100">{stats ? stats.openings.unused : "—"}</div>
          <div className="text-xs text-slate-400">Total {stats ? stats.openings.total : "—"}</div>
        </div>
        <div className="rounded-lg border border-slate-200/10 bg-slate-950/20 p-3">
          <div className="text-xs text-slate-400">Titles</div>
          <div className="mt-1 text-lg font-semibold text-slate-100">{stats ? stats.titles.unused : "—"}</div>
          <div className="text-xs text-slate-400">Total {stats ? stats.titles.total : "—"}</div>
        </div>
        <div className="rounded-lg border border-slate-200/10 bg-slate-950/20 p-3">
          <div className="text-xs text-slate-400">Albums</div>
          <div className="mt-1 text-lg font-semibold text-slate-100">{stats ? stats.albums.unused : "—"}</div>
          <div className="text-xs text-slate-400">Total {stats ? stats.albums.total : "—"}</div>
        </div>
        <div className="rounded-lg border border-slate-200/10 bg-slate-950/20 p-3">
          <div className="text-xs text-slate-400">Database</div>
          <div className="mt-1 text-xs text-slate-300">
            {db.user}@{db.host}:{db.port}/{db.database}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button variant="secondary" disabled={busy} onClick={() => refresh()}>
              Refresh
            </Button>
            <Button variant="destructive" disabled={busy} onClick={() => setConfirmClearOpen(true)}>
              Clear songs DB
            </Button>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200/10 bg-slate-950/20 p-3">
        <div className="text-xs text-slate-300">Generate</div>
        <Input className="h-9 w-28" type="number" value={count} onChange={(e) => setCount(Math.max(1, Number(e.target.value) || 1))} />
        <div className="ml-2 text-xs text-slate-300">Rows per page</div>
        <Input className="h-9 w-20" type="number" value={pageSize} onChange={(e) => setPageSize(Math.max(10, Math.min(500, Number(e.target.value) || 100)))} />
        <div className="ml-auto flex items-center gap-2">
          <Button variant="secondary" size="sm" disabled={busy || page <= 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
            Prev
          </Button>
          <div className="text-xs text-slate-300">Page {pageLabel}</div>
          <Button variant="secondary" size="sm" disabled={busy || page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
          <div className="flex h-full min-h-0 flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <TabsList className="self-start">
              <TabsTrigger value="openings">Openings</TabsTrigger>
              <TabsTrigger value="titles">Titles</TabsTrigger>
              <TabsTrigger value="albums">Albums</TabsTrigger>
            </TabsList>
            <div className="ml-auto flex items-center gap-2">
              <Button variant="primary" disabled={busy} onClick={() => generate(tab)}>
                Generate
              </Button>
              <Button variant="secondary" disabled={busy} onClick={() => importFile(tab)}>
                Import
              </Button>
              <Button variant="destructive" disabled={busy} onClick={() => setConfirmClearPool(tab)}>
                Clear
              </Button>
            </div>
          </div>

          <TabsContent value="openings" className="mt-0 flex min-h-0 flex-1 overflow-hidden">
            <div className="grid h-full min-h-0 grid-cols-[1fr_1fr] gap-3">
            <DataTable<OpeningRow>
              rows={openings}
              selectedId={selectedId}
              onSelect={setSelectedId}
              fill
              columns={[
                { key: "id", header: "ID", render: (r) => r.id, span: 1 },
                { key: "used", header: "Used", render: (r) => r.usedCount, span: 1 },
                { key: "line1", header: "Line 1", render: (r) => r.line1, span: 4 },
                { key: "line2", header: "Line 2", render: (r) => r.line2, span: 4 },
              ]}
              maxHeightClassName=""
            />
            <div className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-slate-200/10 bg-slate-950/20 p-3">
              <div className="text-xs text-slate-300">Preview</div>
              <div className="mt-2 min-h-0 flex-1 overflow-auto whitespace-pre-wrap text-sm text-slate-100">
                {selectedOpening ? `${selectedOpening.line1}\n${selectedOpening.line2}` : ""}
              </div>
            </div>
            </div>
          </TabsContent>

          <TabsContent value="titles" className="mt-0 flex min-h-0 flex-1 overflow-hidden">
            <div className="grid h-full min-h-0 grid-cols-[1fr_1fr] gap-3">
            <DataTable<TitleRow>
              rows={titles}
              selectedId={selectedId}
              onSelect={setSelectedId}
              fill
              columns={[
                { key: "id", header: "ID", render: (r) => r.id, span: 1 },
                { key: "used", header: "Used", render: (r) => r.usedCount, span: 1 },
                { key: "text", header: "Title", render: (r) => r.text, span: 8 },
              ]}
              maxHeightClassName=""
            />
            <div className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-slate-200/10 bg-slate-950/20 p-3">
              <div className="text-xs text-slate-300">Preview</div>
              <div className="mt-2 min-h-0 flex-1 overflow-auto whitespace-pre-wrap text-sm text-slate-100">{selectedText?.text ?? ""}</div>
            </div>
            </div>
          </TabsContent>

          <TabsContent value="albums" className="mt-0 flex min-h-0 flex-1 overflow-hidden">
            <div className="grid h-full min-h-0 grid-cols-[1fr_1fr] gap-3">
            <DataTable<TitleRow>
              rows={albums}
              selectedId={selectedId}
              onSelect={setSelectedId}
              fill
              columns={[
                { key: "id", header: "ID", render: (r) => r.id, span: 1 },
                { key: "used", header: "Used", render: (r) => r.usedCount, span: 1 },
                { key: "text", header: "Album", render: (r) => r.text, span: 8 },
              ]}
              maxHeightClassName=""
            />
            <div className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-slate-200/10 bg-slate-950/20 p-3">
              <div className="text-xs text-slate-300">Preview</div>
              <div className="mt-2 min-h-0 flex-1 overflow-auto whitespace-pre-wrap text-sm text-slate-100">{selectedText?.text ?? ""}</div>
            </div>
            </div>
          </TabsContent>
          </div>
        </Tabs>
      </div>

      <Dialog open={confirmClearOpen} onOpenChange={setConfirmClearOpen}>
        <DialogContent title="Confirm" className="max-w-xl h-[320px] flex flex-col">
          <div className="min-h-0 flex-1 p-4">
            <div className="text-sm text-slate-100">
              This will delete ALL generated songs from Postgres (songs + history). Continue?
            </div>
          </div>
          <div className="flex justify-end gap-2 border-t border-slate-200/10 px-4 py-3">
            <Button variant="secondary" onClick={() => setConfirmClearOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={async () => {
                await clearDb();
                setConfirmClearOpen(false);
              }}
            >
              {clearing === "songs" ? "Deleting..." : "Delete"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmClearPool !== null} onOpenChange={(v) => !v && setConfirmClearPool(null)}>
        <DialogContent title="Confirm" className="max-w-xl h-[320px] flex flex-col">
          <div className="min-h-0 flex-1 p-4">
            <div className="text-sm text-slate-100">
              This will delete ALL rows from the {confirmClearPool ?? "pool"} table in Postgres. Continue?
            </div>
          </div>
          <div className="flex justify-end gap-2 border-t border-slate-200/10 px-4 py-3">
            <Button variant="secondary" onClick={() => setConfirmClearPool(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={async () => {
                const kind = confirmClearPool;
                if (!kind) return;
                await clearPool(kind);
                setConfirmClearPool(null);
              }}
            >
              {clearing && clearing !== "songs" ? "Deleting..." : "Delete"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
