import { useState } from 'react';
import { BellRing, Loader2, Send } from 'lucide-react';

import {
  usePushNotificationHistory,
  useSendPushNotification,
} from '@/hooks/use-desktop-notifications';
import { toast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

function formatTimestamp(value: string | null | undefined) {
  if (!value) return 'Unknown time';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export function DesktopPushNotificationsPanel() {
  const { data: historyData, isLoading: historyLoading } = usePushNotificationHistory();
  const sendPushNotification = useSendPushNotification();
  const [pushTitle, setPushTitle] = useState('');
  const [pushMessage, setPushMessage] = useState('');

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
    <div className="space-y-6">
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <BellRing className="h-5 w-5 text-sky-400" />
            Broadcast Push Notification
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-slate-400">
            New messages appear at the top of the desktop notification bell. Offline users receive them when they reconnect.
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
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-lg">Recent Broadcasts</CardTitle>
        </CardHeader>
        <CardContent>
          {historyLoading ? (
            <p className="text-sm text-slate-500">Loading history…</p>
          ) : history.length === 0 ? (
            <p className="text-sm text-slate-500">No push messages sent yet.</p>
          ) : (
            <div className="space-y-3">
              {history.map((item) => (
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
        </CardContent>
      </Card>
    </div>
  );
}

export default function DesktopNotificationsPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Desktop Notifications</h1>
        <p className="text-sm text-slate-400">
          Send real-time push messages to signed-in Camxora desktop users.
        </p>
      </div>
      <DesktopPushNotificationsPanel />
    </div>
  );
}
