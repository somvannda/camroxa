import logoUrl from "../assets/brand/camxora-logo.svg";
import { Icon } from "../components/icon";

function windowAction(action: "minimize" | "toggleMaximize" | "close"): void {
  void window.camxora?.window?.[action]?.();
}

export function TitleBar() {
  return (
    <header className="drag-region flex h-12 shrink-0 items-center justify-between border-b border-border bg-surface-1 px-4">
      <div className="flex items-center gap-2.5">
        <img src={logoUrl} alt="" className="h-7 w-7 rounded-[7px]" />
        <span className="text-[15px] font-semibold tracking-[-0.01em] text-text-primary">Camxora</span>
        <span className="text-caption text-text-muted">Desktop 2.0</span>
      </div>

      <div className="no-drag flex items-center gap-4">
        <div className="flex items-center gap-1">
          <button
            className="flex h-7 w-8 items-center justify-center rounded-[6px] text-text-secondary hover:bg-surface-hover hover:text-text-primary"
            onClick={() => windowAction("minimize")}
            aria-label="Minimize"
          >
            <Icon name="fa-minus" size={13} />
          </button>
          <button
            className="flex h-7 w-8 items-center justify-center rounded-[6px] text-text-secondary hover:bg-surface-hover hover:text-text-primary"
            onClick={() => windowAction("toggleMaximize")}
            aria-label="Maximize"
          >
            <Icon name="fa-square" size={11} />
          </button>
          <button
            className="flex h-7 w-8 items-center justify-center rounded-[6px] text-text-secondary hover:bg-danger-soft hover:text-danger"
            onClick={() => windowAction("close")}
            aria-label="Close"
          >
            <Icon name="fa-xmark" size={14} />
          </button>
        </div>
      </div>
    </header>
  );
}
