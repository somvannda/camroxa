import { useEffect, useState } from 'react';
import { BellRing, Download, Loader2, Send } from 'lucide-react';

import {
  usePublishSoftwareUpdate,
  usePushNotificationHistory,
  useSendPushNotification,
  useSoftwareUpdateConfig,
  useUpdateSoftwareUpdateConfig,
} from '@/hooks/use-desktop-notifications';
import { toast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

function formatTimestamp(value: string | null | undefined) {
  if (!value) return 'Not published yet';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export function DesktopNotificationsSection() {
  const { data: softwareUpdate, isLoading: softwareLoading } = useSoftwareUpdateConfig();
  const { data: historyData, isLoading: historyLoading } = usePushNotificationHistory();
  const updateSoftwareUpdate = useUpdateSoftwareUpdateConfig();
  const publishSoftwareUpdate = usePublishSoftwareUpdate();
  const sendPushNotification = useSendPushNotification();

  const [version, setVersion] = useState('');
  const [downloadUrl, setDownloadUrl] = useState('');
  const [mandatory, setMandatory] = useState(false);
  const [releaseNotes, setReleaseNotes] = useState('');
  const [pushTitle, setPushTitle] = useState('');
  const [pushMessage, setPushMessage] = useState('');

  useEffect(() => {
    if (!softwareUpdate) return;
    setVersion(softwareUpdate.version || '');
    setDownloadUrl(softwareUpdate.download_url || '');
    setMandatory(softwareUpdate.mandatory);
    setReleaseNotes(softwareUpdate.release_notes || '');
  }, [softwareUpdate]);

  const saveSoftwareUpdate = () => {
    if (!version.trim()) {
      toast({ title: 'Version is required', variant: 'destructive' });
      return;
    }
    updateSoftwareUpdate.mutate(
      {
        version: version.trim(),
        download_url: downloadUrl.trim(),
        mandatory,
        release_notes: releaseNotes.trim(),
      },
      {
        onSuccess: () => toast({ title: 'Software update draft saved' }),
      },
    );
  };

  const publishUpdate = () => {
    publishSoftwareUpdate.mutate(undefined, {
      onSuccess: (result) =>
        toast({
          title: `Update ${result.version} published`,
          description: `Sent to ${result.recipients} active user(s).`,
        }),
      onError: (error: Error) =>
        toast({
          title: 'Unable to publish update',
          description: error.message,
          variant: 'destructive',
        }),
    });
  };

  const sendPush = () => {
    if (!pushTitle.trim() || !pushMessage.trim()) {
      toast({ title: 'Title and message are required', variant: 'destructive' });
      return;
    }
    sendPushNotification.mutate(
      { title: pushTitle.trim(), message: pushMessage.trim() },
      {
        onSuccess: (result) => {
          toast({
            title: 'Push notification sent',
            description: `Delivered to ${result.recipients} active user(s).`,
          });
          setPushTitle('');
          setPushMessage('');
        },
      },
    );
  };

  const history = historyData?.items ?? [];

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <BellRing className="h-5 w-5 text-sky-400" />
            Push Notification Message
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-slate-400">
            Broadcast a message to all active desktop users. Offline users receive it when they reconnect.
          </p>
          <div className="space-y-2">
            <Label htmlFor="push-title">Title</Label>
            <Input
              id="push-title"
              value={pushTitle}
              onChange={(e) => setPushTitle(e.target.value)}
              placeholder="Maintenance tonight"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="push-message">Message</Label>
            <Textarea
              id="push-message"
              value={pushMessage}
              onChange={(e) => setPushMessage(e.target.value)}
              placeholder="Camxora will be unavailable from 11 PM to midnight for upgrades."
              rows={5}
            />
          </div>
          <Button onClick={sendPush} disabled={sendPushNotification.isPending}>
            {sendPushNotification.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Send className="mr-2 h-4 w-4" />
            )}
            Send Push Notification
          </Button>

          <div className="border-t border-slate-800 pt-4">
            <p className="mb-3 text-sm font-medium text-slate-200">Recent broadcasts</p>
            {historyLoading ? (
              <p className="text-sm text-slate-500">Loading history…</p>
            ) : history.length === 0 ? (
              <p className="text-sm text-slate-500">No push messages sent yet.</p>
            ) : (
              <div className="space-y-3">
                {history.slice(0, 8).map((item) => (
                  <div key={item.id} className="rounded-md border border-slate-800 p-3">
                    <p className="text-sm font-medium text-slate-100">{item.title}</p>
                    <p className="mt-1 text-sm text-slate-400">{item.message}</p>
                    <p className="mt-2 text-xs text-slate-500">
                      {formatTimestamp(item.created_at)} · {item.recipients} recipient(s)
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Download className="h-5 w-5 text-sky-400" />
            Software Update Version
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-slate-400">
            Manage the desktop release shown in the notification bell. Publish when you are ready to notify users.
          </p>
          {softwareLoading ? (
            <p className="text-sm text-slate-500">Loading software update settings…</p>
          ) : (
            <>
              <div className="space-y-2">
                <Label htmlFor="update-version">Version</Label>
                <Input
                  id="update-version"
                  value={version}
                  onChange={(e) => setVersion(e.target.value)}
                  placeholder="2.5.0"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="update-download-url">Download URL</Label>
                <Input
                  id="update-download-url"
                  value={downloadUrl}
                  onChange={(e) => setDownloadUrl(e.target.value)}
                  placeholder="https://downloads.camxora.com/desktop/Camxora-2.5.0.exe"
                />
              </div>
              <div className="flex items-center justify-between rounded-md border border-slate-800 px-3 py-2">
                <div>
                  <p className="text-sm font-medium text-slate-200">Mandatory update</p>
                  <p className="text-xs text-slate-500">Marks the notification as required in the desktop app.</p>
                </div>
                <input
                  id="update-mandatory"
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-600 bg-slate-900"
                  checked={mandatory}
                  onChange={(event) => setMandatory(event.target.checked)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="update-release-notes">Release notes</Label>
                <Textarea
                  id="update-release-notes"
                  value={releaseNotes}
                  onChange={(e) => setReleaseNotes(e.target.value)}
                  placeholder="Bug fixes, performance improvements, and new music workflow tools."
                  rows={5}
                />
              </div>
              <p className="text-xs text-slate-500">
                Last published: {formatTimestamp(softwareUpdate?.published_at)}
              </p>
              <div className="flex flex-wrap gap-3">
                <Button
                  variant="outline"
                  onClick={saveSoftwareUpdate}
                  disabled={updateSoftwareUpdate.isPending}
                >
                  {updateSoftwareUpdate.isPending && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Save Draft
                </Button>
                <Button onClick={publishUpdate} disabled={publishSoftwareUpdate.isPending}>
                  {publishSoftwareUpdate.isPending && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Publish Update Notification
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
