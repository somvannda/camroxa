import * as React from "react";
import { useAppStore } from "@/store/useAppStore";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import type { ImageSampleFile } from "../../../../shared/app-types";
import { FolderOpen, RefreshCcw, Save } from "lucide-react";

export function ImageSamplesTab() {
  const { data, updateSettings, setFooterStatus } = useAppStore();
  const savedDir = data.settings.imageSamplesDir ?? "";

  const [folderDraft, setFolderDraft] = React.useState(savedDir);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [items, setItems] = React.useState<ImageSampleFile[]>([]);
  const [preview, setPreview] = React.useState<ImageSampleFile | null>(null);

  React.useEffect(() => {
    setFolderDraft(savedDir);
  }, [savedDir]);

  const canUseFs = !!window.mgApi?.imageSamplesList;

  const scan = React.useCallback(
    async (pathToScan: string) => {
      const folderPath = String(pathToScan || "").trim();
      setError(null);
      setItems([]);
      if (!folderPath) {
        setError("No folder selected");
        return;
      }
      if (!window.mgApi?.imageSamplesList) {
        setError("Folder gallery requires the Electron app runtime");
        return;
      }
      setLoading(true);
      try {
        const res = await window.mgApi.imageSamplesList({ folderPath });
        if ("items" in res) {
          setItems(res.items);
          if (res.items.length === 0) setError("No images found in this folder (PNG/JPG/WEBP)");
        } else {
          setError(res.message);
        }
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  React.useEffect(() => {
    void scan(folderDraft);
  }, [folderDraft, scan]);

  const canSave = !!folderDraft.trim();
  const isDirty = folderDraft !== savedDir;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden">
      <div className="shrink-0 flex items-center gap-2">
        <div className="text-xs text-slate-300">Folder</div>
        <div className="relative min-w-0 flex-1">
          <Input
            readOnly
            value={folderDraft}
            placeholder="No folder selected"
            title={folderDraft || "No folder selected"}
            className="pr-10"
          />
          <button
            type="button"
            className="absolute right-1 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-300 hover:bg-slate-950/40 hover:text-slate-100 disabled:opacity-40"
            disabled={!folderDraft}
            onClick={async () => {
              if (!folderDraft) return;
              await window.mgApi?.openPath(folderDraft);
            }}
          >
            <FolderOpen className="h-4 w-4" />
          </button>
        </div>
        <Button
          variant="primary"
          onClick={async () => {
            const res = await window.mgApi?.pickPath({ kind: "directory", defaultPath: folderDraft || undefined, title: "Select image samples folder" });
            if (!res || res.canceled) return;
            if ("path" in res) setFolderDraft(res.path);
          }}
        >
          <FolderOpen className="h-4 w-4" />
          Select Folder
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden rounded-lg border border-slate-200/10 bg-slate-950/20">
        <div className="h-full overflow-auto p-3">
          {!canUseFs ? (
            <div className="py-10 text-center text-sm text-slate-400">This view is only available in the Electron app.</div>
          ) : loading ? (
            <div className="py-10 text-center text-sm text-slate-400">Scanning folder…</div>
          ) : error ? (
            <div className="py-10 text-center text-sm text-slate-400">{error}</div>
          ) : (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-3">
              {items.map((it) => (
                <button
                  type="button"
                  key={it.filePath}
                  className="group overflow-hidden rounded-lg border border-slate-200/10 bg-slate-950/30 text-left hover:border-slate-200/20 hover:bg-slate-950/40"
                  onClick={() => setPreview(it)}
                  title={it.fileName}
                >
                  <div className="aspect-square w-full overflow-hidden bg-slate-950/40">
                    <img src={it.fileUrl} alt={it.fileName} className="h-full w-full object-cover transition-transform duration-150 group-hover:scale-[1.02]" />
                  </div>
                  <div className="px-2 py-1.5">
                    <div className="truncate text-[11px] text-slate-200">{it.fileName}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="shrink-0 flex items-center justify-between gap-2">
        <div className="text-xs text-slate-400">
          {canUseFs && !loading && !error ? `${items.length} image${items.length === 1 ? "" : "s"}` : ""}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" disabled={!folderDraft || loading} onClick={() => void scan(folderDraft)}>
            <RefreshCcw className="h-4 w-4" />
            Refresh
          </Button>
          <Button
            variant="primary"
            disabled={!canSave || !isDirty}
            onClick={async () => {
              if (!folderDraft.trim()) return;
              setFooterStatus("Saving image samples folder…", 30);
              await updateSettings({ imageSamplesDir: folderDraft.trim() });
              setFooterStatus("Saved image samples folder", 100);
              setTimeout(() => setFooterStatus("Ready", null), 1200);
            }}
          >
            <Save className="h-4 w-4" />
            Save
          </Button>
        </div>
      </div>

      <Dialog open={!!preview} onOpenChange={(v) => !v && setPreview(null)}>
        <DialogContent title={preview?.fileName ?? "Preview"} className="max-w-5xl h-[720px] flex flex-col">
          <div className="min-h-0 flex-1 p-4">
            <div className="h-full overflow-hidden rounded-lg border border-slate-200/10 bg-slate-950/30">
              {preview ? (
                <img src={preview.fileUrl} alt={preview.fileName} className="h-full w-full object-contain" />
              ) : null}
            </div>
            <div className="mt-3 text-xs text-slate-300">{preview?.filePath ?? ""}</div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

