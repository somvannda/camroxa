import { Minus, Square, X } from "lucide-react";

function windowAction(action: "minimize" | "toggleMaximize" | "close"): void {
  void window.camxora?.window?.[action]?.();
}

export function TitleBar() {
  return (
    <header className="drag-region flex h-12 shrink-0 items-center justify-between border-b border-border bg-surface-1 px-4">
      <div className="flex items-center gap-3">
        <div className="flex h-6 w-6 items-center justify-center rounded-[6px] bg-accent text-[11px] font-semibold text-accent-ink">
          C
        </div>
        <span className="text-meta font-semibold tracking-[0.12em] text-text-primary">CAMXORA</span>
        <span className="text-caption text-text-muted">Desktop 2.0</span>
      </div>

      <div className="no-drag flex items-center gap-4">
        <div className="flex items-center gap-1">
          <button
            className="flex h-7 w-8 items-center justify-center rounded-[6px] text-text-secondary hover:bg-surface-hover hover:text-text-primary"
            onClick={() => windowAction("minimize")}
            aria-label="Minimize"
          >
            <Minus size={14} />
          </button>
          <button
            className="flex h-7 w-8 items-center justify-center rounded-[6px] text-text-secondary hover:bg-surface-hover hover:text-text-primary"
            onClick={() => windowAction("toggleMaximize")}
            aria-label="Maximize"
          >
            <Square size={12} />
          </button>
          <button
            className="flex h-7 w-8 items-center justify-center rounded-[6px] text-text-secondary hover:bg-danger-soft hover:text-danger"
            onClick={() => windowAction("close")}
            aria-label="Close"
          >
            <X size={14} />
          </button>
        </div>
      </div>
    </header>
  );
}
