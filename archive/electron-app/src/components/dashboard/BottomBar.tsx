import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import type { PromptTemplate } from "../../../shared/app-types";
import { PauseCircle, PlayCircle } from "lucide-react";

export function BottomBar(props: {
  template: string;
  templates: PromptTemplate[];
  onTemplateChange: (v: string) => void;
  running: boolean;
  onSubmit: () => void;
  onRepeat: () => void;
  onExport: () => void;
  onRun: () => void;
  onEvaluate: () => void;
  onSave: () => void;
  onUpdatePrompt: () => void;
  onMergeOk: () => void;
  onMergeAlt: () => void;
  onClose: () => void;
}) {
  return (
    <div className="rounded-lg border border-slate-200/10 bg-slate-950/30 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2">
          <div className="text-xs text-slate-300">Template</div>
          <Select value={props.template} onChange={(e) => props.onTemplateChange(e.target.value)}>
            <option value="Default">Default</option>
            {props.templates.map((t) => (
              <option key={t.id} value={t.name}>
                {t.name}
              </option>
            ))}
          </Select>
        </div>

        <Button size="sm" onClick={props.onSubmit}>
          Submit
        </Button>
        <Button size="sm" onClick={props.onRepeat}>
          Repeat steps
        </Button>
        <Button size="sm" onClick={props.onExport}>
          Export
        </Button>
        <Button size="sm" onClick={props.onRun}>
          {props.running ? <PauseCircle className="h-4 w-4" /> : <PlayCircle className="h-4 w-4" />}
          Run
        </Button>
        <Button size="sm" onClick={props.onEvaluate}>
          Evaluate
        </Button>
        <Button size="sm" onClick={props.onSave}>
          Save
        </Button>
        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" variant="secondary" onClick={props.onMergeOk}>
            Merge OK
          </Button>
          <Button size="sm" variant="secondary" onClick={props.onMergeAlt}>
            Merge ALT
          </Button>
          <Button size="sm" onClick={props.onUpdatePrompt}>
            Update prompt
          </Button>
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between">
        <div className="text-xs text-slate-400">mode</div>
        <Button size="sm" variant="secondary" onClick={props.onClose}>
          Close
        </Button>
      </div>
    </div>
  );
}

