import * as React from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";

type DialogContextValue = {
  open: boolean;
  setOpen: (v: boolean) => void;
};

const DialogContext = React.createContext<DialogContextValue | null>(null);

export function Dialog({ open, onOpenChange, children }: { open: boolean; onOpenChange: (v: boolean) => void; children: React.ReactNode }) {
  const value = React.useMemo(() => ({ open, setOpen: onOpenChange }), [open, onOpenChange]);
  return <DialogContext.Provider value={value}>{children}</DialogContext.Provider>;
}

export function DialogTrigger({ children }: { children: React.ReactNode }) {
  const ctx = React.useContext(DialogContext);
  if (!ctx) return children;
  return (
    <span
      onClick={() => ctx.setOpen(true)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") ctx.setOpen(true);
      }}
      role="button"
      tabIndex={0}
    >
      {children}
    </span>
  );
}

export function DialogContent({
  title,
  children,
  className,
  draggable = true,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
  draggable?: boolean;
}) {
  const ctx = React.useContext(DialogContext);
  const isOpen = Boolean(ctx?.open);
  const [offset, setOffset] = React.useState({ x: 0, y: 0 });
  const dragging = React.useRef<{ startX: number; startY: number; baseX: number; baseY: number } | null>(null);

  React.useEffect(() => {
    if (!isOpen) return;
    setOffset({ x: 0, y: 0 });
  }, [isOpen]);

  React.useEffect(() => {
    if (!draggable) return;
    function onMove(e: PointerEvent) {
      if (!dragging.current) return;
      const dx = e.clientX - dragging.current.startX;
      const dy = e.clientY - dragging.current.startY;
      setOffset({ x: dragging.current.baseX + dx, y: dragging.current.baseY + dy });
    }
    function onUp() {
      dragging.current = null;
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [draggable]);

  if (!ctx || !ctx.open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6">
      <div className="absolute inset-0 bg-black/55" onClick={() => ctx.setOpen(false)} />
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          "relative w-full max-w-5xl rounded-xl border border-slate-200/10 bg-[#0a1226] shadow-2xl",
          className,
        )}
        style={draggable ? { transform: `translate(${offset.x}px, ${offset.y}px)` } : undefined}
      >
        <div
          className={cn(
            "flex items-center justify-between border-b border-slate-200/10 px-4 py-3",
            draggable ? "cursor-move select-none" : "",
          )}
          onPointerDown={(e) => {
            if (!draggable) return;
            if (e.button !== 0) return;
            const target = e.target as HTMLElement;
            if (target.closest("button, input, textarea, select, a")) return;
            dragging.current = { startX: e.clientX, startY: e.clientY, baseX: offset.x, baseY: offset.y };
          }}
        >
          <div className="text-sm font-semibold text-slate-100">{title}</div>
          <button
            type="button"
            onClick={() => ctx.setOpen(false)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-slate-800/60 focus:outline-none focus:ring-2 focus:ring-blue-500/60"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}

