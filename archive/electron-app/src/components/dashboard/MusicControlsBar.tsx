import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Slider } from "@/components/ui/Slider";
import { Switch } from "@/components/ui/Switch";
import { Textarea } from "@/components/ui/Textarea";
import type { Profile } from "../../../shared/app-types";

export function MusicControlsBar(props: {
  runFromDate: string;
  runToDate: string;
  onRunFromDateChange: (v: string) => void;
  onRunToDateChange: (v: string) => void;
  description: string;
  onDescriptionChange: (v: string) => void;
  onLoadDescription: () => void;
  onSelectAllDescription: () => void;
  shuffleDescription: boolean;
  onShuffleDescriptionChange: (v: boolean) => void;
  allDescriptionsSelected: boolean;
  matchDescriptionStructure: boolean;
  onMatchDescriptionStructureChange: (v: boolean) => void;
  structure: string;
  onStructureChange: (v: string) => void;
  onLoadStructure: () => void;
  onSelectAllStructure: () => void;
  shuffleStructure: boolean;
  onShuffleStructureChange: (v: boolean) => void;
  cycleStructures: boolean;
  onCycleStructuresChange: (v: boolean) => void;
  allStructuresSelected: boolean;
  language: string;
  onLanguageChange: (v: string) => void;
  creativity: number;
  onCreativityChange: (v: number) => void;
  sort: number;
  onSortChange: (v: number) => void;
  defaultSongCount: number;
  onDefaultSongCountChange: (v: number) => void;
  uniqueOpening: boolean;
  onUniqueOpeningChange: (v: boolean) => void;
  strictLevel: 1 | 2 | 3 | 4 | 5;
  onStrictLevelChange: (v: 1 | 2 | 3 | 4 | 5) => void;
  uniquenessHistoryWindow: 50 | 100 | 200 | 500 | 1500;
  onUniquenessHistoryWindowChange: (v: 50 | 100 | 200 | 500 | 1500) => void;
  shuffle: boolean;
  onToggleShuffle: () => void;
  profiles: Profile[];
  channelOkProfileIds: string[];
  channelAltProfileIds: string[];
  onChannelOkProfileIdsChange: (ids: string[]) => void;
  onChannelAltProfileIdsChange: (ids: string[]) => void;
  onGenerate: () => void;
  generating: boolean;
  onStop: () => void;
}) {
  const okSet = new Set(props.channelOkProfileIds);
  const altSet = new Set(props.channelAltProfileIds);

  function toggleOk(id: string) {
    props.onChannelOkProfileIdsChange(okSet.has(id) ? props.channelOkProfileIds.filter((x) => x !== id) : [...props.channelOkProfileIds, id]);
  }

  function toggleAlt(id: string) {
    props.onChannelAltProfileIdsChange(
      altSet.has(id) ? props.channelAltProfileIds.filter((x) => x !== id) : [...props.channelAltProfileIds, id],
    );
  }

  return (
    <div className="grid gap-3 rounded-xl border border-slate-200/10 bg-slate-950/20 p-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="text-xs text-slate-300">From</div>
          <Input className="h-9 w-36" type="date" value={props.runFromDate} onChange={(e) => props.onRunFromDateChange(e.target.value)} />
          <div className="text-xs text-slate-300">To</div>
          <Input className="h-9 w-36" type="date" value={props.runToDate} onChange={(e) => props.onRunToDateChange(e.target.value)} />
        </div>
        <div className="flex items-center gap-2">
          <div className="text-xs text-slate-300">Language</div>
          <Select value={props.language} onChange={(e) => props.onLanguageChange(e.target.value)}>
            <option value="English">English</option>
            <option value="German">German</option>
            <option value="Spanish">Spanish</option>
            <option value="French">French</option>
          </Select>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-xs text-slate-300">Creativity</div>
          <div className="w-28">
            <Slider value={props.creativity} min={0} max={100} onValueChange={props.onCreativityChange} />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="text-xs text-slate-300">Unique opening</div>
          <Switch checked={props.uniqueOpening} onCheckedChange={props.onUniqueOpeningChange} />
        </div>

        <div className="flex items-center gap-2">
          <div className="text-xs text-slate-300">Strict</div>
          <Select value={String(props.strictLevel)} onChange={(e) => props.onStrictLevelChange(Number(e.target.value) as 1 | 2 | 3 | 4 | 5)}>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="4">4</option>
            <option value="5">5</option>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <div className="text-xs text-slate-300">History</div>
          <Select
            value={String(props.uniquenessHistoryWindow)}
            onChange={(e) => props.onUniquenessHistoryWindowChange(Number(e.target.value) as 50 | 100 | 200 | 500 | 1500)}
          >
            <option value="50">50</option>
            <option value="100">100</option>
            <option value="200">200</option>
            <option value="500">500</option>
            <option value="1500">1500</option>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <div className="text-xs text-slate-300">Count</div>
          <Input className="h-9 w-16 text-center" type="number" value={props.defaultSongCount} onChange={(e) => props.onDefaultSongCountChange(Math.max(1, Number(e.target.value) || 1))} />
        </div>

        {props.generating ? (
          <Button variant="destructive" size="md" onClick={props.onStop}>
            Stop
          </Button>
        ) : (
          <Button variant="success" size="md" onClick={props.onGenerate}>
            Generate
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border border-slate-200/10 bg-slate-950/20">
          <div className="flex items-center justify-between px-3 py-2">
            <div className="text-sm font-semibold text-slate-100">Song description</div>
          </div>
          <div className="border-t border-slate-200/10 p-3">
            <Textarea className="h-32" value={props.description} onChange={(e) => props.onDescriptionChange(e.target.value)} />
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Button size="sm" onClick={props.onLoadDescription}>
                Load
              </Button>
              <div className="ml-1 flex items-center gap-2">
                <div className="text-xs text-slate-300">Shuffle</div>
                <Switch checked={props.shuffleDescription} onCheckedChange={props.onShuffleDescriptionChange} />
              </div>
              <div className="ml-1 flex items-center gap-2">
                <div className="text-xs text-slate-300">All</div>
                <Switch checked={props.allDescriptionsSelected} onCheckedChange={props.onSelectAllDescription} />
              </div>
              <div className="ml-1 flex items-center gap-2">
                <div className="text-xs text-slate-300">Match</div>
                <Switch checked={props.matchDescriptionStructure} onCheckedChange={props.onMatchDescriptionStructureChange} />
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-slate-200/10 bg-slate-950/20">
          <div className="flex items-center justify-between px-3 py-2">
            <div className="text-sm font-semibold text-slate-100">Song structure</div>
          </div>
          <div className="border-t border-slate-200/10 p-3">
            <Textarea className="h-32" value={props.structure} onChange={(e) => props.onStructureChange(e.target.value)} />
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Button size="sm" onClick={props.onLoadStructure}>
                Load
              </Button>
              <div className="ml-1 flex items-center gap-2">
                <div className="text-xs text-slate-300">Shuffle</div>
                <Switch checked={props.shuffleStructure} onCheckedChange={props.onShuffleStructureChange} disabled={props.cycleStructures || props.matchDescriptionStructure} />
              </div>
              <div className="ml-1 flex items-center gap-2">
                <div className="text-xs text-slate-300">Cycle</div>
                <Switch checked={props.cycleStructures} onCheckedChange={props.onCycleStructuresChange} disabled={props.matchDescriptionStructure} />
              </div>
              <div className="ml-1 flex items-center gap-2">
                <div className="text-xs text-slate-300">All</div>
                <Switch checked={props.allStructuresSelected} onCheckedChange={props.onSelectAllStructure} />
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-slate-200/10 bg-slate-950/20">
          <div className="flex items-center justify-between px-3 py-2">
            <div className="text-sm font-semibold text-slate-100">OK channels</div>
            <div className="text-[11px] text-slate-400">{props.channelOkProfileIds.length}</div>
          </div>
          <div className="max-h-40 overflow-auto border-t border-slate-200/10">
            {props.profiles.map((p) => (
              <button
                key={`ok-${p.id}`}
                type="button"
                onClick={() => toggleOk(p.id)}
                className="grid w-full grid-cols-[26px_1fr_44px] items-center gap-2 border-t border-slate-200/10 px-3 py-2 text-left text-sm hover:bg-slate-950/30"
              >
                <input
                  type="checkbox"
                  checked={okSet.has(p.id)}
                  onChange={(e) => {
                    e.stopPropagation();
                    toggleOk(p.id);
                  }}
                  className="h-4 w-4 rounded border border-slate-200/20 bg-slate-950/40"
                />
                <div className="truncate text-slate-100" title={p.name}>
                  {p.name}
                </div>
                <div className="text-right font-mono text-[11px] text-slate-400">
                  {okSet.has(p.id) ? props.channelOkProfileIds.indexOf(p.id) + 1 : ""}
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200/10 bg-slate-950/20">
          <div className="flex items-center justify-between px-3 py-2">
            <div className="text-sm font-semibold text-slate-100">ALT channels</div>
            <div className="text-[11px] text-slate-400">{props.channelAltProfileIds.length}</div>
          </div>
          <div className="max-h-40 overflow-auto border-t border-slate-200/10">
            {props.profiles.map((p) => (
              <button
                key={`alt-${p.id}`}
                type="button"
                onClick={() => toggleAlt(p.id)}
                className="grid w-full grid-cols-[26px_1fr_44px] items-center gap-2 border-t border-slate-200/10 px-3 py-2 text-left text-sm hover:bg-slate-950/30"
              >
                <input
                  type="checkbox"
                  checked={altSet.has(p.id)}
                  onChange={(e) => {
                    e.stopPropagation();
                    toggleAlt(p.id);
                  }}
                  className="h-4 w-4 rounded border border-slate-200/20 bg-slate-950/40"
                />
                <div className="truncate text-slate-100" title={p.name}>
                  {p.name}
                </div>
                <div className="text-right font-mono text-[11px] text-slate-400">
                  {altSet.has(p.id) ? props.channelAltProfileIds.indexOf(p.id) + 1 : ""}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
