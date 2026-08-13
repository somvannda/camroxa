import { useState } from 'react';

import { Loader2, Plus, Pencil } from 'lucide-react';



import { InstallerFilesTable } from '@/components/software-updates/installer-files-table';

import {

  ReleaseEditorDialog,

  type ReleaseEditorInitialValues,

  type ReleaseEditorMode,

} from '@/components/software-updates/release-editor-dialog';

import { ReleaseStatusCard } from '@/components/software-updates/release-status-card';

import {

  useSoftwareUpdateConfig,

  useUnpublishSoftwareUpdate,

  type DesktopInstallerFile,

} from '@/hooks/use-desktop-notifications';

import { toast } from '@/hooks/use-toast';

import { Button } from '@/components/ui/button';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';



type EditorSession = {

  mode: ReleaseEditorMode;

  prefilledInstaller?: DesktopInstallerFile | null;

  publishIntent?: boolean;

};



function hasDraftConfig(config: {

  version?: string;

  download_url?: string;

  release_notes?: string;

} | undefined) {

  if (!config) return false;

  return Boolean(config.version?.trim() || config.download_url?.trim());

}



function configToInitialValues(

  config: {

    version: string;

    download_url: string;

    mandatory: boolean;

    release_notes: string;

  } | undefined,

): ReleaseEditorInitialValues {

  if (!config) return {};

  return {

    version: config.version || '',

    downloadUrl: config.download_url || '',

    forceUpdate: config.mandatory,

    releaseNotes: config.release_notes || '',

  };

}



export function SoftwareUpdatesPanel() {

  const { data: softwareUpdate, isLoading: softwareLoading } = useSoftwareUpdateConfig();

  const unpublishSoftwareUpdate = useUnpublishSoftwareUpdate();



  const [editorOpen, setEditorOpen] = useState(false);

  const [editorSession, setEditorSession] = useState<EditorSession>({ mode: 'new' });



  const isPublished = Boolean(softwareUpdate?.is_published ?? softwareUpdate?.published_at);

  const hasLiveRelease = Boolean(softwareUpdate?.live_version?.trim() || isPublished);

  const showEditDraft = hasDraftConfig(softwareUpdate);



  const openEditor = (session: EditorSession) => {

    setEditorSession(session);

    setEditorOpen(true);

  };



  const openNewRelease = () => openEditor({ mode: 'new' });



  const openEditDraft = () =>

    openEditor({

      mode: 'edit-draft',

    });



  const openPublishInstaller = (file: DesktopInstallerFile) =>

    openEditor({

      mode: 'from-installer',

      prefilledInstaller: file,

      publishIntent: true,

    });



  const openDraftInstaller = (file: DesktopInstallerFile) =>

    openEditor({

      mode: 'from-installer',

      prefilledInstaller: file,

    });



  const unpublishUpdate = () => {

    unpublishSoftwareUpdate.mutate(undefined, {

      onSuccess: (result) =>
        toast({
          title: 'Live release moved to draft',
          description: result.restored_live_version
            ? `Website, changelog, and force update reverted to ${result.restored_live_version}.`
            : 'No previous live release was available to restore.',
        }),

      onError: (error: Error) =>

        toast({ title: 'Unpublish failed', description: error.message, variant: 'destructive' }),

    });

  };



  return (

    <>

      <Card className="border-slate-800 bg-slate-900/50">

        <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">

          <div>

            <CardTitle className="text-lg">Desktop releases</CardTitle>

            <p className="mt-1 text-sm text-slate-400">

              Upload installers, configure release metadata, and publish to /download and in-app updates.

            </p>

          </div>

          <div className="flex shrink-0 flex-wrap gap-2">

            {showEditDraft ? (

              <Button type="button" variant="outline" size="sm" onClick={openEditDraft}>

                <Pencil className="mr-2 h-4 w-4" />

                Edit draft

              </Button>

            ) : null}

            <Button type="button" size="sm" onClick={openNewRelease}>

              <Plus className="mr-2 h-4 w-4" />

              New release

            </Button>

          </div>

        </CardHeader>

        <CardContent className="space-y-6">

          {softwareLoading ? (

            <p className="text-sm text-slate-500">Loading software update settings…</p>

          ) : (

            <>

              <ReleaseStatusCard

                version={softwareUpdate?.version ?? ''}

                downloadUrl={softwareUpdate?.download_url ?? ''}

                isPublished={isPublished}

                publishedAt={softwareUpdate?.published_at ?? null}

                liveVersion={softwareUpdate?.live_version ?? ''}

                liveDownloadUrl={softwareUpdate?.live_download_url ?? ''}

                liveMandatory={Boolean(softwareUpdate?.live_mandatory)}

                livePublishedAt={softwareUpdate?.live_published_at ?? null}

              />



              <div className="rounded-md border border-sky-900/40 bg-sky-950/20 px-3 py-3 text-xs text-slate-400">

                <p>

                  Workflow: upload an installer via <span className="text-slate-300">New release</span>, then

                  click <span className="text-slate-300">Publish</span> on that row to go live — or open the

                  release editor to adjust version, release notes, and publish options first.

                </p>

              </div>



              <InstallerFilesTable

                onPublishClick={openPublishInstaller}

                onDraftClick={openDraftInstaller}

              />



              {hasLiveRelease ? (

                <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-800 px-4 py-3">

                  <div>

                    <p className="text-sm font-medium text-slate-200">Live release</p>

                    <p className="text-xs text-slate-500">

                      Move the live version back to draft. Website, changelog, and force update revert to the previous live release.

                    </p>

                  </div>

                  <Button

                    type="button"

                    variant="outline"

                    onClick={unpublishUpdate}

                    disabled={unpublishSoftwareUpdate.isPending}

                  >

                    {unpublishSoftwareUpdate.isPending && (

                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />

                    )}

                    Unpublish

                  </Button>

                </div>

              ) : null}

            </>

          )}

        </CardContent>

      </Card>



      <ReleaseEditorDialog

        open={editorOpen}

        onOpenChange={setEditorOpen}

        mode={editorSession.mode}

        initialValues={configToInitialValues(softwareUpdate)}

        prefilledInstaller={editorSession.prefilledInstaller}

        publishIntent={editorSession.publishIntent}

      />

    </>

  );

}



export default function SoftwareUpdatesPage() {

  return (

    <div className="space-y-6 p-6">

      <div>

        <h1 className="text-2xl font-bold text-slate-100">Software Updates</h1>

        <p className="text-sm text-slate-400">

          Manage desktop release versions, download links, and forced update rollout.

        </p>

      </div>

      <SoftwareUpdatesPanel />

    </div>

  );

}

