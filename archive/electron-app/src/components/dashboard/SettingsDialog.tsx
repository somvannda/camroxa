import * as React from "react";
import { Dialog, DialogContent } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { useAppStore } from "@/store/useAppStore";
import { AlertTriangle, Download, FolderOpen, Search } from "lucide-react";

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
};

export function SettingsPanel(props: {
  mode: "dialog" | "page";
  onRequestClose?: () => void;
  tab?: string;
  onTabChange?: (v: string) => void;
  allowedTabs?: string[];
  hideTabsList?: boolean;
}) {
  const { data, updateSettings, resetAll, createProfile, updateProfile, deleteProfile } = useAppStore();
  const s = data.settings;

  const allowedTabs = React.useMemo(() => {
    if (!props.allowedTabs?.length) return null;
    return new Set(props.allowedTabs);
  }, [props.allowedTabs]);

  const readOnlyTab = typeof props.tab === "string" && !props.onTabChange;
  const [tabInternal, setTabInternal] = React.useState(() => {
    const initial = typeof props.tab === "string" ? props.tab : "api";
    if (allowedTabs && !allowedTabs.has(initial)) return props.allowedTabs?.[0] ?? "api";
    return initial;
  });

  const tab = typeof props.tab === "string" ? props.tab : tabInternal;
  const setTab = props.onTabChange
    ? props.onTabChange
    : readOnlyTab
      ? (_v: string) => undefined
      : (v: string) => setTabInternal(v);

  React.useEffect(() => {
    if (typeof props.tab === "string") return;
    if (!allowedTabs) return;
    if (allowedTabs.has(tabInternal)) return;
    setTabInternal(props.allowedTabs?.[0] ?? "api");
  }, [allowedTabs, props.allowedTabs, props.tab, tabInternal]);

  const [songDraftProvider, setSongDraftProvider] = React.useState(s.songDraftProvider);
  const [deepseekApiKey, setDeepseekApiKey] = React.useState(s.deepseekApiKey);
  const [openaiApiKey, setOpenaiApiKey] = React.useState(s.openaiApiKey);
  const [slaiSongApiKey, setSlaiSongApiKey] = React.useState(s.slaiSongApiKey);
  const [slaiSongModel, setSlaiSongModel] = React.useState(s.slaiSongModel);
  const [slaiImgApiKey, setSlaiImgApiKey] = React.useState(s.slaiImgApiKey);
  const [slaiImgModel, setSlaiImgModel] = React.useState(s.slaiImgModel);
  const [ffmpegPath, setFfmpegPath] = React.useState(s.ffmpegPath);
  const [downloadsDir, setDownloadsDir] = React.useState(s.downloadsDir);
  const [mergedDir, setMergedDir] = React.useState(s.mergedDir);
  const [defaultSongCount, setDefaultSongCount] = React.useState(s.defaultSongCount);
  const [imageOutputDir, setImageOutputDir] = React.useState(s.imageOutputDir);
  const [imageResolution, setImageResolution] = React.useState(s.imageResolution);
  const [styleStrength, setStyleStrength] = React.useState(s.styleStrength);
  const [backgroundSourceMode, setBackgroundSourceMode] = React.useState(s.backgroundSourceMode ?? "samples");
  const [sunoTimeoutMs, setSunoTimeoutMs] = React.useState(s.sunoTimeoutMs);
  const [sunoRetryCount, setSunoRetryCount] = React.useState(s.sunoRetryCount);
  const [sunoDefaultVersion, setSunoDefaultVersion] = React.useState(s.sunoDefaultVersion);
  const [sunoMergeEnabled, setSunoMergeEnabled] = React.useState(s.sunoMergeEnabled);
  const [sunoMergeGroupSize, setSunoMergeGroupSize] = React.useState(s.sunoMergeGroupSize);
  const [sunoApiKey, setSunoApiKey] = React.useState(s.sunoApiKey);
  const [sunoOutputDir, setSunoOutputDir] = React.useState(s.sunoOutputDir);
  const [sunoCallbackUrl, setSunoCallbackUrl] = React.useState(s.sunoCallbackUrl);
  const [dbHost, setDbHost] = React.useState(s.dbHost);
  const [dbPort, setDbPort] = React.useState(s.dbPort);
  const [dbUser, setDbUser] = React.useState(s.dbUser);
  const [dbPassword, setDbPassword] = React.useState(s.dbPassword);
  const [dbName, setDbName] = React.useState(s.dbName);

  const [newProfileName, setNewProfileName] = React.useState("");
  const [selectedProfileId, setSelectedProfileId] = React.useState<string | null>(s.activeProfileOkId);

  const [notice, setNotice] = React.useState<string | null>(null);
  const [noticeTone, setNoticeTone] = React.useState<"ok" | "error" | "info">("info");

  const [ffmpegMissing, setFfmpegMissing] = React.useState(false);

  const [poolCounts, setPoolCounts] = React.useState<null | {
    openings: { total: number; unused: number };
    titles: { total: number; unused: number };
    albums: { total: number; unused: number };
  }>(null);
  const [poolBusy, setPoolBusy] = React.useState(false);

  const [ngrokStatus, setNgrokStatus] = React.useState<{
    running: boolean;
    publicUrl: string | null;
    callbackUrl: string | null;
    localPort: number | null;
    lastError: string | null;
    callbackPort: number | null;
  } | null>(null);

  React.useEffect(() => {
    setSongDraftProvider(s.songDraftProvider);
    setDeepseekApiKey(s.deepseekApiKey);
    setOpenaiApiKey(s.openaiApiKey);
    setSlaiSongApiKey(s.slaiSongApiKey);
    setSlaiSongModel(s.slaiSongModel);
    setSlaiImgApiKey(s.slaiImgApiKey);
    setSlaiImgModel(s.slaiImgModel);
    setFfmpegPath(s.ffmpegPath);
    setDownloadsDir(s.downloadsDir);
    setMergedDir(s.mergedDir);
    setDefaultSongCount(s.defaultSongCount);
    setImageOutputDir(s.imageOutputDir);
    setImageResolution(s.imageResolution);
    setStyleStrength(s.styleStrength);
    setBackgroundSourceMode(s.backgroundSourceMode ?? "samples");
    setSunoTimeoutMs(s.sunoTimeoutMs);
    setSunoRetryCount(s.sunoRetryCount);
    setSunoDefaultVersion(s.sunoDefaultVersion);
    setSunoMergeEnabled(s.sunoMergeEnabled);
    setSunoMergeGroupSize(s.sunoMergeGroupSize);
    setSunoApiKey(s.sunoApiKey);
    setSunoOutputDir(s.sunoOutputDir);
    setSunoCallbackUrl(s.sunoCallbackUrl);
    setDbHost(s.dbHost);
    setDbPort(s.dbPort);
    setDbUser(s.dbUser);
    setDbPassword(s.dbPassword);
    setDbName(s.dbName);
    setSelectedProfileId(s.activeProfileOkId);

    window.mgApi
      ?.ngrokStatus()
      .then((st) => setNgrokStatus(st))
      .catch(() => setNgrokStatus(null));
  }, [
    s.songDraftProvider,
    s.deepseekApiKey,
    s.openaiApiKey,
    s.slaiSongApiKey,
    s.slaiSongModel,
    s.slaiImgApiKey,
    s.slaiImgModel,
    s.ffmpegPath,
    s.downloadsDir,
    s.mergedDir,
    s.defaultSongCount,
    s.imageOutputDir,
    s.imageResolution,
    s.styleStrength,
    s.backgroundSourceMode,
    s.sunoTimeoutMs,
    s.sunoRetryCount,
    s.sunoDefaultVersion,
    s.sunoMergeEnabled,
    s.sunoMergeGroupSize,
    s.sunoApiKey,
    s.sunoOutputDir,
    s.sunoCallbackUrl,
    s.dbHost,
    s.dbPort,
    s.dbUser,
    s.dbPassword,
    s.dbName,
    s.activeProfileOkId,
  ]);

  React.useEffect(() => {
    let cancelled = false;
    async function run() {
      if (!window.mgApi?.pathExists) {
        if (!cancelled) setFfmpegMissing(!ffmpegPath.trim());
        return;
      }
      if (!ffmpegPath.trim()) {
        if (!cancelled) setFfmpegMissing(true);
        return;
      }
      const r = await window.mgApi.pathExists(ffmpegPath);
      if (!cancelled) setFfmpegMissing(!r.exists);
    }
    void run();
    return () => {
      cancelled = true;
    };
  }, [ffmpegPath, open]);

  async function save() {
    const patch: Parameters<typeof updateSettings>[0] = {
      songDraftProvider,
      deepseekApiKey,
      openaiApiKey,
      slaiSongApiKey,
      slaiSongModel,
      slaiImgApiKey,
      slaiImgModel,
      ffmpegPath,
      downloadsDir,
      mergedDir,
      defaultSongCount,
      imageOutputDir,
      imageResolution,
      styleStrength,
      backgroundSourceMode,
      sunoTimeoutMs,
      sunoRetryCount,
      sunoDefaultVersion,
      sunoMergeEnabled,
      sunoMergeGroupSize,
      sunoApiKey,
      sunoOutputDir,
      sunoCallbackUrl,
      dbHost,
      dbPort,
      dbUser,
      dbPassword,
      dbName,
    };

    await updateSettings(patch);
    setNoticeTone("ok");
    setNotice("Saved");
    setTimeout(() => setNotice(null), 2200);
  }

  async function testDb() {
    if (!window.mgApi?.testDbConnection) {
      setNoticeTone("error");
      setNotice("Database test is unavailable. Please restart the Electron app.");
      setTimeout(() => setNotice(null), 3500);
      return;
    }
    setNoticeTone("info");
    setNotice("Testing connection...");
    try {
      const result = await window.mgApi.testDbConnection({
        host: dbHost,
        port: dbPort,
        user: dbUser,
        password: dbPassword,
        database: dbName,
      });
      setNoticeTone(result.ok ? "ok" : "error");
      setNotice(result.message);
      setTimeout(() => setNotice(null), 3500);
    } catch (e) {
      setNoticeTone("error");
      setNotice(e instanceof Error ? e.message : "Test failed");
      setTimeout(() => setNotice(null), 3500);
    }
  }

  async function migrateDb() {
    if (!window.mgApi?.ensureDbAndMigrate) {
      setNoticeTone("error");
      setNotice("Migration is unavailable. Please restart the Electron app.");
      setTimeout(() => setNotice(null), 3500);
      return;
    }
    setNoticeTone("info");
    setNotice("Running migrations...");
    try {
      const result = await window.mgApi.ensureDbAndMigrate({
        host: dbHost,
        port: dbPort,
        user: dbUser,
        password: dbPassword,
        database: dbName,
      });
      setNoticeTone(result.ok ? "ok" : "error");
      setNotice(result.message);
      setTimeout(() => setNotice(null), 4500);
    } catch (e) {
      setNoticeTone("error");
      setNotice(e instanceof Error ? e.message : "Migration failed");
      setTimeout(() => setNotice(null), 4500);
    }
  }

  async function refreshPools() {
    if (!window.mgApi?.poolsStats) {
      setNoticeTone("error");
      setNotice("Pools are unavailable. Please restart the Electron app.");
      setTimeout(() => setNotice(null), 3500);
      return;
    }
    setPoolBusy(true);
    try {
      const stats = await window.mgApi.poolsStats({ host: dbHost, port: dbPort, user: dbUser, password: dbPassword, database: dbName });
      setPoolCounts(stats);
    } catch (e) {
      setNoticeTone("error");
      setNotice(e instanceof Error ? e.message : "Failed to load pool stats");
      setTimeout(() => setNotice(null), 4500);
    } finally {
      setPoolBusy(false);
    }
  }

  async function importPool(kind: "titles" | "albums" | "openings") {
    if (!window.mgApi?.poolsImport || !window.mgApi?.pickPath) {
      setNoticeTone("error");
      setNotice("Pools import is unavailable. Please restart the Electron app.");
      setTimeout(() => setNotice(null), 3500);
      return;
    }
    const pick = await window.mgApi.pickPath({ kind: "file", title: "Select a text file" });
    if (!("path" in pick) || !pick.path) return;
    setPoolBusy(true);
    setNoticeTone("info");
    setNotice("Importing...");
    try {
      const r = await window.mgApi.poolsImport({
        kind,
        filePath: pick.path,
        cfg: { host: dbHost, port: dbPort, user: dbUser, password: dbPassword, database: dbName },
      });
      setNoticeTone("ok");
      setNotice(`Imported ${r.inserted}`);
      setTimeout(() => setNotice(null), 2500);
      await refreshPools();
    } catch (e) {
      setNoticeTone("error");
      setNotice(e instanceof Error ? e.message : "Import failed");
      setTimeout(() => setNotice(null), 4500);
    } finally {
      setPoolBusy(false);
    }
  }

  async function openPath(targetPath: string) {
    if (!window.mgApi?.openPath) {
      setNoticeTone("error");
      setNotice("Open path is unavailable. Please restart the Electron app.");
      setTimeout(() => setNotice(null), 3500);
      return;
    }
    await window.mgApi.openPath(targetPath);
  }

  async function browseDirectory(current: string, title: string, setter: (v: string) => void) {
    if (!window.mgApi?.pickPath) {
      setNoticeTone("error");
      setNotice("Browse is unavailable. Please restart the Electron app.");
      setTimeout(() => setNotice(null), 3500);
      return;
    }
    const result = await window.mgApi.pickPath({ kind: "directory", defaultPath: current, title });
    if ("path" in result && result.path) setter(result.path);
  }

  async function browseFile(current: string, title: string, setter: (v: string) => void) {
    if (!window.mgApi?.pickPath) {
      setNoticeTone("error");
      setNotice("Browse is unavailable. Please restart the Electron app.");
      setTimeout(() => setNotice(null), 3500);
      return;
    }
    const result = await window.mgApi.pickPath({
      kind: "file",
      defaultPath: current,
      title,
      filters: [
        { name: "Executables", extensions: ["exe"] },
        { name: "All", extensions: ["*"] },
      ],
    });
    if ("path" in result && result.path) setter(result.path);
  }

  async function downloadAndSetFfmpeg() {
    if (!window.mgApi?.downloadFfmpeg || !window.mgApi?.pickPath) {
      setNoticeTone("error");
      setNotice("FFmpeg download is unavailable. Please restart the Electron app.");
      setTimeout(() => setNotice(null), 3500);
      return;
    }
    setNoticeTone("info");
    setNotice("Choose an install directory...");
    const pick = await window.mgApi.pickPath({ kind: "directory", title: "Select FFmpeg install directory" });
    if (!("path" in pick) || !pick.path) {
      setNotice(null);
      return;
    }
    setNoticeTone("info");
    setNotice("Downloading FFmpeg...");
    try {
      const result = await window.mgApi.downloadFfmpeg({ installDir: pick.path });
      setFfmpegPath(result.ffmpegPath);
      setNoticeTone("ok");
      setNotice("FFmpeg downloaded");
      setTimeout(() => setNotice(null), 3500);
    } catch (e) {
      setNoticeTone("error");
      setNotice(e instanceof Error ? e.message : "Download failed");
      setTimeout(() => setNotice(null), 4500);
    }
  }

  return (
    <div className={props.mode === "page" ? "flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200/10 bg-slate-950/20" : "flex min-h-0 flex-1 flex-col"}>
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="p-4">
          <Tabs value={tab} onValueChange={setTab}>
              {props.hideTabsList ? null : (
                <TabsList>
                  {!allowedTabs || allowedTabs.has("api") ? <TabsTrigger value="api">API</TabsTrigger> : null}
                  {!allowedTabs || allowedTabs.has("generation") ? <TabsTrigger value="generation">Generation</TabsTrigger> : null}
                  {!allowedTabs || allowedTabs.has("image") ? <TabsTrigger value="image">Image</TabsTrigger> : null}
                  {!allowedTabs || allowedTabs.has("automation") ? <TabsTrigger value="automation">SUNO</TabsTrigger> : null}
                  {!allowedTabs || allowedTabs.has("profiles") ? <TabsTrigger value="profiles">Profiles</TabsTrigger> : null}
                  {!allowedTabs || allowedTabs.has("paths") ? <TabsTrigger value="paths">Paths</TabsTrigger> : null}
                  {!allowedTabs || allowedTabs.has("db") ? <TabsTrigger value="db">Database</TabsTrigger> : null}
                </TabsList>
              )}

              <div className="mt-3 min-h-0 flex-1 overflow-auto pr-1">
                {!allowedTabs || allowedTabs.has("api") ? (
                  <TabsContent value="api">
              <Card>
                <CardHeader>
                  <CardTitle>API</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">Song draft provider</div>
                    <Select value={songDraftProvider} onChange={(e) => setSongDraftProvider(e.target.value as typeof songDraftProvider)}>
                      <option value="deepseek">DeepSeek</option>
                      <option value="slai">SLAI</option>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">DeepSeek API key</div>
                    <Input value={deepseekApiKey} onChange={(e) => setDeepseekApiKey(e.target.value)} placeholder="" type="password" />
                    <div className="text-[11px] text-slate-500">If empty, the app will later fall back to the DEEPSEEK_API_KEY environment variable.</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">SLAI Song API key</div>
                    <Input value={slaiSongApiKey} onChange={(e) => setSlaiSongApiKey(e.target.value)} placeholder="" type="password" />
                    <div className="text-[11px] text-slate-500">Used when Song draft provider is set to SLAI.</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">SLAI Song model</div>
                    <Input value={slaiSongModel} onChange={(e) => setSlaiSongModel(e.target.value)} placeholder="gpt-5.5" />
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">OpenAI API key</div>
                    <Input value={openaiApiKey} onChange={(e) => setOpenaiApiKey(e.target.value)} placeholder="" type="password" />
                    <div className="text-[11px] text-slate-500">If empty, the app falls back to OPENAI_API_KEY (already configured in your environment).</div>
                    <div className="text-[11px] text-slate-500">OpenAI is used for lyrics polish only.</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">SLAI IMG API key</div>
                    <Input value={slaiImgApiKey} onChange={(e) => setSlaiImgApiKey(e.target.value)} placeholder="" type="password" />
                    <div className="text-[11px] text-slate-500">Used for background + thumbnail image generation.</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">SLAI IMG model</div>
                    <Input value={slaiImgModel} onChange={(e) => setSlaiImgModel(e.target.value)} placeholder="cgpt-web/gpt-5.5-pro" />
                  </div>
                </CardContent>
              </Card>
                  </TabsContent>
                ) : null}

                {!allowedTabs || allowedTabs.has("generation") ? (
                  <TabsContent value="generation">
              <Card>
                <CardHeader>
                  <CardTitle>Generation</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">Default song count</div>
                    <Input
                      type="number"
                      value={defaultSongCount}
                      onChange={(e) => setDefaultSongCount(Math.max(1, Number(e.target.value) || 1))}
                    />
                  </div>
                  <div className="text-xs text-slate-400">Language and creativity are controlled from the top toolbar.</div>
                </CardContent>
              </Card>
                  </TabsContent>
                ) : null}

                {!allowedTabs || allowedTabs.has("image") ? (
                  <TabsContent value="image">
              <Card>
                <CardHeader>
                  <CardTitle>Image</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">Output directory</div>
                    <div className="flex items-center gap-2">
                      <Input value={imageOutputDir} onChange={(e) => setImageOutputDir(e.target.value)} />
                      <Button variant="secondary" size="sm" onClick={() => browseDirectory(imageOutputDir, "Select image output directory", setImageOutputDir)}>
                        <Search className="h-4 w-4" />
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => openPath(imageOutputDir)}>
                        <FolderOpen className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">Resolution</div>
                    <Select value={imageResolution} onChange={(e) => setImageResolution(e.target.value as typeof imageResolution)}>
                      <option value="1920x1080">1920x1080 (16:9)</option>
                      <option value="1080x1920">1080x1920 (9:16)</option>
                    </Select>
                    <div className="text-[11px] text-slate-500">Use 1920x1080 for YouTube thumbnails; 1080x1920 for Shorts/Reels.</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">Style strength (0-100)</div>
                    <Input
                      type="number"
                      value={styleStrength}
                      onChange={(e) => setStyleStrength(Math.min(100, Math.max(0, Number(e.target.value) || 0)))}
                    />
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">Background source mode</div>
                    <Select value={backgroundSourceMode} onChange={(e) => setBackgroundSourceMode(e.target.value as "samples" | "prompt")}>
                      <option value="samples">Sample images (SLAI IMG)</option>
                    </Select>
                    <div className="text-[11px] text-slate-500">
                      Generates backgrounds by remixing a Sample Image using the selected prompt template + car catalog.
                    </div>
                  </div>
                </CardContent>
              </Card>
                  </TabsContent>
                ) : null}

                {!allowedTabs || allowedTabs.has("profiles") ? (
                  <TabsContent value="profiles">
                  <Card>
                    <CardHeader>
                      <CardTitle>Profiles</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="text-xs text-slate-400">
                        Select a profile before generating. Suno outputs will be grouped by profile.
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-2">
                          <div className="text-xs font-semibold text-slate-200">Profile list</div>
                          <div className="max-h-[360px] overflow-auto rounded-md border border-slate-200/10">
                            {data.profiles.length === 0 ? (
                              <div className="px-3 py-6 text-center text-sm text-slate-400">No profiles yet.</div>
                            ) : (
                              data.profiles.map((p) => (
                                <button
                                  key={p.id}
                                  type="button"
                                  className={
                                    "w-full border-t border-slate-200/10 px-3 py-2 text-left text-sm hover:bg-slate-950/30 " +
                                    (selectedProfileId === p.id ? "bg-blue-600/15" : "")
                                  }
                                  onClick={() => setSelectedProfileId(p.id)}
                                >
                                  <div className="flex items-center justify-between gap-2">
                                    <div className="truncate text-slate-100">{p.name}</div>
                                    {s.activeProfileOkId === p.id ? (
                                      <div className="rounded bg-emerald-600/20 px-2 py-0.5 text-[11px] text-emerald-200">OK</div>
                                    ) : s.activeProfileAltId === p.id ? (
                                      <div className="rounded bg-purple-600/20 px-2 py-0.5 text-[11px] text-purple-200">ALT</div>
                                    ) : null}
                                  </div>
                                  <div className="mt-0.5 truncate text-[11px] text-slate-400">Folder: {p.folderName}</div>
                                </button>
                              ))
                            )}
                          </div>

                          <div className="space-y-1">
                            <div className="text-xs text-slate-300">New profile name</div>
                            <div className="flex items-center gap-2">
                              <Input value={newProfileName} onChange={(e) => setNewProfileName(e.target.value)} placeholder="e.g. bass reactor" />
                              <Button
                                onClick={async () => {
                                  const name = newProfileName.trim();
                                  if (!name) return;
                                  await createProfile(name);
                                  setNewProfileName("");
                                }}
                              >
                                Create
                              </Button>
                            </div>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <div className="text-xs font-semibold text-slate-200">Profile details</div>
                          {selectedProfileId ? (
                            (() => {
                              const p = data.profiles.find((x) => x.id === selectedProfileId) ?? null;
                              if (!p) return <div className="text-sm text-slate-400">Select a profile.</div>;
                              return (
                                <div className="space-y-3">
                                  <div className="space-y-1">
                                    <div className="text-xs text-slate-300">Name</div>
                                    <Input value={p.name} onChange={(e) => updateProfile(p.id, { name: e.target.value })} />
                                  </div>

                                  <div className="space-y-1">
                                    <div className="text-xs text-slate-300">Folder name</div>
                                    <Input value={p.folderName} onChange={(e) => updateProfile(p.id, { folderName: e.target.value })} />
                                  </div>

                                  <div className="space-y-1">
                                    <div className="text-xs text-slate-300">Run prefix (optional)</div>
                                    <Input value={p.runPrefix} onChange={(e) => updateProfile(p.id, { runPrefix: e.target.value })} placeholder="e.g. 01" />
                                  </div>

                                  <div className="space-y-1">
                                    <div className="text-xs text-slate-300">Channel logo (center)</div>
                                    <div className="flex items-center gap-2">
                                      <Input value={p.logoPath} onChange={(e) => updateProfile(p.id, { logoPath: e.target.value })} placeholder="Select a PNG/JPG logo" />
                                      <Button
                                        variant="secondary"
                                        size="sm"
                                        onClick={async () => {
                                          const picked = await window.mgApi?.pickPath({
                                            kind: "file",
                                            defaultPath: p.logoPath,
                                            title: "Select logo image",
                                            filters: [{ name: "Images", extensions: ["png", "jpg", "jpeg"] }],
                                          });
                                          if (picked && picked.canceled === false) await updateProfile(p.id, { logoPath: picked.path });
                                        }}
                                      >
                                        <Search className="h-4 w-4" />
                                      </Button>
                                      <Button
                                        variant="secondary"
                                        size="sm"
                                        onClick={() => {
                                          if (!p.logoPath.trim()) return;
                                          window.mgApi?.showItemInFolder(p.logoPath);
                                        }}
                                      >
                                        <FolderOpen className="h-4 w-4" />
                                      </Button>
                                    </div>
                                    <div className="text-[11px] text-slate-500">Used by Video renderer as a centered overlay.</div>
                                  </div>

                                  <div className="flex items-center gap-2">
                                    <Button
                                      variant="destructive"
                                      onClick={async () => {
                                        if (!window.confirm(`Delete profile "${p.name}"? This does not delete files on disk.`)) return;
                                        await deleteProfile(p.id);
                                        setSelectedProfileId((prev) => (prev === p.id ? null : prev));
                                      }}
                                    >
                                      Delete
                                    </Button>
                                  </div>
                                </div>
                              );
                            })()
                          ) : (
                            <div className="text-sm text-slate-400">Select a profile from the list.</div>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  </TabsContent>
                ) : null}

                {!allowedTabs || allowedTabs.has("automation") ? (
                  <TabsContent value="automation">
              <Card>
                <CardHeader>
                  <CardTitle>SUNO Automation</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">Suno API key</div>
                    <Input value={sunoApiKey} onChange={(e) => setSunoApiKey(e.target.value)} type="password" />
                    <div className="text-[11px] text-slate-500">Stored locally in settings. Do not share this key.</div>
                  </div>

                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">Suno output directory</div>
                    <div className="flex items-center gap-2">
                      <Input value={sunoOutputDir} onChange={(e) => setSunoOutputDir(e.target.value)} />
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={async () => {
                          const picked = await window.mgApi?.pickPath({
                            kind: "directory",
                            defaultPath: sunoOutputDir,
                            title: "Select Suno output directory",
                          });
                          if (picked && picked.canceled === false) setSunoOutputDir(picked.path);
                        }}
                      >
                        <Search className="h-4 w-4" />
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => window.mgApi?.showItemInFolder(sunoOutputDir)}>
                        <FolderOpen className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">Callback URL</div>
                    <Input value={sunoCallbackUrl} onChange={(e) => setSunoCallbackUrl(e.target.value)} />
                    <div className="text-[11px] text-slate-500">Used to satisfy API requirements; polling is still used.</div>
                  </div>

                  <div className="space-y-2 rounded-md border border-slate-200/10 bg-slate-950/20 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-xs font-semibold text-slate-200">ngrok callback tunnel</div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={async () => {
                            const r = await window.mgApi?.ngrokStart();
                            if (r && r.ok === true) {
                              const st = await window.mgApi?.ngrokStatus();
                              if (st) setNgrokStatus(st);
                              if (r.status.callbackUrl) setSunoCallbackUrl(r.status.callbackUrl);
                            } else if (r && r.ok === false) {
                              setNoticeTone("error");
                              setNotice(r.message);
                            }
                          }}
                        >
                          Start
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={async () => {
                            const r = await window.mgApi?.ngrokStop();
                            if (r && r.ok) {
                              const st = await window.mgApi?.ngrokStatus();
                              if (st) setNgrokStatus(st);
                            }
                          }}
                        >
                          Stop
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={async () => {
                            const st = await window.mgApi?.ngrokStatus();
                            if (st) setNgrokStatus(st);
                          }}
                        >
                          Refresh
                        </Button>
                      </div>
                    </div>
                    <div className="text-[11px] text-slate-400">
                      {ngrokStatus?.running
                        ? `Running: ${ngrokStatus.callbackUrl || ngrokStatus.publicUrl || "(starting...)"}`
                        : `Not running${ngrokStatus?.lastError ? ` · ${ngrokStatus.lastError}` : ""}`}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">Timeout (ms)</div>
                    <Input type="number" value={sunoTimeoutMs} onChange={(e) => setSunoTimeoutMs(Math.max(1000, Number(e.target.value) || 0))} />
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">Retry count</div>
                    <Input type="number" value={sunoRetryCount} onChange={(e) => setSunoRetryCount(Math.max(0, Number(e.target.value) || 0))} />
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    <div className="space-y-1">
                      <div className="text-xs text-slate-300">Default Suno version</div>
                      <Select value={sunoDefaultVersion} onChange={(e) => setSunoDefaultVersion(e.target.value as "v5" | "v5.5")}
                      >
                        <option value="v5">v5</option>
                        <option value="v5.5">v5.5</option>
                      </Select>
                    </div>

                    <div className="space-y-1">
                      <div className="text-xs text-slate-300">Auto merge downloads</div>
                      <Select value={sunoMergeEnabled ? "on" : "off"} onChange={(e) => setSunoMergeEnabled(e.target.value === "on")}
                      >
                        <option value="off">Off</option>
                        <option value="on">On</option>
                      </Select>
                    </div>

                    <div className="space-y-1">
                      <div className="text-xs text-slate-300">Merge group size (0 = merge all)</div>
                      <Input
                        type="number"
                        value={sunoMergeGroupSize}
                        disabled={!sunoMergeEnabled}
                        onChange={(e) => setSunoMergeGroupSize(Math.max(0, Number(e.target.value) || 0))}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
                  </TabsContent>
                ) : null}

                {!allowedTabs || allowedTabs.has("paths") ? (
                  <TabsContent value="paths">
              <Card>
                <CardHeader>
                  <CardTitle>Paths</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-xs text-slate-300">
                      <span>FFmpeg path</span>
                      {ffmpegMissing ? <AlertTriangle className="h-4 w-4 text-amber-300" /> : null}
                    </div>
                    <div className="flex items-center gap-2">
                      <Input value={ffmpegPath} onChange={(e) => setFfmpegPath(e.target.value)} placeholder="C:\\ffmpeg\\bin\\ffmpeg.exe" />
                      <Button variant="secondary" size="sm" onClick={() => browseFile(ffmpegPath, "Select ffmpeg.exe", setFfmpegPath)}>
                        <Search className="h-4 w-4" />
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => window.mgApi?.showItemInFolder(ffmpegPath)}>
                        <FolderOpen className="h-4 w-4" />
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => downloadAndSetFfmpeg()} title="Download FFmpeg">
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                    {ffmpegMissing ? <div className="text-[11px] text-amber-200">FFmpeg is missing or the path is invalid.</div> : null}
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">Downloads dir</div>
                    <div className="flex items-center gap-2">
                      <Input value={downloadsDir} onChange={(e) => setDownloadsDir(e.target.value)} />
                      <Button variant="secondary" size="sm" onClick={() => browseDirectory(downloadsDir, "Select downloads directory", setDownloadsDir)}>
                        <Search className="h-4 w-4" />
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => openPath(downloadsDir)}>
                        <FolderOpen className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-slate-300">Merged dir</div>
                    <div className="flex items-center gap-2">
                      <Input value={mergedDir} onChange={(e) => setMergedDir(e.target.value)} />
                      <Button variant="secondary" size="sm" onClick={() => browseDirectory(mergedDir, "Select merged output directory", setMergedDir)}>
                        <Search className="h-4 w-4" />
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => openPath(mergedDir)}>
                        <FolderOpen className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
                  </TabsContent>
                ) : null}

                {!allowedTabs || allowedTabs.has("db") ? (
                  <TabsContent value="db">
              <Card>
                <CardHeader>
                  <CardTitle>Database</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <div className="text-xs text-slate-300">Host</div>
                      <Input value={dbHost} onChange={(e) => setDbHost(e.target.value)} />
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-slate-300">Port</div>
                      <Input type="number" value={dbPort} onChange={(e) => setDbPort(Math.max(1, Number(e.target.value) || 5432))} />
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-slate-300">Database</div>
                      <Input value={dbName} onChange={(e) => setDbName(e.target.value)} />
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-slate-300">User</div>
                      <Input value={dbUser} onChange={(e) => setDbUser(e.target.value)} />
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-slate-300">Password</div>
                      <Input value={dbPassword} onChange={(e) => setDbPassword(e.target.value)} type="password" />
                    </div>
                  </div>
                  <div className="pt-2">
                    <Button variant="secondary" onClick={() => testDb()}>
                      Test connection
                    </Button>
                    <Button variant="primary" onClick={() => migrateDb()}>
                      Migrate
                    </Button>
                  </div>

                  <div className="pt-2 space-y-2">
                    <div className="text-xs font-semibold text-slate-200">Phrase pools</div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button variant="secondary" onClick={() => refreshPools()} disabled={poolBusy}>
                        Refresh
                      </Button>
                      <Button variant="secondary" onClick={() => importPool("openings")} disabled={poolBusy}>
                        Import openings
                      </Button>
                      <Button variant="secondary" onClick={() => importPool("titles")} disabled={poolBusy}>
                        Import titles
                      </Button>
                      <Button variant="secondary" onClick={() => importPool("albums")} disabled={poolBusy}>
                        Import albums
                      </Button>
                    </div>
                    <div className="text-xs text-slate-400">
                      {poolCounts
                        ? `Openings: ${poolCounts.openings.total} (unused ${poolCounts.openings.unused}) · Titles: ${poolCounts.titles.total} (unused ${poolCounts.titles.unused}) · Albums: ${poolCounts.albums.total} (unused ${poolCounts.albums.unused})`
                        : "Click Refresh to load counts."}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      Openings file format: either `line1\tline2` per row, or two lines per pair.
                    </div>
                  </div>
                </CardContent>
              </Card>
                  </TabsContent>
                ) : null}
              </div>
            </Tabs>
          </div>

          <div className="mt-auto flex items-center justify-between border-t border-slate-200/10 px-4 py-3">
            <Button variant="destructive" onClick={() => resetAll()}>
              Reset local data
            </Button>
            <div className="min-w-0 flex-1 px-3 text-xs text-slate-300">
              {!window.mgApi ? (
                <span className="text-red-300">Electron bridge not loaded (running in browser mode)</span>
              ) : (
                <span className="text-slate-400">Electron bridge v{window.mgApi.bridgeVersion}</span>
              )}
              {notice ? (
                <span className={noticeTone === "ok" ? "text-emerald-300" : noticeTone === "error" ? "text-red-300" : "text-slate-300"}>
                  {notice}
                </span>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              {props.mode === "dialog" ? (
                <Button variant="secondary" onClick={() => props.onRequestClose?.()}>
                  Cancel
                </Button>
              ) : null}
              <Button onClick={() => save()}>Save</Button>
            </div>
          </div>
      </div>
    </div>
  );
}

export function SettingsDialog({ open, onOpenChange }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Settings" className="max-w-5xl h-[85vh] max-h-[85vh] flex flex-col">
        <SettingsPanel mode="dialog" onRequestClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
