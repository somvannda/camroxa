import type { ReactNode } from "react";
import logoUrl from "../../assets/brand/camxora-logo.svg";

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
        <div className="flex items-center gap-2.5">
          <img src={logoUrl} alt="" className="h-7 w-7 rounded-[7px]" />
          <span className="text-[15px] font-semibold tracking-[-0.01em] text-text-primary">Camxora</span>
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
