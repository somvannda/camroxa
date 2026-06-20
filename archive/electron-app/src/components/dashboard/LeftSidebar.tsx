import * as React from "react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Switch } from "@/components/ui/Switch";
import { Textarea } from "@/components/ui/Textarea";
import { MetricBar } from "@/components/dashboard/MetricBar";
import type { Song } from "../../../shared/app-types";
import type { SongDraft } from "../../../shared/app-types";
import { Input } from "@/components/ui/Input";
import { Slider } from "@/components/ui/Slider";
import { Dialog, DialogContent } from "@/components/ui/Dialog";

export function LeftSidebar(props: {
  effects: { valence: number; dance: number; instr: number };
  song: Song | null;
  drafts: SongDraft[];
  onDraftChange: (id: string, patch: Partial<SongDraft>) => void;
  onPolishLyrics: (strength: number) => void;
  autoGenImage: boolean;
  autoGSuno: boolean;
  onAutoGenImageChange: (v: boolean) => void;
  onAutoGSunoChange: (v: boolean) => void;
}) {
  const [polishStrength, setPolishStrength] = React.useState(50);
  const [detailsOpen, setDetailsOpen] = React.useState(false);

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      return;
    }
  }

  return (
    <div className="flex h-full min-w-0 flex-col gap-3 overflow-hidden">
      <Card className="flex min-h-0 flex-1 flex-col">
        <CardHeader>
          <CardTitle>Song</CardTitle>
        </CardHeader>
        <CardContent className="flex min-h-0 flex-1 flex-col gap-3">
          <div className="space-y-2">
            <div className="text-xs font-semibold text-slate-200">Effects</div>
            <div className="grid min-w-0 grid-cols-3 gap-3">
              <MetricBar label="Valence" value={props.effects.valence} tone="amber" />
              <MetricBar label="Danceability" value={props.effects.dance} tone="blue" />
              <MetricBar label="Instrumental" value={props.effects.instr} tone="blue" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <Input
              value={props.drafts[0]?.album ?? ""}
              onChange={(e) => props.onDraftChange(props.drafts[0]?.id ?? "draft-01", { album: e.target.value })}
              placeholder="Album"
            />
            <Input
              value={props.drafts[0]?.title ?? ""}
              onChange={(e) => props.onDraftChange(props.drafts[0]?.id ?? "draft-01", { title: e.target.value })}
              placeholder="Title"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={() => copyText(props.song?.title ?? "")}
              disabled={!props.song}
            >
              Copy title
            </Button>
            <Button size="sm" onClick={() => copyText(props.song?.lyricsPolished ?? "")}
              disabled={!props.song}
            >
              Copy lyrics
            </Button>
            <Button
              size="sm"
              onClick={() =>
                copyText(
                  props.song ? `Title: ${props.song.title}\nAlbum: ${props.song.album}\n\n${props.song.lyricsPolished}` : "",
                )
              }
              disabled={!props.song}
            >
              Copy both
            </Button>
            <Button
              size="sm"
              variant="secondary"
              className="bg-amber-600 text-white hover:bg-amber-500"
              onClick={() => props.onPolishLyrics(polishStrength)}
              disabled={!props.song}
            >
              Polish
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setDetailsOpen(true)} disabled={!props.song}>
              Revisions
            </Button>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-xs text-slate-300">Polish</div>
            <Slider value={polishStrength} min={0} max={100} onValueChange={setPolishStrength} />
          </div>

          <Textarea className="min-h-0 flex-1" value={props.song?.lyricsPolished ?? ""} readOnly placeholder="No song generated yet." />

          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <Switch checked={props.autoGenImage} onCheckedChange={props.onAutoGenImageChange} />
              <div className="text-xs text-slate-200">Auto-Gen Image</div>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={props.autoGSuno} onCheckedChange={props.onAutoGSunoChange} />
              <div className="text-xs text-slate-200">Auto-G Suno</div>
            </div>
          </div>

        </CardContent>
      </Card>

      <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
        <DialogContent title="Song details" className="max-w-5xl h-[680px] flex flex-col">
          <div className="min-h-0 flex-1 p-4">
            <div className="grid h-full min-h-0 grid-cols-2 gap-4">
            <Card className="flex min-h-0 flex-col overflow-hidden">
              <div className="px-4 py-3 text-sm font-semibold text-slate-100">Inputs</div>
              <div className="min-h-0 flex-1 overflow-auto border-t border-slate-200/10 px-4 py-3 text-sm text-slate-100 whitespace-pre-wrap">
                {props.song ? `Description:\n${props.song.songDescription}\n\nStructure:\n${props.song.songStructure}` : ""}
              </div>
            </Card>
            <Card className="flex min-h-0 flex-col overflow-hidden">
              <div className="px-4 py-3 text-sm font-semibold text-slate-100">Lyrics</div>
              <div className="min-h-0 flex-1 overflow-auto border-t border-slate-200/10 px-4 py-3 text-sm text-slate-100 whitespace-pre-wrap">
                {props.song ? props.song.lyricsPolished : ""}
              </div>
            </Card>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

