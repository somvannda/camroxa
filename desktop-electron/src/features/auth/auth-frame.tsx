import type { ReactNode } from "react";

export function AuthFrame({
  children,
  footer = "Sign in",
}: {
  children: ReactNode;
  footer?: string;
}) {
  return (
    <div className="flex h-full flex-col bg-bg">
      <div className="drag-region flex h-12 items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-3">
          <div className="flex h-6 w-6 items-center justify-center rounded-[6px] bg-accent text-[11px] font-semibold text-accent-ink">
            C
          </div>
          <span className="text-meta font-semibold tracking-[0.12em] text-text-primary">CAMXORA</span>
          <span className="text-caption text-text-muted">Desktop 2.0</span>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center overflow-y-auto p-6">
        <div className="w-full max-w-[420px]">{children}</div>
      </div>

      <div className="flex h-8 items-center justify-between border-t border-border px-4 text-caption text-text-muted">
        <span>Camxora Desktop 2.0.0</span>
        <span className="font-mono">{footer}</span>
      </div>
    </div>
  );
}
